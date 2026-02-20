import sys
import os

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Verifying imports...")
try:
    import mcp
    import sqlite3
    import dotenv
    print("Imports successful.")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

print("Verifying modules...")
try:
    from database import init_db
    from scanner import scan_directory
    from ai_handler import get_ai_handler
    from main import mcp as mcp_inst
    print("Modules loaded successfully.")
except Exception as e:
    print(f"Module load failed: {e}")
    sys.exit(1)

print("Scanning for files just to test DB...")
try:
    init_db()
    # Scan the current directory itself as a test
    scan_directory(os.path.dirname(os.path.abspath(__file__)))
    print("DB Initialized and scan ran.")
except Exception as e:
    print(f"DB/Scan failed: {e}")
    sys.exit(1)

print("Verification complete.")
