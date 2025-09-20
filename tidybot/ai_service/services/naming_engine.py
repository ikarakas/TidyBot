from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import re
import logging
from dataclasses import dataclass
from enum import Enum
from .language_detector import LanguageDetector

logger = logging.getLogger(__name__)


class NamingPattern(Enum):
    CONTENT_BASED = "content_based"
    DATE_BASED = "date_based"
    SEQUENTIAL = "sequential"
    CATEGORY_PREFIX = "category_prefix"
    CUSTOM_TEMPLATE = "custom_template"


@dataclass
class NamingRule:
    pattern: NamingPattern
    template: str
    parameters: Dict[str, Any]
    priority: int = 0


class SmartNamingEngine:
    def __init__(self):
        self.language_detector = LanguageDetector()
        self.default_patterns = {
            NamingPattern.CONTENT_BASED: "{category}_{description}_{date}",
            NamingPattern.DATE_BASED: "{year}-{month}-{day}_{description}",
            NamingPattern.SEQUENTIAL: "{category}_{number:04d}_{description}",
            NamingPattern.CATEGORY_PREFIX: "{category}_{original_name}",
            NamingPattern.CUSTOM_TEMPLATE: "{template}"
        }
        
        self.category_keywords = {
            'invoice': ['invoice', 'bill', 'payment', 'receipt', 'transaction'],
            'report': ['report', 'analysis', 'summary', 'overview', 'review'],
            'presentation': ['presentation', 'slides', 'deck', 'powerpoint'],
            'screenshot': ['screenshot', 'capture', 'snip', 'screen'],
            'photo': ['photo', 'picture', 'image', 'portrait', 'landscape'],
            'document': ['document', 'doc', 'text', 'note', 'memo'],
            'spreadsheet': ['excel', 'spreadsheet', 'data', 'table', 'csv'],
            'contract': ['contract', 'agreement', 'terms', 'legal'],
            'resume': ['resume', 'cv', 'curriculum', 'vitae', 'profile'],
            'email': ['email', 'message', 'correspondence', 'mail'],
        }

        # German category keywords
        self.german_category_keywords = {
            'rechnung': ['rechnung', 'quittung', 'zahlung', 'kosten', 'beleg'],
            'bericht': ['bericht', 'analyse', 'zusammenfassung', 'übersicht', 'auswertung'],
            'präsentation': ['präsentation', 'vortrag', 'folien'],
            'dokument': ['dokument', 'unterlage', 'schreiben', 'text', 'notiz'],
            'tabelle': ['excel', 'tabelle', 'daten', 'liste'],
            'vertrag': ['vertrag', 'vereinbarung', 'bedingungen'],
            'lebenslauf': ['lebenslauf', 'bewerbung', 'cv'],
            'brief': ['brief', 'schreiben', 'mitteilung', 'nachricht'],
        }
    
    async def generate_name(
        self, 
        file_path: Path, 
        analysis_result: Dict[str, Any],
        naming_rule: Optional[NamingRule] = None,
        preserve_extension: bool = True
    ) -> Tuple[str, float]:
        
        try:
            if naming_rule:
                new_name = await self._apply_naming_rule(file_path, analysis_result, naming_rule)
            else:
                new_name = await self._generate_smart_name(file_path, analysis_result)
            
            confidence_score = self._calculate_confidence(analysis_result, new_name)
            
            if preserve_extension:
                extension = file_path.suffix
                if not new_name.endswith(extension):
                    new_name = f"{new_name}{extension}"
            
            new_name = self._sanitize_filename(new_name)
            
            return new_name, confidence_score
            
        except Exception as e:
            logger.error(f"Error generating name for {file_path}: {e}")
            return file_path.name, 0.0
    
    async def _generate_smart_name(self, file_path: Path, analysis: Dict[str, Any]) -> str:
        components = []

        # Detect language for better naming
        text_for_detection = self._extract_text_for_detection(analysis)
        language_info = self.language_detector.get_language_info(text_for_detection)
        detected_lang = language_info['detected_language']

        # Use language-specific category determination
        category = self._determine_category(analysis, detected_lang)
        if category:
            components.append(category)

        description = self._extract_description(analysis, detected_lang)
        if description:
            components.append(description)

        date_component = self._extract_date_component(analysis, file_path)
        if date_component:
            components.append(date_component)

        if not components:
            components.append(file_path.stem)

        return '_'.join(components)
    
    def _extract_text_for_detection(self, analysis: Dict[str, Any]) -> str:
        """Extract all available text for language detection"""
        text_parts = []

        if 'text' in analysis and analysis['text']:
            text_parts.append(analysis['text'])

        if 'ocr_text' in analysis and analysis['ocr_text']:
            text_parts.append(analysis['ocr_text'])

        if 'caption' in analysis and analysis['caption']:
            text_parts.append(analysis['caption'])

        if 'keywords' in analysis and analysis['keywords']:
            text_parts.append(' '.join(analysis['keywords']))

        if 'metadata' in analysis and isinstance(analysis['metadata'], dict):
            metadata = analysis['metadata']
            if metadata.get('title'):
                text_parts.append(metadata['title'])
            if metadata.get('subject'):
                text_parts.append(metadata['subject'])

        return ' '.join(text_parts)

    def _determine_category(self, analysis: Dict[str, Any], language: str = 'unknown') -> Optional[str]:
        file_type = analysis.get('type', 'unknown')
        
        if file_type == 'image' and analysis.get('is_screenshot'):
            return 'screenshot'
        
        text_content = ''
        if 'text' in analysis:
            text_content = analysis['text'].lower()
        elif 'ocr_text' in analysis:
            text_content = analysis['ocr_text'].lower()
        elif 'caption' in analysis:
            text_content = analysis['caption'].lower()
        
        keywords = analysis.get('keywords', [])
        if keywords:
            text_content += ' ' + ' '.join(keywords).lower()
        
        # Use language-specific keywords if German is detected
        if language == 'german':
            for category, category_keywords in self.german_category_keywords.items():
                if any(keyword in text_content for keyword in category_keywords):
                    return category

        # Fall back to English keywords
        for category, category_keywords in self.category_keywords.items():
            if any(keyword in text_content for keyword in category_keywords):
                return category
        
        type_to_category = {
            'image': 'image',
            'document': 'document',
            'spreadsheet': 'data',
            'presentation': 'presentation',
            'video': 'video',
            'audio': 'audio'
        }
        
        return type_to_category.get(file_type, 'file')
    
    def _extract_description(self, analysis: Dict[str, Any], language: str = 'unknown') -> str:
        descriptions = []
        
        if 'caption' in analysis and analysis['caption']:
            caption = analysis['caption']
            caption = re.sub(r'[^\w\s-]', '', caption)
            words = caption.split()[:5]
            if words:
                descriptions.append('_'.join(words))
        
        if 'keywords' in analysis and analysis['keywords']:
            top_keywords = analysis['keywords'][:3]
            if top_keywords:
                descriptions.append('_'.join(top_keywords))
        
        if 'metadata' in analysis:
            metadata = analysis['metadata']
            if isinstance(metadata, dict):
                if metadata.get('title'):
                    title = re.sub(r'[^\w\s-]', '', metadata['title'])
                    words = title.split()[:4]
                    if words:
                        descriptions.append('_'.join(words))
                
                if metadata.get('subject'):
                    subject = re.sub(r'[^\w\s-]', '', metadata['subject'])
                    words = subject.split()[:3]
                    if words:
                        descriptions.append('_'.join(words))
        
        if 'objects' in analysis and analysis['objects']:
            top_objects = [obj['label'] for obj in analysis['objects'][:2]]
            if top_objects:
                descriptions.append('_'.join(top_objects))
        
        if 'ocr_text' in analysis and analysis['ocr_text']:
            text = analysis['ocr_text']
            lines = text.split('\n')
            if lines and lines[0]:
                # For German text, preserve umlauts and ß
                if language == 'german':
                    first_line = re.sub(r'[^\w\s\-äöüÄÖÜß]', '', lines[0])
                else:
                    first_line = re.sub(r'[^\w\s-]', '', lines[0])
                words = first_line.split()[:4]
                if words:
                    descriptions.append('_'.join(words))
        
        if descriptions:
            description = descriptions[0]
            description = description.lower().replace(' ', '_')
            description = re.sub(r'_+', '_', description)
            description = description[:50]
            return description
        
        return ""
    
    def _extract_date_component(self, analysis: Dict[str, Any], file_path: Path) -> str:
        date = None
        
        if 'dates' in analysis and analysis['dates']:
            date_str = analysis['dates'][0]
            date = self._parse_date_string(date_str)
        
        if not date and 'metadata' in analysis:
            metadata = analysis['metadata']
            if isinstance(metadata, dict):
                for date_field in ['created', 'modified', 'DateTime', 'DateTimeOriginal']:
                    if date_field in metadata and metadata[date_field]:
                        date = self._parse_date_string(str(metadata[date_field]))
                        if date:
                            break
        
        if not date:
            stat = file_path.stat()
            date = datetime.fromtimestamp(stat.st_mtime)
        
        if date:
            return date.strftime("%Y%m%d")
        
        return datetime.now().strftime("%Y%m%d")
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        date_formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S"
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None
    
    async def _apply_naming_rule(
        self, 
        file_path: Path, 
        analysis: Dict[str, Any], 
        rule: NamingRule
    ) -> str:
        
        template = rule.template
        params = rule.parameters
        
        replacements = {
            'category': self._determine_category(analysis) or 'file',
            'description': self._extract_description(analysis) or 'unnamed',
            'date': self._extract_date_component(analysis, file_path),
            'year': datetime.now().strftime("%Y"),
            'month': datetime.now().strftime("%m"),
            'day': datetime.now().strftime("%d"),
            'original_name': file_path.stem,
            'extension': file_path.suffix.lstrip('.'),
            'number': params.get('counter', 1),
            'custom_field': params.get('custom_field', '')
        }
        
        for key, value in replacements.items():
            template = template.replace(f"{{{key}}}", str(value))
        
        return template
    
    def _calculate_confidence(self, analysis: Dict[str, Any], new_name: str) -> float:
        confidence = 0.5
        
        if analysis.get('error'):
            return 0.1
        
        if 'caption' in analysis and analysis['caption']:
            confidence += 0.2
        
        if 'keywords' in analysis and len(analysis['keywords']) > 3:
            confidence += 0.15
        
        if 'metadata' in analysis and analysis['metadata']:
            metadata = analysis['metadata']
            if metadata.get('title') or metadata.get('subject'):
                confidence += 0.15
        
        if 'ocr_text' in analysis and len(analysis.get('ocr_text', '')) > 50:
            confidence += 0.1
        
        if 'objects' in analysis and len(analysis['objects']) > 0:
            confidence += 0.1
        
        if new_name != 'unnamed' and '_' in new_name:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _sanitize_filename(self, filename: str, max_length: int = 200) -> str:
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        filename = re.sub(r'_+', '_', filename)
        
        filename = filename.strip('_. ')
        
        if len(filename) > max_length:
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2:
                name, ext = name_parts
                max_name_length = max_length - len(ext) - 1
                filename = f"{name[:max_name_length]}.{ext}"
            else:
                filename = filename[:max_length]
        
        return filename or "unnamed"
    
    async def suggest_alternatives(
        self,
        file_path: Path,
        analysis: Dict[str, Any],
        num_suggestions: int = 3
    ) -> List[Tuple[str, float]]:

        suggestions = []

        rules = [
            NamingRule(NamingPattern.CONTENT_BASED, self.default_patterns[NamingPattern.CONTENT_BASED], {}),
            NamingRule(NamingPattern.DATE_BASED, self.default_patterns[NamingPattern.DATE_BASED], {}),
            NamingRule(NamingPattern.CATEGORY_PREFIX, self.default_patterns[NamingPattern.CATEGORY_PREFIX], {})
        ]

        for rule in rules[:num_suggestions]:
            try:
                name = await self._apply_naming_rule(file_path, analysis, rule)
                confidence = self._calculate_confidence(analysis, name)
                suggestions.append((name, confidence))
            except:
                continue

        return suggestions