import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "files.db")

print(f"Conectando a la base de datos: {db_path}\n")

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Obtener el número total de archivos
    c.execute("SELECT COUNT(*) FROM files")
    total_files = c.fetchone()[0]
    print(f"Total de archivos indexados: {total_files}")
    print("-" * 40)

    # Mostrar los últimos 5 archivos agregados
    c.execute("SELECT filename, size, path FROM files ORDER BY id DESC LIMIT 5")
    archivos = c.fetchall()

    if archivos:
        print("Últimos 5 archivos en la base de datos:")
        for idx, archivo in enumerate(archivos, 1):
            nombre, tamaño, ruta = archivo
            print(f"{idx}. {nombre} ({tamaño} bytes) - {ruta}")
    else:
        print("La base de datos está vacía.")

except sqlite3.Error as e:
    print(f"Error al conectar o consultar la base de datos: {e}")
finally:
    if conn:
        conn.close()
