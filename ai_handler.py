import sys
import os
import json
import warnings

# Suppress warnings that corrupt JSON-RPC stdout
warnings.simplefilter("ignore")

from pathlib import Path

# Try importing the new library first
try:
    from google import genai
except ImportError:
    # If not found, try the old one but warn to stderr (not stdout)
    try:
        import google.generativeai as genai
    except ImportError:
        sys.stderr.write("Error: google-genai library not found. Please run: pip install google-genai\n")
        genai = None

class AIHandler:
    def __init__(self, enabled=False, model="gemini-3.1-pro-preview"):
        self.enabled = enabled
        self.model_name = model
        # Fix for attribute error: main.py accesses ai.model, so we must alias it
        self.model = model 
        self.client = None
        
        if self.enabled:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                sys.stderr.write("Warning: AI_ENABLED is true but GOOGLE_API_KEY is missing.\n")
                self.enabled = False
            elif genai:
                try:
                    self.client = genai.Client(api_key=api_key)
                except Exception as e:
                    sys.stderr.write(f"Failed to initialize Gemini client: {e}\n")
                    self.enabled = False

    def _read_file_snippet(self, file_path: str, max_chars=2000) -> str:
        """Reads a snippet of the file to send to the AI."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(max_chars)
        except Exception:
            return "(Binary or unreadable content)"

    def generate_description(self, file_path: str) -> str:
        if not self.enabled or not self.client:
            return "AI generation disabled or client not initialized."
        
        snippet = self._read_file_snippet(file_path)
        filename = Path(file_path).name
        
        prompt = f"""
        Analyze the following file information and provide a concise 1-sentence description of what this file likely contains.
        
        Filename: {filename}
        Content Snippet:
        {snippet}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            return f"Error generating description: {str(e)}"

    def generate_tags(self, file_path: str) -> list:
        if not self.enabled or not self.client:
            return []
        
        snippet = self._read_file_snippet(file_path)
        filename = Path(file_path).name
        
        prompt = f"""
        Generate exactly 5 relevant tags for the following file. 
        Return ONLY a JSON array of strings, e.g. ["tag1", "tag2"].
        
        Filename: {filename}
        Content Snippet:
        {snippet}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            text = response.text.strip()
            # Clean up markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text.rsplit("\n", 1)[0]
            
            return json.loads(text)
        except Exception as e:
            sys.stderr.write(f"Error generating tags: {str(e)}\n")
            return ["error_generating_tags", str(e)]

def get_ai_handler():
    enabled = os.getenv("AI_ENABLED", "false").lower() == "true"
    model = os.getenv("AI_MODEL", "gemini-1.5-flash")
    return AIHandler(enabled=enabled, model=model)
