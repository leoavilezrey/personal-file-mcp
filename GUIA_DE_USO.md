# Guía Maestra: Servidor MCP de Archivos Personales con IA (Gemini)

Esta guía te llevará desde cero hasta tener tu propio "ChatGPT privado" que conoce tus archivos.

## ¿Qué hace este proyecto?
1.  **Lee tus archivos**: Escanea carpetas que tú le indiques.
2.  **Organiza**: Guarda información (nombre, tamaño, fecha) en una base de datos local (`files.db`).
3.  **Analiza con IA**: Usa Google Gemini para leer tus archivos y explicarte qué contienen o etiquetarlos automáticamente.
4.  **Conecta**: Funciona como un "servidor" al que puedes conectar aplicaciones como Claude Desktop.

---

## PASO 1: Instalación (Solo se hace una vez)

1.  **Abrir Terminal**: Abre PowerShell y ve a la carpeta del proyecto:
    ```powershell
    cd c:\Users\DELL\Proyectos\personal_file_mcp
    ```

2.  **Crear Entorno Virtual** (Para no mezclar cosas con tu sistema):
    ```powershell
    python -m venv venv
    ```

3.  **Activar Entorno**:
    ```powershell
    .\venv\Scripts\activate
    ```
    *Verás `(venv)` al principio de la línea.*

4.  **Instalar Librerías**:
    ```powershell
    pip install -r requirements.txt
# Si ya instalaste antes y actualizaste el código, ejecuta esto para actualizar las librerías:
# pip install --upgrade -r requirements.txt

    ```

---

## PASO 2: Configuración de la IA (Tu API Key)

Para que funcione la magia de la IA, necesitamos tu llave de Google.

1.  **Ejecuta el script de ayuda**:
    ```powershell
    python setup_env.py
    ```
2.  **Pega tu API Key**: Cuando te lo pida, pega la clave que obtuviste de Google (Ctrl+V) y presiona Enter.

*Esto creará automáticamente un archivo llamado `.env` con tu configuración.*

---

## PASO 3: Probando el Servidor

Antes de conectarlo a Claude, verifiquemos que vive.

1.  Ejecuta:
    ```powershell
    python main.py
    ```
2.  Si ves mensajes de error, algo falló.
3.  Si **no ves nada** y el cursor se queda parpadeando o esperando, **¡ES BUENA SEÑAL!** Significa que el servidor está corriendo y escuchando.
4.  Presiona `Ctrl+C` para detenerlo por ahora.

---

## PASO 4: Conectar a Claude Desktop

Para hablar con tus archivos desde una interfaz bonita, usamos Claude Desktop.

1.  Abre el archivo de configuración de Claude:
    - Presiona `Windows + R`.
    - Escribe `%APPDATA%\Claude` y Enter.
    - Abre `claude_desktop_config.json` con el Bloc de Notas o VS Code.

2.  Asegúrate que tenga este contenido (Copia y pega con cuidado):

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

3.  Guarda el archivo y reinicia Claude Desktop.

---

## PASO 5: ¡A Usar! (Ejemplos)

Ahora, en el chat de Claude, verás un icono de un enchufe 🔌 que dice "mis-archivos". Puedes hablarle naturalmente:

### 1. Indexar tus documentos (Primero haz esto)
> "Por favor escanea todos los documentos en mi carpeta C:\Users\DELL\Documents\Trabajo"

*El servidor leerá todos los archivos y guardará sus datos básicos en la base de datos `files.db`.*

### 2. Buscar algo específico
> "¿Tengo algún archivo que hable sobre 'presupuesto' o 'finanzas'?"

### 3. Usar la IA para entender un archivo
> "Encontré este archivo 'reporte_final.pdf'. ¿Puedes leerlo y hacerme un resumen de 5 puntos?"

*Aquí es donde el servidor usa tu API Key de Gemini para leer el contenido real del archivo y explicártelo.*

---

## Preguntas Frecuentes

**¿Dónde está la base de datos?**
Es un archivo llamado `files.db` en la carpeta del proyecto. Es automática. Si la borras, solo tienes que volver a escanear (indexar) tus carpetas.

**¿La IA lee todos mis archivos automáticamente?**
No. Solo lee el contenido cuando tú le pides específicamente analizar un archivo o cuando usas la herramienta de generar metadatos. El escaneo inicial solo mira nombres y fechas.

---

## PASO 6: Trucos y "Prompts" Avanzados

Una vez que ya escaneaste tus carpetas, prueba estas ideas para aprovechar tu base de datos:

### 🕵️‍♂️ Detective de Archivos (Búsquedas Inteligentes)
Como tus archivos están en una base de datos SQL, Claude puede hacer búsquedas que Windows no puede:

1.  **Limpieza de Disco:**
    > "Busca cuáles son los 10 archivos más pesados que tengo escaneados y muéstrame su tamaño en MB."

2.  **Recuperar el contexto:**
    > "Busca archivos que tengan 'factura' o 'pago' en el nombre, y dime de qué fechas son."

3.  **Auditoría de Tipos:**
    > "¿Cuántos archivos .pdf tengo en total comparado con archivos .docx?"

### 🧠 Tu Segundo Cerebro (Análisis con IA)
Aquí es donde combinamos la base de datos con Gemini:

1.  **Resumen Masivo:**
    > "Encuentra todos los archivos que contengan 'proyecto' en el nombre. Luego, para los primeros 3, genera un resumen de su contenido."

2.  **Etiquetado Automático:**
    > "Analiza el archivo 'notas_reunion.txt' y genera etiquetas (tags) automáticas para guardarlas en la base de datos."

3.  **Búsqueda Semántica (Pregunta sobre el contenido):**
    > "¿En qué archivo hablo sobre los 'requisitos del sistema'? No recuerdo el nombre del archivo, pero sé que está ahí."
    *(Nota: Claude abrirá y leerá los candidatos más probables para responderte).*
