#!/usr/bin/env python3
"""
Start the Lihi's Assistant web interface
"""

import sys
import subprocess
import webbrowser
import time
import os

def main():
    print("\n🌟 Starting Lihi's Assistant Web Interface...")
    print("=" * 50)
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'prefix'):
        print("⚠️  Warning: No virtual environment detected.")
        print("   Consider activating a virtual environment first.")
        print()
    
    # Change to project root directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    os.chdir(project_root)
    
    # Set environment variables if .env file exists
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded environment variables from .env file")
    else:
        print("⚠️  No .env file found. Make sure OPENAI_API_KEY is set.")
    
    # Dependencies should be installed manually before running
    
    print("\n🚀 Starting FastAPI server...")
    print("   Access the application at: http://localhost:7777")
    print("   Press Ctrl+C to stop the server")
    print("=" * 50 + "\n")

    # Open browser after a short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:7777")
    
    import threading
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start the server
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "src.api.app:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "7777"
        ])
    except KeyboardInterrupt:
        print("\n\n✋ Server stopped by user")
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()