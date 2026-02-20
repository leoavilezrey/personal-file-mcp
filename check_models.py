
import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    print("Using google-genai library")
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    print("Listing models...")
    # The new SDK might use different iteration
    try:
        # Try listing models if the method exists
        if hasattr(client, "models") and hasattr(client.models, "list"):
            for m in client.models.list():
                print(f"- {m.name}")
        else:
            print("client.models.list not found. Trying generic approach.")
    except Exception as e:
        print(f"Error listing models: {e}")

except ImportError:
    print("google-genai not found, trying google.generativeai")
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    for m in genai.list_models():
        print(f"- {m.name}")
