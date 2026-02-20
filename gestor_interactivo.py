import sqlite3
import os
import math
import sys
import msvcrt
import datetime
from pathlib import Path
from scanner import scan_directory

db_path = os.path.join(os.path.dirname(__file__), "files.db")

def get_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def mostrar_estadisticas():
    conn = get_connection()
    c = conn.cursor()
    
    # Cantidad de registros (archivos)
    c.execute("SELECT count(*) as total FROM files")
    total_files = c.fetchone()['total']
    
    # Cuántas etiquetas únicas tiene la base de datos
    c.execute("SELECT count(DISTINCT value) as total_tags FROM metadata WHERE key='tag'")
    total_tags = c.fetchone()['total_tags']
    
    # Cuántos registros NO tienen ni etiqueta ni descripción
    c.execute("""
        SELECT count(*) as total FROM files f 
        LEFT JOIN descriptions d ON f.id = d.file_id 
        WHERE d.id IS NULL AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')
    """)
    sin_nada = c.fetchone()['total']
    
    # Archivos sin descripcion
    c.execute("SELECT count(*) as total FROM files f LEFT JOIN descriptions d ON f.id = d.file_id WHERE d.id IS NULL")
    sin_desc = c.fetchone()['total']

    # Archivos sin etiquetas
    c.execute("SELECT count(*) as total FROM files WHERE id NOT IN (SELECT file_id FROM metadata WHERE key='tag')")
    sin_tags = c.fetchone()['total']

    print("\n" + "="*50)
    print("📊 ESTADÍSTICAS DE LA BASE DE DATOS")
    print("="*50)
    print(f"📁 Total de archivos registrados: {total_files}")
    print(f"🏷️  Total de etiquetas (tags) únicas: {total_tags}")
    print("-" * 50)
    print(f"📝 Registros sin descripción: {sin_desc}")
    print(f"🏷️  Registros sin etiquetas: {sin_tags}")
    print(f"⚠️  Registros completamente VACÍOS de info: {sin_nada}")
    print("="*50)
    opcion = input("\nPresiona ENTER para volver al menú o escribe 'q' para salir: ").strip().lower()
    conn.close()
    if opcion == 'q':
        print("\n¡Hasta luego! Cerrando gestor...")
        sys.exit(0)

def explorar_archivos():
    print("\n" + "-"*50)
    print("🔍 FILTROS DE BÚSQUEDA")
    print("Deja en blanco (presiona ENTER) para no filtrar por esa opción.")
    print("-" * 50)
    
    ubicacion = input("📁 Buscar por texto en ruta/URL (ej. Documents o youtube): ").strip()
    
    # Obtener etiquetas para el autocompletado del buscador
    conn_temp = get_connection()
    c_temp = conn_temp.cursor()
    c_temp.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
    todas_las_etiquetas = [row['value'] for row in c_temp.fetchall()]
    conn_temp.close()
    
    tag = ingresar_tags_interactivo(
        todas_las_etiquetas, 
        mensaje_prompt="🏷️  Etiqueta específica a buscar (deja en blanco y presiona ENTER para omitir):",
        modo_unico=True # Una bandera porque el buscador originalmente solo buscaba de a un tag
    )
    # Limpiar exhaustivamente comas y espacios en blanco que deja el autocompletado
    tag = tag.replace(",", "").strip()
    
    dias = input("📅 Periodo de tiempo: modificados últimos N días (ej. 30): ").strip()
    tipo_archivo = input("📄 Tipo (ej. pdf, docx, jpg) o escribe 'web' para ver enlaces: ").strip()
    filtro_metadata = input("⚠️ ¿Ver SOLO los registros SIN descripción/etiquetas? (s/n): ").strip().lower()
    
    query = """
    SELECT f.id, f.filename, f.path, f.size, f.resource_type, f.modified_at, d.description 
    FROM files f
    LEFT JOIN descriptions d ON f.id = d.file_id
    WHERE 1=1
    """
    params = []
    
    # Aplicar filtros
    if ubicacion:
        query += " AND f.path LIKE ?"
        params.append(f"%{ubicacion}%")
    if tag:
        query += " AND f.id IN (SELECT file_id FROM metadata WHERE key='tag' AND value LIKE ?)"
        params.append(f"%{tag}%")
    if dias.isdigit():
        query += f" AND f.modified_at >= datetime('now', '-{dias} days')"
    if tipo_archivo:
        if tipo_archivo.lower() in ('web', 'link', 'enlace', 'nube', 'url'):
            query += " AND f.resource_type = 'web'"
        else:
            if not tipo_archivo.startswith('.'):
                tipo_archivo = '.' + tipo_archivo
            query += " AND lower(f.extension) = ?"
            params.append(tipo_archivo.lower())
    if filtro_metadata == 's':
        query += " AND d.id IS NULL AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')"
        
    query += " ORDER BY f.modified_at DESC"
    
    conn = get_connection()
    c = conn.cursor()
    c.execute(query, params)
    resultados = c.fetchall()
    
    if not resultados:
        print("\n❌ No se encontraron registros usando estos filtros.")
        conn.close()
        return

    # Paginación (20 a 30 registros) seleccionable
    print("\n¿Cuántos registros quieres ver por página? (Por defecto: 20)")
    pag_size_input = input("Cantidad: ").strip()
    page_size = int(pag_size_input) if pag_size_input.isdigit() else 20
    
    total_records = len(resultados)
    total_pages = math.ceil(total_records / page_size)
    current_page = 1
    
    while True:
        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_records)
        page_results = resultados[start_idx:end_idx]
        
        print("\n" + "="*90)
        print(f"📄 RESULTADOS - Página {current_page}/{total_pages} (Registros {start_idx+1} al {end_idx} de {total_records} en total)")
        print("="*90)
        print(f"{'Nº':<4} | {'Nombre del Archivo':<45} | {'Fecha':<12} | {'Datos'}")
        print("-" * 90)
        
        for i, row in enumerate(page_results):
            global_idx = start_idx + i + 1
            fecha = row['modified_at'][:10] if row['modified_at'] else "N/A"
            filename = row['filename'][:42] + "..." if len(row['filename']) > 45 else row['filename']
            
            # Comprobar si tiene tags
            c.execute("SELECT 1 FROM metadata WHERE file_id=? AND key='tag' LIMIT 1", (row['id'],))
            tiene_tags = c.fetchone() is not None
            
            if row['description'] or tiene_tags:
                estado = "Tiene Info"
            else:
                estado = "Vacío"
                
            print(f"{global_idx:<4} | {filename:<45} | {fecha:<12} | {estado}")
            
        print("-" * 90)
        print("\nOpciones de Paginación y Edición:")
        print("[Número] Seleccionar un registro para ver/editar su información")
        print("[ S ] Siguiente página (+ registros)")
        print("[ A ] Página anterior  (- registros)")
        print("[ Q ] Salir de la consulta al menú principal")
        
        opcion = input("\nElige una opción: ").strip().lower()
        
        if opcion == 'q':
            break
        elif opcion == 's':
            if current_page < total_pages: current_page += 1
            else: print("\n⚠️ Ya estás en la última página. No hay más registros adelante.")
        elif opcion == 'a':
            if current_page > 1: current_page -= 1
            else: print("\n⚠️ Ya estás en la primera página.")
        elif opcion.isdigit():
            idx = int(opcion)
            if 1 <= idx <= total_records:
                # El usuario eligió editar un registro
                editar_registro(conn, resultados[idx-1]['id'])
                # Al volver, recargar la consulta para actualizar visualmente la tabla
                c.execute(query, params)
                resultados = c.fetchall()
            else:
                print("\n⚠️ Número fuera de los límites de búsqueda.")
        else:
            print("\n⚠️ Opción no válida.")
            
    conn.close()

def ingresar_tags_interactivo(todas_las_etiquetas, mensaje_prompt=None, modo_unico=False):
    print("\n" + "-"*50)
    if mensaje_prompt:
        print(mensaje_prompt)
    else:
        print("Escribe tus etiquetas separadas por coma (,).")
        
    print("A medida que escribas, verás sugerencias.")
    print("Presiona TAB para usar la primera sugerencia, o ENTER cuando termines.")
    print("-" * 50)
    
    entrada = ""
    while True:
        partes = entrada.split(",")
        palabra_actual = partes[-1].lstrip()
        
        sugerencias = []
        # Mostrar sugerencias solo si hay una palabra y no termina en coma aun
        if palabra_actual and not entrada.endswith(","):
            sugerencias = [t for t in todas_las_etiquetas if t.lower().startswith(palabra_actual.lower())]
            
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        texto_mostrar = f"> {entrada}"
        if sugerencias:
            texto_mostrar += f"  (Sugeridas: {' | '.join(sugerencias[:5])})"
            
        sys.stdout.write(texto_mostrar)
        sys.stdout.flush()
        
        try:
            char = msvcrt.getwch()
            if char in ('\x00', '\xe0'): # Control codes skip
                msvcrt.getwch()
                continue
        except Exception:
            continue
            
        if char in ('\r', '\n'):
            print()
            return entrada
        elif char == '\x03': # Ctrl+C
            raise KeyboardInterrupt
        elif char == '\b': # Backspace
            if len(entrada) > 0:
                entrada = entrada[:-1]
        elif char == '\t': # Tab autocomplete
            if sugerencias:
                prefijo = " " if len(partes) > 1 else ""
                partes[-1] = prefijo + sugerencias[0]
                entrada = ",".join(partes) + ", "
        else:
            entrada += char

def editar_registro(conn, file_id):
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    archivo = c.fetchone()
    
    c.execute("SELECT description, source FROM descriptions WHERE file_id = ?", (file_id,))
    desc_row = c.fetchone()
    
    c.execute("SELECT value FROM metadata WHERE file_id = ? AND key = 'tag'", (file_id,))
    tags = [row['value'] for row in c.fetchall()]
    
    while True:
        print("\n" + "#"*70)
        print("🔍 DETALLES ESPECÍFICOS DEL REGISTRO")
        print("#"*70)
        print(f"Nombre:    {archivo['filename']}")
        if dict(archivo).get('resource_type') == 'web':
            print(f"Tipo/Ruta: ENLACE WEB: {archivo['path']}")
            print(f"Tamaño:    N/A (Web)")
        else:
            print(f"Carpeta:   {archivo['path']}")
            size_kb = (archivo['size'] / 1024) if archivo['size'] else 0
            print(f"Tamaño:    {size_kb:.1f} KB")
        print(f"Fecha mod: {archivo['modified_at']}")
        print("-" * 70)
        
        desc = desc_row['description'] if desc_row else "⚠️ (SIN DESCRIPCIÓN)"
        fuente = f" (Fuente: {desc_row['source']})" if desc_row else ""
        print(f"Descripción{fuente}: \n   -> {desc}")
        print("\nEtiquetas:")
        print(f"   -> {', '.join(tags) if tags else '⚠️ (SIN ETIQUETAS)'}")
        print("#"*70)
        
        print("\n¿Qué quieres hacer con este registro?")
        print("1. 📝 Agregar o Modificar Descripción")
        print("2. 🏷️  Agregar Etiquetas (Tags)")
        print("3. 🗑️  Borrar todas las Etiquetas")
        print("4. 🔙 Volver a los resultados de búsqueda")
        
        opc = input("> ").strip()
        
        if opc == '1':
            nueva_desc = input("\nEscribe la nueva descripción: ").strip()
            if nueva_desc:
                if desc_row:
                    c.execute("UPDATE descriptions SET description=?, source='Manual' WHERE file_id=?", (nueva_desc, file_id))
                else:
                    c.execute("INSERT INTO descriptions (file_id, description, source, model_used) VALUES (?, ?, 'Manual', 'None')", (file_id, nueva_desc))
                conn.commit()
                desc_row = {'description': nueva_desc, 'source': 'Manual'} # Actualiza variable para vista
                print("✅ ¡Descripción guardada con éxito!")
                
        elif opc == '2':
            # Primero, buscar y mostrar todas las etiquetas únicas existentes (sin ocultar los errores largos)
            c.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
            todas_las_etiquetas = [row['value'] for row in c.fetchall()]
            
            print("\n" + "-"*50)
            print("🏷️  ETIQUETAS EXISTENTES EN TU BASE DE DATOS:")
            if todas_las_etiquetas:
                # Agruparlas en bloques y truncar visualmente las muy largas para no destruir la pantalla,
                # pero mostrando que existen para que el usuario pueda detectarlas y borrarlas.
                etiquetas_visuales = [t[:35] + "..." if len(t) > 35 else t for t in todas_las_etiquetas]
                for i in range(0, len(etiquetas_visuales), 5):
                    print(" | ".join(etiquetas_visuales[i:i+5]))
            else:
                print("(Aún no has creado ninguna etiqueta en toda la base de datos)")
            print("-" * 50)
            
            nuevos_tags = ingresar_tags_interactivo(todas_las_etiquetas)
            
            if nuevos_tags:
                lista_tags = [t.strip() for t in nuevos_tags.split(",") if t.strip()]
                for t in lista_tags:
                    if t not in tags:
                        c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, 'tag', ?)", (file_id, t))
                        tags.append(t)
                conn.commit()
                print("✅ ¡Etiquetas guardadas con éxito!")
                
        elif opc == '3':
            confirm = input("\n⚠️ ¿Estás seguro de que quieres limpiar las etiquetas de este archivo? (s/n): ").strip().lower()
            if confirm == 's':
                c.execute("DELETE FROM metadata WHERE file_id=? AND key='tag'", (file_id,))
                conn.commit()
                tags = []
                print("🗑️ Etiquetas eliminadas.")
                
        elif opc == '4':
            break

def procesar_carpeta_manual(conn):
    ruta = input("\nIntroduce la ruta completa de la carpeta que quieres revisar/escanear:\n> ").strip()
    if not ruta: return
    ruta_abs = os.path.abspath(ruta)
    if not os.path.exists(ruta_abs):
        print(f"❌ Error: La ruta '{ruta_abs}' no existe.")
        return

    print("=== Herramienta de Agregar/Etiquetar por Carpeta (Manual) ===")
    print(f"\nEscaneando '{ruta_abs}' para actualizar base de datos...")
    scan_directory(ruta_abs)
    
    c = conn.cursor()
    c.execute("SELECT id, filename, path, size FROM files WHERE path LIKE ? AND resource_type='local' ORDER BY filename ASC", (f"{ruta_abs}%",))
    archivos = c.fetchall()
    
    if not archivos:
        print("No se encontraron archivos en la ruta.")
        return
        
    print(f"\nPaso 2: Se van a revisar {len(archivos)} archivos.")
    print("Escribe los datos y presiona ENTER. Escribe 'salir' para detener el proceso.\n")
    
    c.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
    todas_las_etiquetas = [row['value'] for row in c.fetchall()]

    for idx, row in enumerate(archivos, 1):
        file_id = row['id']
        size_kb = (row['size'] / 1024) if row['size'] else 0
        print(f"\n[{idx}/{len(archivos)}]: {row['filename']} ({size_kb:.1f} KB)")
        
        c.execute("SELECT description, source FROM descriptions WHERE file_id=?", (file_id,))
        desc = c.fetchone()
        c.execute("SELECT value FROM metadata WHERE file_id=? AND key='tag'", (file_id,))
        tags_act = [t['value'] for t in c.fetchall()]
        
        print("--- Metadatos actuales ---")
        if desc: print(f"Desc: {desc['description']}")
        if tags_act: print(f"Tags: {', '.join(tags_act)}")
        print("--------------------------")
        
        nueva_desc = input("✏️ Escribe una descripción (ENTER para omitir, 'salir' para terminar):\n> ").strip()
        if nueva_desc.lower() == 'salir': break
        
        nuevos_tags = ingresar_tags_interactivo(todas_las_etiquetas, mensaje_prompt="✏️ Escribe etiquetas separadas por comas (o ENTER para omitir):", modo_unico=False)
        
        cambios = False
        if nueva_desc:
            if desc:
                c.execute("UPDATE descriptions SET description=?, source='Manual' WHERE file_id=?", (nueva_desc, file_id))
            else:
                c.execute("INSERT INTO descriptions(file_id, description, source, model_used) VALUES(?, ?, 'Manual', 'None')", (file_id, nueva_desc))
            cambios = True
            
        if nuevos_tags:
            lista = [t.strip() for t in nuevos_tags.split(",") if t.strip()]
            for t in lista:
                if t not in tags_act:
                    c.execute("INSERT INTO metadata(file_id, key, value) VALUES(?, 'tag', ?)", (file_id, t))
                    if t not in todas_las_etiquetas: todas_las_etiquetas.append(t)
            cambios = True
            
        if cambios:
            conn.commit()
            print("✅ Guardado.")
        else:
            print("⏭️ Saltado sin cambios.")

def agregar_enlace_web(conn):
    print("\n" + "="*50)
    print("🌐 AGREGAR ENLACE WEB O NUBE")
    print("="*50)
    
    url = input("Pega el enlace web (ej. https://drive.google...): ").strip()
    if not url: return
    
    filename = input("Nombre o título de este enlace: ").strip()
    if not filename: return
    
    c = conn.cursor()
    c.execute("SELECT id FROM files WHERE path=?", (url,))
    if c.fetchone():
        print("⚠️ Este enlace ya está registrado.")
        return
        
    ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    c.execute("INSERT INTO files (path, filename, extension, resource_type, created_at, modified_at) VALUES (?, ?, '.link', 'web', ?, ?)",
              (url, filename, ahora, ahora))
    conn.commit()
    file_id = c.lastrowid
    
    print(f"\n✅ Enlace '{filename}' indexado a tu base de datos.")
    print("¿Deseas agregarle etiquetas y descripción de inmediato? (s/n)")
    if input("> ").strip().lower() == 's':
        editar_registro(conn, file_id)

def menu_principal():
    while True:
        print("\n" + "="*50)
        print("🚀 GESTOR VISUAL DE BASE DE DATOS")
        print("="*50)
        print("1. 📊 Ver Cantidades y Estadísticas del Proyecto")
        print("2. 🔎 Buscar, Paginar y Editar Registros")
        print("3. 📂 Escanear y Etiquetar Carpeta Manualmente")
        print("4. 🌐 Guardar Nuevo Enlace Web (Nube/Internet)")
        print("5. ❌ Salir")
        print("="*50)
        
        opcion = input("Selecciona una opción (1-5): ").strip()
        
        if opcion == '1':
            mostrar_estadisticas()
        elif opcion == '2':
            explorar_archivos()
        elif opcion == '3':
            conn = get_connection()
            procesar_carpeta_manual(conn)
            conn.close()
        elif opcion == '4':
            conn = get_connection()
            agregar_enlace_web(conn)
            conn.close()
        elif opcion == '5':
            print("¡Hasta luego! Cerrando gestor...")
            break
        else:
            print("⚠️ Opción inválida. Intenta del 1 al 5.")

if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\nOperación cancelada. Saliendo...")
