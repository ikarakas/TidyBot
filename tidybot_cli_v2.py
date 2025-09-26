#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
TidyBot CLI v2 - Intelligent file organization tool with archive handling
"""

import os
import sys
import json
import gzip
import zipfile
import tarfile
import shutil
import hashlib
import argparse
import tempfile
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime
import argcomplete
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich import print as rprint
from rich.tree import Tree

# Initialize Rich console
console = Console()

# API Configuration
API_BASE_URL = "http://127.0.0.1:11007/api/v1"

# Archive extensions
ARCHIVE_EXTENSIONS = {'.gz', '.zip', '.tar', '.tar.gz', '.tar.bz2', '.7z', '.rar', '.bz2', '.xz'}


class TidyBotCLI:
    def __init__(self, api_url: str = API_BASE_URL):
        self.api_url = api_url
        self.session = requests.Session()

    def check_connection(self) -> bool:
        """Check if API is reachable"""
        try:
            response = self.session.get(f"{self.api_url.replace('/api/v1', '')}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

    def is_archive(self, file_path: Path) -> bool:
        """Check if file is an archive/compressed file"""
        # Check for double extensions like .tar.gz
        suffixes = ''.join(file_path.suffixes)
        if suffixes in ARCHIVE_EXTENSIONS:
            return True
        return file_path.suffix.lower() in ARCHIVE_EXTENSIONS

    def extract_archive_sample(self, file_path: Path, max_files: int = 5) -> Optional[Dict]:
        """Extract and analyze sample files from archive"""
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="tidybot_")
            extracted_info = {
                'type': 'archive',
                'original_name': file_path.name,
                'contents': [],
                'suggested_base_name': None
            }

            # Handle different archive types
            if file_path.suffix == '.gz':
                # For .gz files, check if it's a .tar.gz or just a compressed file
                if '.tar' in file_path.name:
                    with tarfile.open(file_path, 'r:gz') as tar:
                        members = tar.getmembers()[:max_files]
                        for member in members:
                            if member.isfile():
                                extracted_info['contents'].append(member.name)
                else:
                    # Single file compression
                    decompressed_name = file_path.stem  # Remove .gz
                    extracted_info['contents'].append(decompressed_name)
                    extracted_info['suggested_base_name'] = Path(decompressed_name).stem

            elif file_path.suffix == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zf:
                    file_list = zf.namelist()[:max_files]
                    extracted_info['contents'] = file_list

            elif file_path.suffix in {'.tar', '.tar.bz2', '.tar.xz'}:
                mode = 'r:*'  # Auto-detect compression
                with tarfile.open(file_path, mode) as tar:
                    members = tar.getmembers()[:max_files]
                    for member in members:
                        if member.isfile():
                            extracted_info['contents'].append(member.name)

            # Analyze content patterns to suggest a name
            if extracted_info['contents']:
                # Look for common patterns
                common_prefixes = self._find_common_prefix(extracted_info['contents'])
                if common_prefixes:
                    extracted_info['suggested_base_name'] = common_prefixes

            return extracted_info

        except Exception as e:
            console.print(f"[yellow]Warning: Could not analyze archive {file_path.name}: {e}[/yellow]")
            return None
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def _find_common_prefix(self, file_list: List[str]) -> Optional[str]:
        """Find common prefix in file names"""
        if not file_list:
            return None

        # Get just the filenames, not paths
        names = [Path(f).name for f in file_list]
        if not names:
            return None

        # Find common prefix
        prefix = os.path.commonprefix(names)
        if len(prefix) > 3:  # Meaningful prefix
            return prefix.rstrip('_-. ')

        return None

    def process_file(self, file_path: Path, handle_archives: str = 'skip') -> Dict:
        """Process a single file through the API or handle locally for archives"""

        # Check if it's an archive
        if self.is_archive(file_path):
            if handle_archives == 'skip':
                console.print(f"[yellow]Skipping archive: {file_path.name}[/yellow]")
                return {
                    'suggested_name': file_path.name,
                    'confidence_score': 0.0,
                    'category': 'archive',
                    'skipped': True,
                    'reason': 'Archive file skipped'
                }
            elif handle_archives == 'decompress':
                # Try to analyze archive contents
                archive_info = self.extract_archive_sample(file_path)
                if archive_info and archive_info.get('suggested_base_name'):
                    base_name = archive_info['suggested_base_name']
                    # For single compressed files (.js.gz, .html.gz), just keep the compression extension
                    if file_path.suffix == '.gz' and not '.tar' in file_path.name:
                        # It's a single file compression like file.js.gz
                        # Keep original if the base name is already in the filename
                        if base_name in file_path.stem:
                            new_name = file_path.name  # Keep original
                        else:
                            # Use the base name + .gz only
                            new_name = f"{base_name}.gz"
                    else:
                        # For archives (.zip, .tar.gz), keep full extension
                        new_name = f"{base_name}{''.join(file_path.suffixes)}"
                    return {
                        'suggested_name': new_name,
                        'confidence_score': 0.4,  # Lower confidence for archives
                        'category': 'archive',
                        'archive_contents': archive_info['contents'][:3],
                        'analyzed': True
                    }
                else:
                    # Couldn't analyze, keep original with low confidence
                    return {
                        'suggested_name': file_path.name,
                        'confidence_score': 0.1,
                        'category': 'archive',
                        'analyzed': False
                    }
            else:  # 'keep'
                # Keep original name but mark as archive
                return {
                    'suggested_name': file_path.name,
                    'confidence_score': 0.2,
                    'category': 'archive',
                    'kept_original': True
                }

        # For non-archive files, use the API
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, 'application/octet-stream')}
                response = self.session.post(f"{self.api_url}/files/process", files=files)
                if response.status_code == 200:
                    result = response.json()
                    # Cap confidence for certain file types
                    if result.get('confidence_score', 0) > 0.9 and 'unknown' in result.get('category', ''):
                        result['confidence_score'] = 0.3
                    return result
                else:
                    raise Exception(f"API error: {response.status_code}")
        except Exception as e:
            console.print(f"[red]Error processing {file_path.name}: {e}[/red]")
            return {
                'suggested_name': file_path.name,
                'confidence_score': 0.0,
                'category': 'error',
                'error': str(e)
            }

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[Path]:
        """Scan directory for all files"""
        files = []
        pattern = "**/*" if recursive else "*"
        for path in directory.glob(pattern):
            if path.is_file() and not path.name.startswith('.'):
                files.append(path)
        return files

    def recommend_mode(self, directory: Path, preset: str = "default",
                      handle_archives: str = 'skip', verbose: bool = False, single_file: Path = None):
        """Recommendation mode - just show what would be done"""
        if single_file:
            console.print(f"\n[bold cyan]📋 Processing file:[/bold cyan] {single_file}")
            files = [single_file]
        else:
            console.print(f"\n[bold cyan]📋 Scanning directory:[/bold cyan] {directory}")
            files = self.scan_directory(directory)
            console.print(f"Found {len(files)} files\n")

        console.print(f"[dim]Archive handling: {handle_archives}[/dim]\n")

        if not files:
            console.print("[yellow]No files found to process[/yellow]")
            return

        recommendations = []
        archives_found = 0
        skipped_files = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing files...", total=len(files))

            for file_path in files:
                if self.is_archive(file_path):
                    archives_found += 1

                result = self.process_file(file_path, handle_archives)

                if result.get('skipped'):
                    skipped_files += 1
                    if verbose:
                        console.print(f"[dim]Skipped: {file_path.name}[/dim]")
                else:
                    recommendations.append({
                        'original': file_path,
                        'suggested_name': result.get('suggested_name', file_path.name),
                        'confidence': result.get('confidence_score', 0),
                        'category': result.get('category', 'unknown'),
                        'archive_contents': result.get('archive_contents', None)
                    })

                progress.update(task, advance=1)

        # Display recommendations
        if recommendations:
            table = Table(title="File Rename Recommendations", show_lines=True)
            table.add_column("Current Name", style="cyan", no_wrap=False)
            table.add_column("Suggested Name", style="green")
            table.add_column("Confidence", justify="center")
            table.add_column("Category", style="yellow")

            for rec in recommendations:
                # Color code confidence
                conf = rec['confidence']
                if conf > 0.8:
                    confidence_color = "green"
                elif conf > 0.5:
                    confidence_color = "yellow"
                elif conf > 0.2:
                    confidence_color = "orange1"
                else:
                    confidence_color = "red"

                # Add archive indicator
                name_display = rec['original'].name
                if rec['category'] == 'archive' and rec.get('archive_contents'):
                    name_display += " 📦"

                table.add_row(
                    name_display,
                    rec['suggested_name'],
                    f"[{confidence_color}]{rec['confidence']*100:.0f}%[/{confidence_color}]",
                    rec['category']
                )

            console.print(table)

        # Summary statistics
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total files: {len(files)}")
        console.print(f"  Archives found: {archives_found}")
        if skipped_files > 0:
            console.print(f"  Skipped files: {skipped_files}")
        console.print(f"  Files analyzed: {len(recommendations)}")
        console.print(f"  Files needing rename: {sum(1 for r in recommendations if r['original'].name != r['suggested_name'])}")

        if recommendations:
            avg_conf = sum(r['confidence'] for r in recommendations)/len(recommendations)
            console.print(f"  Average confidence: {avg_conf*100:.0f}%")

            # Warning for low confidence
            low_conf = [r for r in recommendations if r['confidence'] < 0.3]
            if low_conf:
                console.print(f"  [yellow]⚠️  Low confidence files: {len(low_conf)}[/yellow]")

    def auto_rename_mode(self, directory: Path, preset: str = "default",
                        handle_archives: str = 'skip', confidence_threshold: float = 0.5,
                        dry_run: bool = False, verbose: bool = False, single_file: Path = None):
        """Auto rename mode - rename files based on AI suggestions"""
        if single_file:
            console.print(f"\n[bold cyan]🔄 Auto-rename file:[/bold cyan] {single_file}")
            files = [single_file]
        else:
            console.print(f"\n[bold cyan]🔄 Auto-rename mode:[/bold cyan] {directory}")
            files = self.scan_directory(directory)
            console.print(f"Found {len(files)} files\n")

        console.print(f"[dim]Archive handling: {handle_archives}[/dim]")
        console.print(f"[dim]Confidence threshold: {confidence_threshold*100:.0f}%[/dim]\n")

        if not files:
            console.print("[yellow]No files found to process[/yellow]")
            return

        rename_operations = []
        skipped_low_confidence = 0
        skipped_archives = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing files...", total=len(files))

            for file_path in files:
                result = self.process_file(file_path, handle_archives)
                suggested_name = result.get('suggested_name', file_path.name)
                confidence = result.get('confidence_score', 0)

                # Skip if confidence too low
                if confidence < confidence_threshold:
                    skipped_low_confidence += 1
                    if verbose:
                        console.print(f"[yellow]Skipping {file_path.name} - confidence {confidence*100:.0f}% below threshold[/yellow]")
                elif result.get('skipped'):
                    skipped_archives += 1
                elif suggested_name != file_path.name:
                    new_path = file_path.parent / suggested_name

                    # Handle duplicates
                    if new_path.exists():
                        base = new_path.stem
                        ext = ''.join(new_path.suffixes)
                        counter = 1
                        while new_path.exists():
                            new_path = file_path.parent / f"{base}_{counter}{ext}"
                            counter += 1

                    rename_operations.append((file_path, new_path, confidence))

                progress.update(task, advance=1)

        # Show what will be done
        if rename_operations:
            table = Table(title="Files to Rename", show_lines=True)
            table.add_column("Current", style="cyan")
            table.add_column("New", style="green")
            table.add_column("Confidence", justify="center")

            for old, new, conf in rename_operations:
                table.add_row(old.name, new.name, f"{conf*100:.0f}%")

            console.print(table)

            if dry_run:
                console.print("\n[yellow]DRY RUN - No files were renamed[/yellow]")
            else:
                if Confirm.ask(f"\nRename {len(rename_operations)} files?"):
                    for old_path, new_path, _ in rename_operations:
                        old_path.rename(new_path)
                        if verbose:
                            console.print(f"✅ Renamed: {old_path.name} → {new_path.name}")

                    console.print(f"\n[green]✨ Successfully renamed {len(rename_operations)} files[/green]")
                else:
                    console.print("[yellow]Operation cancelled[/yellow]")
        else:
            console.print("[green]No files need renaming[/green]")

        # Summary
        if skipped_low_confidence > 0:
            console.print(f"[yellow]Skipped {skipped_low_confidence} files due to low confidence[/yellow]")
        if skipped_archives > 0:
            console.print(f"[yellow]Skipped {skipped_archives} archive files[/yellow]")

    def search_mode(self, query: str, search_type: str = "natural", 
                   limit: int = 20, include_content: bool = False, 
                   file_types: str = None, categories: str = None,
                   verbose: bool = False):
        """Search mode - search indexed files"""
        console.print(f"\n[bold cyan]🔍 Searching:[/bold cyan] {query}")
        console.print(f"[dim]Search type: {search_type}[/dim]")
        console.print(f"[dim]Limit: {limit} results[/dim]\n")

        try:
            # Prepare search request
            search_data = {
                "query": query,
                "search_type": search_type,
                "limit": limit,
                "content_only": include_content
            }

            # Add filters if specified
            if file_types:
                search_data["file_types"] = file_types
            if categories:
                search_data["categories"] = categories

            # Make search request
            response = self.session.post(f"{self.api_url}/search/query", json=search_data)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if not results:
                    console.print("[yellow]No results found[/yellow]")
                    return

                # Display results
                table = Table(title=f"Search Results for '{query}'", show_lines=True)
                table.add_column("File Path", style="cyan", no_wrap=False)
                table.add_column("File Name", style="green")
                table.add_column("Score", justify="center")
                table.add_column("Category", style="yellow")
                table.add_column("Size", justify="right")
                
                if include_content:
                    table.add_column("Preview", style="dim", no_wrap=False)

                for result in results:
                    file_path = result.get('file_path', '')
                    file_name = result.get('file_name', '')
                    score = result.get('score', 0)
                    category = result.get('category', 'unknown')
                    file_size = result.get('file_size', 0)
                    preview = result.get('content_preview', '') if include_content else ''

                    # Format file size
                    if file_size > 1024 * 1024:
                        size_str = f"{file_size / (1024 * 1024):.1f} MB"
                    elif file_size > 1024:
                        size_str = f"{file_size / 1024:.1f} KB"
                    else:
                        size_str = f"{file_size} B"

                    # Color code score
                    if score > 0.8:
                        score_color = "green"
                    elif score > 0.6:
                        score_color = "yellow"
                    elif score > 0.4:
                        score_color = "orange1"
                    else:
                        score_color = "red"

                    # Truncate preview if too long
                    if include_content and preview:
                        preview = preview[:100] + "..." if len(preview) > 100 else preview

                    row_data = [
                        file_path,
                        file_name,
                        f"[{score_color}]{score*100:.0f}%[/{score_color}]",
                        category,
                        size_str
                    ]
                    
                    if include_content:
                        row_data.append(preview)

                    table.add_row(*row_data)

                console.print(table)

                # Summary
                console.print(f"\n[bold]Summary:[/bold]")
                console.print(f"  Query: {query}")
                console.print(f"  Search type: {search_type}")
                console.print(f"  Results found: {len(results)}")
                console.print(f"  Total available: {data.get('total', len(results))}")

                if verbose:
                    console.print(f"\n[dim]API Response:[/dim]")
                    console.print(json.dumps(data, indent=2))

            else:
                console.print(f"[red]Search failed: {response.status_code}[/red]")
                if verbose:
                    console.print(f"Response: {response.text}")

        except Exception as e:
            console.print(f"[red]Search error: {e}[/red]")
            if verbose:
                import traceback
                console.print(traceback.format_exc())

    def index_mode(self, directory: Path, recursive: bool = True, 
                  monitor: bool = False, verbose: bool = False):
        """Index mode - index a directory for search"""
        console.print(f"\n[bold cyan]📚 Indexing directory:[/bold cyan] {directory}")
        console.print(f"[dim]Recursive: {recursive}[/dim]")
        console.print(f"[dim]Monitor: {monitor}[/dim]\n")

        if not directory.exists():
            console.print(f"[red]Directory not found: {directory}[/red]")
            return

        if not directory.is_dir():
            console.print(f"[red]Path is not a directory: {directory}[/red]")
            return

        try:
            # Index directory
            response = self.session.post(
                f"{self.api_url}/search/index/directory",
                params={
                    "path": str(directory),
                    "recursive": recursive,
                    "monitor": monitor
                }
            )

            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]✅ Directory indexed successfully[/green]")
                console.print(f"  Files indexed: {data.get('files_indexed', 0)}")
                console.print(f"  Directories scanned: {data.get('directories_scanned', 0)}")
                console.print(f"  Indexing time: {data.get('indexing_time_ms', 0)}ms")
                
                if verbose:
                    console.print(f"\n[dim]Index details:[/dim]")
                    console.print(json.dumps(data, indent=2))
            else:
                console.print(f"[red]Indexing failed: {response.status_code}[/red]")
                if verbose:
                    console.print(f"Response: {response.text}")

        except Exception as e:
            console.print(f"[red]Indexing error: {e}[/red]")
            if verbose:
                import traceback
                console.print(traceback.format_exc())

    def stats_mode(self, verbose: bool = False):
        """Stats mode - show search and indexing statistics"""
        console.print(f"\n[bold cyan]📊 TidyBot Statistics[/bold cyan]\n")

        try:
            response = self.session.get(f"{self.api_url}/search/stats")
            
            if response.status_code == 200:
                data = response.json()
                
                # Index statistics
                index_stats = data.get('index', {})
                console.print("[bold]Search Index:[/bold]")
                console.print(f"  Total files indexed: {index_stats.get('total_files', 0)}")
                console.print(f"  Index size: {index_stats.get('index_size_mb', 0):.2f} MB")
                console.print(f"  Last updated: {index_stats.get('last_updated', 'Never')}")
                
                # Search engine info
                search_engine = data.get('search_engine', {})
                console.print(f"\n[bold]Search Engine:[/bold]")
                console.print(f"  Index path: {search_engine.get('index_path', 'N/A')}")
                console.print(f"  Semantic search: {'Yes' if search_engine.get('has_semantic_search') else 'No'}")
                
                # Offline stats
                offline_stats = data.get('offline', {})
                console.print(f"\n[bold]Offline Cache:[/bold]")
                console.print(f"  Cached files: {offline_stats.get('cached_files', 0)}")
                console.print(f"  Cache size: {offline_stats.get('cache_size_mb', 0):.2f} MB")
                console.print(f"  Pending operations: {offline_stats.get('pending_operations', 0)}")

                if verbose:
                    console.print(f"\n[dim]Full statistics:[/dim]")
                    console.print(json.dumps(data, indent=2))
            else:
                console.print(f"[red]Failed to get statistics: {response.status_code}[/red]")
                if verbose:
                    console.print(f"Response: {response.text}")

        except Exception as e:
            console.print(f"[red]Statistics error: {e}[/red]")
            if verbose:
                import traceback
                console.print(traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(
        description='TidyBot CLI v2 - Intelligent file organization with archive handling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Archive Handling Options:
  skip       - Skip archive files completely (default)
  keep       - Keep original names for archives
  decompress - Analyze archive contents to suggest better names

Search Types:
  natural    - Natural language search (default)
  semantic   - AI-powered semantic similarity search
  exact      - Exact phrase matching
  fuzzy      - Fuzzy matching with typos
  regex      - Regular expression search

Examples:
  # File organization
  tidybot recommend ~/Downloads --handle-archives skip
  tidybot auto ~/Documents --confidence 0.7
  tidybot reorganize ~/Desktop --dry-run
  
  # Search functionality
  tidybot search "amazon invoice" --type natural
  tidybot search "screenshots from last week" --content
  tidybot search "financial documents" --type semantic --categories invoice,receipt
  tidybot index ~/Documents --monitor
  tidybot stats
        '''
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode', required=True)

    # Recommend mode
    recommend_parser = subparsers.add_parser('recommend', help='Show rename recommendations without making changes')
    recommend_parser.add_argument('directory', type=str, help='Directory or file to analyze')
    recommend_parser.add_argument('--preset', default='default',
                                 choices=['default', 'screenshot', 'document', 'photo', 'code'],
                                 help='Processing preset to use')
    recommend_parser.add_argument('--handle-archives', default='skip',
                                 choices=['skip', 'keep', 'decompress'],
                                 help='How to handle compressed/archive files (default: skip)')
    recommend_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Auto rename mode
    auto_parser = subparsers.add_parser('auto', help='Automatically rename files based on AI suggestions')
    auto_parser.add_argument('directory', type=str, help='Directory or file to process')
    auto_parser.add_argument('--preset', default='default',
                            choices=['default', 'screenshot', 'document', 'photo', 'code'],
                            help='Processing preset to use')
    auto_parser.add_argument('--handle-archives', default='skip',
                            choices=['skip', 'keep', 'decompress'],
                            help='How to handle compressed/archive files (default: skip)')
    auto_parser.add_argument('--dry-run', action='store_true', help='Preview changes without renaming')
    auto_parser.add_argument('--confidence', type=float, default=0.5,
                            help='Minimum confidence threshold (0.0-1.0, default: 0.5)')
    auto_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Reorganize mode
    reorg_parser = subparsers.add_parser('reorganize', help='Completely reorganize folder structure')
    reorg_parser.add_argument('directory', type=str, help='Directory to reorganize')
    reorg_parser.add_argument('--preset', default='default',
                             choices=['default', 'screenshot', 'document', 'photo', 'code'],
                             help='Processing preset to use')
    reorg_parser.add_argument('--handle-archives', default='skip',
                             choices=['skip', 'keep', 'decompress'],
                             help='How to handle compressed/archive files (default: skip)')
    reorg_parser.add_argument('--dry-run', action='store_true', help='Preview changes without reorganizing')
    reorg_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Search mode
    search_parser = subparsers.add_parser('search', help='Search indexed files by content')
    search_parser.add_argument('query', type=str, help='Search query')
    search_parser.add_argument('--type', default='natural',
                              choices=['natural', 'semantic', 'exact', 'fuzzy', 'regex'],
                              help='Search type (default: natural)')
    search_parser.add_argument('--limit', type=int, default=20,
                              help='Maximum number of results (default: 20)')
    search_parser.add_argument('--content', action='store_true',
                              help='Include content preview in results')
    search_parser.add_argument('--file-types', type=str,
                              help='Filter by file types (comma-separated: pdf,docx,jpg)')
    search_parser.add_argument('--categories', type=str,
                              help='Filter by categories (comma-separated: invoice,screenshot)')
    search_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Index mode
    index_parser = subparsers.add_parser('index', help='Index a directory for search')
    index_parser.add_argument('directory', type=str, help='Directory to index')
    index_parser.add_argument('--no-recursive', action='store_true',
                             help='Do not index subdirectories')
    index_parser.add_argument('--monitor', action='store_true',
                             help='Monitor directory for changes')
    index_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Stats mode
    stats_parser = subparsers.add_parser('stats', help='Show search and indexing statistics')
    stats_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Server settings
    parser.add_argument('--api-url', default=API_BASE_URL, help='TidyBot API URL')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')

    # Enable auto-completion
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    # Setup console based on color preference
    global console
    if args.no_color:
        console = Console(no_color=True)

    # Initialize CLI
    cli = TidyBotCLI(api_url=args.api_url)

    # Check API connection
    if not cli.check_connection():
        console.print("[red]❌ Cannot connect to TidyBot API[/red]")
        console.print(f"Please ensure the backend is running at {args.api_url}")
        sys.exit(1)

    # Convert path to Path object
    path = Path(args.directory).expanduser().resolve()

    if not path.exists():
        console.print(f"[red]❌ Path not found: {path}[/red]")
        sys.exit(1)

    # Handle single file or directory
    if path.is_file():
        # For single file, use parent directory and filter to just this file
        directory = path.parent
        single_file = path
    else:
        directory = path
        single_file = None

    # Execute mode
    try:
        if args.mode == 'recommend':
            cli.recommend_mode(
                directory,
                preset=args.preset,
                handle_archives=args.handle_archives,
                verbose=args.verbose,
                single_file=single_file
            )
        elif args.mode == 'auto':
            cli.auto_rename_mode(
                directory,
                preset=args.preset,
                handle_archives=args.handle_archives,
                confidence_threshold=args.confidence,
                dry_run=args.dry_run,
                verbose=args.verbose,
                single_file=single_file
            )
        elif args.mode == 'reorganize':
            if single_file:
                console.print("[red]❌ Reorganize mode requires a directory, not a single file[/red]")
                sys.exit(1)
            console.print("[yellow]Reorganize mode not yet implemented in v2[/yellow]")
        elif args.mode == 'search':
            cli.search_mode(
                query=args.query,
                search_type=args.type,
                limit=args.limit,
                include_content=args.content,
                file_types=args.file_types,
                categories=args.categories,
                verbose=args.verbose
            )
        elif args.mode == 'index':
            index_directory = Path(args.directory).expanduser().resolve()
            cli.index_mode(
                directory=index_directory,
                recursive=not args.no_recursive,
                monitor=args.monitor,
                verbose=args.verbose
            )
        elif args.mode == 'stats':
            cli.stats_mode(verbose=args.verbose)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        if args.verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()