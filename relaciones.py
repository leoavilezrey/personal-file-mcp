"""
relaciones.py
─────────────
Módulo compartido para gestionar relaciones entre registros de cualquier tabla:
    - files (archivos y enlaces web)
    - apps (aplicaciones instaladas)
    - cuentas_web (servicios web registrados)

Las relaciones son BIDIRECCIONALES: crear A→B hace que B también vea a A.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "files.db")

TABLAS_VALIDAS = ["files", "apps", "cuentas_web"]
TABLAS_LABELS  = {"files": "Archivo/Link", "apps": "App", "cuentas_web": "Cuenta Web"}

# ─────────────────────────────────────────────
# INICIALIZAR TABLA
# ─────────────────────────────────────────────
def init_relaciones(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notas_relacion (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            origen_tabla  TEXT    NOT NULL,
            origen_id     INTEGER NOT NULL,
            descripcion   TEXT    NOT NULL,
            destino_tabla TEXT    NOT NULL,
            destino_id    INTEGER NOT NULL,
            fecha_reg     TEXT
        )
    """)
    conn.commit()

# ─────────────────────────────────────────────
# OBTENER NOMBRE LEGIBLE DE UN REGISTRO
# ─────────────────────────────────────────────
def _get_nombre(conn, tabla, record_id):
    """Devuelve el nombre o título del registro según la tabla."""
    try:
        if tabla == "files":
            r = conn.execute("SELECT filename FROM files WHERE id=?", (record_id,)).fetchone()
            return r["filename"] if r else f"(ID {record_id} no encontrado)"
        elif tabla == "apps":
            r = conn.execute("SELECT nombre FROM apps WHERE id=?", (record_id,)).fetchone()
            return r["nombre"] if r else f"(ID {record_id} no encontrado)"
        elif tabla == "cuentas_web":
            r = conn.execute("SELECT sitio FROM cuentas_web WHERE id=?", (record_id,)).fetchone()
            return r["sitio"] if r else f"(ID {record_id} no encontrado)"
    except Exception:
        return f"(error al buscar ID {record_id})"
    return "—"

# ─────────────────────────────────────────────
# VER RELACIONES DE UN REGISTRO
# ─────────────────────────────────────────────
def ver_relaciones(conn, mi_tabla, mi_id):
    """
    Devuelve todas las relaciones de un registro, en ambas direcciones.
    Retorna lista de dicts con info del registro relacionado y la descripción.
    """
    rows = conn.execute("""
        SELECT * FROM notas_relacion
        WHERE (origen_tabla=? AND origen_id=?)
           OR (destino_tabla=? AND destino_id=?)
        ORDER BY fecha_reg DESC
    """, (mi_tabla, mi_id, mi_tabla, mi_id)).fetchall()

    resultados = []
    for r in rows:
        # Determinar cuál es el extremo "otro" (el que no soy yo)
        if r["origen_tabla"] == mi_tabla and r["origen_id"] == mi_id:
            otro_tabla = r["destino_tabla"]
            otro_id    = r["destino_id"]
        else:
            otro_tabla = r["origen_tabla"]
            otro_id    = r["origen_id"]

        otro_nombre = _get_nombre(conn, otro_tabla, otro_id)
        resultados.append({
            "rel_id":      r["id"],
            "otro_tabla":  otro_tabla,
            "otro_id":     otro_id,
            "otro_nombre": otro_nombre,
            "descripcion": r["descripcion"],
            "fecha_reg":   r["fecha_reg"],
        })
    return resultados

# ─────────────────────────────────────────────
# MOSTRAR RELACIONES (para incrustar en la vista de detalle)
# ─────────────────────────────────────────────
def mostrar_relaciones(conn, mi_tabla, mi_id):
    """Imprime el bloque de relaciones. Retorna la lista para otros usos."""
    relaciones = ver_relaciones(conn, mi_tabla, mi_id)
    sep = "-" * 70
    if not relaciones:
        print(f"{sep}\n🔗 Sin relaciones registradas aún.")
    else:
        print(f"{sep}\n🔗 RELACIONADO CON ({len(relaciones)}):")
        for i, rel in enumerate(relaciones, 1):
            label = TABLAS_LABELS.get(rel["otro_tabla"], rel["otro_tabla"])
            print(f"  {i}. [{label} #{rel['otro_id']}] {rel['otro_nombre']}")
            print(f"       └─ {rel['descripcion']}")
    return relaciones

# ─────────────────────────────────────────────
# AGREGAR RELACIÓN
# ─────────────────────────────────────────────
def agregar_relacion(conn, mi_tabla, mi_id):
    """Guía interactiva para crear una relación desde el registro actual."""
    print("\n" + "="*50)
    print("🔗 AGREGAR RELACIÓN CON OTRO REGISTRO")
    print("="*50)

    # 1. Elegir tabla destino
    print("\n¿Con qué tipo de registro quieres relacionarlo?")
    opciones = [t for t in TABLAS_VALIDAS]
    for i, t in enumerate(opciones, 1):
        print(f"  {i}. {TABLAS_LABELS[t]}")
    sel = input("\n> ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(opciones)):
        print("⚠️ Opción inválida."); return
    destino_tabla = opciones[int(sel) - 1]

    # 2. Ingresar ID destino
    print(f"\n📋 Ingresa el ID del {TABLAS_LABELS[destino_tabla]} al que quieres apuntar:")
    id_str = input("ID > ").strip()
    if not id_str.isdigit():
        print("⚠️ Debes ingresar un número."); return
    destino_id = int(id_str)

    # Verificar que existe
    nombre_destino = _get_nombre(conn, destino_tabla, destino_id)
    if "no encontrado" in nombre_destino or "error" in nombre_destino:
        print(f"❌ No existe un registro con ID {destino_id} en '{TABLAS_LABELS[destino_tabla]}'."); return

    # Evitar relacionar consigo mismo
    if destino_tabla == mi_tabla and destino_id == mi_id:
        print("⚠️ No puedes relacionar un registro consigo mismo."); return

    # Verificar que no exista ya esa relación
    existe = conn.execute("""
        SELECT id FROM notas_relacion
        WHERE (origen_tabla=? AND origen_id=? AND destino_tabla=? AND destino_id=?)
           OR (origen_tabla=? AND origen_id=? AND destino_tabla=? AND destino_id=?)
    """, (mi_tabla, mi_id, destino_tabla, destino_id,
          destino_tabla, destino_id, mi_tabla, mi_id)).fetchone()
    if existe:
        print(f"⚠️ Ya existe una relación con '{nombre_destino}'."); return

    print(f"\n✅ Encontrado: [{TABLAS_LABELS[destino_tabla]} #{destino_id}] {nombre_destino}")

    # 3. Escribir descripción
    print("\n📝 Escribe una descripción de esta relación:")
    print("   (ej: 'Este PDF es el manual de esta app', 'Esta cuenta almacena estos archivos')")
    descripcion = input("> ").strip()
    if not descripcion:
        print("⚠️ La descripción no puede estar vacía."); return

    # 4. Guardar
    import datetime
    conn.execute("""
        INSERT INTO notas_relacion
            (origen_tabla, origen_id, descripcion, destino_tabla, destino_id, fecha_reg)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (mi_tabla, mi_id, descripcion, destino_tabla, destino_id,
          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    print(f"\n✅ Relación creada: apunta a [{TABLAS_LABELS[destino_tabla]} #{destino_id}] {nombre_destino}")

# ─────────────────────────────────────────────
# ELIMINAR RELACIÓN
# ─────────────────────────────────────────────
def eliminar_relacion(conn, mi_tabla, mi_id):
    """Muestra las relaciones actuales y permite eliminar una por número."""
    relaciones = ver_relaciones(conn, mi_tabla, mi_id)
    if not relaciones:
        print("ℹ️ No hay relaciones para eliminar."); return

    print("\n🗑️ ¿Cuál relación quieres eliminar?")
    mostrar_relaciones(conn, mi_tabla, mi_id)

    sel = input("\nNúmero de relación a eliminar (o ENTER para cancelar): ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(relaciones)):
        print("Cancelado."); return

    rel = relaciones[int(sel) - 1]
    confirm = input(f"⚠️ ¿Eliminar relación con '{rel['otro_nombre']}'? (s/n): ").lower()
    if confirm == 's':
        conn.execute("DELETE FROM notas_relacion WHERE id=?", (rel["rel_id"],))
        conn.commit()
        print("🗑️ Relación eliminada.")
    else:
        print("Cancelado.")

# ─────────────────────────────────────────────
# MENÚ DE GESTIÓN (llamado desde el detalle de cualquier registro)
# ─────────────────────────────────────────────
def menu_relaciones(conn, mi_tabla, mi_id):
    """Submenú completo de gestión de relaciones para un registro."""
    while True:
        print("\n" + "="*50)
        print("🔗 GESTIONAR RELACIONES")
        print("="*50)
        mostrar_relaciones(conn, mi_tabla, mi_id)
        print("\n1. ➕ Agregar nueva relación")
        print("2. 🗑️  Eliminar una relación")
        print("3. 🔙 Volver")
        opc = input("\n> ").strip()
        if opc == '1':
            agregar_relacion(conn, mi_tabla, mi_id)
        elif opc == '2':
            eliminar_relacion(conn, mi_tabla, mi_id)
        elif opc == '3':
            break
