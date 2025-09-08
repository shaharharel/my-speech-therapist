"""
Database maintenance utilities
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def backup_database(backup_suffix: str = None) -> str:
    """Create a backup of the current database"""
    db_path = 'db/lihi_assistant.db'
    
    if not os.path.exists(db_path):
        return None
        
    if backup_suffix is None:
        backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    backup_path = f"{db_path}.backup_{backup_suffix}"
    shutil.copy2(db_path, backup_path)
    
    logger.info(f"Database backed up to: {backup_path}")
    return backup_path

def clear_corrupted_database() -> bool:
    """Clear corrupted database and create fresh start"""
    db_path = 'db/lihi_assistant.db'
    
    try:
        # Test if database is readable
        if os.path.exists(db_path):
            backup_path = backup_database("corrupted")
            
            # Remove database files
            for suffix in ['', '-shm', '-wal']:
                file_path = f"{db_path}{suffix}"
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
            logger.info("Database cleared successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return False
    
    return True

def check_database_health() -> dict:
    """Check database health and return status"""
    db_path = 'db/lihi_assistant.db'
    
    if not os.path.exists(db_path):
        return {"status": "missing", "message": "Database file not found"}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check table existence
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        if not tables:
            conn.close()
            return {"status": "empty", "message": "Database exists but is empty"}
        
        # Check record count
        cursor.execute("SELECT COUNT(*) FROM checkpoints")
        count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "healthy", 
            "message": f"Database healthy with {count} records",
            "record_count": count
        }
        
    except Exception as e:
        return {"status": "corrupted", "message": f"Database error: {str(e)}"}

if __name__ == "__main__":
    # Command line interface for maintenance
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python database_maintenance.py [check|backup|clear]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        status = check_database_health()
        print(f"Status: {status['status']}")
        print(f"Message: {status['message']}")
        
    elif command == "backup":
        backup_path = backup_database()
        if backup_path:
            print(f"Backup created: {backup_path}")
        else:
            print("No database to backup")
            
    elif command == "clear":
        if clear_corrupted_database():
            print("Database cleared successfully")
        else:
            print("Failed to clear database")
            
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)