#!/usr/bin/env python3
"""
Main entry point for Lihi's Assistant
"""

import sys
import os

# Add the project root to Python path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def main():
    """Main entry point - start the web interface"""
    print("\n🌟 Starting Lihi's Assistant...")
    print("=" * 50)
    
    # Import and run the web start script
    try:
        from src.scripts.start_web import main as start_web
        start_web()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()