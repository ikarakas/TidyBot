#!/bin/bash

echo "🚀 Installing TidyBot CLI..."

# Install Python dependencies
echo "📦 Installing dependencies..."
pip3 install -r cli_requirements.txt

# Create symlink for easier access
echo "🔗 Creating tidybot command..."
if [ -d "/usr/local/bin" ]; then
    sudo ln -sf "$(pwd)/tidybot_cli.py" /usr/local/bin/tidybot
    echo "✅ Created 'tidybot' command"
else
    echo "⚠️  /usr/local/bin not found, creating alias instead"
    echo "alias tidybot='$(pwd)/tidybot_cli.py'" >> ~/.bashrc
    echo "alias tidybot='$(pwd)/tidybot_cli.py'" >> ~/.zshrc 2>/dev/null
fi

# Setup bash completion
echo "🎯 Setting up auto-completion..."

# For bash
if [ -f ~/.bashrc ]; then
    echo 'eval "$(register-python-argcomplete tidybot)"' >> ~/.bashrc
    echo "✅ Bash auto-completion configured"
fi

# For zsh
if [ -f ~/.zshrc ]; then
    echo 'eval "$(register-python-argcomplete tidybot)"' >> ~/.zshrc
    echo "✅ Zsh auto-completion configured"
fi

echo ""
echo "✨ Installation complete!"
echo ""
echo "📋 Usage examples:"
echo "  tidybot recommend ~/Downloads              # Show recommendations"
echo "  tidybot auto ~/Documents --dry-run         # Preview auto-rename"
echo "  tidybot reorganize ~/Desktop               # Reorganize folder"
echo ""
echo "🔄 Please restart your terminal or run 'source ~/.bashrc' (or ~/.zshrc)"
echo ""
echo "📝 For auto-completion to work, press TAB after typing 'tidybot '"