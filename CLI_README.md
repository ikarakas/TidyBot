# TidyBot CLI - Intelligent File Organization Tool

A powerful command-line interface for intelligent file organization using AI. TidyBot analyzes your files and provides smart naming suggestions, automatic renaming, and complete folder reorganization capabilities.

## Features

- **🔍 Recommendation Mode**: Preview AI-suggested file names without making changes
- **🤖 Auto Rename Mode**: Automatically rename files based on AI analysis
- **🏗️ Reorganize Mode**: Complete folder restructuring with intelligent categorization
- **✨ Auto-completion**: Bash/Zsh tab completion support
- **🎨 Rich Output**: Beautiful colored tables and progress indicators
- **🔒 Safe Operations**: Dry-run mode, confirmation prompts, file count verification

## Installation

```bash
# Install dependencies
pip3 install argcomplete rich requests

# Make executable
chmod +x tidybot_cli.py

# Optional: Create system-wide command
sudo ln -sf $(pwd)/tidybot_cli.py /usr/local/bin/tidybot

# Setup auto-completion
eval "$(register-python-argcomplete tidybot)"
```

## Usage

### Three Operation Modes

#### 1. Recommendation Mode
Shows what changes would be made without modifying any files:

```bash
tidybot recommend ~/Downloads
tidybot recommend ~/Documents --preset document --verbose
```

#### 2. Auto Rename Mode
Automatically renames files based on AI suggestions:

```bash
tidybot auto ~/Screenshots                  # Rename with default settings
tidybot auto ~/Photos --dry-run            # Preview without changes
tidybot auto ~/Downloads --confidence 0.7  # Only rename high-confidence files
```

#### 3. Reorganize Mode
Complete folder restructuring - creates folders, moves files, cleans up empty directories:

```bash
tidybot reorganize ~/Desktop              # Full reorganization
tidybot reorganize ~/Downloads --dry-run  # Preview structure
tidybot reorganize ~/Documents --preset document
```

## Presets

Available presets optimize processing for different file types:

- `default` - General-purpose processing
- `screenshot` - Optimized for screenshots
- `document` - Focus on document organization
- `photo` - Photo library organization
- `code` - Source code file organization

## Examples

### Organize Downloads Folder
```bash
# See recommendations first
tidybot recommend ~/Downloads

# Auto-rename files
tidybot auto ~/Downloads --dry-run
tidybot auto ~/Downloads  # Execute if happy

# Full reorganization
tidybot reorganize ~/Downloads
```

### Process Screenshots
```bash
tidybot auto ~/Screenshots --preset screenshot
```

### Organize Documents with High Confidence
```bash
tidybot auto ~/Documents --preset document --confidence 0.8
```

## How It Works

### Recommendation Mode
1. Scans directory for all files
2. Sends each file to AI for analysis
3. Displays suggested names in a table
4. Shows confidence scores and categories
5. No files are modified

### Auto Rename Mode
1. Analyzes all files in directory
2. Filters by confidence threshold
3. Shows rename plan
4. Asks for confirmation
5. Renames files, handling duplicates

### Reorganize Mode
1. Deep analysis of all files
2. Creates intelligent folder structure:
   - Screenshots → Screenshots/YYYY/
   - Documents → Documents/Type/
   - Images → Images/YYYY/Month/
   - Code → Code/Language/
3. Verifies file count integrity
4. Moves files to new structure
5. Cleans up empty folders

## Safety Features

- **Dry Run**: Preview all changes with `--dry-run`
- **Confirmations**: Always asks before making changes
- **File Count Verification**: Ensures no files are lost during reorganization
- **Duplicate Handling**: Automatically handles naming conflicts
- **Confidence Thresholds**: Only rename files above confidence level

## Options

```bash
Global Options:
  --api-url URL      Custom API endpoint (default: http://127.0.0.1:11007)
  --no-color         Disable colored output
  -h, --help         Show help message

Mode-Specific Options:
  --preset NAME      Processing preset to use
  --dry-run          Preview changes without executing
  --confidence N     Minimum confidence (0.0-1.0, default: 0.5)
  -v, --verbose      Show detailed processing information
```

## Requirements

- Python 3.7+
- TidyBot backend server running on port 11007
- Dependencies: requests, rich, argcomplete

## Troubleshooting

### API Connection Error
```
❌ Cannot connect to TidyBot API
```
**Solution**: Ensure the backend is running:
```bash
cd tidybot/ai_service
source venv/bin/activate
python -m uvicorn app.main:app --reload --port 11007
```

### Low Confidence Scores
Empty or corrupt files may receive low confidence scores. The AI needs actual content to analyze effectively.

### Auto-completion Not Working
Run: `eval "$(register-python-argcomplete tidybot)"` in your shell or add it to ~/.bashrc or ~/.zshrc

## Advanced Usage

### Custom API Endpoint
```bash
tidybot --api-url http://192.168.1.100:11007 recommend ~/Files
```

### Batch Processing
```bash
for dir in ~/Downloads ~/Desktop ~/Documents; do
    tidybot recommend "$dir" --verbose
done
```

### Scheduled Organization
Add to crontab for weekly organization:
```bash
0 2 * * 0 /usr/local/bin/tidybot reorganize ~/Downloads --preset default
```

## Notes

- The tool respects hidden files (starting with `.`) and skips them
- Package contents (.app bundles) are not traversed
- Original file modification times are preserved
- Network drives may have slower processing times

## License

Part of the TidyBot project - AI-powered file organization system.