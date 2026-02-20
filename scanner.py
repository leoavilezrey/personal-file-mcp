import os
import mimetypes
from pathlib import Path
from datetime import datetime
from database import get_db_connection

def scan_directory(directory_path: str):
    """
    Scans the given directory recursively and adds/updates files in the database.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    root_dir = Path(directory_path).resolve()
    if not root_dir.exists():
        print(f"Directory not found: {directory_path}")
        return

    print(f"Scanning directory: {root_dir}")
    
    count_new = 0
    count_updated = 0
    
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden directories (optional but good practice) or specific ones
        # dirs[:] = [d for d in dirs if not d.startswith('.')] 
        
        for file in files:
            file_path = Path(root) / file
            
            # Skip hidden files
            # if file.startswith('.'): continue
            
            try:
                stats = file_path.stat()
                size = stats.st_size
                created_at = datetime.fromtimestamp(stats.st_ctime)
                modified_at = datetime.fromtimestamp(stats.st_mtime)
                extension = file_path.suffix.lower()
                
                # Check if file exists
                c.execute("SELECT id FROM files WHERE path = ?", (str(file_path),))
                existing = c.fetchone()
                
                if existing:
                    # Update existing
                    c.execute('''
                        UPDATE files 
                        SET size=?, modified_at=?, created_at=?
                        WHERE id=?
                    ''', (size, modified_at, created_at, existing['id']))
                    count_updated += 1
                else:
                    c.execute('''
                        INSERT INTO files (path, filename, extension, size, created_at, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (str(file_path), file, extension, size, created_at, modified_at))
                    count_new += 1
                    
            except PermissionError:
                print(f"Permission denied: {file_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                
    conn.commit()
    conn.close()
    print(f"Scan complete. New: {count_new}, Updated: {count_updated}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        scan_directory(sys.argv[1])
    else:
        print("Usage: python scanner.py <directory_path>")
