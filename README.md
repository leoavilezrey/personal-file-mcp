# Personal File MCP Server

A Model Context Protocol (MCP) server for managing and searching personal files.

## Features
- **File Scanning**: Recursively indexes files into a local SQLite database.
- **Search**: Fast file search by name.
- **Metadata**: Extracts basic file stats (size, dates) and allows AI-generated descriptions.
- **AI Integration**: Optional toggle to use an AI model for generating file summaries and tags.

## Setup

1. **Environment**:
   The project uses a virtual environment `venv`. Activate it before running:
   - Windows: `.\venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables** (Optional):
   Create a `.env` file or set variables:
   - `AI_ENABLED=true` (to enable AI features)
   - `AI_MODEL=llama3` (or your preferred model)

## Usage

### Running the Server
```bash
python main.py
```

### Tools
- `scan_files(path)`: Index a directory.
- `search_files(query)`: Search for files.
- `get_file_metadata(path)`: Get full details.
- `generate_ai_metadata(path)`: Generate AI description (requires AI enabled).

## Configuration
The database is stored in `files.db` in the same directory.
