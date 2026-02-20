import os
import sqlite3
import time
from database import get_db_connection
from scanner import scan_directory
from main import generate_ai_metadata
from ai_handler import get_ai_handler

def analyze_directory(directory_path: str, max_files: int = 0):
    """
    Escanea un directorio y luego pide a la IA que genere metadata 
    para los archivos que aún no la tienen.
    """
    # 1. Primero, asegúrate de que todos los archivos estén indexados
    print(f"Paso 1: Escaneando directorio: {directory_path} (buscando archivos nuevos/modificados)...")
    scan_directory(directory_path)
    print("Escaneo rápido completado.\n")

    # 2. Verificar que la IA esté habilitada
    ai = get_ai_handler()
    if not ai.enabled:
        print("❌ ERROR: La IA está desactivada. Revisa tu archivo .env (AI_ENABLED=true y GOOGLE_API_KEY correcta).")
        return

    # 3. Buscar archivos en la base de datos de este directorio que NO tengan descripción
    conn = get_db_connection()
    c = conn.cursor()
    
    # Busca archivos que empiecen con la ruta dada y que NO estén en la tabla de descripciones
    query_files = """
        SELECT f.id, f.path, f.filename, f.size 
        FROM files f
        LEFT JOIN descriptions d ON f.id = d.file_id
        WHERE f.path LIKE ? AND d.id IS NULL
        ORDER BY f.size ASC -- Opcional: Procesar primero los archivos más pequeños
    """
    
    # Añadimos % al final para buscar todos los subdirectorios
    search_path = f"{os.path.abspath(directory_path)}%"
    c.execute(query_files, (search_path,))
    archivos_pendientes = c.fetchall()
    conn.close()

    total_pendientes = len(archivos_pendientes)
    print(f"Paso 2: Se encontraron {total_pendientes} archivos sin metadata de IA.")
    
    if total_pendientes == 0:
        print("¡Todo está actualizado! No hay archivos pendientes por analizar en esta ruta.")
        return

    # Limitar si el usuario lo pidió
    if max_files > 0:
        print(f"Limites activados: Solo se procesarán los primeros {max_files} archivos.")
        archivos_pendientes = archivos_pendientes[:max_files]

    # 4. Procesar cada archivo pendiente con la IA
    print("\nIniciando análisis con IA (esto podría tomar tiempo)...")
    print("-" * 50)
    
    for idx, (file_id, path, filename, size) in enumerate(archivos_pendientes, 1):
        # Ignorar archivos muy grandes (más de 1MB por ejemplo), ya que solo vas a leer un extracto
        print(f"[{idx}/{len(archivos_pendientes)}] Analizando: {filename} ({size} bytes)...")
        
        try:
             # Llamar a la herramienta de MCP que ya tienes que hace el trabajo
             resultado = generate_ai_metadata(path)
             
             if "Error" in resultado or "disabled" in resultado:
                 print(f"  ⚠️ Error: {resultado}")
                 # Si es un error de cuota (429), podrías querer pausar más o detener
                 if "429" in resultado:
                     print("  ⚠️ Límite de API alcanzado. Esperando 1 minuto antes del próximo...")
                     time.sleep(60) 
             else:
                 print(f"  ✅ {resultado}")
                 
             # Respetar los límites de la API de Google (incluso en la versión de pago es buena práctica)
             # Esperar 2 segundos entre solicitudes
             time.sleep(2) 
             
        except Exception as e:
             print(f"  ❌ Excepción inesperada: {str(e)}")

    print("-" * 50)
    print("Análisis masivo finalizado.")

if __name__ == "__main__":
    import sys
    
    # Pedir al usuario confirmación o parámetros
    ruta_objetivo = "C:\\Users\\DELL\\Documents"
    
    # Puedes pasar parámetros por consola, ej: python analizador_masivo.py C:\Users\ruta 10
    if len(sys.argv) > 1:
        ruta_objetivo = sys.argv[1]
    
    limite = 0
    if len(sys.argv) > 2:
        try:
            limite = int(sys.argv[2])
        except ValueError:
            pass

    print(f"Iniciando analizador en: {ruta_objetivo}")
    analyze_directory(ruta_objetivo, limite)
