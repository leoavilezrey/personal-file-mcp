"""
test_analisis_videos.py
══════════════════════════════════════════════════════════════════════════════
Script de PRUEBA para el flujo de Análisis Cruzado de Videos de YouTube.
Funciona COMPLETAMENTE INDEPENDIENTE de la base de datos.

Flujo comparativo:
  PASO A → MODO MANUAL   : Genera prompt → lo pegas en Gemini Studio
  PASO B → MODO AUTOMÁTICO: Usa transcripciones reales + Gemini API
  PASO C → COMPARACIÓN   : Guarda ambos resultados juntos para comparar

Requisitos:
  pip install youtube-transcript-api google-genai
══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import re
import json
import textwrap
import datetime
from pathlib import Path

# ── UTF-8 en Windows ─────────────────────────────────────────────────────────
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent

# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS GLOBALES
# ═════════════════════════════════════════════════════════════════════════════

def sep(c="─", n=70):
    print(c * n)

def titulo(texto, c="═"):
    sep(c)
    print(f"  {texto}")
    sep(c)

def cargar_env():
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

def extraer_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None

def obtener_transcripcion(video_id: str, idiomas=("es", "en")) -> tuple[str, str]:
    """
    Retorna (texto, estado) donde estado puede ser:
      'ok', 'truncado', 'sin_transcripcion', 'error_lib'

    NOTA: youtube-transcript-api v1.x requiere instanciar YouTubeTranscriptApi()
          como objeto — ya NO tiene métodos de clase estáticos (list_transcripts, etc.)
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
    except ImportError:
        return "", "error_lib"

    try:
        api = YouTubeTranscriptApi()               # ← instancia de objeto (v1.x)
        transcript_list = api.list(video_id)       # ← .list() sobre la instancia

        # 1er intento: idiomas preferidos (es, en)
        transcript = None
        for lang in idiomas:
            try:
                transcript = transcript_list.find_transcript([lang])
                break
            except NoTranscriptFound:
                continue

        # 2do intento: cualquier auto-generado disponible
        if transcript is None:
            all_codes = [t.language_code for t in transcript_list]
            if all_codes:
                try:
                    transcript = transcript_list.find_generated_transcript(all_codes)
                except Exception:
                    pass

        # 3er intento: el primero que haya (manual o auto)
        if transcript is None:
            for t in transcript_list:
                transcript = t
                break

        if transcript is None:
            return "[Sin transcripción disponible para este video]", "sin_transcripcion"

        entries = transcript.fetch()

        # v1.x: los fragmentos son objetos FetchedTranscriptSnippet (.text como atributo)
        # Compatibilidad hacia atrás con dicts de versiones <1.x
        partes = []
        for e in entries:
            if hasattr(e, 'text'):
                partes.append(e.text.replace("\n", " "))
            elif isinstance(e, dict):
                partes.append(e.get("text", "").replace("\n", " "))

        texto = " ".join(partes).strip()
        palabras = texto.split()
        estado = "ok"
        if len(palabras) > 3500:
            texto = " ".join(palabras[:3500]) + "\n[...transcripción truncada a 3500 palabras...]"
            estado = "truncado"
        return texto, estado

    except Exception as e:
        return f"[⚠️ {type(e).__name__}: {e}]", "sin_transcripcion"


def llamar_gemini(prompt: str, model_name: str) -> tuple[str, str]:
    """
    Retorna (respuesta, estado) donde estado puede ser:
      'ok', 'error_key', 'error_lib', 'error_api'
    """
    cargar_env()
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "tu_api_key_aqui":
        return "", "error_key"

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text.strip(), "ok"
    except ImportError:
        pass
    except Exception as e:
        return f"[Error API: {e}]", "error_api"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text.strip(), "ok"
    except ImportError:
        return "", "error_lib"
    except Exception as e:
        return f"[Error API: {e}]", "error_api"


# ═════════════════════════════════════════════════════════════════════════════
#  CONSTRUCTORES DE PROMPT
# ═════════════════════════════════════════════════════════════════════════════

INSTRUCCIONES_COMUNES = """
══════════════════════════════════════
INSTRUCCIONES (sigue el orden exacto)
══════════════════════════════════════

## PASO 1 — Extracción Individual
Para CADA video extrae los 3 conceptos técnicos o ideas principales.
Omite introducciones, saludos y auto-promociones del canal.

## PASO 2 — Análisis Cruzado (NÚCLEO)
  a) ¿En qué puntos específicos CONCUERDAN los autores?
  b) ¿Qué CONTRADICCIONES o enfoques opuestos existen entre videos?
     (indica explícitamente cuál video dice qué)
  c) ¿Qué concepto de un video COMPLEMENTA algo incompleto en otro?

  → Presenta esto como TABLA COMPARATIVA:
    | Tema | Video 1 | Video 2 | Video 3 |

## PASO 3 — Síntesis Unificada
  - La "gran lección" que solo se entiende combinando las tres fuentes.
  - 3-5 pasos de acción concretos que emergen del análisis cruzado.
  - Términos técnicos clave compartidos entre videos.

Formato: Markdown con títulos claros. Sé directo y técnico.
"""

def construir_prompt_manual(videos: list[dict]) -> str:
    fuentes = ""
    for i, v in enumerate(videos, 1):
        fuentes += f"\nVideo {i}: {v['url']}"
        if v.get("titulo"):
            fuentes += f'  ← "{v["titulo"]}"'

    return f"""Eres un analista experto. Analiza a profundidad los siguientes videos de YouTube. No hagas resúmenes aislados; busca correlaciones profundas, contrastes y patrones entre los contenidos.

══════════════
FUENTE DE DATOS
══════════════
{fuentes}
{INSTRUCCIONES_COMUNES}"""


def construir_prompt_automatico(videos: list[dict]) -> str:
    fuentes = ""
    for i, v in enumerate(videos, 1):
        transcripcion = v.get("transcripcion", "[Sin transcripción]")
        fuentes += f"""
{'─'*60}
VIDEO {i}: "{v.get('titulo', f'Video {i}')}"
URL: {v['url']}
TRANSCRIPCIÓN:
{transcripcion}
"""
    return f"""Eres un analista experto. Tienes las transcripciones COMPLETAS de {len(videos)} videos de YouTube. Haz un análisis cruzado profundo — NO tres resúmenes aislados.

══════════════════════════
TRANSCRIPCIONES DE VIDEOS
══════════════════════════
{fuentes}
{INSTRUCCIONES_COMUNES}"""


# ═════════════════════════════════════════════════════════════════════════════
#  GUARDAR RESULTADOS
# ═════════════════════════════════════════════════════════════════════════════

def guardar_comparacion(videos: list[dict], resultado_manual: str,
                         resultado_auto: str, modelo: str) -> Path:
    """Guarda ambos resultados en un único archivo comparativo."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = BASE_DIR / f"comparacion_analisis_{ts}.txt"

    linea = "=" * 70
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(f"{linea}\n")
        f.write("COMPARACIÓN: MODO MANUAL vs MODO AUTOMÁTICO\n")
        f.write(f"Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Modelo automático: {modelo}\n")
        f.write(f"{linea}\n\n")

        f.write("VIDEOS ANALIZADOS:\n")
        for i, v in enumerate(videos, 1):
            f.write(f"  {i}. {v.get('titulo', 'Sin título')}\n")
            f.write(f"     {v['url']}\n")
            estado_t = v.get("estado_transcripcion", "—")
            palabras_t = len(v.get("transcripcion", "").split())
            f.write(f"     Transcripción: {estado_t} ({palabras_t} palabras)\n")
        f.write(f"\n{'─'*70}\n\n")

        f.write("╔══════════════════════════════════════════╗\n")
        f.write("║  RESULTADO A — MODO MANUAL               ║\n")
        f.write("║  (prompt pegado en Gemini Studio/otros)  ║\n")
        f.write("╚══════════════════════════════════════════╝\n\n")
        if resultado_manual:
            f.write(resultado_manual)
        else:
            f.write("[Sin resultado — el usuario no pegó respuesta en modo manual]\n")

        f.write(f"\n\n{'─'*70}\n\n")
        f.write("╔══════════════════════════════════════════╗\n")
        f.write(f"║  RESULTADO B — MODO AUTOMÁTICO           ║\n")
        f.write(f"║  Modelo: {modelo:<33}║\n")
        f.write("╚══════════════════════════════════════════╝\n\n")
        if resultado_auto:
            f.write(resultado_auto)
        else:
            f.write("[Sin resultado — error en API o sin configurar]\n")

        f.write(f"\n\n{'='*70}\n[Fin del archivo comparativo]\n")

    return archivo

def guardar_prompt(prompt: str, nombre_base: str) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = BASE_DIR / f"{nombre_base}_{ts}.txt"
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(prompt)
    return archivo


# ═════════════════════════════════════════════════════════════════════════════
#  PASO 0: INGRESAR VIDEOS (compartido entre modos)
# ═════════════════════════════════════════════════════════════════════════════

def ingresar_videos() -> list[dict]:
    titulo("🎬  INGRESO DE VIDEOS", "═")
    n_str = input("¿Cuántos videos quieres analizar? (2-5, defecto=3): ").strip()
    n = int(n_str) if n_str.isdigit() and 2 <= int(n_str) <= 5 else 3
    print(f"\nIngresa las URLs de {n} videos de YouTube:\n")
    videos = []
    for i in range(1, n + 1):
        sep()
        print(f"  📺 Video {i} de {n}")
        url = input("  URL de YouTube: ").strip()
        while not url:
            print("  ⚠️ La URL es obligatoria.")
            url = input("  URL de YouTube: ").strip()
        titulo_v = input("  Título/tema breve (ENTER para omitir): ").strip() or f"Video {i}"
        vid_id = extraer_video_id(url)
        if vid_id:
            print(f"  ✅ ID detectado: {vid_id}")
        else:
            print("  ⚠️ No se pudo detectar el ID del video (¿URL válida?)")
        videos.append({"url": url, "titulo": titulo_v, "video_id": vid_id})
    return videos


# ═════════════════════════════════════════════════════════════════════════════
#  PASO A: MODO MANUAL
# ═════════════════════════════════════════════════════════════════════════════

def ejecutar_modo_manual(videos: list[dict]) -> str:
    """Ejecuta el modo manual. Retorna el texto de análisis pegado (o vacío)."""
    titulo("✍️  PASO A — MODO MANUAL", "═")
    print("El script genera el prompt estructurado.")
    print("Tú lo pegas en Gemini Studio / ChatGPT y luego traes la respuesta aquí.\n")

    prompt = construir_prompt_manual(videos)
    archivo_prompt = guardar_prompt(prompt, "prompt_manual")

    sep("═")
    print("📋  PROMPT GENERADO  (también guardado en disco)\n")
    sep()
    print(prompt)
    sep("═")
    print(f"\n💾 Guardado en: {archivo_prompt.name}")
    print("\n" + "▶" * 60)
    print("  AHORA: Copia ese prompt y pégalo en Gemini Studio o ChatGPT.")
    print("  URL Gemini Studio → https://aistudio.google.com/prompts/new_chat")
    print("▶" * 60)

    print("\n¿Quieres pegar la respuesta de la IA aquí para guardarla? (s/n): ", end="")
    if input().strip().lower() != 's':
        print("ℹ️  OK. El archivo de comparación quedará vacío para el modo manual.")
        return ""

    print("\n📥 Pega la respuesta completa de la IA.")
    print("   Cuando termines, escribe exactamente  FIN  en una línea nueva y presiona ENTER.\n")
    lineas = []
    while True:
        linea = input()
        if linea.strip().upper() == "FIN":
            break
        lineas.append(linea)

    if lineas:
        resultado = "\n".join(lineas)
        print(f"\n✅ Respuesta capturada ({len(resultado.split())} palabras).")
        return resultado
    else:
        print("ℹ️ No se pegó contenido.")
        return ""


# ═════════════════════════════════════════════════════════════════════════════
#  PASO B: MODO AUTOMÁTICO
# ═════════════════════════════════════════════════════════════════════════════

MODELOS = [
    "gemini-2.0-flash",          # ✅ Rápido y estable
    "gemini-2.5-flash",          # ✅ Más reciente
    "gemini-2.5-pro",            # ✅ Más potente
    "gemini-2.0-flash-lite",     # ✅ Económico
    "gemini-3.1-pro-preview",    # ✅ Experimental más reciente
    "gemini-3-flash-preview",    # ✅ Experimental flash
]

def obtener_modelos_disponibles() -> list[str]:
    """Consulta la API para obtener los modelos disponibles. Fallback a lista fija."""
    cargar_env()
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key == "tu_api_key_aqui":
        return MODELOS
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        disponibles = []
        for m in client.models.list():
            name = m.name.replace("models/", "")
            # Filtrar solo los modelos Gemini de texto relevantes (sin TTS, imagen, robótica, etc.)
            if ("gemini" in name
                    and not any(x in name for x in ["tts", "image", "computer", "robotics", "research", "banana", "nano"])
                    and "generateContent" in (m.supported_actions or [])):
                disponibles.append(name)
        return disponibles if disponibles else MODELOS
    except Exception:
        return MODELOS


def ejecutar_modo_automatico(videos: list[dict]) -> tuple[str, str]:
    """Ejecuta el modo automático. Retorna (resultado, modelo_usado)."""
    titulo("🤖  PASO B — MODO AUTOMÁTICO", "═")
    print("El script descargará transcripciones y llamará a Gemini API.\n")

    # Seleccionar modelo — lista dinámica desde la API
    print("⏳ Consultando modelos disponibles en tu API key...")
    modelos_disp = obtener_modelos_disponibles()
    print(f"   {len(modelos_disp)} modelos encontrados.\n")
    print("Modelo Gemini a usar:")
    for i, m in enumerate(modelos_disp, 1):
        marca = "  ⭐" if i == 1 else ""
        print(f"  {i}. {m}{marca}")
    print(f"  (ENTER = usar el primero: {modelos_disp[0]})")
    sel = input("> ").strip()
    modelo = modelos_disp[int(sel) - 1] if sel.isdigit() and 1 <= int(sel) <= len(modelos_disp) else modelos_disp[0]
    print(f"  ✅ Usando: {modelo}\n")

    # Descargar transcripciones
    sep()
    print("📥 Descargando transcripciones...\n")
    for v in videos:
        vid_id = v.get("video_id")
        if not vid_id:
            print(f"  ❌ {v['titulo']}: ID no válido, se omite transcripción.")
            v["transcripcion"] = "[ID de video no detectado]"
            v["estado_transcripcion"] = "sin_id"
            continue

        print(f"  🔄 [{v['titulo']}] — ID: {vid_id}")
        texto, estado = obtener_transcripcion(vid_id)
        v["transcripcion"] = texto
        v["estado_transcripcion"] = estado

        if estado == "ok":
            palabras = len(texto.split())
            preview = " ".join(texto.split()[:20])
            print(f"     ✅ {palabras} palabras  |  \"{preview}...\"")
        elif estado == "truncado":
            palabras = len(texto.split())
            print(f"     ✅ {palabras} palabras (truncado a 3500)")
        elif estado == "sin_transcripcion":
            print(f"     ⚠️  Sin transcripción disponible: {texto[:80]}")
        elif estado == "error_lib":
            print(f"     ❌ Error: youtube-transcript-api no instalado.")
        print()

    # Construir prompt con transcripciones
    prompt_auto = construir_prompt_automatico(videos)
    n_palabras_prompt = len(prompt_auto.split())
    tokens_est = int(n_palabras_prompt * 1.3)

    sep()
    print(f"📊 Prompt construido:")
    print(f"   Palabras: {n_palabras_prompt:,}  |  Tokens estimados: ~{tokens_est:,}")

    # Guardar prompt automático también
    archivo_prompt_auto = guardar_prompt(prompt_auto, "prompt_automatico_con_transcripciones")
    print(f"   Guardado en: {archivo_prompt_auto.name}")

    # Mostrar preview opcional
    print("\n¿Ver preview del prompt antes de enviar? (s/n): ", end="")
    if input().strip().lower() == 's':
        lineas = prompt_auto.split("\n")
        print()
        for l in lineas[:50]:
            print(l)
        if len(lineas) > 50:
            print(f"\n... [{len(lineas)-50} líneas más] ...")

    # Llamar a Gemini
    sep()
    print(f"🚀 Enviando a Gemini ({modelo})...")
    print("   Esto puede tomar 15-60 segundos...\n")

    resultado, estado_api = llamar_gemini(prompt_auto, modelo)

    if estado_api == "error_key":
        print("❌ GOOGLE_API_KEY no configurada en .env")
        return "", modelo
    elif estado_api == "error_lib":
        print("❌ Librería google-genai no instalada: pip install google-genai")
        return "", modelo
    elif estado_api == "error_api":
        print(f"❌ Error de API: {resultado}")
        return resultado, modelo
    else:
        sep("═")
        print("✅ ANÁLISIS AUTOMÁTICO RECIBIDO:\n")
        for linea in resultado.split("\n"):
            if len(linea) > 110:
                print(textwrap.fill(linea, width=110))
            else:
                print(linea)
        sep("═")
        return resultado, modelo


# ═════════════════════════════════════════════════════════════════════════════
#  PASO C: VISTA COMPARATIVA EN CONSOLA
# ═════════════════════════════════════════════════════════════════════════════

def mostrar_comparacion_consola(resultado_manual: str, resultado_auto: str):
    titulo("📊  PASO C — COMPARACIÓN DE RESULTADOS", "═")

    man_palabras = len(resultado_manual.split()) if resultado_manual else 0
    auto_palabras = len(resultado_auto.split()) if resultado_auto else 0

    print(f"  {'Métrica':<30} | {'MANUAL':>12} | {'AUTOMÁTICO':>12}")
    sep()
    print(f"  {'Palabras en respuesta':<30} | {man_palabras:>12,} | {auto_palabras:>12,}")
    print(f"  {'Tiene resultado':<30} | {'✅ Sí' if resultado_manual else '❌ No':>12} | {'✅ Sí' if resultado_auto else '❌ No':>12}")
    sep("═")

    # Comparar si los pasos están presentes
    pasos = ["PASO 1", "PASO 2", "PASO 3", "tabla", "conclusi"]
    print(f"\n  Presencia de secciones clave:")
    print(f"  {'Sección':<28} | {'MANUAL':>10} | {'AUTOMÁTICO':>10}")
    sep()
    for p in pasos:
        en_man  = "✅" if p.lower() in resultado_manual.lower() else "❌"
        en_auto = "✅" if p.lower() in resultado_auto.lower() else "❌"
        print(f"  {p:<28} | {en_man:>10} | {en_auto:>10}")
    sep("═")
    print()


# ═════════════════════════════════════════════════════════════════════════════
#  MENÚ PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

def verificar_dependencias() -> dict:
    estado = {}
    try:
        import youtube_transcript_api as yta
        v = getattr(yta, '__version__', '?')
        estado["youtube_transcript_api"] = f"✅ v{v}"
    except ImportError:
        estado["youtube_transcript_api"] = "❌ No instalado  →  pip install youtube-transcript-api"

    try:
        from google import genai
        estado["google_genai"] = "✅ google-genai (nuevo)"
    except ImportError:
        try:
            import google.generativeai
            estado["google_genai"] = "✅ google-generativeai (antiguo)"
        except ImportError:
            estado["google_genai"] = "❌ No instalado  →  pip install google-genai"

    cargar_env()
    key = os.getenv("GOOGLE_API_KEY", "")
    if key and key != "tu_api_key_aqui":
        estado["api_key"] = f"✅ Configurada ({key[:8]}...)"
    else:
        estado["api_key"] = "⚠️  No configurada en .env"

    return estado


def main():
    titulo("🎬  TEST — ANÁLISIS CRUZADO DE VIDEOS (COMPARATIVO)", "═")
    print("  Este script ejecuta MANUAL → AUTOMÁTICO con los mismos videos")
    print("  y guarda un archivo comparativo de ambos resultados.\n")

    # Verificar dependencias
    print("📦 Verificando dependencias...\n")
    deps = verificar_dependencias()
    etiquetas = {
        "youtube_transcript_api": "youtube-transcript-api",
        "google_genai":           "Gemini API library   ",
        "api_key":                "GOOGLE_API_KEY       ",
    }
    for k, v in deps.items():
        print(f"  {etiquetas[k]}: {v}")

    sep()
    print("\n¿Cómo quieres proceder?\n")
    print("  1. ▶ Ejecutar AMBOS modos (Manual → Automático) y comparar")
    print("  2. ✍️  Solo MANUAL")
    print("  3. 🤖 Solo AUTOMÁTICO")
    print("  0. 🚪 Salir")
    sep()
    opc = input("Elige (0-3): ").strip()

    if opc == '0':
        print("👋 ¡Hasta luego!")
        return

    # ── Ingresar videos (siempre primero) ────────────────────────────────
    print()
    videos = ingresar_videos()

    resultado_manual = ""
    resultado_auto   = ""
    modelo_usado     = MODELOS[0]

    # ── Ejecutar modos ────────────────────────────────────────────────────
    if opc in ('1', '2'):
        print()
        sep("═")
        resultado_manual = ejecutar_modo_manual(videos)

    if opc in ('1', '3'):
        print()
        sep("═")
        # Para evitar reingresar el modelo en modo 1, pregunta directamente
        resultado_auto, modelo_usado = ejecutar_modo_automatico(videos)

    # ── Guardar comparación ───────────────────────────────────────────────
    if opc == '1':
        print()
        sep("═")
        mostrar_comparacion_consola(resultado_manual, resultado_auto)
        archivo = guardar_comparacion(videos, resultado_manual, resultado_auto, modelo_usado)
        titulo(f"💾  ARCHIVO GUARDADO: {archivo.name}", "═")
        print(f"   Ruta completa: {archivo}")
        print()
        print("  Este archivo contiene:")
        print("  • Lista de videos con estado de transcripción")
        print("  • Resultado A — análisis manual (pegado por ti)")
        print("  • Resultado B — análisis automático (Gemini API)")
        print("  • Métricas de comparación")
        sep("═")
    elif resultado_auto:
        archivo = guardar_comparacion(videos, resultado_manual, resultado_auto, modelo_usado)
        print(f"\n💾 Guardado en: {archivo.name}")

    sep("═")
    print("✅ Prueba finalizada.")
    print(f"   Archivos generados en: {BASE_DIR}")
    sep("═")


if __name__ == "__main__":
    main()
