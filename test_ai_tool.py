
import os
import sys
from unittest.mock import MagicMock

# MOCK FastMCP to return the original function when used as a decorator
# This must be done BEFORE importing main
mock_mcp_instance = MagicMock()
def mock_tool():
    def decorator(func):
        return func
    return decorator
mock_mcp_instance.tool = mock_tool

# Patch the module
sys.modules["mcp.server.fastmcp"] = MagicMock()
sys.modules["mcp.server.fastmcp"].FastMCP = MagicMock(return_value=mock_mcp_instance)

# Add current dir to path
sys.path.append(os.getcwd())

# Import main
try:
    from main import generate_ai_metadata, scan_files
except Exception as e:
    print(f"Error importing main: {e}")
    sys.exit(1)

# Ensure database has files
db_path = "files.db"
if not os.path.exists(db_path):
    print("Database not found. Scanning scanning current dir...")
    print(scan_files(os.getcwd()))

# Find a file to test
import sqlite3
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT path FROM files LIMIT 1")
row = c.fetchone()
conn.close()

if not row:
    print("No files in database to test.")
    sys.exit(1)

test_file = row[0]
print(f"Testing AI metadata generation for: {test_file}")

# Run the tool function
try:
    result = generate_ai_metadata(test_file)
    print("\n--- RESULT ---")
    print(result)
except Exception as e:
    print("\n--- CRASHED ---")
    print(e)
    import traceback
    traceback.print_exc()
