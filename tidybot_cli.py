#!/usr/bin/env python3
"""
TidyBot CLI - Intelligent file organization tool
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
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

    def process_file(self, file_path: Path) -> Dict:
        """Process a single file through the API"""
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/octet-stream')}
            response = self.session.post(f"{self.api_url}/files/process", files=files)
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"API error: {response.status_code}")

    def get_file_hash(self, file_path: Path) -> str:
        """Calculate file hash for duplicate detection"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[Path]:
        """Scan directory for all files"""
        files = []
        pattern = "**/*" if recursive else "*"
        for path in directory.glob(pattern):
            if path.is_file() and not path.name.startswith('.'):
                files.append(path)
        return files

    def recommend_mode(self, directory: Path, preset: str = "default", verbose: bool = False):
        """Recommendation mode - just show what would be done"""
        console.print(f"\n[bold cyan]📋 Scanning directory:[/bold cyan] {directory}")

        files = self.scan_directory(directory)
        console.print(f"Found {len(files)} files\n")

        if not files:
            console.print("[yellow]No files found to process[/yellow]")
            return

        recommendations = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing files...", total=len(files))

            for file_path in files:
                try:
                    result = self.process_file(file_path)
                    recommendations.append({
                        'original': file_path,
                        'suggested_name': result.get('suggested_name', file_path.name),
                        'confidence': result.get('confidence_score', 0),
                        'category': result.get('category', 'unknown'),
                        'organization': result.get('organization', {})
                    })
                except Exception as e:
                    if verbose:
                        console.print(f"[red]Error processing {file_path.name}: {e}[/red]")

                progress.update(task, advance=1)

        # Display recommendations
        table = Table(title="File Rename Recommendations", show_lines=True)
        table.add_column("Current Name", style="cyan", no_wrap=False)
        table.add_column("Suggested Name", style="green")
        table.add_column("Confidence", justify="center")
        table.add_column("Category", style="yellow")

        for rec in recommendations:
            confidence_color = "green" if rec['confidence'] > 0.8 else "yellow" if rec['confidence'] > 0.5 else "red"
            table.add_row(
                rec['original'].name,
                rec['suggested_name'],
                f"[{confidence_color}]{rec['confidence']*100:.0f}%[/{confidence_color}]",
                rec['category']
            )

        console.print(table)

        # Summary statistics
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Total files: {len(files)}")
        console.print(f"  Files needing rename: {sum(1 for r in recommendations if r['original'].name != r['suggested_name'])}")
        console.print(f"  Average confidence: {sum(r['confidence'] for r in recommendations)/len(recommendations)*100:.0f}%")

    def auto_rename_mode(self, directory: Path, preset: str = "default", dry_run: bool = False, verbose: bool = False):
        """Auto rename mode - rename files based on AI suggestions"""
        console.print(f"\n[bold cyan]🔄 Auto-rename mode:[/bold cyan] {directory}")

        files = self.scan_directory(directory)
        console.print(f"Found {len(files)} files\n")

        if not files:
            console.print("[yellow]No files found to process[/yellow]")
            return

        rename_operations = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing files...", total=len(files))

            for file_path in files:
                try:
                    result = self.process_file(file_path)
                    suggested_name = result.get('suggested_name', file_path.name)

                    if suggested_name != file_path.name and result.get('confidence_score', 0) > 0.5:
                        new_path = file_path.parent / suggested_name

                        # Handle duplicates
                        if new_path.exists():
                            base = new_path.stem
                            ext = new_path.suffix
                            counter = 1
                            while new_path.exists():
                                new_path = file_path.parent / f"{base}_{counter}{ext}"
                                counter += 1

                        rename_operations.append((file_path, new_path, result.get('confidence_score', 0)))

                except Exception as e:
                    if verbose:
                        console.print(f"[red]Error processing {file_path.name}: {e}[/red]")

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

    def reorganize_mode(self, directory: Path, preset: str = "default", dry_run: bool = False, verbose: bool = False):
        """Reorganize mode - complete restructuring with folder creation"""
        console.print(f"\n[bold cyan]🏗️ Reorganize mode:[/bold cyan] {directory}")

        files = self.scan_directory(directory)
        initial_count = len(files)
        console.print(f"Found {initial_count} files\n")

        if not files:
            console.print("[yellow]No files found to reorganize[/yellow]")
            return

        # Analyze all files and determine organization structure
        organization_plan = defaultdict(list)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing organization structure...", total=len(files))

            for file_path in files:
                try:
                    result = self.process_file(file_path)
                    suggested_name = result.get('suggested_name', file_path.name)
                    organization = result.get('organization', {})

                    # Determine folder structure based on file type and content
                    category = result.get('category', 'misc')
                    date_info = result.get('date_extracted')

                    # Create folder hierarchy
                    if category == 'screenshot':
                        folder = 'Screenshots'
                        if date_info:
                            year = datetime.fromisoformat(date_info).year
                            folder = f'Screenshots/{year}'
                    elif category == 'document':
                        doc_type = result.get('document_type', 'general')
                        folder = f'Documents/{doc_type.title()}'
                    elif category == 'image':
                        folder = 'Images'
                        if date_info:
                            year = datetime.fromisoformat(date_info).year
                            month = datetime.fromisoformat(date_info).strftime('%B')
                            folder = f'Images/{year}/{month}'
                    elif category == 'code':
                        language = result.get('language', 'misc')
                        folder = f'Code/{language.title()}'
                    else:
                        folder = 'Miscellaneous'

                    organization_plan[folder].append({
                        'original': file_path,
                        'new_name': suggested_name,
                        'confidence': result.get('confidence_score', 0)
                    })

                except Exception as e:
                    if verbose:
                        console.print(f"[red]Error processing {file_path.name}: {e}[/red]")
                    # Put failed files in misc
                    organization_plan['Miscellaneous'].append({
                        'original': file_path,
                        'new_name': file_path.name,
                        'confidence': 0
                    })

                progress.update(task, advance=1)

        # Display organization plan as tree
        tree = Tree("📁 [bold]Reorganization Plan[/bold]")

        total_moves = 0
        for folder, file_list in sorted(organization_plan.items()):
            folder_branch = tree.add(f"📂 {folder} ({len(file_list)} files)")
            for item in file_list[:5]:  # Show first 5 files
                folder_branch.add(f"📄 {item['new_name']}")
            if len(file_list) > 5:
                folder_branch.add(f"... and {len(file_list) - 5} more")
            total_moves += len(file_list)

        console.print(tree)

        # Verify file count
        console.print(f"\n[bold]File Count Verification:[/bold]")
        console.print(f"  Original files: {initial_count}")
        console.print(f"  Files to organize: {total_moves}")

        if initial_count != total_moves:
            console.print(f"[red]⚠️ WARNING: File count mismatch![/red]")
            return

        console.print(f"[green]✓ File count verified[/green]")

        if dry_run:
            console.print("\n[yellow]DRY RUN - No changes made[/yellow]")
        else:
            if Confirm.ask(f"\nReorganize {initial_count} files into {len(organization_plan)} folders?"):
                # Create folders and move files
                for folder, file_list in organization_plan.items():
                    target_dir = directory / folder
                    target_dir.mkdir(parents=True, exist_ok=True)

                    for item in file_list:
                        old_path = item['original']
                        new_path = target_dir / item['new_name']

                        # Handle duplicates
                        if new_path.exists():
                            base = new_path.stem
                            ext = new_path.suffix
                            counter = 1
                            while new_path.exists():
                                new_path = target_dir / f"{base}_{counter}{ext}"
                                counter += 1

                        shutil.move(str(old_path), str(new_path))

                        if verbose:
                            console.print(f"✅ Moved: {old_path.name} → {folder}/{new_path.name}")

                # Clean up empty directories
                for root, dirs, files in os.walk(directory, topdown=False):
                    for dir_name in dirs:
                        dir_path = Path(root) / dir_name
                        if not any(dir_path.iterdir()):
                            dir_path.rmdir()
                            if verbose:
                                console.print(f"🗑️ Removed empty folder: {dir_path}")

                # Final verification
                final_files = self.scan_directory(directory)
                final_count = len(final_files)

                console.print(f"\n[bold green]✨ Reorganization Complete![/bold green]")
                console.print(f"  Files reorganized: {initial_count}")
                console.print(f"  New folders created: {len(organization_plan)}")
                console.print(f"  Final file count: {final_count}")

                if initial_count != final_count:
                    console.print(f"[red]⚠️ WARNING: Final file count mismatch![/red]")
            else:
                console.print("[yellow]Operation cancelled[/yellow]")


def main():
    parser = argparse.ArgumentParser(
        description='TidyBot CLI - Intelligent file organization tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  tidybot recommend ~/Downloads                    # Show rename recommendations
  tidybot auto ~/Documents --dry-run              # Preview auto-rename without changes
  tidybot reorganize ~/Desktop --preset photo     # Reorganize photos
  tidybot auto ~/Screenshots --confidence 0.7     # Only rename high-confidence files
        '''
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode', required=True)

    # Recommend mode
    recommend_parser = subparsers.add_parser('recommend', help='Show rename recommendations without making changes')
    recommend_parser.add_argument('directory', type=str, help='Directory to analyze')
    recommend_parser.add_argument('--preset', default='default', choices=['default', 'screenshot', 'document', 'photo', 'code'],
                                 help='Processing preset to use')
    recommend_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Auto rename mode
    auto_parser = subparsers.add_parser('auto', help='Automatically rename files based on AI suggestions')
    auto_parser.add_argument('directory', type=str, help='Directory to process')
    auto_parser.add_argument('--preset', default='default', choices=['default', 'screenshot', 'document', 'photo', 'code'],
                            help='Processing preset to use')
    auto_parser.add_argument('--dry-run', action='store_true', help='Preview changes without renaming')
    auto_parser.add_argument('--confidence', type=float, default=0.5, help='Minimum confidence threshold (0.0-1.0)')
    auto_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

    # Reorganize mode
    reorg_parser = subparsers.add_parser('reorganize', help='Completely reorganize folder structure')
    reorg_parser.add_argument('directory', type=str, help='Directory to reorganize')
    reorg_parser.add_argument('--preset', default='default', choices=['default', 'screenshot', 'document', 'photo', 'code'],
                             help='Processing preset to use')
    reorg_parser.add_argument('--dry-run', action='store_true', help='Preview changes without reorganizing')
    reorg_parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output')

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

    # Convert directory to Path
    directory = Path(args.directory).expanduser().resolve()

    if not directory.exists():
        console.print(f"[red]❌ Directory not found: {directory}[/red]")
        sys.exit(1)

    if not directory.is_dir():
        console.print(f"[red]❌ Not a directory: {directory}[/red]")
        sys.exit(1)

    # Execute mode
    try:
        if args.mode == 'recommend':
            cli.recommend_mode(directory, preset=args.preset, verbose=args.verbose)
        elif args.mode == 'auto':
            cli.auto_rename_mode(directory, preset=args.preset, dry_run=args.dry_run, verbose=args.verbose)
        elif args.mode == 'reorganize':
            cli.reorganize_mode(directory, preset=args.preset, dry_run=args.dry_run, verbose=args.verbose)
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