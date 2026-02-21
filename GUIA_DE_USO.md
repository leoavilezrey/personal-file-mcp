# Guía Maestra: Gestor Personal de Archivos y Base de Datos Local

Última actualización: 2026-02-20

Este proyecto es un **gestor interactivo de consola** que centraliza tu información personal:
archivos locales, enlaces web, aplicaciones instaladas, cuentas web y las relaciones entre ellos.

---

## 🏗️ Arquitectura del Proyecto

```
personal_file_mcp/
├── gestor_interactivo.py  ← Menú principal, búsqueda y edición de archivos
├── gestor_apps.py         ← Gestión de apps y cuentas web
├── relaciones.py          ← Sistema de relaciones entre registros
├── scanner.py             ← Escaneo de carpetas
├── database.py            ← Definición de tablas base
├── main.py                ← Servidor MCP (para Claude Desktop)
├── files.db               ← Base de datos SQLite (NO se sube a Git)
├── .env                   ← API Keys (NO se sube a Git)
└── respaldos/             ← Backups automáticos (NO se suben a Git)
```

---

## 🚀 Cómo Arrancar

```powershell
cd c:\Users\DELL\Proyectos\personal_file_mcp
python gestor_interactivo.py
```

> **Nota:** Si ves caracteres raros, el UTF-8 se configura automáticamente al iniciar.

---

## 📋 Menú Principal

```
==================================================
🚀 GESTOR VISUAL DE BASE DE DATOS
==================================================
1. 📊 Ver Estadísticas
2. 🔎 Buscar y Abrir Registros
3. 📂 Escanear y Etiquetar Carpeta
4. 🌐 Guardar Nuevo Enlace Web
5. 🤖 Exportar/Importar para IA
6. 💾 Crear Backup de Seguridad
7. 📱 Gestor de Apps Instaladas
8. ❌ Salir
```

---

## 🔎 Opción 2: Búsqueda de Registros

Permite filtrar por: **ruta/URL**, **etiqueta**, **días**, **tipo de archivo** o registros vacíos.

### Tabla de resultados

```
Nº   | ID BD  | Nombre del Archivo                       | Fecha        | Info
1    | 847    | GUIA_DE_USO.md                           | 2026-02-19   | [ ]
2    | 848    | gestor_interactivo.py                    | 2026-02-19   | [+]
```

- `Nº` = posición en la lista actual
- `ID BD` = ID real en la base de datos (úsalo para crear relaciones)
- `[+]` = tiene descripción o etiquetas / `[ ]` = vacío

### Comandos en la tabla

| Comando | Acción |
|---|---|
| `5` | Ver y editar el registro número 5 |
| `o5` | Abrir directamente el archivo/link número 5 |
| `S` / `A` | Siguiente / Anterior página |
| `Q` | Volver al menú |

---

## 📄 Detalle de un Registro (Archivos)

Al entrar a un registro verás sus datos + sus relaciones automáticamente:

```
######################################################################
🔍 DETALLES DEL REGISTRO
######################################################################
Nombre: GUIA_DE_USO.md
Ruta:   C:\...\GUIA_DE_USO.md
----------------------------------------------------------------------
Descripción: Manual de uso del proyecto
Etiquetas:   guia, documentacion
----------------------------------------------------------------------
🔗 RELACIONADO CON (1):
  1. [App #3] Gestor Visual BD
       └─ Esta guía explica cómo usar esta app
######################################################################
1. 📝 Editar Desc | 2. 🏷️ Agregar Tags | 3. 🗑️ Limpiar Tags | 4. 🚀 Abrir | 5. 🔗 Relaciones | 6. 🔙 Volver
```

---

## 📱 Opción 7: Gestor de Apps y Cuentas

```
── APLICACIONES INSTALADAS ──────────────
1. ➕ Registrar nueva app
2. 🔍 Listar / Filtrar apps
3. 📊 Estadísticas de apps
── CUENTAS WEB / SERVICIOS ──────────────
4. 🌐 Registrar cuenta web
5. 🔍 Listar / Filtrar cuentas web
6. 📊 Estadísticas de cuentas
─────────────────────────────────────────
7. 🔙 Volver al menú principal
```

### Apps — Campos disponibles

| Campo | Valores posibles |
|---|---|
| Plataforma | Android, Windows, Web, iOS, Linux, MacOS, Otro |
| Categoría | Productividad, Comunicación, Entretenimiento, Finanzas, Desarrollo... |
| Estado | Instalada / Desinstalada / Pendiente |
| Gratuita | Sí / No |
| Link de tienda | URL directa |

### Cuentas Web — Campos disponibles

| Campo | Valores posibles |
|---|---|
| Sitio | Nombre del servicio (ej: GitHub, Netflix) |
| Categoría | Correo, Redes Sociales, Desarrollo, Finanzas, IA... |
| Email/Usuario | Con qué cuenta estás registrado |
| Estado | Activa / Inactiva / Pendiente / Eliminada |
| Plan | Gratuito / Premium / De pago / Trial |
| 2FA | ✅ Sí / ❌ No |

---

## 🔗 Sistema de Relaciones Entre Registros

Cualquier registro (archivo, app o cuenta web) puede estar relacionado con cualquier otro.
Las relaciones son **bidireccionales**: si A apunta a B, B también ve a A.

### Cómo crear una relación

1. Entra al detalle de cualquier registro
2. Elige la opción **"Relaciones"**
3. Elige el tipo de destino: `Archivo`, `App` o `Cuenta Web`
4. Escribe el **ID BD** del registro destino (visible en la tabla de listado)
5. Escribe una descripción libre de la relación

### Cómo encontrar el ID de un registro

- En la tabla de búsqueda de archivos: columna **`ID BD`**
- En la tabla de apps: columna **`ID`**
- En la tabla de cuentas web: columna **`ID`**

---

## 🗃️ Tablas en la Base de Datos

| Tabla | Contenido |
|---|---|
| `files` | Archivos locales y enlaces web |
| `descriptions` | Descripciones de archivos |
| `metadata` | Tags y etiquetas (clave-valor) |
| `apps` | Aplicaciones instaladas en dispositivos |
| `cuentas_web` | Servicios web donde tienes cuenta |
| `notas_relacion` | Relaciones entre registros de cualquier tabla |

---

## 💾 Backup y Git

### Backup de la base de datos (desde el menú)
```
Opción 6 → Crear Backup de Seguridad
```
Se guarda un `.zip` en la carpeta `respaldos/`. Súbelo a la nube manualmente.

### Guardar cambios de código en GitHub

```powershell
# 1. Ver qué cambió
git status

# 2. Preparar archivos
git add gestor_interactivo.py gestor_apps.py relaciones.py

# 3. Guardar con mensaje
git commit -m "Descripción del cambio"

# 4. Subir a GitHub
git push origin master
```

> ⚠️ **Nunca** uses `git add .` sin revisar `git status` antes.
> El `.gitignore` ya protege `.env`, `files.db` y `respaldos/`.

---

## 🔌 Conexión con Claude Desktop (Servidor MCP)

Para usar el servidor con Claude Desktop:

```json
{
  "mcpServers": {
    "mis-archivos": {
      "command": "c:\\Users\\DELL\\Proyectos\\personal_file_mcp\\venv\\Scripts\\python.exe",
      "args": ["c:\\Users\\DELL\\Proyectos\\personal_file_mcp\\main.py"]
    }
  }
}
```

Archivo de config: `%APPDATA%\Claude\claude_desktop_config.json`

---

## 📅 Historial de Cambios

| Fecha | Cambio |
|---|---|
| 2026-02-19 | Creación del proyecto base, scanner, servidor MCP |
| 2026-02-20 | Gestor interactivo con búsqueda y paginación |
| 2026-02-20 | Fix de codificación UTF-8 en PowerShell |
| 2026-02-20 | Comando `o[N]` para abrir registros directamente |
| 2026-02-20 | Módulo `gestor_apps.py`: apps instaladas y cuentas web |
| 2026-02-20 | Módulo `relaciones.py`: sistema de relaciones bidireccionales entre registros |
| 2026-02-20 | Columna ID visible en todas las tablas de listado |
