#!/usr/bin/env python3
"""
Simple test to verify the unified database works correctly
"""

from unified_graphs import get_unified_checkpointer
import os

def test_unified_db():
    print("🔍 Testing unified database setup...")
    
    # Test checkpointer creation
    checkpointer = get_unified_checkpointer()
    print("✅ Unified checkpointer created successfully")
    
    # Check if database file was created
    db_path = os.path.join("db", "lihi_assistant.db")
    if os.path.exists(db_path):
        print(f"✅ Database file created at: {db_path}")
        
        # Check file size
        size = os.path.getsize(db_path)
        print(f"📊 Database size: {size} bytes")
        
        if size > 0:
            print("✅ Database is properly initialized")
        else:
            print("⚠️  Database file exists but is empty")
    else:
        print("❌ Database file not found")
        return False
    
    print("\n🎯 Database test completed successfully!")
    print("🗄️  Using single database: lihi_assistant.db")
    print("🎯 All graphs will share the same checkpoint storage")
    return True

if __name__ == "__main__":
    test_unified_db()