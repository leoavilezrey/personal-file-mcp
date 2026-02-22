import sqlite3
import os
import sys
import json
import math
import msvcrt
import datetime
import zipfile
import webbrowser
import subprocess
from pathlib import Path

# ── UTF-8 en Windows ──────────────────────────────────────────────────────────
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(__file__)
DB_PATH    = os.path.join(BASE_DIR, "files.db")
CACHE_YT   = os.path.join(BASE_DIR, "cache_youtube.json")
CACHE_DRV  = os.path.join(BASE_DIR, "cache_drive.json")
CACHE_OD   = os.path.join(BASE_DIR, "cache_onedrive.json")
CACHE_DBX  = os.path.join(BASE_DIR, "cache_dropbox.json")

# ── Importaciones locales ─────────────────────────────────────────────────────
from scanner import scan_directory
from relaciones import init_relaciones, mostrar_relaciones, menu_relaciones

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS GLOBALES
# ══════════════════════════════════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def sep(c="─", n=70):
    print(c * n)

def elegir_de_lista(opciones, titulo="Elige una opción"):
    print(f"\n{titulo}:")
    for i, op in enumerate(opciones, 1):
        print(f"  {i}. {op}")
    while True:
        sel = input("> ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(opciones):
            return opciones[int(sel) - 1]
        print("⚠️ Opción inválida.")

def ingresar_tags_interactivo(todas, mensaje=None, unico=False, prefijo=""):
    """Entrada interactiva de tags con autocompletado por TAB.
    prefijo: texto que se muestra a la izquierda del cursor en cada render
             (ej: '  Tag              | ').
    """
    if mensaje:
        print(mensaje)
    entrada = ""
    while True:
        partes = entrada.split(",")
        actual = partes[-1].lstrip()
        sugs = [t for t in todas if t.lower().startswith(actual.lower())] if actual and not entrada.endswith(",") else []
        sys.stdout.write('\r' + ' ' * 120 + '\r')
        txt = f"{prefijo}> {entrada}"
        if sugs:
            txt += f"  ({' | '.join(sugs[:4])})"
        sys.stdout.write(txt)
        sys.stdout.flush()
        ch = msvcrt.getwch()
        if ch in ('\r', '\n'):
            print()
            return entrada
        elif ch == '\x03':
            raise KeyboardInterrupt
        elif ch == '\b':
            entrada = entrada[:-1] if entrada else ""
        elif ch == '\t':
            if sugs:
                pfx = " " if len(partes) > 1 else ""
                partes[-1] = pfx + sugs[0]
                entrada = ",".join(partes) + ", "
        else:
            entrada += ch

# Sentinel para volver al menú principal desde cualquier nivel
VOLVER_PRINCIPAL = "__VOLVER_PRINCIPAL__"

def cargar_cache(archivo):
    if os.path.exists(archivo):
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_cache(archivo, datos):
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)

def get_all_tags(conn):
    """Reúne todos los tags únicos de todas las tablas."""
    tags = set()
    for row in conn.execute("SELECT DISTINCT value FROM metadata WHERE key='tag'").fetchall():
        tags.add(row[0])
    for tabla in ('apps', 'cuentas_web', 'paginas_sin_registro'):
        for row in conn.execute(f"SELECT tags FROM {tabla} WHERE tags IS NOT NULL").fetchall():
            for t in row[0].split(','):
                t = t.strip()
                if t: tags.add(t)
    return sorted(tags)

# ══════════════════════════════════════════════════════════════════════════════
#  INIT TABLAS
# ══════════════════════════════════════════════════════════════════════════════

def init_tablas(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS apps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            plataforma  TEXT NOT NULL,
            categoria   TEXT,
            version     TEXT,
            estado      TEXT DEFAULT 'Instalada',
            es_gratis   INTEGER DEFAULT 1,
            link_tienda TEXT,
            notas       TEXT,
            tags        TEXT,
            fecha_reg   TEXT
        );
        CREATE TABLE IF NOT EXISTS cuentas_web (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sitio           TEXT NOT NULL,
            url             TEXT,
            categoria       TEXT,
            email_usuario   TEXT,
            estado          TEXT DEFAULT 'Activa',
            plan            TEXT DEFAULT 'Gratuito',
            tiene_2fa       INTEGER DEFAULT 0,
            notas           TEXT,
            tags            TEXT,
            fecha_reg       TEXT
        );
        CREATE TABLE IF NOT EXISTS paginas_sin_registro (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            url         TEXT NOT NULL,
            categoria   TEXT,
            descripcion TEXT,
            tags        TEXT,
            fecha_reg   TEXT
        );
    """)
    conn.commit()
    init_relaciones(conn)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════
PLATAFORMAS = ["Android", "Windows", "Web", "iOS", "Linux", "MacOS", "Otro"]
CATEGORIAS_APP = [
    "Productividad", "Comunicación", "Entretenimiento", "Educación",
    "Finanzas", "Salud", "Fotografía", "Música", "Seguridad",
    "Desarrollo", "Juegos", "Navegación", "Utilidades", "Otro"
]
CAT_WEB = [
    "Correo / Email", "Redes Sociales", "Trabajo / Freelance", "Almacenamiento en Nube",
    "Educación / Cursos", "Entretenimiento", "Finanzas / Pagos", "Desarrollo / Tech",
    "Noticias / Blogs", "Compras", "Salud", "Juegos", "IA / Herramientas", "Referencia", "Otro"
]

# ══════════════════════════════════════════════════════════════════════════════
#  MÓDULO 1 — AGREGAR REGISTROS
# ══════════════════════════════════════════════════════════════════════════════

# ── Archivos PC ───────────────────────────────────────────────────────────────
def agregar_archivo_pc(conn):
    print("\n1. 📂 Escanear carpeta (manual)\n2. 🤖 Exportar IDs sin metadata para IA\n3. 📥 Importar respuestas de IA\n4. 🔙 Volver")
    opc = input("> ").strip()
    if opc == '1':
        ruta = input("\nRuta de la carpeta: ").strip()
        if not ruta or not os.path.exists(ruta):
            print("❌ Ruta no válida.")
            return
        ruta_abs = os.path.abspath(ruta)
        scan_directory(ruta_abs)
        c = conn.cursor()
        c.execute("SELECT id, filename FROM files WHERE path LIKE ? AND resource_type='local' ORDER BY filename ASC", (f"{ruta_abs}%",))
        archivos = c.fetchall()
        if not archivos:
            print("⚠️ No se encontraron archivos nuevos.")
            return
        c.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
        todas = [r['value'] for r in c.fetchall()]
        for i, row in enumerate(archivos, 1):
            print(f"\n[{i}/{len(archivos)}] {row['filename']}")
            desc = input("✏️ Descripción (ENTER para omitir, 'salir' para parar): ").strip()
            if desc.lower() == 'salir':
                break
            tags = ingresar_tags_interactivo(todas, "🏷️ Tags (coma para separar):")
            if desc:
                c.execute("INSERT OR IGNORE INTO descriptions(file_id, description, source, model_used) VALUES(?,?,'Manual','None')", (row['id'], desc))
            if tags:
                for t in [t.strip() for t in tags.split(",") if t.strip()]:
                    c.execute("INSERT INTO metadata(file_id, key, value) VALUES(?,'tag',?)", (row['id'], t))
            conn.commit()
        print("✅ Proceso completado.")
    elif opc == '2':
        c = conn.cursor()
        c.execute("SELECT f.id, f.filename, f.path FROM files f WHERE f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')")
        regs = c.fetchall()
        if not regs:
            print("✅ Todo está etiquetado.")
            return
        with open(os.path.join(BASE_DIR, "archivos_para_ia.txt"), "w", encoding="utf-8") as f:
            for r in regs:
                f.write(f"ID: {r['id']} | Nombre: {r['filename']} | Ruta: {r['path']}\n")
        print("✅ Generado 'archivos_para_ia.txt'. Pega las respuestas en 'respuestas.txt'.")
    elif opc == '3':
        print("\n📋 RECORDATORIO — Flujo de etiquetado con IA:")
        print(f"  1. Usa la opción 2 para exportar → genera 'archivos_para_ia.txt'")
        print(f"  2. Pega ese contenido en una IA (ChatGPT, Gemini, etc.)")
        print(f"  3. Pídele tags en formato:  123 | tag1, tag2, tag3")
        print(f"  4. Guarda las respuestas como 'respuestas.txt' en:")
        print(f"     {BASE_DIR}")
        print()
        resp = os.path.join(BASE_DIR, "respuestas.txt")
        if not os.path.exists(resp):
            print("❌ No hay 'respuestas.txt' todavía. Créalo y vuelve a intentarlo.")
            return
        c = conn.cursor()
        with open(resp, "r", encoding="utf-8") as f:
            for line in f:
                if '|' in line:
                    fid, tags = line.strip().split('|', 1)
                    for t in tags.split(','):
                        c.execute("INSERT INTO metadata (file_id, key, value) VALUES (?, 'tag', ?)", (fid.strip(), t.strip().lower()))
        conn.commit()
        print("✅ Importado correctamente.")

def agregar_enlace_web_archivo(conn):
    url    = input("\n🌐 URL: ").strip()
    nombre = input("📛 Nombre: ").strip()
    if not url or not nombre:
        return
    ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("INSERT INTO files (path, filename, extension, resource_type, created_at, modified_at) VALUES (?,?,'.link','web',?,?)", (url, nombre, ahora, ahora))
    conn.commit()
    print("✅ Enlace guardado.")

# ── Nube ──────────────────────────────────────────────────────────────────────
def lanzar_gestor_nubes():
    script = os.path.join(BASE_DIR, "gestor_nubes.py")
    print("\n☁️  SINCRONIZAR NUBES — Información")
    print("─"*60)
    print("  Los datos extraídos se guardan como archivos JSON en:")
    print(f"  📁 {BASE_DIR}")
    print("    • cache_youtube.json  → Videos de YouTube (Me gusta)")
    print("    • cache_drive.json    → Archivos de Google Drive")
    print("    • cache_onedrive.json → Archivos de OneDrive")
    print("    • cache_dropbox.json  → Archivos de Dropbox")
    print("  🔍 Para buscarlos: Menú 3 › ☁️ Elementos en Nubes")
    print("  💾 Para importarlos a la BD local: usa la opción 4 de este")
    print("     menú (Importar Nubes → BD), DESPUÉS de sincronizar aquí.")
    print("─"*60)
    subprocess.run([sys.executable, script])

# ── Importar JSONs de nube → BD local ────────────────────────────────────────
CACHE_NUBES_MAP = [
    ("YouTube",      CACHE_YT),
    ("Google Drive", CACHE_DRV),
    ("OneDrive",     CACHE_OD),
    ("Dropbox",      CACHE_DBX),
]

def importar_nubes_a_bd(conn):
    """
    Lee cada cache_*.json y registra los ítems nuevos en la BD local
    como resource_type='web'. Evita duplicados por URL.
    """
    ahora = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_nuevos = 0
    sep("=")
    print("☁️  IMPORTAR ARCHIVOS DE NUBES A BD LOCAL")
    sep("=")
    for origen, ruta_json in CACHE_NUBES_MAP:
        if not os.path.exists(ruta_json):
            print(f"  ⏭️  {origen}: sin caché ({os.path.basename(ruta_json)} no encontrado)")
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
            existente = conn.execute(
                "SELECT id FROM files WHERE path=? AND resource_type='web'", (link,)
            ).fetchone()
            if existente:
                continue
            conn.execute(
                "INSERT INTO files (path, filename, extension, resource_type, created_at, modified_at) VALUES (?,?,'.link','web',?,?)",
                (link, nombre, ahora, ahora)
            )
            fid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            tag_origen = origen.lower().replace(" ", "_")
            conn.execute("INSERT INTO metadata (file_id, key, value) VALUES (?,'tag',?)", (fid, tag_origen))
            if comentario:
                conn.execute(
                    "INSERT INTO descriptions (file_id, description, source, model_used) VALUES (?,?,'Nube','None')",
                    (fid, comentario[:500])
                )
            nuevos += 1
        conn.commit()
        total_nuevos += nuevos
        print(f"  ✅  {origen}: {nuevos} nuevo(s) importado(s)  (total en caché: {len(items)})")
    sep()
    if total_nuevos > 0:
        print(f"  🎉  Total importado: {total_nuevos} registro(s) nuevos a la BD.")
        print("  💡  Ahora puedes buscarlos en: Menú 3 › 📁 Archivos PC")
        print("      (filtrar por tag: youtube, google_drive, onedrive o dropbox)")
    else:
        print("  ℹ️  No hay registros nuevos. La BD ya está al día con los cachés.")
        print("  💡  Para datos frescos: usa opción 3 ☁️ Sincronizar Nubes primero.")
    sep("=")
    input("\nPresiona ENTER para continuar...")

# ── Apps ──────────────────────────────────────────────────────────────────────
def agregar_app(conn):
    sep("="); print("➕ REGISTRAR NUEVA APLICACIÓN"); sep("=")
    nombre     = input("📛 Nombre: ").strip()
    if not nombre: return
    plataforma = elegir_de_lista(PLATAFORMAS, "📱 Plataforma")
    categoria  = elegir_de_lista(CATEGORIAS_APP, "📂 Categoría")
    version    = input("🔢 Versión (ENTER omitir): ").strip() or None
    link       = input("🔗 Link tienda/web (ENTER omitir): ").strip() or None
    es_gratis  = input("💰 ¿Es gratuita? (s/n): ").strip().lower() != 'n'
    estado     = elegir_de_lista(["Instalada", "Desinstalada", "Pendiente"], "📌 Estado")
    notas      = input("📝 Notas (ENTER omitir): ").strip() or None
    print("🏷️  Tags (TAB=autocompletar, coma=separar):")
    tags_str   = ingresar_tags_interactivo(get_all_tags(conn))
    tags       = tags_str.strip() or None
    fecha      = datetime.datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO apps (nombre,plataforma,categoria,version,estado,es_gratis,link_tienda,notas,tags,fecha_reg) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (nombre, plataforma, categoria, version, estado, 1 if es_gratis else 0, link, notas, tags, fecha))
    conn.commit()
    print(f"\n✅ '{nombre}' registrada.")

# ── Cuentas web ───────────────────────────────────────────────────────────────
def agregar_cuenta_web(conn):
    sep("="); print("🌐 REGISTRAR CUENTA WEB"); sep("=")
    sitio     = input("🌐 Nombre del sitio: ").strip()
    if not sitio: return
    url       = input("🔗 URL: ").strip() or None
    categoria = elegir_de_lista(CAT_WEB, "📂 Categoría")
    email     = input("📧 Email/Usuario: ").strip() or None
    estado    = elegir_de_lista(["Activa", "Inactiva", "Pendiente de verificar", "Eliminada"], "📌 Estado")
    plan      = elegir_de_lista(["Gratuito", "Premium", "De pago", "Trial"], "💳 Plan")
    twofa     = input("🔐 ¿Tiene 2FA? (s/n): ").strip().lower() == 's'
    notas     = input("📝 Notas (ENTER omitir): ").strip() or None
    print("🏷️  Tags (TAB=autocompletar, coma=separar):")
    tags_str  = ingresar_tags_interactivo(get_all_tags(conn))
    tags      = tags_str.strip() or None
    fecha     = datetime.datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO cuentas_web (sitio,url,categoria,email_usuario,estado,plan,tiene_2fa,notas,tags,fecha_reg) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (sitio, url, categoria, email, estado, plan, 1 if twofa else 0, notas, tags, fecha))
    conn.commit()
    print(f"\n✅ Cuenta en '{sitio}' registrada.")

# ── Páginas sin registro ──────────────────────────────────────────────────────
def agregar_pagina_sin_registro(conn):
    sep("="); print("🔖 REGISTRAR PÁGINA SIN REGISTRO"); sep("=")
    nombre    = input("📛 Nombre/Título: ").strip()
    if not nombre: return
    url       = input("🔗 URL: ").strip()
    if not url: return
    categoria = elegir_de_lista(CAT_WEB, "📂 Categoría")
    desc      = input("📝 Descripción breve: ").strip() or None
    print("🏷️  Tags (TAB=autocompletar, coma=separar):")
    tags_str  = ingresar_tags_interactivo(get_all_tags(conn))
    tags      = tags_str.strip() or None
    fecha     = datetime.datetime.now().strftime("%Y-%m-%d")
    conn.execute("INSERT INTO paginas_sin_registro (nombre,url,categoria,descripcion,tags,fecha_reg) VALUES(?,?,?,?,?,?)",
                 (nombre, url, categoria, desc, tags, fecha))
    conn.commit()
    print(f"\n✅ '{nombre}' registrada.")

def menu_agregar(conn):
    while True:
        print("\n" + "═"*60)
        print("➕  AGREGAR archivos a la BD")
        print("═"*60)
        print("1. 📁  Archivos PC  (escanear/etiquetar/IA)")
        print("2. 🌐  Enlace web a archivos PC")
        print("3. ☁️   Sincronizar Nubes  (YouTube/Drive/OneDrive/Dropbox)")
        print("4. 💾  Importar Nubes → BD local  (JSON → registros)")
        print("5. 📱  App instalada  (PC o Android)")
        print("6. 🔑  Cuenta web  (con registro/login)")
        print("7. 🔖  Página sin registro  (wiki, foros, etc.)")
        print("─"*60)
        print("8. 🔙  Volver al menú anterior")
        print("0. 🏠  Menú principal")
        print("═"*60)
        opc = input("Elige (0-8): ").strip()
        if   opc == '1': agregar_archivo_pc(conn)
        elif opc == '2': agregar_enlace_web_archivo(conn)
        elif opc == '3': lanzar_gestor_nubes()
        elif opc == '4': importar_nubes_a_bd(conn)
        elif opc == '5': agregar_app(conn)
        elif opc == '6': agregar_cuenta_web(conn)
        elif opc == '7': agregar_pagina_sin_registro(conn)
        elif opc in ('8', 'q'): break
        elif opc == '0': return VOLVER_PRINCIPAL

# ══════════════════════════════════════════════════════════════════════════════
#  MÓDULO 2 — ESTADÍSTICAS
# ══════════════════════════════════════════════════════════════════════════════

def stats_archivos_pc(conn):
    c = conn.cursor()
    total     = c.execute("SELECT count(*) FROM files").fetchone()[0]
    locales   = c.execute("SELECT count(*) FROM files WHERE resource_type='local'").fetchone()[0]
    webs      = c.execute("SELECT count(*) FROM files WHERE resource_type='web'").fetchone()[0]
    sin_desc  = c.execute("SELECT count(*) FROM files WHERE id NOT IN (SELECT file_id FROM descriptions)").fetchone()[0]
    sin_tags  = c.execute("SELECT count(*) FROM files WHERE id NOT IN (SELECT file_id FROM metadata WHERE key='tag')").fetchone()[0]
    n_tags    = c.execute("SELECT count(DISTINCT value) FROM metadata WHERE key='tag'").fetchone()[0]
    sep("="); print("📁 ESTADÍSTICAS — ARCHIVOS PC"); sep("=")
    print(f"  Total registros     : {total}")
    print(f"  Archivos locales    : {locales}")
    print(f"  Links/webs          : {webs}")
    print(f"  Tags únicas         : {n_tags}")
    print(f"  Sin descripción     : {sin_desc}")
    print(f"  Sin etiquetas       : {sin_tags}")
    sep("=")

def stats_nubes():
    caches = [
        ("YouTube",  CACHE_YT),
        ("Drive",    CACHE_DRV),
        ("OneDrive", CACHE_OD),
        ("Dropbox",  CACHE_DBX),
    ]
    sep("="); print("☁️  ESTADÍSTICAS — NUBES"); sep("=")
    total_global = 0
    for nombre, ruta in caches:
        datos = cargar_cache(ruta)
        print(f"  {nombre:<12}: {len(datos)} elementos")
        total_global += len(datos)
    sep()
    print(f"  TOTAL EN CACHÉ     : {total_global}")
    sep("=")

def stats_apps(conn):
    total = conn.execute("SELECT count(*) FROM apps").fetchone()[0]
    sep("="); print("📱 ESTADÍSTICAS — APPS INSTALADAS"); sep("=")
    print(f"  Total registradas   : {total}\n")
    print(f"  {'Plataforma':<14} | {'Total':>6} | {'Instaladas':>10} | {'Pendientes':>10}")
    sep()
    for row in conn.execute("SELECT DISTINCT plataforma FROM apps ORDER BY plataforma").fetchall():
        pl   = row[0]
        tot  = conn.execute("SELECT count(*) FROM apps WHERE plataforma=?", (pl,)).fetchone()[0]
        inst = conn.execute("SELECT count(*) FROM apps WHERE plataforma=? AND estado='Instalada'", (pl,)).fetchone()[0]
        pend = conn.execute("SELECT count(*) FROM apps WHERE plataforma=? AND estado='Pendiente'", (pl,)).fetchone()[0]
        print(f"  {pl:<14} | {tot:>6} | {inst:>10} | {pend:>10}")
    sep("=")

def stats_cuentas(conn):
    total   = conn.execute("SELECT count(*) FROM cuentas_web").fetchone()[0]
    activas = conn.execute("SELECT count(*) FROM cuentas_web WHERE estado='Activa'").fetchone()[0]
    con2fa  = conn.execute("SELECT count(*) FROM cuentas_web WHERE tiene_2fa=1").fetchone()[0]
    pago    = conn.execute("SELECT count(*) FROM cuentas_web WHERE plan IN ('Premium','De pago')").fetchone()[0]
    sep("="); print("🔑 ESTADÍSTICAS — CUENTAS WEB"); sep("=")
    print(f"  Total cuentas       : {total}")
    print(f"  Activas             : {activas}")
    print(f"  Con 2FA             : {con2fa}")
    print(f"  De pago             : {pago}")
    sep()
    print("  Por categoría:")
    for r in conn.execute("SELECT categoria, count(*) n FROM cuentas_web GROUP BY categoria ORDER BY n DESC").fetchall():
        print(f"    {(r['categoria'] or 'Sin cat'):<22}: {r['n']}")
    sep("=")

def stats_paginas(conn):
    total = conn.execute("SELECT count(*) FROM paginas_sin_registro").fetchone()[0]
    sep("="); print("🔖 ESTADÍSTICAS — PÁGINAS SIN REGISTRO"); sep("=")
    print(f"  Total registradas   : {total}")
    sep()
    print("  Por categoría:")
    for r in conn.execute("SELECT categoria, count(*) n FROM paginas_sin_registro GROUP BY categoria ORDER BY n DESC").fetchall():
        print(f"    {(r['categoria'] or 'Sin cat'):<22}: {r['n']}")
    sep("=")

def stats_global(conn):
    pc     = conn.execute("SELECT count(*) FROM files").fetchone()[0]
    apps   = conn.execute("SELECT count(*) FROM apps").fetchone()[0]
    ctas   = conn.execute("SELECT count(*) FROM cuentas_web").fetchone()[0]
    pags   = conn.execute("SELECT count(*) FROM paginas_sin_registro").fetchone()[0]
    nubes  = sum(len(cargar_cache(r)) for r in [CACHE_YT, CACHE_DRV, CACHE_OD, CACHE_DBX])
    total  = pc + apps + ctas + pags + nubes
    sep("═"); print("🌍 VISTA GLOBAL — TODOS LOS REGISTROS"); sep("═")
    print(f"  📁 Archivos PC          : {pc}")
    print(f"  ☁️  Elementos en nube    : {nubes}")
    print(f"  📱 Apps instaladas       : {apps}")
    print(f"  🔑 Cuentas web           : {ctas}")
    print(f"  🔖 Páginas sin registro  : {pags}")
    sep()
    print(f"  ▶ TOTAL GENERAL         : {total}")
    sep("═")

def menu_estadisticas(conn):
    while True:
        print("\n" + "═"*60)
        print("📊  ESTADÍSTICAS")
        print("═"*60)
        print("1. 📁  Archivos PC")
        print("2. ☁️   Nubes  (caché)")
        print("3. 📱  Apps instaladas")
        print("4. 🔑  Cuentas web")
        print("5. 🔖  Páginas sin registro")
        print("6. 🌍  Vista Global")
        print("─"*60)
        print("7. 🔙  Volver al menú anterior")
        print("0. 🏠  Menú principal")
        print("═"*60)
        opc = input("Elige (0-7): ").strip()
        if   opc == '1': stats_archivos_pc(conn)
        elif opc == '2': stats_nubes()
        elif opc == '3': stats_apps(conn)
        elif opc == '4': stats_cuentas(conn)
        elif opc == '5': stats_paginas(conn)
        elif opc == '6': stats_global(conn)
        elif opc in ('7', 'q'): break
        elif opc == '0': return VOLVER_PRINCIPAL

# ══════════════════════════════════════════════════════════════════════════════
#  MÓDULO 3 — BUSCAR Y EDITAR
# ══════════════════════════════════════════════════════════════════════════════

def abrir_recurso(path, resource_type=None):
    try:
        if resource_type == 'web' or path.startswith('http'):
            print(f"🚀 Abriendo: {path}")
            webbrowser.open(path)
        else:
            if os.path.exists(path):
                print(f"🚀 Abriendo: {path}")
                os.startfile(path)
            else:
                print(f"❌ El archivo ya no existe en: {path}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ── Buscar archivos PC ────────────────────────────────────────────────────────
def buscar_archivos_pc(conn):
    c = conn.cursor()
    c.execute("SELECT DISTINCT value FROM metadata WHERE key='tag' ORDER BY value ASC")
    todas = [r['value'] for r in c.fetchall()]
    sep("=")
    print("🔍 BUSCAR ARCHIVOS PC")
    print("  ENTER = sin filtro | TAB = autocompletar tag | coma = separar ext. múltiples")
    sep("=")
    print(f"  {'CAMPO':<18} | {'INCLUIR (con esto)':<25} | {'EXCLUIR (sin esto)'}")
    sep("-")

    print(f"  {'Nombre/Ruta':<18} | ", end="")
    ubicacion = input("").strip()
    print(f"  {'':18}   ", end="")
    excluir_ubic = input("⛔ Excluir ruta: ").strip()

    tag_raw = ingresar_tags_interactivo(todas, unico=True, prefijo=f"  {'Tag incluir':<18} | ")
    tag = tag_raw.replace(",", "").strip()
    excluir_tag_raw = ingresar_tags_interactivo(todas, unico=True, prefijo=f"  {'Tag excluir':<18} | ")
    excluir_tag = excluir_tag_raw.replace(",", "").strip()

    dias = input(f"  {'Ultimos N dias':<18} | ").strip()

    print(f"  {'Ext. (coma=varios)':<18} | ", end="")
    tipo_raw = input("").strip()         # ej: "pdf, docx" o "pdf"
    print(f"  {'':18}   ", end="")
    excluir_tipo_raw = input("⛔ Excluir ext: ").strip()  # ej: "txt, ini"

    print(f"  {'Tiene info (s/n)':<18} | ", end="")
    tiene_info = input("").strip().lower()   # 's' = con info | 'n' = sin info | else = todos
    sep()

    def _parse_exts(raw):
        """Convierte 'pdf, docx' → ['.pdf', '.docx']; 'web' → ['__web__']"""
        result = []
        for t in [x.strip().lower() for x in raw.split(',') if x.strip()]:
            if t in ('web', 'link', 'url'):
                result.append('__web__')
            else:
                result.append(t if t.startswith('.') else '.' + t)
        return result

    tipos_inc = _parse_exts(tipo_raw)
    tipos_exc = _parse_exts(excluir_tipo_raw)

    q = "SELECT f.id, f.filename, f.path, f.resource_type, f.modified_at, d.description FROM files f LEFT JOIN descriptions d ON f.id=d.file_id WHERE 1=1"
    params = []
    # Inclusivos
    if ubicacion: q += " AND f.path LIKE ?"; params.append(f"%{ubicacion}%")
    if tag:       q += " AND f.id IN (SELECT file_id FROM metadata WHERE key='tag' AND value LIKE ?)"; params.append(f"%{tag}%")
    if dias.isdigit(): q += f" AND f.modified_at >= datetime('now','-{dias} days')"
    if tipos_inc:
        if tipos_inc == ['__web__']:
            q += " AND f.resource_type='web'"
        elif '__web__' in tipos_inc:
            exts = [e for e in tipos_inc if e != '__web__']
            ph = ','.join('?' * len(exts))
            q += f" AND (f.resource_type='web' OR lower(f.extension) IN ({ph}))"
            params.extend(exts)
        else:
            ph = ','.join('?' * len(tipos_inc))
            q += f" AND lower(f.extension) IN ({ph})"
            params.extend(tipos_inc)
    # Exclusivos
    if excluir_ubic: q += " AND f.path NOT LIKE ?"; params.append(f"%{excluir_ubic}%")
    if excluir_tag:  q += " AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag' AND value LIKE ?)"; params.append(f"%{excluir_tag}%")
    if tipos_exc:
        if tipos_exc == ['__web__']:
            q += " AND f.resource_type != 'web'"
        elif '__web__' in tipos_exc:
            exts = [e for e in tipos_exc if e != '__web__']
            ph = ','.join('?' * len(exts))
            q += f" AND f.resource_type != 'web' AND lower(f.extension) NOT IN ({ph})"
            params.extend(exts)
        else:
            ph = ','.join('?' * len(tipos_exc))
            q += f" AND (f.extension IS NULL OR lower(f.extension) NOT IN ({ph}))"
            params.extend(tipos_exc)
    # Filtro por info
    if tiene_info == 's':
        q += " AND (d.id IS NOT NULL OR f.id IN (SELECT file_id FROM metadata WHERE key='tag'))"
    elif tiene_info == 'n':
        q += " AND d.id IS NULL AND f.id NOT IN (SELECT file_id FROM metadata WHERE key='tag')"
    q += " ORDER BY f.modified_at DESC"
    rows = c.execute(q, params).fetchall()
    if not rows: print("❌ Sin resultados."); return

    page, ps = 1, 20
    total = len(rows)
    pages = math.ceil(total / ps)
    while True:
        start = (page - 1) * ps
        chunk = rows[start:start + ps]
        sep("=")
        print(f"Página {page}/{pages} — {total} resultados")
        sep()
        print(f"{'N.':<4} | {'ID':<6} | {'Nombre':<42} | {'Fecha':<12} | Info")
        sep()
        for i, r in enumerate(chunk):
            gi    = start + i + 1
            fecha = (r['modified_at'] or '')[:10]
            nom   = r['filename'][:39] + "..." if len(r['filename']) > 42 else r['filename']
            tiene = c.execute("SELECT 1 FROM metadata WHERE file_id=? AND key='tag' LIMIT 1", (r['id'],)).fetchone()
            est   = "[+]" if (r['description'] or tiene) else "[ ]"
            print(f"{gi:<4} | {r['id']:<6} | {nom:<42} | {fecha:<12} | {est}")
        sep()
        print("[N] Detalles/Editar | [oN] Abrir archivo | [fN] Ir a carpeta | [s/a] Páginas | [q] Volver | [0] Menú principal")
        opc = input("> ").strip().lower()
        if opc == 'q': break
        elif opc == '0': return VOLVER_PRINCIPAL
        elif opc == 's' and page < pages: page += 1
        elif opc == 'a' and page > 1:    page -= 1
        elif opc.startswith('f') and opc[1:].isdigit():
            idx = int(opc[1:])
            if 1 <= idx <= total:
                path = rows[idx-1]['path']
                rtype = rows[idx-1]['resource_type']
                if rtype != 'web' and os.path.exists(path):
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(path)}"', shell=True)
                    print(f"📂 Abriendo carpeta de: {os.path.basename(path)}")
                else:
                    print("⚠️ Solo disponible para archivos locales existentes.")
        elif opc.startswith('o') and opc[1:].isdigit():
            idx = int(opc[1:])
            if 1 <= idx <= total: abrir_recurso(rows[idx-1]['path'], rows[idx-1]['resource_type'])
        elif opc.isdigit():
            idx = int(opc)
            if 1 <= idx <= total:
                res = _editar_archivo_pc(conn, rows[idx-1]['id'])
                if res == VOLVER_PRINCIPAL: return VOLVER_PRINCIPAL
                rows = c.execute(q, params).fetchall(); total = len(rows)

def _editar_archivo_pc(conn, file_id):
    c = conn.cursor()
    arch  = c.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    desc_row = c.execute("SELECT description FROM descriptions WHERE file_id=?", (file_id,)).fetchone()
    tags  = [r['value'] for r in c.execute("SELECT value FROM metadata WHERE file_id=? AND key='tag'", (file_id,)).fetchall()]
    while True:
        sep("#"); print("🔍 DETALLE DEL ARCHIVO"); sep("#")
        print(f"Nombre : {arch['filename']}")
        print(f"Ruta   : {arch['path']}")
        print(f"Desc   : {desc_row['description'] if desc_row else '⚠️ Sin descripción'}")
        print(f"Tags   : {', '.join(tags) if tags else '⚠️ Sin etiquetas'}")
        mostrar_relaciones(conn, "files", file_id)
        sep()
        print("1. ✏️ Desc | 2. 🏷️ Tags | 3. 🗑️ Limpiar tags | 4. 🚀 Abrir | 5. 📂 Ir a carpeta | 6. 🔗 Relaciones | 7. 🔙 Volver | 0. 🏠 Principal")
        opc = input("> ").strip()
        if opc == '0': return VOLVER_PRINCIPAL
        elif opc == '1':
            nd = input("Nueva descripción: ").strip()
            if nd:
                if desc_row: c.execute("UPDATE descriptions SET description=?,source='Manual' WHERE file_id=?", (nd, file_id))
                else:        c.execute("INSERT INTO descriptions(file_id,description,source,model_used) VALUES(?,?,'Manual','None')", (file_id, nd))
                conn.commit(); desc_row = {'description': nd}; print("✅ Guardado.")
        elif opc == '2':
            nt = ingresar_tags_interactivo(get_all_tags(conn), "🏷️ Tags (TAB=autocompletar):")
            if nt:
                for t in [t.strip() for t in nt.split(",") if t.strip()]:
                    if t not in tags:
                        c.execute("INSERT INTO metadata(file_id,key,value) VALUES(?,'tag',?)", (file_id, t))
                        tags.append(t)
                conn.commit(); print("✅ Tags guardados.")
        elif opc == '3':
            if input("⚠️ ¿Limpiar tags? (s/n): ").lower() == 's':
                c.execute("DELETE FROM metadata WHERE file_id=? AND key='tag'", (file_id,))
                conn.commit(); tags = []; print("🗑️ Limpio.")
        elif opc == '4': abrir_recurso(arch['path'], arch['resource_type'])
        elif opc == '5':
            path = arch['path']
            if arch['resource_type'] != 'web' and os.path.exists(path):
                subprocess.Popen(f'explorer /select,"{os.path.abspath(path)}"', shell=True)
                print(f"📂 Carpeta abierta y archivo seleccionado.")
            else:
                print("⚠️ Solo para archivos locales existentes.")
        elif opc == '6': menu_relaciones(conn, "files", file_id)
        elif opc in ('7', 'q'): break

# ── Buscar en nubes ───────────────────────────────────────────────────────────
CACHE_MAP = {
    "youtube":  CACHE_YT,
    "drive":    CACHE_DRV,
    "onedrive": CACHE_OD,
    "dropbox":  CACHE_DBX,
}

def _origen_a_cache(origen):
    """Devuelve la ruta del cache JSON dado el origen de un item."""
    o = origen.lower()
    if 'youtube'  in o: return CACHE_YT
    if 'drive'    in o: return CACHE_DRV
    if 'onedrive' in o: return CACHE_OD
    if 'dropbox'  in o: return CACHE_DBX
    return None

def _ver_editar_nube(item):
    """Muestra detalles de un elemento de caché y permite editar nombre/comentario/tags."""
    cache_file = _origen_a_cache(item.get('origen', ''))
    while True:
        sep("#"); print(f"☁️  {item.get('nombre','Sin nombre').upper()}"); sep("#")
        print(f"Origen     : {item.get('origen','—')}")
        print(f"Link       : {item.get('link','—')}")
        print(f"Comentario : {item.get('comentario','—')}")
        print(f"Tags       : {item.get('tags','—')}")
        sep()
        print("1. 🚀 Abrir | 2. ✏️ Nombre | 3. ✏️ Comentario | 4. 🏷️ Tags | 5. 🔙 Volver | 0. 🏠 Principal")
        opc = input("> ").strip()
        if opc == '0': return VOLVER_PRINCIPAL
        elif opc == '1': abrir_recurso(item.get('link',''))
        elif opc == '2':
            nd = input(f"Nombre [{item['nombre']}]: ").strip()
            if nd and cache_file:
                datos = cargar_cache(cache_file)
                for d in datos:
                    if d.get('id') == item.get('id'):
                        d['nombre'] = nd; item['nombre'] = nd; break
                guardar_cache(cache_file, datos); print("✅ Guardado.")
        elif opc == '3':
            nc = input(f"Comentario [{item.get('comentario','')}]: ").strip()
            if nc and cache_file:
                datos = cargar_cache(cache_file)
                for d in datos:
                    if d.get('id') == item.get('id'):
                        d['comentario'] = nc; item['comentario'] = nc; break
                guardar_cache(cache_file, datos); print("✅ Guardado.")
        elif opc == '4':
            print("🏷️ Tags actuales:", item.get('tags', '(ninguno)'))
            print("Ingresa tags separados por coma (se reemplazarán los actuales):")
            nt = input("> ").strip()
            if nt and cache_file:
                datos = cargar_cache(cache_file)
                for d in datos:
                    if d.get('id') == item.get('id'):
                        d['tags'] = nt; item['tags'] = nt; break
                guardar_cache(cache_file, datos); print("✅ Tags guardados.")
        elif opc in ('5', 'q'): break

def buscar_nubes():
    todos = []
    for ruta in [CACHE_YT, CACHE_DRV, CACHE_OD, CACHE_DBX]:
        todos.extend(cargar_cache(ruta))
    if not todos:
        print("⚠️ Caché vacío. Ve a Agregar > Sincronizar Nubes primero.")
        return
    # Tags disponibles en los JSON de caché
    tags_nube = sorted({t.strip() for item in todos for t in (item.get('tags') or '').split(',') if t.strip()})
    sep("=")
    print(f"☁️  BUSCAR EN NUBES — {len(todos)} elementos en caché")
    print("  ENTER = sin filtro | TAB = autocompletar tag")
    sep("=")
    print(f"  {'CAMPO':<18} | {'INCLUIR (con esto)':<25} | {'EXCLUIR (sin esto)'}")
    sep("-")

    filtro      = input(f"  {'Origen(yt/drv/od/dbx)':<18} | ").strip().lower()

    print(f"  {'Titulo':<18} | ", end="")
    termino     = input("").strip().lower()
    print(f"  {'':18}   ", end="")
    excluir_txt = input("⛔ Excluir titulo: ").strip().lower()

    tag_f_raw   = ingresar_tags_interactivo(tags_nube, unico=True, prefijo=f"  {'Tag incluir':<18} | ")
    tag_f       = tag_f_raw.replace(",", "").strip().lower()
    excluir_tag_raw = ingresar_tags_interactivo(tags_nube, unico=True, prefijo=f"  {'Tag excluir':<18} | ")
    excluir_tag = excluir_tag_raw.replace(",", "").strip().lower()
    sep()
    res = []
    for item in todos:
        origen_ok     = not filtro      or filtro      in item.get('origen', '').lower()
        texto_ok      = not termino     or termino     in item['nombre'].lower() or termino in item.get('comentario', '').lower()
        excl_txt_ok   = not excluir_txt or (excluir_txt not in item['nombre'].lower() and excluir_txt not in item.get('comentario','').lower())
        tag_ok        = not tag_f       or tag_f       in item.get('tags', '').lower()
        excl_tag_ok   = not excluir_tag or excluir_tag not in item.get('tags', '').lower()
        if origen_ok and texto_ok and excl_txt_ok and tag_ok and excl_tag_ok:
            res.append(item)
    if not res: print("❌ Sin coincidencias."); return

    page, ps = 0, 20
    total = len(res)
    while True:
        inicio = page * ps
        chunk  = res[inicio:inicio + ps]
        pages  = max(1, (total + ps - 1) // ps)
        sep("=")
        print(f"☁️  {total} resultados — Página {page+1}/{pages}")
        sep()
        for i, r in enumerate(chunk):
            gi  = inicio + i
            nom = r['nombre'][:68] + "..." if len(r['nombre']) > 71 else r['nombre']
            tags_s = f" [{r['tags']}]" if r.get('tags') else ""
            print(f"[{gi:>3}] {r.get('origen','?'):<12} | {nom}{tags_s}")
        sep()
        print("[N] Ver/Editar | [oN] Abrir enlace | [s/a] Páginas | [q] Volver | [0] Principal")
        opc = input("> ").strip().lower()
        if opc == 'q': break
        elif opc == '0': return VOLVER_PRINCIPAL
        elif opc == 's' and page + 1 < pages: page += 1
        elif opc == 'a' and page > 0:         page -= 1
        elif opc.startswith('o') and opc[1:].isdigit():
            n = int(opc[1:])
            if 0 <= n < total: abrir_recurso(res[n]['link'])
        elif opc.isdigit():
            n = int(opc)
            if 0 <= n < total:
                r2 = _ver_editar_nube(res[n])
                if r2 == VOLVER_PRINCIPAL: return VOLVER_PRINCIPAL

# ── Buscar apps ───────────────────────────────────────────────────────────────
def buscar_apps(conn):
    sep("=")
    print("📱 BUSCAR APPS")
    print("  ENTER = sin filtro | TAB = autocompletar tag")
    sep("=")
    print(f"  {'CAMPO':<18} | {'INCLUIR (con esto)':<25} | {'EXCLUIR (sin esto)'}")
    sep("-")

    print(f"  {'Nombre':<18} | ", end="")
    nom          = input("").strip()
    print(f"  {'':18}   ", end="")
    excluir_nom  = input("⛔ Excluir nombre: ").strip()

    plat         = input(f"  {'Plataforma':<18} | ").strip()
    cat          = input(f"  {'Categoria':<18} | ").strip()
    est          = input(f"  {'Estado':<18} | ").strip()

    tag_f_raw    = ingresar_tags_interactivo(get_all_tags(conn), unico=True, prefijo=f"  {'Tag incluir':<18} | ")
    tag_f        = tag_f_raw.replace(",", "").strip()
    excluir_tag_raw = ingresar_tags_interactivo(get_all_tags(conn), unico=True, prefijo=f"  {'Tag excluir':<18} | ")
    excluir_tag  = excluir_tag_raw.replace(",", "").strip()
    sep()
    q = "SELECT * FROM apps WHERE 1=1"
    p = []
    # Inclusivos
    if nom:        q += " AND nombre LIKE ?";    p.append(f"%{nom}%")
    if plat:       q += " AND plataforma LIKE ?"; p.append(f"%{plat}%")
    if cat:        q += " AND categoria LIKE ?";  p.append(f"%{cat}%")
    if est:        q += " AND estado LIKE ?";     p.append(f"%{est}%")
    if tag_f:      q += " AND tags LIKE ?";       p.append(f"%{tag_f}%")
    # Exclusivos
    if excluir_nom: q += " AND nombre NOT LIKE ?"; p.append(f"%{excluir_nom}%")
    if excluir_tag: q += " AND (tags IS NULL OR tags NOT LIKE ?)"; p.append(f"%{excluir_tag}%")
    q += " ORDER BY plataforma, nombre ASC"
    rows = conn.execute(q, p).fetchall()
    if not rows: print("❌ Sin resultados."); return
    sep("=")
    print(f"{'N.':<4} | {'ID':<5} | {'Nombre':<24} | {'Plataforma':<10} | {'Estado':<14} | {'Tags'}")
    sep()
    for i, r in enumerate(rows, 1):
        nom_s = r['nombre'][:22] + ".." if len(r['nombre']) > 24 else r['nombre']
        print(f"{i:<4} | {r['id']:<5} | {nom_s:<24} | {r['plataforma']:<10} | {r['estado']:<14} | {r['tags'] or '—'}")
    sep()
    sel = input("Número para ver/editar (ENTER salir): ").strip()
    if sel.isdigit():
        n = int(sel)
        if 1 <= n <= len(rows):
            _editar_app(conn, rows[n-1]['id'])

def _editar_app(conn, app_id):
    while True:
        r = conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone()
        if not r: break
        sep("#"); print(f"📱 {r['nombre'].upper()}"); sep("#")
        print(f"Plataforma : {r['plataforma']}")
        print(f"Categoría  : {r['categoria'] or '—'}")
        print(f"Versión    : {r['version'] or '—'}")
        print(f"Estado     : {r['estado']}")
        print(f"Gratuita   : {'Sí' if r['es_gratis'] else 'No'}")
        print(f"Link       : {r['link_tienda'] or '—'}")
        print(f"Tags       : {r['tags'] or '—'}")
        print(f"Notas      : {r['notas'] or '—'}")
        mostrar_relaciones(conn, "apps", app_id)
        sep()
        print("1. ✏️ Editar | 2. 🔗 Abrir link | 3. 🗑️ Eliminar | 4. 🔗 Relaciones | 5. 🔙 Volver")
        opc = input("> ").strip()
        if opc == '1':
            upd = {}
            for col, prompt in [('nombre', f"Nombre [{r['nombre']}]: "), ('version', f"Versión [{r['version']}]: "),
                                  ('link_tienda', f"Link [{r['link_tienda']}]: "), ('notas', f"Notas: ")]:
                v = input(prompt).strip()
                if v: upd[col] = v
            print(f"🏷️ Tags [{r['tags']}] (TAB=autocompletar, ENTER=mantener):")
            nt = ingresar_tags_interactivo(get_all_tags(conn))
            if nt.strip(): upd['tags'] = nt.strip()
            if input("¿Cambiar plataforma? (s/n): ").lower() == 's':
                upd['plataforma'] = elegir_de_lista(PLATAFORMAS, "Nueva plataforma")
            if input("¿Cambiar estado? (s/n): ").lower() == 's':
                upd['estado'] = elegir_de_lista(["Instalada", "Desinstalada", "Pendiente"], "Nuevo estado")
            if upd:
                conn.execute(f"UPDATE apps SET {', '.join(f'{k}=?' for k in upd)} WHERE id=?", list(upd.values()) + [app_id])
                conn.commit(); print("✅ Guardado.")
        elif opc == '2':
            if r['link_tienda']: webbrowser.open(r['link_tienda'])
            else: print("⚠️ Sin link.")
        elif opc == '3':
            if input(f"⚠️ ¿Eliminar '{r['nombre']}'? (s/n): ").lower() == 's':
                conn.execute("DELETE FROM apps WHERE id=?", (app_id,)); conn.commit(); print("🗑️ Eliminada."); break
        elif opc == '4': menu_relaciones(conn, "apps", app_id)
        elif opc == '5': break

# ── Buscar cuentas web ────────────────────────────────────────────────────────
def buscar_cuentas(conn):
    sep("=")
    print("🔑 BUSCAR CUENTAS WEB")
    print("  ENTER = sin filtro | TAB = autocompletar tag")
    sep("=")
    print(f"  {'CAMPO':<18} | {'INCLUIR (con esto)':<25} | {'EXCLUIR (sin esto)'}")
    sep("-")

    print(f"  {'Sitio':<18} | ", end="")
    sitio        = input("").strip()
    print(f"  {'':18}   ", end="")
    excluir_sit  = input("⛔ Excluir sitio: ").strip()

    cat          = input(f"  {'Categoria':<18} | ").strip()
    est          = input(f"  {'Estado':<18} | ").strip()

    tag_f_raw    = ingresar_tags_interactivo(get_all_tags(conn), unico=True, prefijo=f"  {'Tag incluir':<18} | ")
    tag_f        = tag_f_raw.replace(",", "").strip()
    excluir_tag_raw = ingresar_tags_interactivo(get_all_tags(conn), unico=True, prefijo=f"  {'Tag excluir':<18} | ")
    excluir_tag  = excluir_tag_raw.replace(",", "").strip()
    sep()
    q = "SELECT * FROM cuentas_web WHERE 1=1"
    p = []
    # Inclusivos
    if sitio:       q += " AND sitio LIKE ?";    p.append(f"%{sitio}%")
    if cat:         q += " AND categoria LIKE ?"; p.append(f"%{cat}%")
    if est:         q += " AND estado LIKE ?";    p.append(f"%{est}%")
    if tag_f:       q += " AND tags LIKE ?";      p.append(f"%{tag_f}%")
    # Exclusivos
    if excluir_sit: q += " AND sitio NOT LIKE ?"; p.append(f"%{excluir_sit}%")
    if excluir_tag: q += " AND (tags IS NULL OR tags NOT LIKE ?)"; p.append(f"%{excluir_tag}%")
    q += " ORDER BY categoria, sitio ASC"
    rows = conn.execute(q, p).fetchall()
    if not rows: print("❌ Sin resultados."); return
    sep("=")
    print(f"{'N.':<4} | {'ID':<5} | {'Sitio':<22} | {'Email/Usuario':<22} | {'Estado':<14} | {'2FA'} | {'Tags'}")
    sep()
    for i, r in enumerate(rows, 1):
        sit  = r['sitio'][:20] + ".." if len(r['sitio']) > 22 else r['sitio']
        mail = (r['email_usuario'] or '—')[:20]
        tfa  = "✅" if r['tiene_2fa'] else "❌"
        tags_s = (r['tags'] or '—')[:20]
        print(f"{i:<4} | {r['id']:<5} | {sit:<22} | {mail:<22} | {r['estado']:<14} | {tfa}  | {tags_s}")
    sep(); print(f"Total: {len(rows)}")
    sel = input("Número para ver/editar (ENTER salir): ").strip()
    if sel.isdigit():
        n = int(sel)
        if 1 <= n <= len(rows):
            _editar_cuenta(conn, rows[n-1]['id'])

def _editar_cuenta(conn, cid):
    while True:
        r = conn.execute("SELECT * FROM cuentas_web WHERE id=?", (cid,)).fetchone()
        if not r: break
        sep("#"); print(f"🌐 {r['sitio'].upper()}"); sep("#")
        print(f"URL          : {r['url'] or '—'}")
        print(f"Categoría    : {r['categoria'] or '—'}")
        print(f"Email/Usuario: {r['email_usuario'] or '—'}")
        print(f"Estado       : {r['estado']}")
        print(f"Plan         : {r['plan']}")
        print(f"2FA          : {'✅ Sí' if r['tiene_2fa'] else '❌ No'}")
        print(f"Tags         : {r['tags'] or '—'}")
        print(f"Notas        : {r['notas'] or '—'}")
        mostrar_relaciones(conn, "cuentas_web", cid)
        sep()
        print("1. ✏️ Editar | 2. 🔗 Abrir sitio | 3. 🗑️ Eliminar | 4. 🔗 Relaciones | 5. 🔙 Volver")
        opc = input("> ").strip()
        if opc == '1':
            upd = {}
            for col, pr in [('sitio', f"Sitio [{r['sitio']}]: "), ('url', f"URL [{r['url']}]: "),
                             ('email_usuario', f"Email [{r['email_usuario']}]: "),
                             ('notas', f"Notas: ")]:
                v = input(pr).strip()
                if v: upd[col] = v
            print(f"🏷️ Tags [{r['tags']}] (TAB=autocompletar, ENTER=mantener):")
            nt = ingresar_tags_interactivo(get_all_tags(conn))
            if nt.strip(): upd['tags'] = nt.strip()
            if input("¿Cambiar estado? (s/n): ").lower() == 's':
                upd['estado'] = elegir_de_lista(["Activa", "Inactiva", "Pendiente de verificar", "Eliminada"], "Nuevo estado")
            if input("¿Cambiar plan? (s/n): ").lower() == 's':
                upd['plan'] = elegir_de_lista(["Gratuito", "Premium", "De pago", "Trial"], "Nuevo plan")
            if upd:
                conn.execute(f"UPDATE cuentas_web SET {', '.join(f'{k}=?' for k in upd)} WHERE id=?", list(upd.values()) + [cid])
                conn.commit(); print("✅ Guardado.")
        elif opc == '2':
            if r['url']: webbrowser.open(r['url'])
            else: print("⚠️ Sin URL.")
        elif opc == '3':
            if input(f"⚠️ ¿Eliminar '{r['sitio']}'? (s/n): ").lower() == 's':
                conn.execute("DELETE FROM cuentas_web WHERE id=?", (cid,)); conn.commit(); print("🗑️ Eliminada."); break
        elif opc == '4': menu_relaciones(conn, "cuentas_web", cid)
        elif opc == '5': break

# ── Buscar páginas sin registro ───────────────────────────────────────────────
def buscar_paginas(conn):
    sep("=")
    print("🔖 BUSCAR PÁGINAS SIN REGISTRO")
    print("  ENTER = sin filtro | TAB = autocompletar tag")
    sep("=")
    print(f"  {'CAMPO':<18} | {'INCLUIR (con esto)':<25} | {'EXCLUIR (sin esto)'}")
    sep("-")

    print(f"  {'Nombre':<18} | ", end="")
    nom          = input("").strip()
    print(f"  {'':18}   ", end="")
    excluir_nom  = input("⛔ Excluir nombre: ").strip()

    cat          = input(f"  {'Categoria':<18} | ").strip()

    tag_f_raw    = ingresar_tags_interactivo(get_all_tags(conn), unico=True, prefijo=f"  {'Tag incluir':<18} | ")
    tag_f        = tag_f_raw.replace(",", "").strip()
    excluir_tag_raw = ingresar_tags_interactivo(get_all_tags(conn), unico=True, prefijo=f"  {'Tag excluir':<18} | ")
    excluir_tag  = excluir_tag_raw.replace(",", "").strip()
    sep()
    q   = "SELECT * FROM paginas_sin_registro WHERE 1=1"
    p   = []
    # Inclusivos
    if nom:        q += " AND nombre LIKE ?";    p.append(f"%{nom}%")
    if cat:        q += " AND categoria LIKE ?"; p.append(f"%{cat}%")
    if tag_f:      q += " AND tags LIKE ?";      p.append(f"%{tag_f}%")
    # Exclusivos
    if excluir_nom: q += " AND nombre NOT LIKE ?"; p.append(f"%{excluir_nom}%")
    if excluir_tag: q += " AND (tags IS NULL OR tags NOT LIKE ?)"; p.append(f"%{excluir_tag}%")
    q += " ORDER BY nombre ASC"
    rows = conn.execute(q, p).fetchall()
    if not rows: print("❌ Sin resultados."); return
    sep("=")
    print(f"{'N.':<4} | {'ID':<5} | {'Nombre':<30} | {'Categoría':<20} | {'Tags'}")
    sep()
    for i, r in enumerate(rows, 1):
        nom_s = r['nombre'][:28] + ".." if len(r['nombre']) > 30 else r['nombre']
        print(f"{i:<4} | {r['id']:<5} | {nom_s:<30} | {(r['categoria'] or '—'):<20} | {r['tags'] or '—'}")
    sep(); print(f"Total: {len(rows)}")
    sel = input("Número para ver/editar (ENTER salir): ").strip()
    if sel.isdigit():
        n = int(sel)
        if 1 <= n <= len(rows):
            _editar_pagina(conn, rows[n-1]['id'])

def _editar_pagina(conn, pid):
    while True:
        r = conn.execute("SELECT * FROM paginas_sin_registro WHERE id=?", (pid,)).fetchone()
        if not r: break
        sep("#"); print(f"🔖 {r['nombre'].upper()}"); sep("#")
        print(f"URL         : {r['url']}")
        print(f"Categoría   : {r['categoria'] or '—'}")
        print(f"Descripción : {r['descripcion'] or '—'}")
        print(f"Tags        : {r['tags'] or '—'}")
        print(f"Registrada  : {r['fecha_reg']}")
        sep()
        print("1. ✏️ Editar | 2. 🔗 Abrir URL | 3. 🗑️ Eliminar | 4. 🔙 Volver")
        opc = input("> ").strip()
        if opc == '1':
            upd = {}
            for col, pr in [('nombre', f"Nombre [{r['nombre']}]: "), ('url', f"URL [{r['url']}]: "),
                             ('descripcion', f"Descripción: ")]:
                v = input(pr).strip()
                if v: upd[col] = v
            print(f"🏷️ Tags [{r['tags']}] (TAB=autocompletar, ENTER=mantener):")
            nt = ingresar_tags_interactivo(get_all_tags(conn))
            if nt.strip(): upd['tags'] = nt.strip()
            if input("¿Cambiar categoría? (s/n): ").lower() == 's':
                upd['categoria'] = elegir_de_lista(CAT_WEB, "Nueva categoría")
            if upd:
                conn.execute(f"UPDATE paginas_sin_registro SET {', '.join(f'{k}=?' for k in upd)} WHERE id=?", list(upd.values()) + [pid])
                conn.commit(); print("✅ Guardado.")
        elif opc == '2': abrir_recurso(r['url'])
        elif opc == '3':
            if input(f"⚠️ ¿Eliminar '{r['nombre']}'? (s/n): ").lower() == 's':
                conn.execute("DELETE FROM paginas_sin_registro WHERE id=?", (pid,)); conn.commit(); print("🗑️ Eliminada."); break
        elif opc == '4': break

def menu_buscar(conn):
    while True:
        print("\n" + "═"*60)
        print("🔍  BUSCAR y editar registros en la BD")
        print("═"*60)
        print("1. 📁  Archivos PC")
        print("2. ☁️   Elementos en Nubes  (caché)")
        print("3. 📱  Apps instaladas")
        print("4. 🔑  Cuentas web")
        print("5. 🔖  Páginas sin registro")
        print("─"*60)
        print("6. 🔙  Volver al menú anterior")
        print("0. 🏠  Menú principal")
        print("═"*60)
        opc = input("Elige (0-6): ").strip()
        if   opc == '1':
            if buscar_archivos_pc(conn) == VOLVER_PRINCIPAL: return VOLVER_PRINCIPAL
        elif opc == '2':
            if buscar_nubes() == VOLVER_PRINCIPAL: return VOLVER_PRINCIPAL
        elif opc == '3': buscar_apps(conn)
        elif opc == '4': buscar_cuentas(conn)
        elif opc == '5': buscar_paginas(conn)
        elif opc in ('6', 'q'): break
        elif opc == '0': return VOLVER_PRINCIPAL

# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

def crear_respaldo():
    backup_dir = os.path.join(BASE_DIR, "respaldos")
    os.makedirs(backup_dir, exist_ok=True)
    fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta  = os.path.join(backup_dir, f"respaldo_{fecha}.zip")
    try:
        with zipfile.ZipFile(ruta, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(DB_PATH, "files.db")
        print(f"✅ Respaldo creado: {ruta}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  MENÚ PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def menu_principal():
    conn = get_conn()
    init_tablas(conn)
    while True:
        print("\n" + "█"*60)
        print("█" + " " * 18 + "GESTOR PERSONAL" + " " * 25 + "█")
        print("█"*60)
        print("  1. ➕  AGREGAR archivos a la BD")
        print("  2. 📊  ESTADÍSTICAS")
        print("  3. 🔍  BUSCAR y editar registros en la BD")
        print("  ─────────────────────────────────────────────────")
        print("  4. 💾  Crear Respaldo de Seguridad")
        print("  5. ❌  Salir")
        print("█"*60)
        opc = input("Elige (1-5): ").strip()
        if   opc == '1': menu_agregar(conn)
        elif opc == '2': menu_estadisticas(conn)
        elif opc == '3': menu_buscar(conn)
        elif opc == '4': crear_respaldo()
        elif opc == '5':
            conn.close()
            print("\n¡Hasta luego! 👋")
            break

if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n\nSaliendo...")
