from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os
import sys

# DEBUG LOGGING - CRITICAL FOR DIAGNOSIS
debug_file = os.path.join(os.path.dirname(__file__), "debug_start.log")
with open(debug_file, "a") as f:
    f.write(f"Starting server... Python: {sys.executable}\n")

# Load environment variables from .env file (Absolute Path)
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

from scanner import scan_directory
from database import get_db_connection
from ai_handler import get_ai_handler

# Initialize FastMCP
mcp = FastMCP("Personal File Server")

@mcp.tool()
def scan_files(path: str) -> str:
    """Scans a directory and updates the database with file information. Args: path (absolute path to directory)"""
    if not os.path.exists(path):
        return f"Error: Path {path} does not exist."
    
    try:
        scan_directory(path)
        return f"Successfully scanned {path}"
    except Exception as e:
        return f"Error scanning {path}: {str(e)}"

@mcp.tool()
def search_files(query: str) -> str:
    """Searches for files in the database by filename (SQL LIKE). Args: query (search term)"""
    conn = get_db_connection()
    c = conn.cursor()
    search_term = f"%{query}%"
    c.execute("SELECT path, filename, size FROM files WHERE filename LIKE ?", (search_term,))
    results = c.fetchall()
    conn.close()
    
    if not results:
        return "No files found."
    
    return "\n".join([f"{r['filename']} ({r['path']}) - {r['size']} bytes" for r in results])

@mcp.tool()
def get_file_metadata(path: str) -> str:
    """Retrieves metadata and description for a specific file. Args: path (full file path)"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE path = ?", (path,))
    file_record = c.fetchone()
    
    if not file_record:
        conn.close()
        return "File not found in database. Try scanning the directory first."
    
    # Get metadata
    c.execute("SELECT key, value FROM metadata WHERE file_id = ?", (file_record['id'],))
    metadata = {row['key']: row['value'] for row in c.fetchall()}
    
    # Get descriptions
    c.execute("SELECT description, source FROM descriptions WHERE file_id = ?", (file_record['id'],))
    descriptions = [f"[{row['source']}] {row['description']}" for row in c.fetchall()]
    
    conn.close()
    
    output = [
        f"File: {file_record['filename']}",
        f"Path: {file_record['path']}",
        f"Size: {file_record['size']} bytes",
        f"Created: {file_record['created_at']}",
        "Metadata:",
        *[f"  {k}: {v}" for k, v in metadata.items()],
        "Descriptions:",
        *[f"  {d}" for d in descriptions]
    ]
    return "\n".join(output)

@mcp.tool()
def generate_ai_metadata(path: str) -> str:
    """Generates AI description and tags for a file (if AI is enabled). Args: path (full file path)"""
    ai = get_ai_handler()
    if not ai.enabled:
        return "AI mode is disabled. Set AI_ENABLED=true environment variable to enable."
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM files WHERE path = ?", (path,))
    file_record = c.fetchone()
    
    if not file_record:
        conn.close()
        return "File not found in database. Try scanning directory first."
    
    # Generate content (mock or real)
    try:
        description = ai.generate_description(path)
        tags = ai.generate_tags(path)
        
        # Save to DB
        c.execute("SELECT id FROM descriptions WHERE file_id = ? AND source = 'AI'", (file_record['id'],))
        existing_desc = c.fetchone()
        
        if existing_desc:
            c.execute("UPDATE descriptions SET description = ?, model_used = ? WHERE id = ?",
                      (description, ai.model, existing_desc['id']))
        else:
            c.execute("INSERT INTO descriptions (file_id, description, source, model_used) VALUES (?, ?, ?, ?)",
                      (file_record['id'], description, "AI", ai.model))
        
        for tag in tags:
            # Check for existing tag to avoid duplicates?
            c.execute("SELECT id FROM metadata WHERE file_id=? AND key=? AND value=?", (file_record['id'], "tag", tag))
            if not c.fetchone():
                c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, ?, ?)",
                        (file_record['id'], "tag", tag))
            
        conn.commit()
        conn.close()
        
        return f"AI metadata generated: {description} | Tags: {tags}"
    except Exception as e:
        conn.close()
        return f"Error generating metadata: {str(e)}"

@mcp.tool()
def query_database(query: str) -> str:
    """Executes a READ-ONLY SQL query against the files database. Use this for counting, aggregation, or filtering.
    Allowed: SELECT. Blocked: INSERT, UPDATE, DELETE, DROP.
    Example: 'SELECT COUNT(*) FROM files' or 'SELECT SUM(size) FROM files'
    Args: query (SQL string)"""
    
    # 1. Basic security check (prevent modification)
    normalized_query = query.strip().upper()
    if not normalized_query.startswith("SELECT"):
        return "Error: Only SELECT queries are allowed for safety."
        
    prevent_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
    for kw in prevent_keywords:
        if kw in normalized_query:
            return f"Error: Query contains forbidden keyword '{kw}'. Read-only access allowed."

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(query)
        results = c.fetchall()
        conn.close()
        
        if not results:
            return "Query executed successfully but returned no results."
            
        # Format results converting Row objects to dicts
        import json
        return json.dumps([dict(row) for row in results], indent=2, default=str)
        
    except Exception as e:
        return f"Database Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()
