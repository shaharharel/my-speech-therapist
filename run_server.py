#!/usr/bin/env python3
"""
Simple server runner for development
"""

import os
import sys
import subprocess

def main():
    """Start the development server"""
    # Ensure we're in the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    
    print("🚀 Starting Lihi's Assistant Development Server...")
    print("📍 URL: http://localhost:9000")
    print("⏹️  Press Ctrl+C to stop")
    print("=" * 50)
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "src.api.app:app", 
            "--reload", 
            "--host", "0.0.0.0", 
            "--port", "9000"
        ])
    except KeyboardInterrupt:
        print("\n👋 Server stopped!")

if __name__ == "__main__":
    main()