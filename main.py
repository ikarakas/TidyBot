#!/usr/bin/env python3
"""
TidyBot - AI-Powered File Organization System
Main entry point for the application
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Main entry point for TidyBot"""
    print("🤖 TidyBot - AI File Organization System")
    print("="*50)

    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        sys.exit(1)

    # Change to AI service directory
    service_path = Path(__file__).parent / "tidybot" / "ai_service"

    if not service_path.exists():
        print("❌ TidyBot service not found")
        sys.exit(1)

    print("✅ Starting TidyBot server...")
    print("📍 Server: http://localhost:11007")
    print("📖 API Docs: http://localhost:11007/docs")
    print("Press Ctrl+C to stop")
    print("="*50)

    # Start the server
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "11007"
        ], cwd=service_path)
    except KeyboardInterrupt:
        print("\n✅ TidyBot stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()