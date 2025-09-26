#!/bin/bash

echo "🚀 Installing TidyBot..."

# Check Python version
echo "🐍 Checking Python version..."
python3 --version

# Install TidyBot package
echo "📦 Installing TidyBot package..."
pip3 install -e .

# Install additional dependencies
echo "📦 Installing AI dependencies..."
pip3 install -r tidybot/ai_service/requirements.txt

# Install spaCy language model
echo "🌍 Installing spaCy language model..."
python3 -m spacy download en_core_web_sm

# Create convenient aliases
echo "🔗 Creating convenient aliases..."

# For bash
if [ -f ~/.bashrc ]; then
    echo "alias tidybot='python3 $(pwd)/tidybot_cli_v2.py'" >> ~/.bashrc
    echo "alias tidybot-server='python3 $(pwd)/scripts/main.py'" >> ~/.bashrc
    echo "✅ Bash aliases configured"
fi

# For zsh
if [ -f ~/.zshrc ]; then
    echo "alias tidybot='python3 $(pwd)/tidybot_cli_v2.py'" >> ~/.zshrc
    echo "alias tidybot-server='python3 $(pwd)/scripts/main.py'" >> ~/.zshrc
    echo "✅ Zsh aliases configured"
fi

echo ""
echo "✨ Installation complete!"
echo ""
echo "🚀 To start TidyBot:"
echo "  1. Start the server: tidybot-server"
echo "  2. Use the CLI: tidybot recommend ~/Downloads"
echo ""
echo "📋 Usage examples:"
echo "  tidybot recommend ~/Downloads              # Show recommendations"
echo "  tidybot auto ~/Documents --dry-run         # Preview auto-rename"
echo "  tidybot reorganize ~/Desktop               # Reorganize folder"
echo "  tidybot search \"invoice\"                   # Search files"
echo "  tidybot index ~/Documents                  # Index directory"
echo ""
echo "🔄 Please restart your terminal or run 'source ~/.bashrc' (or ~/.zshrc)"
echo ""
echo "📖 For more info, see CLI_README.md"