import sqlite3
import os
import sys
from pathlib import Path
from database import get_db_connection
from scanner import scan_directory

def procesar_carpeta_manual(ruta_carpeta):
    """
    Escanea la carpeta para agregar archivos a la BD y luego itera 
    sobre ellos uno por uno para que el usuario los etiquete manualmente.
    """
    # 1. Asegurarse de que exista la carpeta
    ruta_abs = os.path.abspath(ruta_carpeta)
    if not os.path.exists(ruta_abs):
        print(f"❌ Error: La ruta '{ruta_abs}' no existe.")
        return

    print("=== Herramienta de Agregar/Etiquetar por Carpeta (Manual) ===")
    print(f"\nPaso 1: Escaneando '{ruta_abs}' para actualizar la base de datos...")
    # Esto asegura que los archivos estén en la tabla `files`
    scan_directory(ruta_abs)
    print("Escaneo rápido completado.\n")

    # 2. Obtener la lista de archivos de esa carpeta desde la BD
    conn = get_db_connection()
    c = conn.cursor()
    
    # Buscamos todos los archivos cuya ruta comience con la ruta de la carpeta proporcionada
    search_path = f"{ruta_abs}%"
    c.execute("""
        SELECT id, filename, path, size 
        FROM files 
        WHERE path LIKE ? 
        ORDER BY filename ASC
    """, (search_path,))
    
    archivos = c.fetchall()
    
    if not archivos:
        print("No se encontraron archivos en la base de datos para esta ruta.")
        conn.close()
        return

    print(f"Paso 2: Se van a revisar {len(archivos)} archivos de esta carpeta.\n")
    print("INSTRUCCIONES: Escribe los datos e presiona ENTER. Si no quieres")
    print("agregar descripción o etiquetas a un archivo, simplemente presiona")
    print("ENTER para saltarlo o escribe 'salir' para detener el proceso.\n")
    print("-" * 60)

    for idx, (file_id, filename, filepath, size) in enumerate(archivos, 1):
        size_kb = size / 1024
        print(f"\nArchivo [{idx}/{len(archivos)}]: {filename} ({size_kb:.1f} KB)")
        print(f"Ruta: {filepath}")

        # Mostrar metadata actual
        c.execute("SELECT description, source FROM descriptions WHERE file_id = ?", (file_id,))
        desc_actual = c.fetchone()
        
        c.execute("SELECT value FROM metadata WHERE file_id = ? AND key = 'tag'", (file_id,))
        tags_actuales = [row['value'] for row in c.fetchall()]

        print("\n--- Metadatos Actuales ---")
        if desc_actual:
            print(f"Descripción ({desc_actual['source']}): {desc_actual['description']}")
        else:
            print("Descripción: (Ninguna)")
            
        if tags_actuales:
            print(f"Etiquetas: {', '.join(tags_actuales)}")
        else:
            print("Etiquetas: (Ninguna)")
        print("--------------------------")

        # Ingresar nueva descripción
        print("✏️ Escribe una descripción (ENTER para omitir, 'salir' para terminar):")
        nueva_desc = input("> ").strip()
        
        if nueva_desc.lower() == 'salir':
            print("\nProceso detenido por el usuario.")
            break

        # Ingresar etiquetas
        print("✏️ Escribe nuevas etiquetas separadas por comas (ENTER para omitir):")
        tags_string = input("> ")
        nuevos_tags = [t.strip() for t in tags_string.split(",") if t.strip()]

        cambios = False
        
        # Guardar cambios
        try:
            if nueva_desc:
                if desc_actual:
                    c.execute("UPDATE descriptions SET description = ?, source = 'Manual' WHERE file_id = ?", (nueva_desc, file_id))
                else:
                    c.execute("INSERT INTO descriptions (file_id, description, source, model_used) VALUES (?, ?, 'Manual', 'None')", 
                              (file_id, nueva_desc))
                cambios = True
                
            if nuevos_tags:
                for tag in nuevos_tags:
                    c.execute("SELECT id FROM metadata WHERE file_id=? AND key='tag' AND value=?", (file_id, tag))
                    if not c.fetchone():
                        c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, 'tag', ?)", (file_id, tag))
                cambios = True
                
            if cambios:
                conn.commit()
                print("✅ Metadata guardada.")
            else:
                print("⏭️ Saltado (sin cambios).")
                
        except Exception as e:
            print(f"❌ Error guardando. Detalle: {e}")
            
        print("-" * 60)

    conn.close()
    print("\n✅ Revisión de la carpeta finalizada.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
         ruta = sys.argv[1]
    else:
         ruta = input("Introduce la ruta completa de la carpeta que quieres revisar:\n> ")
         
    procesar_carpeta_manual(ruta)
