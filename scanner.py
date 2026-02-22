import os
import mimetypes
from pathlib import Path
from datetime import datetime
from database import get_db_connection

# ─────────────────────────────────────────────────────────────────────────────
# REGLAS DE EXCLUSIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Extensiones de archivos de sistema/basura que se ignoran siempre
EXTENSIONES_IGNORADAS = {
    '.ini', '.tmp', '.temp', '.lnk', '.sys', '.dll', '.log',
    '.ds_store', '.thumbs', '.bak',
}

# Nombres de archivo exactos que se ignoran siempre (en minúsculas)
NOMBRES_IGNORADOS = {
    'desktop.ini', 'thumbs.db', '.ds_store', 'ntuser.dat',
    'ntuser.ini', 'ntuser.pol',
}

# Prefijos de carpeta que se saltan (ocultas o de sistema)
CARPETAS_SKIP_PREFIJOS = ('.', '$', '~')

# Longitud máxima del NOMBRE DE ARCHIVO que se guarda en BD
# (el path completo puede ser largo; solo recortamos el campo "filename")
MAX_FILENAME_LEN = 150

# Tamaño del lote para commit a la BD (mejora rendimiento con 12k+ archivos)
BATCH_SIZE = 500


# ─────────────────────────────────────────────────────────────────────────────

def _es_ignorable(file_path: Path) -> bool:
    """Devuelve True si el archivo debe ser omitido."""
    nombre = file_path.name.lower()
    ext    = file_path.suffix.lower()

    if nombre in NOMBRES_IGNORADOS:
        return True
    if ext in EXTENSIONES_IGNORADAS:
        return True
    # Archivos ocultos de Windows/Linux
    if nombre.startswith('.') or nombre.startswith('~'):
        return True
    return False


def _recortar_nombre(filename: str, max_len: int = MAX_FILENAME_LEN) -> str:
    """
    Si el nombre supera max_len, guarda:
      <primeros N chars>...<extensión>
    preservando la extensión para que los filtros por tipo sigan funcionando.
    """
    if len(filename) <= max_len:
        return filename
    suffix = Path(filename).suffix          # ej: ".md"
    stem   = Path(filename).stem            # nombre sin extensión
    recorte = max_len - len(suffix) - 3     # 3 para "..."
    return stem[:recorte] + "..." + suffix


def scan_directory(directory_path: str):
    """
    Escanea el directorio recursivamente y agrega/actualiza archivos en la BD.

    Mejoras respecto a la versión anterior:
    - Omite archivos .ini y otros archivos de sistema/basura.
    - Omite archivos con rutas superiores al límite de Windows (260 chars)
      o que den error de acceso; intenta igualmente guardar los que sí pasan.
    - Recorta nombres excesivamente largos antes de guardarlos en BD.
    - Inserta en lotes (BATCH_SIZE) para mayor rendimiento con miles de archivos.
    """
    conn = get_db_connection()
    c = conn.cursor()

    root_dir = Path(directory_path).resolve()
    if not root_dir.exists():
        print(f"❌ Directorio no encontrado: {directory_path}")
        conn.close()
        return

    print(f"📂 Escaneando: {root_dir}")

    count_new       = 0
    count_updated   = 0
    count_skipped   = 0
    count_errors    = 0
    lote_actual     = 0

    for root, dirs, files in os.walk(root_dir):
        # Saltar carpetas ocultas / de sistema
        dirs[:] = [
            d for d in dirs
            if not d.lower().startswith(CARPETAS_SKIP_PREFIJOS)
        ]

        for file in files:
            # ── Construcción segura del path ──────────────────────────────
            try:
                file_path = Path(root) / file
                path_str  = str(file_path)
            except Exception:
                count_errors += 1
                continue

            # ── Regla 1: ignorar archivos de sistema/basura ───────────────
            if _es_ignorable(file_path):
                count_skipped += 1
                continue

            # ── Regla 2: path demasiado largo para Windows ────────────────
            if len(path_str) > 260:
                # Intentamos con el prefijo \\?\ que levanta el límite
                path_str_ext = "\\\\?\\" + path_str
                try:
                    file_path_ext = Path(path_str_ext)
                    stats = file_path_ext.stat()
                except Exception:
                    # Si aún falla, guardamos el registro con datos básicos
                    # usando el nombre recortado — el path queda truncado
                    filename_guardado = _recortar_nombre(file)
                    path_guardado     = path_str[:255]  # recorte de emergencia
                    extension         = file_path.suffix.lower()
                    try:
                        c.execute(
                            "SELECT id FROM files WHERE path = ?",
                            (path_guardado,)
                        )
                        if not c.fetchone():
                            c.execute(
                                "INSERT INTO files (path, filename, extension, size, created_at, modified_at) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                (path_guardado, filename_guardado, extension,
                                 0, datetime.now(), datetime.now())
                            )
                            count_new += 1
                            lote_actual += 1
                    except Exception:
                        count_errors += 1
                    continue
                # Si el prefijo funcionó, usamos stats de la ruta extendida
                size        = stats.st_size
                created_at  = datetime.fromtimestamp(stats.st_ctime)
                modified_at = datetime.fromtimestamp(stats.st_mtime)
                extension   = file_path.suffix.lower()
                filename_guardado = _recortar_nombre(file)
            else:
                # ── Caso normal ───────────────────────────────────────────
                try:
                    stats = file_path.stat()
                except PermissionError:
                    count_errors += 1
                    continue
                except Exception:
                    count_errors += 1
                    continue
                size              = stats.st_size
                created_at        = datetime.fromtimestamp(stats.st_ctime)
                modified_at       = datetime.fromtimestamp(stats.st_mtime)
                extension         = file_path.suffix.lower()
                filename_guardado = _recortar_nombre(file)

            # ── Insertar o actualizar en BD ───────────────────────────────
            try:
                c.execute("SELECT id FROM files WHERE path = ?", (path_str,))
                existing = c.fetchone()

                if existing:
                    c.execute(
                        "UPDATE files SET size=?, modified_at=?, created_at=? WHERE id=?",
                        (size, modified_at, created_at, existing['id'])
                    )
                    count_updated += 1
                else:
                    c.execute(
                        "INSERT INTO files (path, filename, extension, size, created_at, modified_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (path_str, filename_guardado, extension,
                         size, created_at, modified_at)
                    )
                    count_new += 1

                lote_actual += 1

                # ── Commit por lotes ──────────────────────────────────────
                if lote_actual >= BATCH_SIZE:
                    conn.commit()
                    lote_actual = 0
                    print(f"  💾 Lote guardado — nuevos: {count_new}, actualizados: {count_updated} …")

            except Exception as e:
                count_errors += 1

    # Commit final con lo que quede en el buffer
    conn.commit()
    conn.close()

    print(f"\n✅ Escaneo completo.")
    print(f"   📥 Nuevos       : {count_new}")
    print(f"   🔄 Actualizados : {count_updated}")
    print(f"   ⏭️  Omitidos     : {count_skipped}  (archivos de sistema)")
    print(f"   ❌ Errores      : {count_errors}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        scan_directory(sys.argv[1])
    else:
        print("Uso: python scanner.py <ruta_directorio>")
