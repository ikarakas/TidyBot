# TidyBot macOS Application

A modern, native macOS application for intelligent file management powered by AI.

## Features

### 🎨 Modern SwiftUI Interface
- **Native macOS Design**: Built with SwiftUI for a seamless Mac experience
- **Drag & Drop**: Simply drag files into the app to process them
- **Dark Mode Support**: Automatically adapts to system appearance
- **Visual Effects**: Beautiful blur effects and smooth animations

### 📁 File Processing
- **Batch Processing**: Process multiple files simultaneously
- **Real-time Progress**: Monitor processing status with live updates
- **Confidence Scores**: See AI confidence levels for suggested names
- **Alternative Suggestions**: Get multiple naming options for each file

### 🎯 Smart Organization
- **Preset Management**: Create and customize naming presets
- **Flexible Rules**: Configure organization strategies
- **History Tracking**: View and search through processing history
- **Undo Support**: Revert changes when needed

## Requirements

- macOS 14.0 (Sonoma) or later
- Xcode 15.0 or later
- TidyBot AI Service running on port 11007

## Installation

1. Open the Xcode project:
```bash
cd tidybot/frontend/TidyBot
open TidyBot.xcodeproj
```

2. Build and run the project (⌘+R)

## Usage

### Starting the Backend

Before using the app, ensure the AI service is running:

```bash
cd tidybot/ai_service
python -m uvicorn app.main:app --port 11007 --reload
```

### Processing Files

1. **Drag & Drop**: Drag files directly into the app window
2. **Browse**: Click "Browse Files" to select files
3. **Configure**: Choose a preset or customize settings
4. **Process**: Click "Process All" to start batch processing

### Keyboard Shortcuts

- `⌘+O` - Open files
- `⌘+B` - Start batch processing
- `⌘+,` - Open preferences
- `⌘+R` - Refresh connection

## Architecture

The app follows MVVM architecture:

```
TidyBot/
├── Models/          # Data models
├── Views/           # SwiftUI views
├── ViewModels/      # View models and app state
├── Services/        # API client and services
├── Components/      # Reusable UI components
└── Utils/           # Utility functions
```

## Configuration

Settings are stored in UserDefaults and include:

- **Server URL**: Backend service endpoint
- **Processing Options**: OCR, object detection, captioning
- **Organization Rules**: File organization preferences
- **UI Preferences**: Appearance, notifications, sounds

## Development

### Building for Release

1. Select "Product" → "Archive" in Xcode
2. Choose "Distribute App"
3. Select "Direct Distribution"
4. Sign with Developer ID

### Code Signing

Ensure you have:
- Valid Apple Developer account
- Developer ID Application certificate
- Proper entitlements configured

## Troubleshooting

### Connection Issues
- Verify the backend is running on port 11007
- Check server URL in Settings → Advanced
- Use "Test Connection" to diagnose issues

### Performance
- Adjust batch size in Settings → Processing
- Enable/disable AI features as needed
- Clear cache if experiencing slowdowns

## License

MIT License - See LICENSE file for details