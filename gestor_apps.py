import sqlite3
import os
import sys
import webbrowser
import datetime

# Forzar UTF-8 para terminales Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(__file__), "files.db")

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────
PLATAFORMAS = ["Android", "Windows", "Web", "iOS", "Linux", "MacOS", "Otro"]
CATEGORIAS  = [
    "Productividad", "Comunicación", "Entretenimiento", "Educación",
    "Finanzas", "Salud", "Fotografía", "Música", "Seguridad",
    "Desarrollo", "Juegos", "Navegación", "Utilidades", "Otro"
]
CAT_WEB = [
    "Correo / Email", "Redes Sociales", "Trabajo / Freelance", "Almacenamiento en Nube",
    "Educación / Cursos", "Entretenimiento", "Finanzas / Pagos", "Desarrollo / Tech",
    "Noticias / Blogs", "Compras", "Salud", "Juegos", "IA / Herramientas", "Otro"
]

# ─────────────────────────────────────────────
# CONEXIÓN
# ─────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─────────────────────────────────────────────
# INICIALIZAR TABLAS
# ─────────────────────────────────────────────
def init_tablas():
    conn = get_conn()
    # Tabla de apps instaladas
    conn.execute("""
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
        )
    """)
    # Tabla de cuentas web
    conn.execute("""
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
        )
    """)
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def elegir_de_lista(opciones, titulo="Elige una opción"):
    print(f"\n{titulo}:")
    for i, op in enumerate(opciones, 1):
        print(f"  {i}. {op}")
    while True:
        sel = input("> ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(opciones):
            return opciones[int(sel) - 1]
        print("⚠️ Opción inválida.")

def sep(c="-", n=70): print(c * n)

# ══════════════════════════════════════════════
#   MÓDULO DE APPS INSTALADAS
# ══════════════════════════════════════════════

def agregar_app(conn):
    sep("="); print("➕ REGISTRAR NUEVA APLICACIÓN"); sep("=")
    nombre = input("📛 Nombre de la app: ").strip()
    if not nombre: return
    plataforma = elegir_de_lista(PLATAFORMAS, "📱 Plataforma")
    categoria  = elegir_de_lista(CATEGORIAS,  "📂 Categoría")
    version    = input("🔢 Versión (ENTER para omitir): ").strip() or None
    link       = input("🔗 Link de tienda/web (ENTER para omitir): ").strip() or None
    es_gratis  = input("💰 ¿Es gratuita? (s/n): ").strip().lower() != 'n'
    estado     = elegir_de_lista(["Instalada", "Desinstalada", "Pendiente"], "📌 Estado actual")
    notas      = input("📝 Notas (ENTER para omitir): ").strip() or None
    tags       = input("🏷️  Tags separados por coma: ").strip() or None
    fecha      = datetime.datetime.now().strftime("%Y-%m-%d")
    conn.execute("""
        INSERT INTO apps (nombre, plataforma, categoria, version, estado,
                          es_gratis, link_tienda, notas, tags, fecha_reg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (nombre, plataforma, categoria, version, estado,
          1 if es_gratis else 0, link, notas, tags, fecha))
    conn.commit()
    print(f"\n✅ '{nombre}' registrada correctamente.")

def listar_apps(conn):
    sep("="); print("🔍 FILTRAR APLICACIONES"); sep()
    nombre_f = input("📛 Buscar por nombre: ").strip()
    plat_f   = input(f"📱 Plataforma ({'/'.join(PLATAFORMAS[:4])}...): ").strip()
    cat_f    = input("📂 Categoría: ").strip()
    estado_f = input("📌 Estado (Instalada/Desinstalada/Pendiente): ").strip()
    query = "SELECT * FROM apps WHERE 1=1"
    params = []
    if nombre_f: query += " AND nombre LIKE ?";    params.append(f"%{nombre_f}%")
    if plat_f:   query += " AND plataforma LIKE ?"; params.append(f"%{plat_f}%")
    if cat_f:    query += " AND categoria LIKE ?";  params.append(f"%{cat_f}%")
    if estado_f: query += " AND estado LIKE ?";     params.append(f"%{estado_f}%")
    query += " ORDER BY plataforma, nombre ASC"
    rows = conn.execute(query, params).fetchall()
    if not rows: print("\n❌ No se encontraron apps."); return rows
    sep("=")
    print(f"{'N.':<4} | {'Nombre':<25} | {'Plataforma':<10} | {'Categoría':<15} | {'Estado':<12} | {'Gratis'}")
    sep()
    for i, r in enumerate(rows, 1):
        nom = r['nombre'][:23] + ".." if len(r['nombre']) > 25 else r['nombre']
        print(f"{i:<4} | {nom:<25} | {r['plataforma']:<10} | {(r['categoria'] or ''):<15} | {r['estado']:<12} | {'Sí' if r['es_gratis'] else 'No'}")
    sep(); print(f"Total: {len(rows)} apps")
    return rows

def ver_editar_app(conn, app_id):
    while True:
        r = conn.execute("SELECT * FROM apps WHERE id = ?", (app_id,)).fetchone()
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
        sep()
        print("1. ✏️ Editar | 2. 🔗 Abrir link | 3. 🗑️ Eliminar | 4. 🔙 Volver")
        opc = input("> ").strip()
        if opc == '1':
            updates = {}
            for col, prompt in [('nombre', f"Nombre [{r['nombre']}]: "), ('version', f"Versión [{r['version']}]: "),
                                 ('link_tienda', f"Link [{r['link_tienda']}]: "), ('notas', f"Notas [{r['notas']}]: "),
                                 ('tags', f"Tags [{r['tags']}]: ")]:
                v = input(prompt).strip()
                if v: updates[col] = v
            if input("¿Cambiar plataforma? (s/n): ").lower() == 's':
                updates['plataforma'] = elegir_de_lista(PLATAFORMAS, "Nueva plataforma")
            if input("¿Cambiar estado? (s/n): ").lower() == 's':
                updates['estado'] = elegir_de_lista(["Instalada", "Desinstalada", "Pendiente"], "Nuevo estado")
            if updates:
                conn.execute(f"UPDATE apps SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                             list(updates.values()) + [r['id']])
                conn.commit(); print("✅ Guardado.")
        elif opc == '2':
            if r['link_tienda']: webbrowser.open(r['link_tienda']); print("🚀 Enlace abierto.")
            else: print("⚠️ Sin link.")
        elif opc == '3':
            if input(f"⚠️ ¿Eliminar '{r['nombre']}'? (s/n): ").lower() == 's':
                conn.execute("DELETE FROM apps WHERE id = ?", (app_id,))
                conn.commit(); print("🗑️ Eliminada."); break
        elif opc == '4': break

def estadisticas_apps(conn):
    sep("="); print("📊 ESTADÍSTICAS DE APPS"); sep("=")
    total = conn.execute("SELECT count(*) FROM apps").fetchone()[0]
    print(f"Total registradas: {total}\n")
    print(f"{'Plataforma':<14} | {'Total':>6} | {'Instaladas':>10} | {'Pendientes':>10}")
    sep()
    for p in conn.execute("SELECT DISTINCT plataforma FROM apps ORDER BY plataforma").fetchall():
        pl = p[0]
        tot  = conn.execute("SELECT count(*) FROM apps WHERE plataforma=?", (pl,)).fetchone()[0]
        inst = conn.execute("SELECT count(*) FROM apps WHERE plataforma=? AND estado='Instalada'", (pl,)).fetchone()[0]
        pend = conn.execute("SELECT count(*) FROM apps WHERE plataforma=? AND estado='Pendiente'", (pl,)).fetchone()[0]
        print(f"{pl:<14} | {tot:>6} | {inst:>10} | {pend:>10}")
    sep("=")

# ══════════════════════════════════════════════
#   MÓDULO DE CUENTAS WEB
# ══════════════════════════════════════════════

def agregar_cuenta_web(conn):
    sep("="); print("🌐 REGISTRAR CUENTA WEB / SERVICIO"); sep("=")
    sitio = input("🌐 Nombre del sitio (ej. GitHub, Netflix): ").strip()
    if not sitio: return
    url          = input("🔗 URL del sitio: ").strip() or None
    categoria    = elegir_de_lista(CAT_WEB, "📂 Categoría")
    email_usr    = input("📧 Email o usuario con el que estás registrado: ").strip() or None
    estado       = elegir_de_lista(["Activa", "Inactiva", "Pendiente de verificar", "Eliminada"], "📌 Estado de la cuenta")
    plan         = elegir_de_lista(["Gratuito", "Premium", "De pago", "Trial"], "💳 Plan")
    tiene_2fa    = input("🔐 ¿Tiene autenticación de 2 pasos (2FA)? (s/n): ").strip().lower() == 's'
    notas        = input("📝 Notas adicionales (ENTER para omitir): ").strip() or None
    tags         = input("🏷️  Tags separados por coma: ").strip() or None
    fecha        = datetime.datetime.now().strftime("%Y-%m-%d")
    conn.execute("""
        INSERT INTO cuentas_web (sitio, url, categoria, email_usuario, estado,
                                 plan, tiene_2fa, notas, tags, fecha_reg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sitio, url, categoria, email_usr, estado,
          plan, 1 if tiene_2fa else 0, notas, tags, fecha))
    conn.commit()
    print(f"\n✅ Cuenta en '{sitio}' registrada correctamente.")

def listar_cuentas(conn):
    sep("="); print("🔍 FILTRAR CUENTAS WEB"); sep()
    print("Deja en blanco para no filtrar.")
    sitio_f    = input("🌐 Buscar por nombre de sitio: ").strip()
    cat_f      = input("📂 Categoría: ").strip()
    estado_f   = input("📌 Estado (Activa/Inactiva/...): ").strip()
    plan_f     = input("💳 Plan (Gratuito/Premium/...): ").strip()
    query = "SELECT * FROM cuentas_web WHERE 1=1"
    params = []
    if sitio_f:  query += " AND sitio LIKE ?";    params.append(f"%{sitio_f}%")
    if cat_f:    query += " AND categoria LIKE ?"; params.append(f"%{cat_f}%")
    if estado_f: query += " AND estado LIKE ?";   params.append(f"%{estado_f}%")
    if plan_f:   query += " AND plan LIKE ?";      params.append(f"%{plan_f}%")
    query += " ORDER BY categoria, sitio ASC"
    rows = conn.execute(query, params).fetchall()
    if not rows: print("\n❌ No se encontraron cuentas."); return rows
    sep("=")
    print(f"{'N.':<4} | {'Sitio':<22} | {'Categoría':<20} | {'Email/Usuario':<25} | {'Estado':<12} | {'Plan':<10} | {'2FA'}")
    sep()
    for i, r in enumerate(rows, 1):
        sitio = r['sitio'][:20] + ".." if len(r['sitio']) > 22 else r['sitio']
        cat   = (r['categoria'] or "")[:18]
        email = (r['email_usuario'] or "—")[:23]
        twofa = "✅" if r['tiene_2fa'] else "❌"
        print(f"{i:<4} | {sitio:<22} | {cat:<20} | {email:<25} | {r['estado']:<12} | {r['plan']:<10} | {twofa}")
    sep(); print(f"Total: {len(rows)} cuentas")
    return rows

def ver_editar_cuenta(conn, cuenta_id):
    while True:
        r = conn.execute("SELECT * FROM cuentas_web WHERE id = ?", (cuenta_id,)).fetchone()
        if not r: break
        sep("#"); print(f"🌐 {r['sitio'].upper()}"); sep("#")
        print(f"URL          : {r['url'] or '—'}")
        print(f"Categoría    : {r['categoria'] or '—'}")
        print(f"Email/Usuario: {r['email_usuario'] or '—'}")
        print(f"Estado       : {r['estado']}")
        print(f"Plan         : {r['plan']}")
        print(f"2FA activo   : {'✅ Sí' if r['tiene_2fa'] else '❌ No'}")
        print(f"Tags         : {r['tags'] or '—'}")
        print(f"Notas        : {r['notas'] or '—'}")
        print(f"Registrado   : {r['fecha_reg']}")
        sep()
        print("1. ✏️ Editar | 2. 🔗 Abrir sitio | 3. 🗑️ Eliminar | 4. 🔙 Volver")
        opc = input("> ").strip()
        if opc == '1':
            updates = {}
            for col, prompt in [('sitio', f"Sitio [{r['sitio']}]: "), ('url', f"URL [{r['url']}]: "),
                                 ('email_usuario', f"Email/Usuario [{r['email_usuario']}]: "),
                                 ('notas', f"Notas [{r['notas']}]: "), ('tags', f"Tags [{r['tags']}]: ")]:
                v = input(prompt).strip()
                if v: updates[col] = v
            if input("¿Cambiar estado? (s/n): ").lower() == 's':
                updates['estado'] = elegir_de_lista(["Activa", "Inactiva", "Pendiente de verificar", "Eliminada"], "Nuevo estado")
            if input("¿Cambiar plan? (s/n): ").lower() == 's':
                updates['plan'] = elegir_de_lista(["Gratuito", "Premium", "De pago", "Trial"], "Nuevo plan")
            if input("¿Cambiar 2FA? (s/n): ").lower() == 's':
                updates['tiene_2fa'] = 1 if input("¿Tiene 2FA? (s/n): ").lower() == 's' else 0
            if updates:
                conn.execute(f"UPDATE cuentas_web SET {', '.join(f'{k}=?' for k in updates)} WHERE id=?",
                             list(updates.values()) + [r['id']])
                conn.commit(); print("✅ Guardado.")
        elif opc == '2':
            if r['url']: webbrowser.open(r['url']); print("🚀 Sitio abierto en el navegador.")
            else: print("⚠️ Sin URL registrada.")
        elif opc == '3':
            if input(f"⚠️ ¿Eliminar cuenta en '{r['sitio']}'? (s/n): ").lower() == 's':
                conn.execute("DELETE FROM cuentas_web WHERE id = ?", (cuenta_id,))
                conn.commit(); print("🗑️ Eliminada."); break
        elif opc == '4': break

def estadisticas_cuentas(conn):
    sep("="); print("📊 ESTADÍSTICAS DE CUENTAS WEB"); sep("=")
    total   = conn.execute("SELECT count(*) FROM cuentas_web").fetchone()[0]
    activas = conn.execute("SELECT count(*) FROM cuentas_web WHERE estado='Activa'").fetchone()[0]
    con_2fa = conn.execute("SELECT count(*) FROM cuentas_web WHERE tiene_2fa=1").fetchone()[0]
    premium = conn.execute("SELECT count(*) FROM cuentas_web WHERE plan='Premium' OR plan='De pago'").fetchone()[0]
    print(f"Total de cuentas registradas : {total}")
    print(f"Cuentas activas              : {activas}")
    print(f"Con 2FA habilitado           : {con_2fa}")
    print(f"Con plan de pago             : {premium}")
    sep()
    print("Por categoría:")
    for c in conn.execute("SELECT categoria, count(*) as n FROM cuentas_web GROUP BY categoria ORDER BY n DESC").fetchall():
        print(f"  {c['categoria'] or 'Sin categoría':<22}: {c['n']}")
    sep("=")

# ══════════════════════════════════════════════
#   MENÚ PRINCIPAL DEL MÓDULO
# ══════════════════════════════════════════════

def menu_apps():
    init_tablas()
    conn = get_conn()
    while True:
        sep("=")
        print("📱 GESTOR DE APPS Y CUENTAS")
        sep("=")
        print("── APLICACIONES INSTALADAS ──────────────")
        print("1. ➕ Registrar nueva app")
        print("2. 🔍 Listar / Filtrar apps")
        print("3. 📊 Estadísticas de apps")
        print("── CUENTAS WEB / SERVICIOS ──────────────")
        print("4. 🌐 Registrar cuenta web")
        print("5. 🔍 Listar / Filtrar cuentas web")
        print("6. 📊 Estadísticas de cuentas")
        print("─────────────────────────────────────────")
        print("7. 🔙 Volver al menú principal")
        sep("=")
        opc = input("Elige (1-7): ").strip()

        if opc == '1':
            agregar_app(conn)
        elif opc == '2':
            rows = listar_apps(conn)
            if rows:
                sel = input("\n¿Ver detalles? (número o ENTER para salir): ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(rows):
                    ver_editar_app(conn, rows[int(sel)-1]['id'])
        elif opc == '3':
            estadisticas_apps(conn)
        elif opc == '4':
            agregar_cuenta_web(conn)
        elif opc == '5':
            rows = listar_cuentas(conn)
            if rows:
                sel = input("\n¿Ver detalles? (número o ENTER para salir): ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(rows):
                    ver_editar_cuenta(conn, rows[int(sel)-1]['id'])
        elif opc == '6':
            estadisticas_cuentas(conn)
        elif opc == '7':
            conn.close()
            break

if __name__ == "__main__":
    menu_apps()
