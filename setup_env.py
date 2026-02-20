import os

def create_env_file():
    print("=== Configuración Interactiva del Servidor MCP ===")
    print("Este script te ayudará a crear el archivo .env necesario.")
    
    api_key = input("\nPor favor, pega tu GOOGLE_API_KEY aquí: ").strip()
    
    if not api_key:
        print("Error: No ingresaste ninguna API Key. Abortando.")
        return

    env_content = f"""AI_ENABLED=true
AI_MODEL=gemini-1.5-flash
GOOGLE_API_KEY={api_key}
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("\n¡Archivo .env creado exitosamente!")
    print(f"Contenido:\n{env_content}")
    print("\nAhora puedes ejecutar el servidor con: python main.py")

if __name__ == "__main__":
    create_env_file()
