import sqlite3
import os
import math
import sys
import msvcrt
import datetime
import zipfile
import webbrowser
from pathlib import Path
from scanner import scan_directory
from gestor_apps import menu_apps
from relaciones import init_relaciones, mostrar_relaciones, menu_relaciones

# Forzar UTF-8 para que los emojis funcionen en cualquier terminal de Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

db_path = os.path.join(os.path.dirname(__file__), "files.db")

def get_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def abrir_recurso(archivo):
    """Logica unificada para abrir archivos locales o enlaces web."""
    try:
        path = archivo['path']
        r_type = dict(archivo).get('resource_type')
        if r_type == 'web':
            print(f"🚀 Abriendo enlace web: {path}")
            webbrowser.open(path)
        else:
            if os.path.exists(path):
                print(f"🚀 Abriendo archivo local: {path}")
                os.startfile(path)
            else:
                print(f"❌ Error: El archivo ya no existe en la ruta guardada ({path}).")
    except Exception as e:
        print(f"❌ Error al intentar abrir: {e}")

def mostrar_estadisticas():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT count(*) as total FROM files")
    total_files = c.fetchone()['total']
    c.execute("SELECT count(DISTINCT value) as total_tags FROM metadata WHERE key='tag'")
    total_tags = c.fetchone()['total_tags']
    c.execute("""
        SELECT count(*) as total FROM files f 
        LEFT JOIN descriptions d ON f.id = d.file_id 
        WHERE d.id IS NULL AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')
    """)
    sin_nada = c.fetchone()['total']
    c.execute("SELECT count(*) as total FROM files f LEFT JOIN descriptions d ON f.id = d.file_id WHERE d.id IS NULL")
    sin_desc = c.fetchone()['total']
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
        sys.exit(0)

def explorar_archivos():
    print("\n" + "-"*50)
    print("🔍 FILTROS DE BÚSQUEDA")
    print("Deja en blanco para no filtrar por esa opción.")
    print("-" * 50)
    ubicacion = input("📁 Buscar por texto en ruta/URL: ").strip()
    conn_temp = get_connection()
    c_temp = conn_temp.cursor()
    c_temp.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
    todas_las_etiquetas = [row['value'] for row in c_temp.fetchall()]
    conn_temp.close()
    tag = ingresar_tags_interactivo(todas_las_etiquetas, mensaje_prompt="🏷️ Etiqueta específica a buscar:", modo_unico=True)
    tag = tag.replace(",", "").strip()
    dias = input("📅 Periodo de tiempo (últimos N días): ").strip()
    tipo_archivo = input("📄 Tipo (pdf, docx, etc) o 'web': ").strip()
    filtro_metadata = input("⚠️ ¿Ver SOLO los registros SIN descripción/etiquetas? (s/n): ").strip().lower()
    
    query = """
    SELECT f.id, f.filename, f.path, f.size, f.resource_type, f.modified_at, d.description 
    FROM files f
    LEFT JOIN descriptions d ON f.id = d.file_id
    WHERE 1=1
    """
    params = []
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
            if not tipo_archivo.startswith('.'): tipo_archivo = '.' + tipo_archivo
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
        print("\n❌ No se encontraron registros.")
        conn.close()
        return

    page_size = 20
    total_records = len(resultados)
    total_pages = math.ceil(total_records / page_size)
    current_page = 1
    
    while True:
        start_idx = (current_page - 1) * page_size
        end_idx = min(start_idx + page_size, total_records)
        page_results = resultados[start_idx:end_idx]
        
        print("\n" + "="*90)
        print(f"📄 RESULTADOS - Página {current_page}/{total_pages} ({start_idx+1} al {end_idx} de {total_records})")
        print("="*90)
        print(f"{'Nº':<4} | {'ID BD':<6} | {'Nombre del Archivo':<42} | {'Fecha':<12} | {'Info'}")
        print("-" * 90)
        
        for i, row in enumerate(page_results):
            global_idx = start_idx + i + 1
            fecha = row['modified_at'][:10] if row['modified_at'] else "N/A"
            nombre = row['filename'][:39] + "..." if len(row['filename']) > 42 else row['filename']
            c.execute("SELECT 1 FROM metadata WHERE file_id=? AND key='tag' LIMIT 1", (row['id'],))
            tiene_tags = c.fetchone() is not None
            estado = "[+]" if (row['description'] or tiene_tags) else "[ ]"
            print(f"{global_idx:<4} | {row['id']:<6} | {nombre:<42} | {fecha:<12} | {estado}")
            
        print("-" * 90)
        print("\n[Número] Detalles | [O + Nº] Abrir | [S/A] Pág | [Q] Menú")
        opcion = input("\nElige una opción: ").strip().lower()
        if opcion == 'q': break
        elif opcion == 's' and current_page < total_pages: current_page += 1
        elif opcion == 'a' and current_page > 1: current_page -= 1
        elif opcion.startswith('o') and opcion[1:].isdigit():
            idx = int(opcion[1:])
            if 1 <= idx <= total_records: abrir_recurso(resultados[idx-1])
        elif opcion.isdigit():
            idx = int(opcion)
            if 1 <= idx <= total_records:
                editar_registro(conn, resultados[idx-1]['id'])
                c.execute(query, params)
                resultados = c.fetchall()
    conn.close()

def ingresar_tags_interactivo(todas_las_etiquetas, mensaje_prompt=None, modo_unico=False):
    if mensaje_prompt: print(mensaje_prompt)
    entrada = ""
    while True:
        partes = entrada.split(",")
        palabra_actual = partes[-1].lstrip()
        sugerencias = [t for t in todas_las_etiquetas if t.lower().startswith(palabra_actual.lower())] if palabra_actual and not entrada.endswith(",") else []
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        texto_mostrar = f"> {entrada}"
        if sugerencias: texto_mostrar += f" (Sugerencias: {' | '.join(sugerencias[:5])})"
        sys.stdout.write(texto_mostrar)
        sys.stdout.flush()
        char = msvcrt.getwch()
        if char in ('\r', '\n'): print(); return entrada
        elif char == '\x03': raise KeyboardInterrupt
        elif char == '\b': entrada = entrada[:-1] if len(entrada) > 0 else ""
        elif char == '\t':
            if sugerencias:
                prefijo = " " if len(partes) > 1 else ""
                partes[-1] = prefijo + sugerencias[0]
                entrada = ",".join(partes) + ", "
        else: entrada += char

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
        print("🔍 DETALLES DEL REGISTRO")
        print("#"*70)
        print(f"Nombre: {archivo['filename']}")
        print(f"Ruta:   {archivo['path']}")
        print("-" * 70)
        desc = desc_row['description'] if desc_row else "⚠️ (SIN DESCRIPCIÓN)"
        print(f"Descripción: {desc}")
        print(f"Etiquetas:   {', '.join(tags) if tags else '⚠️ (SIN ETIQUETAS)'}")
        mostrar_relaciones(conn, "files", file_id)
        print("#"*70)
        print("\n1. 📝 Editar Desc | 2. 🏷️ Agregar Tags | 3. 🗑️ Limpiar Tags | 4. 🚀 Abrir | 5. 🔗 Relaciones | 6. 🔙 Volver")
        opc = input("> ").strip()
        if opc == '1':
            nueva_desc = input("\nNueva descripción: ").strip()
            if nueva_desc:
                if desc_row: c.execute("UPDATE descriptions SET description=?, source='Manual' WHERE file_id=?", (nueva_desc, file_id))
                else: c.execute("INSERT INTO descriptions(file_id, description, source, model_used) VALUES(?,?,'Manual','None')", (file_id, nueva_desc))
                conn.commit(); desc_row = {'description': nueva_desc, 'source': 'Manual'}
                print("✅ Guardado.")
        elif opc == '2':
            c.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
            todas = [row['value'] for row in c.fetchall()]
            nuevos = ingresar_tags_interactivo(todas)
            if nuevos:
                for t in [t.strip() for t in nuevos.split(",") if t.strip()]:
                    if t not in tags:
                        c.execute("INSERT INTO metadata(file_id, key, value) VALUES(?, 'tag', ?)", (file_id, t))
                        tags.append(t)
                conn.commit(); print("✅ Etiquetas guardadas.")
        elif opc == '3':
            if input("\n⚠️ ¿Limpiar todas las etiquetas? (s/n): ").lower() == 's':
                c.execute("DELETE FROM metadata WHERE file_id=? AND key='tag'", (file_id,))
                conn.commit(); tags = []; print("🗑️ Limpio.")
        elif opc == '4': abrir_recurso(archivo)
        elif opc == '5': menu_relaciones(conn, "files", file_id)
        elif opc == '6': break

def procesar_carpeta_manual(conn):
    ruta = input("\nRuta de la carpeta: ").strip()
    if not ruta or not os.path.exists(ruta): return
    ruta_abs = os.path.abspath(ruta)
    scan_directory(ruta_abs)
    c = conn.cursor()
    c.execute("SELECT id, filename, path, size FROM files WHERE path LIKE ? AND resource_type='local' ORDER BY filename ASC", (f"{ruta_abs}%",))
    archivos = c.fetchall()
    if not archivos: return
    c.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
    todas_etiquetas = [row['value'] for row in c.fetchall()]
    for i, row in enumerate(archivos, 1):
        print(f"\n[{i}/{len(archivos)}] {row['filename']}")
        nueva_desc = input("✏️ Descripción (ENTER para omitir, 'salir' para parar): ").strip()
        if nueva_desc.lower() == 'salir': break
        nuevos_tags = ingresar_tags_interactivo(todas_etiquetas, mensaje_prompt="🏷️ Tags:")
        if nueva_desc:
            c.execute("INSERT INTO descriptions(file_id, description, source, model_used) VALUES(?, ?, 'Manual', 'None')", (row['id'], nueva_desc))
        if nuevos_tags:
            for t in [t.strip() for t in nuevos_tags.split(",") if t.strip()]:
                c.execute("INSERT INTO metadata(file_id, key, value) VALUES(?, 'tag', ?)", (row['id'], t))
        conn.commit()

def agregar_enlace_web(conn):
    url = input("\n🌐 URL del enlace: ").strip()
    nombre = input("📛 Nombre: ").strip()
    if not url or not nombre: return
    c = conn.cursor()
    ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO files (path, filename, extension, resource_type, created_at, modified_at) VALUES (?, ?, '.link', 'web', ?, ?)", (url, nombre, ahora, ahora))
    conn.commit(); print("✅ Enlace guardado.")

def exportar_importar_ia(conn):
    print("\n1. 📤 Exportar para IA | 2. 📥 Importar desde IA | 3. 🔙 Volver")
    opc = input("> ").strip()
    c = conn.cursor()
    if opc == '1':
        c.execute("SELECT f.id, f.filename, f.path, d.description FROM files f LEFT JOIN descriptions d ON f.id = d.file_id WHERE f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')")
        regs = c.fetchall()
        if not regs: print("✅ Todo etiquetado."); return
        with open("archivos_para_ia.txt", "w", encoding="utf-8") as f:
            for r in regs: f.write(f"ID: {r['id']} | Nombre: {r['filename']} | Ruta: {r['path']}\n")
        print("✅ Generado 'archivos_para_ia.txt'.")
    elif opc == '2':
        if not os.path.exists("respuestas.txt"): print("❌ No hay 'respuestas.txt'."); return
        with open("respuestas.txt", "r", encoding="utf-8") as f:
            for line in f:
                if '|' in line:
                    fid, tags = line.strip().split('|')
                    for t in tags.split(','):
                        c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, 'tag', ?)", (fid.strip(), t.strip().lower()))
        conn.commit(); print("✅ Importado.")

def verificar_y_crear_respaldo():
    backup_dir = os.path.join(os.path.dirname(__file__), "respaldos")
    os.makedirs(backup_dir, exist_ok=True)

def crear_respaldo_ahora():
    backup_dir = os.path.join(os.path.dirname(__file__), "respaldos")
    fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_zip = os.path.join(backup_dir, f"respaldo_bd_{fecha}.zip")
    try:
        with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(db_path, "files.db")
        print(f"✅ Respaldo creado: {ruta_zip}")
    except Exception as e: print(f"❌ Error: {e}")

def menu_principal():
    verificar_y_crear_respaldo()
    # Inicializar tabla de relaciones al arrancar
    conn_init = get_connection()
    init_relaciones(conn_init)
    conn_init.close()
    while True:
        print("\n" + "="*50)
        print("🚀 GESTOR VISUAL DE BASE DE DATOS")
        print("="*50)
        print("1. 📊 Ver Estadísticas")
        print("2. 🔎 Buscar y Abrir Registros")
        print("3. 📂 Escanear y Etiquetar Carpeta")
        print("4. 🌐 Guardar Nuevo Enlace Web")
        print("5. 🤖 Exportar/Importar para IA")
        print("6. 💾 Crear Backup de Seguridad")
        print("7. 📱 Gestor de Apps Instaladas")
        print("8. ❌ Salir")
        print("="*50)
        opc = input("Selecciona (1-8): ").strip()
        if opc == '1': mostrar_estadisticas()
        elif opc == '2': explorar_archivos()
        elif opc == '3':
            conn = get_connection(); procesar_carpeta_manual(conn); conn.close()
        elif opc == '4':
            conn = get_connection(); agregar_enlace_web(conn); conn.close()
        elif opc == '5':
            conn = get_connection(); exportar_importar_ia(conn); conn.close()
        elif opc == '6': crear_respaldo_ahora()
        elif opc == '7': menu_apps()
        elif opc == '8': print("¡Adiós!"); break

if __name__ == "__main__":
    try: menu_principal()
    except KeyboardInterrupt: print("\nSaliendo...")