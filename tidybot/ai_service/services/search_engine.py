from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import re
import logging
import asyncio
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import spacy
from whoosh import index
from whoosh.fields import Schema, TEXT, ID, DATETIME, NUMERIC, KEYWORD
from whoosh.qparser import MultifieldParser, QueryParser
from whoosh.query import And, Or, Term, Phrase, DateRange, NumericRange
from whoosh.writing import AsyncWriter
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import FileIndex

logger = logging.getLogger(__name__)


class SearchType(Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    NATURAL_LANGUAGE = "natural_language"
    REGEX = "regex"


@dataclass
class SearchQuery:
    query_text: str
    search_type: SearchType = SearchType.NATURAL_LANGUAGE
    filters: Dict[str, Any] = None
    limit: int = 50
    offset: int = 0
    include_content: bool = False
    sort_by: str = "relevance"
    date_range: Optional[Tuple[datetime, datetime]] = None
    file_types: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None


@dataclass
class SearchResult:
    file_path: str
    file_name: str
    score: float
    highlights: List[str]
    metadata: Dict[str, Any]
    category: str
    tags: List[str]
    file_size: int
    modified_at: datetime
    content_preview: Optional[str] = None


class NaturalLanguageParser:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")

        self.time_patterns = {
            'yesterday': lambda: datetime.now() - timedelta(days=1),
            'today': lambda: datetime.now(),
            'last week': lambda: datetime.now() - timedelta(weeks=1),
            'last month': lambda: datetime.now() - timedelta(days=30),
            'last year': lambda: datetime.now() - timedelta(days=365),
        }

        self.size_units = {
            'kb': 1024,
            'mb': 1024 * 1024,
            'gb': 1024 * 1024 * 1024,
        }

        self.file_type_mappings = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'],
            'documents': ['.pdf', '.doc', '.docx', '.txt'],
            'spreadsheets': ['.xls', '.xlsx', '.csv'],
            'presentations': ['.ppt', '.pptx'],
            'videos': ['.mp4', '.avi', '.mov', '.mkv'],
            'code': ['.py', '.js', '.java', '.cpp', '.html'],
        }

    def parse(self, query: str) -> Dict[str, Any]:
        """Parse natural language query into structured search parameters"""
        doc = self.nlp(query.lower())

        parsed = {
            'keywords': [],
            'filters': {},
            'date_range': None,
            'file_types': [],
            'categories': [],
            'size_constraints': {}
        }

        # Extract entities and keywords
        for token in doc:
            if token.pos_ in ['NOUN', 'PROPN', 'VERB'] and not token.is_stop:
                parsed['keywords'].append(token.text)

        # Extract date references
        date_range = self._extract_date_range(query)
        if date_range:
            parsed['date_range'] = date_range

        # Extract file type references
        file_types = self._extract_file_types(query)
        if file_types:
            parsed['file_types'] = file_types

        # Extract size constraints
        size_constraints = self._extract_size_constraints(query)
        if size_constraints:
            parsed['size_constraints'] = size_constraints

        # Extract category hints
        categories = self._extract_categories(query)
        if categories:
            parsed['categories'] = categories

        return parsed

    def _extract_date_range(self, query: str) -> Optional[Tuple[datetime, datetime]]:
        """Extract date range from natural language"""
        for pattern, date_func in self.time_patterns.items():
            if pattern in query:
                end_date = datetime.now()
                start_date = date_func()
                return (start_date, end_date)

        # Look for specific date patterns
        date_pattern = r'(from|since|after)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(date_pattern, query)
        if match:
            try:
                date_str = match.group(2)
                start_date = datetime.strptime(date_str.replace('/', '-'), '%m-%d-%Y')
                return (start_date, datetime.now())
            except:
                pass

        return None

    def _extract_file_types(self, query: str) -> List[str]:
        """Extract file type references from query"""
        file_types = []

        for type_name, extensions in self.file_type_mappings.items():
            if type_name in query:
                file_types.extend(extensions)

        # Look for specific extensions
        extension_pattern = r'\b\w+\.(pdf|doc|docx|txt|jpg|png|mp4|zip)\b'
        matches = re.findall(extension_pattern, query)
        for ext in matches:
            file_types.append(f'.{ext}')

        return list(set(file_types))

    def _extract_size_constraints(self, query: str) -> Dict[str, int]:
        """Extract file size constraints from query"""
        constraints = {}

        # Pattern for size specifications
        size_pattern = r'(larger|bigger|smaller|less)\s+than\s+(\d+)\s*(kb|mb|gb)?'
        match = re.search(size_pattern, query.lower())

        if match:
            comparison = match.group(1)
            size = int(match.group(2))
            unit = match.group(3) or 'mb'

            size_bytes = size * self.size_units.get(unit, 1024 * 1024)

            if comparison in ['larger', 'bigger']:
                constraints['min_size'] = size_bytes
            else:
                constraints['max_size'] = size_bytes

        return constraints

    def _extract_categories(self, query: str) -> List[str]:
        """Extract category hints from query"""
        categories = []

        category_keywords = {
            'invoice': ['invoice', 'bill', 'payment'],
            'report': ['report', 'analysis', 'summary'],
            'presentation': ['presentation', 'slides', 'deck'],
            'photo': ['photo', 'picture', 'image'],
            'contract': ['contract', 'agreement', 'legal'],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in query.lower() for keyword in keywords):
                categories.append(category)

        return categories


class SearchEngine:
    def __init__(self, index_dir: str = "tidybot_index"):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(exist_ok=True)

        # Initialize Whoosh index
        self.schema = Schema(
            path=ID(stored=True, unique=True),
            name=TEXT(stored=True),
            content=TEXT(stored=True),
            tags=KEYWORD(stored=True, commas=True),
            category=ID(stored=True),
            size=NUMERIC(stored=True),
            modified=DATETIME(stored=True),
            mime_type=ID(stored=True)
        )

        self._init_index()

        # Initialize sentence transformer for semantic search
        try:
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embeddings_cache = {}
        except Exception as e:
            logger.warning(f"Could not load sentence transformer: {e}")
            self.sentence_model = None

        # Initialize NLP parser
        self.nl_parser = NaturalLanguageParser()

    def _init_index(self):
        """Initialize or open Whoosh index"""
        index_path = self.index_dir / "index"
        if index_path.exists():
            self.ix = index.open_dir(str(index_path))
        else:
            index_path.mkdir(exist_ok=True)
            self.ix = index.create_in(str(index_path), self.schema)

    async def search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession] = None
    ) -> List[SearchResult]:
        """Execute a search query"""
        try:
            if query.search_type == SearchType.NATURAL_LANGUAGE:
                return await self._natural_language_search(query, db_session)
            elif query.search_type == SearchType.SEMANTIC:
                return await self._semantic_search(query, db_session)
            elif query.search_type == SearchType.EXACT:
                return await self._exact_search(query, db_session)
            elif query.search_type == SearchType.FUZZY:
                return await self._fuzzy_search(query, db_session)
            elif query.search_type == SearchType.REGEX:
                return await self._regex_search(query, db_session)
            else:
                return await self._basic_search(query, db_session)

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def _natural_language_search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession]
    ) -> List[SearchResult]:
        """Process natural language search query"""
        # Parse the natural language query
        parsed = self.nl_parser.parse(query.query_text)

        # Build Whoosh query
        with self.ix.searcher() as searcher:
            # Create query from keywords
            if parsed['keywords']:
                parser = MultifieldParser(
                    ["name", "content", "tags"],
                    self.ix.schema
                )
                whoosh_query = parser.parse(' '.join(parsed['keywords']))
            else:
                whoosh_query = parser.parse(query.query_text)

            # Apply filters
            filter_query = None

            if parsed['date_range']:
                start, end = parsed['date_range']
                date_filter = DateRange("modified", start, end)
                filter_query = date_filter if not filter_query else And([filter_query, date_filter])

            if parsed['size_constraints']:
                if 'min_size' in parsed['size_constraints']:
                    size_filter = NumericRange("size", parsed['size_constraints']['min_size'], None)
                    filter_query = size_filter if not filter_query else And([filter_query, size_filter])
                if 'max_size' in parsed['size_constraints']:
                    size_filter = NumericRange("size", None, parsed['size_constraints']['max_size'])
                    filter_query = size_filter if not filter_query else And([filter_query, size_filter])

            # Execute search
            results = searcher.search(
                whoosh_query,
                filter=filter_query,
                limit=query.limit
            )

            # Convert to SearchResult objects
            search_results = []
            for hit in results:
                highlights = hit.highlights("content", top=3) if query.include_content else []

                result = SearchResult(
                    file_path=hit['path'],
                    file_name=hit['name'],
                    score=hit.score,
                    highlights=highlights,
                    metadata={},
                    category=hit.get('category', 'general'),
                    tags=hit.get('tags', '').split(',') if hit.get('tags') else [],
                    file_size=hit.get('size', 0),
                    modified_at=hit.get('modified', datetime.now()),
                    content_preview=hit.get('content', '')[:200] if query.include_content else None
                )
                search_results.append(result)

            # If semantic search is available, re-rank results
            if self.sentence_model and len(search_results) > 1:
                search_results = await self._rerank_semantic(
                    query.query_text,
                    search_results
                )

            return search_results

    async def _semantic_search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession]
    ) -> List[SearchResult]:
        """Perform semantic similarity search using embeddings"""
        if not self.sentence_model:
            logger.warning("Semantic search not available, falling back to basic search")
            return await self._basic_search(query, db_session)

        # Get query embedding
        query_embedding = self.sentence_model.encode([query.query_text])[0]

        # Get all documents from database
        if db_session:
            result = await db_session.execute(
                select(FileIndex).limit(1000)  # Limit for performance
            )
            files = result.scalars().all()

            search_results = []
            for file in files:
                # Get or compute document embedding
                if file.file_path not in self.embeddings_cache:
                    doc_text = f"{file.file_name} {file.content or ''}"
                    doc_embedding = self.sentence_model.encode([doc_text])[0]
                    self.embeddings_cache[file.file_path] = doc_embedding
                else:
                    doc_embedding = self.embeddings_cache[file.file_path]

                # Calculate similarity
                similarity = cosine_similarity(
                    [query_embedding],
                    [doc_embedding]
                )[0][0]

                if similarity > 0.3:  # Threshold for relevance
                    result = SearchResult(
                        file_path=file.file_path,
                        file_name=file.file_name,
                        score=float(similarity),
                        highlights=[],
                        metadata=file.metadata or {},
                        category=file.category or 'general',
                        tags=file.tags or [],
                        file_size=file.file_size,
                        modified_at=file.modified_at,
                        content_preview=file.content[:200] if query.include_content else None
                    )
                    search_results.append(result)

            # Sort by similarity score
            search_results.sort(key=lambda x: x.score, reverse=True)
            return search_results[:query.limit]

        return []

    async def _exact_search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession]
    ) -> List[SearchResult]:
        """Perform exact phrase search"""
        with self.ix.searcher() as searcher:
            # Create phrase query
            phrase_query = Phrase("content", query.query_text.split())

            results = searcher.search(phrase_query, limit=query.limit)

            search_results = []
            for hit in results:
                result = SearchResult(
                    file_path=hit['path'],
                    file_name=hit['name'],
                    score=hit.score,
                    highlights=hit.highlights("content", top=3),
                    metadata={},
                    category=hit.get('category', 'general'),
                    tags=hit.get('tags', '').split(',') if hit.get('tags') else [],
                    file_size=hit.get('size', 0),
                    modified_at=hit.get('modified', datetime.now()),
                    content_preview=hit.get('content', '')[:200] if query.include_content else None
                )
                search_results.append(result)

            return search_results

    async def _fuzzy_search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession]
    ) -> List[SearchResult]:
        """Perform fuzzy search with edit distance"""
        with self.ix.searcher() as searcher:
            parser = QueryParser("content", self.ix.schema)
            # Add fuzzy matching with ~ operator
            fuzzy_query = parser.parse(f"{query.query_text}~2")

            results = searcher.search(fuzzy_query, limit=query.limit)

            search_results = []
            for hit in results:
                result = SearchResult(
                    file_path=hit['path'],
                    file_name=hit['name'],
                    score=hit.score,
                    highlights=hit.highlights("content", top=3),
                    metadata={},
                    category=hit.get('category', 'general'),
                    tags=hit.get('tags', '').split(',') if hit.get('tags') else [],
                    file_size=hit.get('size', 0),
                    modified_at=hit.get('modified', datetime.now()),
                    content_preview=hit.get('content', '')[:200] if query.include_content else None
                )
                search_results.append(result)

            return search_results

    async def _regex_search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession]
    ) -> List[SearchResult]:
        """Perform regex pattern search"""
        if not db_session:
            return []

        try:
            pattern = re.compile(query.query_text)

            result = await db_session.execute(
                select(FileIndex).limit(1000)
            )
            files = result.scalars().all()

            search_results = []
            for file in files:
                # Search in content and filename
                content_to_search = f"{file.file_name} {file.content or ''}"

                if pattern.search(content_to_search):
                    matches = pattern.findall(content_to_search)[:3]

                    result = SearchResult(
                        file_path=file.file_path,
                        file_name=file.file_name,
                        score=len(matches),
                        highlights=matches,
                        metadata=file.metadata or {},
                        category=file.category or 'general',
                        tags=file.tags or [],
                        file_size=file.file_size,
                        modified_at=file.modified_at,
                        content_preview=file.content[:200] if query.include_content else None
                    )
                    search_results.append(result)

            search_results.sort(key=lambda x: x.score, reverse=True)
            return search_results[:query.limit]

        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return []

    async def _basic_search(
        self,
        query: SearchQuery,
        db_session: Optional[AsyncSession]
    ) -> List[SearchResult]:
        """Basic keyword search"""
        with self.ix.searcher() as searcher:
            parser = MultifieldParser(
                ["name", "content", "tags"],
                self.ix.schema
            )
            whoosh_query = parser.parse(query.query_text)

            results = searcher.search(whoosh_query, limit=query.limit)

            search_results = []
            for hit in results:
                result = SearchResult(
                    file_path=hit['path'],
                    file_name=hit['name'],
                    score=hit.score,
                    highlights=hit.highlights("content", top=3) if query.include_content else [],
                    metadata={},
                    category=hit.get('category', 'general'),
                    tags=hit.get('tags', '').split(',') if hit.get('tags') else [],
                    file_size=hit.get('size', 0),
                    modified_at=hit.get('modified', datetime.now()),
                    content_preview=hit.get('content', '')[:200] if query.include_content else None
                )
                search_results.append(result)

            return search_results

    async def _rerank_semantic(
        self,
        query_text: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """Re-rank results using semantic similarity"""
        if not self.sentence_model or not results:
            return results

        # Get query embedding
        query_embedding = self.sentence_model.encode([query_text])[0]

        # Calculate semantic scores
        for result in results:
            doc_text = f"{result.file_name} {' '.join(result.highlights)}"
            doc_embedding = self.sentence_model.encode([doc_text])[0]

            similarity = cosine_similarity(
                [query_embedding],
                [doc_embedding]
            )[0][0]

            # Combine with original score
            result.score = result.score * 0.5 + similarity * 0.5

        # Re-sort by combined score
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    async def add_to_index(self, file_data: Dict[str, Any]):
        """Add a file to the search index"""
        try:
            writer = AsyncWriter(self.ix)
            writer.add_document(
                path=file_data['path'],
                name=file_data['name'],
                content=file_data.get('content', ''),
                tags=','.join(file_data.get('tags', [])),
                category=file_data.get('category', 'general'),
                size=file_data.get('size', 0),
                modified=file_data.get('modified', datetime.now()),
                mime_type=file_data.get('mime_type', 'application/octet-stream')
            )
            await writer.commit()
            logger.info(f"Added to search index: {file_data['path']}")

        except Exception as e:
            logger.error(f"Error adding to index: {e}")

    async def update_index(self, file_data: Dict[str, Any]):
        """Update a file in the search index"""
        try:
            # Remove old entry
            writer = AsyncWriter(self.ix)
            writer.delete_by_term('path', file_data['path'])

            # Add updated entry
            writer.add_document(
                path=file_data['path'],
                name=file_data['name'],
                content=file_data.get('content', ''),
                tags=','.join(file_data.get('tags', [])),
                category=file_data.get('category', 'general'),
                size=file_data.get('size', 0),
                modified=file_data.get('modified', datetime.now()),
                mime_type=file_data.get('mime_type', 'application/octet-stream')
            )
            await writer.commit()
            logger.info(f"Updated in search index: {file_data['path']}")

        except Exception as e:
            logger.error(f"Error updating index: {e}")

    async def remove_from_index(self, file_path: str):
        """Remove a file from the search index"""
        try:
            writer = AsyncWriter(self.ix)
            writer.delete_by_term('path', file_path)
            await writer.commit()
            logger.info(f"Removed from search index: {file_path}")

        except Exception as e:
            logger.error(f"Error removing from index: {e}")