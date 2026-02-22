import sqlite3
import os
import math
import sys
import msvcrt
import datetime
import zipfile
import json
import subprocess
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

def ir_a_carpeta(archivo):
    """Abre el Explorador de Windows en la carpeta que contiene el archivo."""
    try:
        path = archivo['path']
        r_type = dict(archivo).get('resource_type')
        if r_type == 'web':
            print("⚠️  Este registro es un enlace web, no tiene carpeta local.")
            return
        carpeta = os.path.dirname(path)
        if os.path.isdir(carpeta):
            print(f"📂 Abriendo carpeta: {carpeta}")
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            print(f"❌ La carpeta no existe: {carpeta}")
    except Exception as e:
        print(f"❌ Error al abrir carpeta: {e}")

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
    print("\n" + "-"*55)
    print("🔍 FILTROS DE BÚSQUEDA — deja en blanco para omitir")
    print("-" * 55)
    print("  Prefijo  '-'  = EXCLUIR ese valor  (ej: -factura)")
    print("-" * 55)

    # --- Filtro por nombre/ruta ---
    ubicacion_inc = input("📁 Ruta/nombre INCLUYE: ").strip()
    ubicacion_exc = input("📁 Ruta/nombre EXCLUYE: ").strip()

    # --- Filtro por tags ---
    conn_temp = get_connection()
    c_temp = conn_temp.cursor()
    c_temp.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
    todas_las_etiquetas = [row['value'] for row in c_temp.fetchall()]
    conn_temp.close()

    print("🏷️  Tag INCLUYE (autocomplete con TAB):")
    tag_inc = ingresar_tags_interactivo(todas_las_etiquetas, modo_unico=True).replace(",", "").strip()
    print("🏷️  Tag EXCLUYE (autocomplete con TAB):")
    tag_exc = ingresar_tags_interactivo(todas_las_etiquetas, modo_unico=True).replace(",", "").strip()

    # --- Filtro por tiempo ---
    dias = input("📅 Periodo (últimos N días): ").strip()

    # --- Filtro por tipo/extensión ---
    print("📄 Extensión/tipo INCLUYE (pdf, docx, web…) — separa con comas:")
    tipos_inc_raw = input("   > ").strip()
    print("📄 Extensión/tipo EXCLUYE — separa con comas:")
    tipos_exc_raw = input("   > ").strip()

    def parse_tipos(raw):
        """Devuelve lista de extensiones normalizadas (con punto) o keywords especiales."""
        resultado = []
        for t in [x.strip().lower() for x in raw.split(",") if x.strip()]:
            if t in ('web', 'link', 'enlace', 'nube', 'url'):
                resultado.append('__web__')
            else:
                resultado.append(t if t.startswith('.') else '.' + t)
        return resultado

    tipos_inc = parse_tipos(tipos_inc_raw)
    tipos_exc = parse_tipos(tipos_exc_raw)

    # --- Filtro por info ---
    print("ℹ️  ¿Filtrar por si tiene información?")
    print("   [s] Solo CON desc/tags  |  [n] Solo SIN desc/tags  |  ENTER = todos")
    filtro_info = input("   > ").strip().lower()

    # ─────────────────────────────────────────────
    # Construcción de la query
    # ─────────────────────────────────────────────
    query = """
    SELECT f.id, f.filename, f.path, f.size, f.resource_type, f.modified_at, d.description 
    FROM files f
    LEFT JOIN descriptions d ON f.id = d.file_id
    WHERE 1=1
    """
    params = []

    # Nombre/ruta inclusivo
    if ubicacion_inc:
        query += " AND f.path LIKE ?"
        params.append(f"%{ubicacion_inc}%")
    # Nombre/ruta excluyente
    if ubicacion_exc:
        query += " AND f.path NOT LIKE ?"
        params.append(f"%{ubicacion_exc}%")

    # Tag inclusivo
    if tag_inc:
        query += " AND f.id IN (SELECT file_id FROM metadata WHERE key='tag' AND value LIKE ?)"
        params.append(f"%{tag_inc}%")
    # Tag excluyente
    if tag_exc:
        query += " AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag' AND value LIKE ?)"
        params.append(f"%{tag_exc}%")

    # Tiempo
    if dias.isdigit():
        query += f" AND f.modified_at >= datetime('now', '-{dias} days')"

    # Tipos inclusivos
    if tipos_inc:
        if '__web__' in tipos_inc and len(tipos_inc) == 1:
            query += " AND f.resource_type = 'web'"
        elif '__web__' in tipos_inc:
            exts = [t for t in tipos_inc if t != '__web__']
            placeholders = ",".join("?" * len(exts))
            query += f" AND (f.resource_type = 'web' OR lower(f.extension) IN ({placeholders}))"
            params.extend(exts)
        else:
            placeholders = ",".join("?" * len(tipos_inc))
            query += f" AND lower(f.extension) IN ({placeholders})"
            params.extend(tipos_inc)

    # Tipos excluyentes
    if tipos_exc:
        if '__web__' in tipos_exc and len(tipos_exc) == 1:
            query += " AND f.resource_type != 'web'"
        elif '__web__' in tipos_exc:
            exts = [t for t in tipos_exc if t != '__web__']
            placeholders = ",".join("?" * len(exts))
            query += f" AND f.resource_type != 'web' AND lower(f.extension) NOT IN ({placeholders})"
            params.extend(exts)
        else:
            placeholders = ",".join("?" * len(tipos_exc))
            query += f" AND lower(f.extension) NOT IN ({placeholders})"
            params.extend(tipos_exc)

    # Filtro info
    if filtro_info == 's':
        query += " AND (d.id IS NOT NULL OR f.id IN (SELECT file_id FROM metadata WHERE key='tag'))"
    elif filtro_info == 'n':
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
        if sugerencias: texto_mostrar += f"  (Sugerencias: {' | '.join(sugerencias[:5])})"
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
        print("\n1. 📝 Editar Desc | 2. 🏷️ Agregar Tags | 3. 🗑️ Limpiar Tags | 4. 🚀 Abrir | 5. 📂 Ir a Carpeta | 6. 🔗 Relaciones | 7. 🔙 Volver")
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
        elif opc == '5': ir_a_carpeta(archivo)
        elif opc == '6': menu_relaciones(conn, "files", file_id)
        elif opc == '7': break

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

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTAR ARCHIVOS DE NUBES (JSON) A LA BASE DE DATOS LOCAL
# ─────────────────────────────────────────────────────────────────────────────
CACHE_NUBES = {
    "YouTube":      "cache_youtube.json",
    "Google Drive": "cache_drive.json",
    "OneDrive":     "cache_onedrive.json",
    "Dropbox":      "cache_dropbox.json",
}

def importar_nubes_a_bd():
    """
    Lee cada archivo cache_*.json generado por gestor_nubes.py y
    registra los ítems nuevos en la BD local como resource_type='web'.
    Muestra un resumen al final y recuerda sincronizar si hay nuevos.
    """
    conn = get_connection()
    c = conn.cursor()
    ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_dir = os.path.dirname(__file__)
    total_nuevos = 0

    print("\n" + "="*55)
    print("☁️  IMPORTAR ARCHIVOS DE NUBES A BD LOCAL")
    print("="*55)

    for origen, archivo in CACHE_NUBES.items():
        ruta_json = os.path.join(base_dir, archivo)
        if not os.path.exists(ruta_json):
            print(f"  ⏭️  {origen}: sin caché ({archivo} no encontrado)")
            continue

        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception as e:
            print(f"  ❌  {origen}: error al leer JSON — {e}")
            continue

        nuevos = 0
        for item in items:
            link  = item.get("link", "").strip()
            nombre = item.get("nombre", "Sin nombre").strip()
            comentario = item.get("comentario", "").strip()
            if not link:
                continue
            # Verificar si ya existe en BD (por path/URL)
            c.execute("SELECT id FROM files WHERE path = ? AND resource_type = 'web'", (link,))
            if c.fetchone():
                continue
            # Insertar
            c.execute(
                "INSERT INTO files (path, filename, extension, resource_type, created_at, modified_at) VALUES (?, ?, '.link', 'web', ?, ?)",
                (link, nombre, ahora, ahora)
            )
            file_id = c.lastrowid
            # Guardar origen como tag
            c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, 'tag', ?)", (file_id, origen.lower().replace(" ", "_")))
            # Guardar comentario como descripción (si existe)
            if comentario:
                c.execute(
                    "INSERT INTO descriptions (file_id, description, source, model_used) VALUES (?, ?, 'Nube', 'None')",
                    (file_id, comentario[:500])
                )
            nuevos += 1

        conn.commit()
        total_nuevos += nuevos
        print(f"  ✅  {origen}: {nuevos} registro(s) nuevo(s) importado(s)  (total en caché: {len(items)})")

    print("-"*55)
    if total_nuevos > 0:
        print(f"  🎉  Total importado: {total_nuevos} registro(s) nuevos a la BD.")
        print("\n  ⚠️  RECUERDA: Si quieres actualizar datos de la nube, ve al")
        print("  gestor de nubes (opción 9 del menú) para sincronizar de nuevo.")
        print("  YouTube / Drive / OneDrive / Dropbox → luego vuelve aquí.")
    else:
        print("  ℹ️  No hay registros nuevos. La BD ya está al día con los caches.")
        print("\n  💡  Para obtener datos frescos de la nube, usa la opción 9")
        print("  (Sincronizar Nubes) y luego vuelve a importar.")
    print("="*55)

    input("\nPresiona ENTER para volver al menú...")
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────

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
        print("2. 🔎 Buscar y Editar Registros")
        print("3. 📂 Escanear y Etiquetar Carpeta")
        print("4. 🌐 Guardar Nuevo Enlace Web")
        print("5. 🤖 Exportar/Importar para IA")
        print("6. 💾 Crear Backup de Seguridad")
        print("7. 📱 Gestor de Apps Instaladas")
        print("8. ☁️  Importar Nubes a BD (JSON → BD)")
        print("9. 🔄 Sincronizar Nubes (YouTube/Drive/OneDrive/Dropbox)")
        print("0. ❌ Salir")
        print("="*50)
        opc = input("Selecciona (0-9): ").strip()
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
        elif opc == '8': importar_nubes_a_bd()
        elif opc == '9':
            from gestor_nubes import menu_principal as menu_nubes
            menu_nubes()
        elif opc == '0': print("¡Adiós!"); break

if __name__ == "__main__":
    try: menu_principal()
    except KeyboardInterrupt: print("\nSaliendo...")