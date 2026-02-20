import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "files.db")

def buscar_archivos_avanzado():
    print("=== Búsqueda Avanzada de Archivos ===")
    print("Deja en blanco (presiona ENTER) los campos que no quieras usar para filtrar.\n")
    
    nombre = input("1. Parte del nombre (ej. reporte): ").strip()
    ubicacion = input("2. Parte de la ubicación/ruta (ej. Documents): ").strip()
    tag = input("3. Etiqueta exacta o parcial (ej. universidad): ").strip()
    descripcion = input("4. Palabra en la descripción (ej. resumen): ").strip()
    tipo = input("5. Tipo de archivo (ej. pdf o .pdf): ").strip()
    dias = input("6. Modificado en los últimos N días (ej. 7, 30): ").strip()
    sin_info = input("7. ¿Mostrar SOLO archivos SIN descripción ni etiquetas? (s / ENTER para no): ").strip().lower()

    # Construir la consulta SQL dinámicamente
    query = """
        SELECT DISTINCT f.id, f.filename, f.path, f.size, d.description, d.source, f.modified_at
        FROM files f
        LEFT JOIN descriptions d ON f.id = d.file_id
        LEFT JOIN metadata m ON f.id = m.file_id AND m.key = 'tag'
        WHERE 1=1
    """
    params = []

    if nombre:
        query += " AND f.filename LIKE ?"
        params.append(f"%{nombre}%")
        
    if ubicacion:
        query += " AND f.path LIKE ?"
        params.append(f"%{ubicacion}%")
        
    if tag:
        query += " AND m.value LIKE ?"
        params.append(f"%{tag}%")
        
    if descripcion:
        query += " AND d.description LIKE ?"
        params.append(f"%{descripcion}%")
        
    if tipo:
        if not tipo.startswith('.'):
            tipo = '.' + tipo
        query += " AND lower(f.extension) = ?"
        params.append(tipo.lower())
        
    if dias.isdigit():
        query += f" AND f.modified_at >= datetime('now', '-{dias} days')"
        
    if sin_info == 's':
        # Filtramos donde no haya descripciones ni etiquetas
        query += " AND d.id IS NULL AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')"

    query += " ORDER BY f.modified_at DESC LIMIT 50"

    print("\n⏳ Buscando...")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    try:
        c.execute(query, params)
        resultados = c.fetchall()
        
        if not resultados:
            print("\n❌ No se encontraron archivos con esos criterios.")
            return
            
        print(f"\n✅ Se encontraron {len(resultados)} archivo(s) (mostrando máximo 50):\n")
        print("=" * 60)
        
        for idx, row in enumerate(resultados, 1):
            size_kb = row['size'] / 1024
            fecha = row['modified_at'][:10] if row['modified_at'] else "Desconocida"
            
            print(f"[{idx}] {row['filename']} ({size_kb:.1f} KB) - {fecha}")
            print(f"Ruta: {row['path']}")
            
            if row['description']:
                print(f"Desc ({row['source']}): {row['description']}")
                
            # Buscar etiquetas para este archivo
            c.execute("SELECT value FROM metadata WHERE file_id = ? AND key = 'tag'", (row['id'],))
            tags = [t['value'] for t in c.fetchall()]
            if tags:
                print(f"Tags: {', '.join(tags)}")
            
            print("-" * 60)
            
        # Opciones interactivas de edición
        print("\n¿Deseas agregar/editar una descripción o etiqueta a alguno de estos archivos?")
        seleccion = input("Escribe el número del archivo (ej. 1) o presiona ENTER para omitir: ")
        
        if seleccion.strip().isdigit():
            idx = int(seleccion) - 1
            if 0 <= idx < len(resultados):
                archivo_elegido = resultados[idx]
                file_id = archivo_elegido['id']
                
                print(f"\n--- Editando: {archivo_elegido['filename']} ---")
                
                # Obtener y mostrar metadata actual
                c.execute("SELECT value FROM metadata WHERE file_id = ? AND key = 'tag'", (file_id,))
                tags_actuales = [t['value'] for t in c.fetchall()]
                
                print("\n--- Metadatos Actuales ---")
                if archivo_elegido['description']:
                    print(f"Descripción ({archivo_elegido['source']}): {archivo_elegido['description']}")
                else:
                    print("Descripción: (Ninguna)")
                    
                if tags_actuales:
                    print(f"Etiquetas: {', '.join(tags_actuales)}")
                else:
                    print("Etiquetas: (Ninguna)")
                print("--------------------------")
                
                # Ingresar descripción
                print("\n✏️ Escribe una nueva descripción (o presiona ENTER para omitir/mantener):")
                nueva_desc = input("> ").strip()
                
                # Ingresar etiquetas
                print("\n✏️ Escribe nuevas etiquetas separadas por comas (o presiona ENTER para omitir):")
                tags_string = input("> ")
                nuevos_tags = [t.strip() for t in tags_string.split(",") if t.strip()]
                
                cambios = False
                
                if nueva_desc:
                    if archivo_elegido['description']:
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
                    print("✅ ¡Metadata guardada exitosamente!")
                else:
                    print("Sin cambios.")
            else:
                print("⚠️ Número inválido.")
            
    except sqlite3.Error as e:
        print(f"⚠️ Error de base de datos: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    while True:
        buscar_archivos_avanzado()
        continuar = input("\n¿Realizar otra búsqueda? (s/n): ")
        if continuar.lower() != 's':
            break
