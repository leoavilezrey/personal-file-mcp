import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "files.db")

def agregar_metadata_manual():
    print("=== Agregar Metadata Manual a un Archivo ===")
    
    # 1. Buscar el archivo primero
    busqueda = input("\nIntroduce parte del nombre del archivo a buscar: ")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT id, filename, path FROM files WHERE filename LIKE ?", (f"%{busqueda}%",))
    resultados = c.fetchall()
    
    if not resultados:
        print("No se encontraron archivos con ese nombre.")
        conn.close()
        return
        
    print("\nArchivos encontrados:")
    for idx, row in enumerate(resultados):
        print(f"[{idx}] {row['filename']} -> {row['path']}")
        
    # 2. Seleccionar archivo
    try:
        seleccion = int(input("\nElige el número del archivo (ej. 0): "))
        if seleccion < 0 or seleccion >= len(resultados):
            print("Selección inválida.")
            conn.close()
            return
            
        archivo_elegido = resultados[seleccion]
        file_id = archivo_elegido['id']
        print(f"\nSeleccionaste: {archivo_elegido['filename']}")
        
    except ValueError:
        print("Debes introducir un número.")
        conn.close()
        return

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

    # 3. Ingresar descripción manual (Opcional)
    print("\n✏️ Escribe una descripción (o presiona ENTER para omitir/mantener la actual):")
    descripcion = input("> ").strip()
    
    # 4. Ingresar etiquetas (tags) (Opcional)
    print("\n✏️ Escribe nuevas etiquetas separadas por comas (o presiona ENTER para omitir):")
    tags_string = input("> ")
    tags = [tag.strip() for tag in tags_string.split(",") if tag.strip()]
    
    # 5. Guardar en base de datos
    try:
        # Guardar descripción solo si el usuario escribió algo
        if descripcion:
            if desc_actual:
                c.execute("UPDATE descriptions SET description = ?, source = 'Manual' WHERE file_id = ?", (descripcion, file_id))
            else:
                c.execute("INSERT INTO descriptions (file_id, description, source, model_used) VALUES (?, ?, 'Manual', 'None')", 
                          (file_id, descripcion))
            
        # Guardar tags solo si el usuario escribió algo
        if tags:
            for tag in tags:
                # Revisar que no esté duplicado
                c.execute("SELECT id FROM metadata WHERE file_id=? AND key='tag' AND value=?", (file_id, tag))
                if not c.fetchone():
                    c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, 'tag', ?)", (file_id, tag))
                
        if descripcion or tags:
            conn.commit()
            print("\n✅ ¡Metadata guardada correctamente!")
        else:
            print("\nNo se hicieron cambios.")
            
    except Exception as e:
        print(f"\n❌ Error al guardar en la base de datos: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    while True:
        agregar_metadata_manual()
        continuar = input("\n¿Deseas agregar metadata a otro archivo? (s/n): ")
        if continuar.lower() != 's':
            break
