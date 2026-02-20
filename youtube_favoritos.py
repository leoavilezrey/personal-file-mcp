import os
import json
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

# Los permisos que necesitamos (solo lectura para ver los videos)
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
MAX_VIDEOS_POR_SESION = 100
HISTORIAL_FILE = "historial_videos_youtube.json"

def main():
    # Permite transporte inseguro solo para pruebas locales (OAUTH)
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"
    
    # Este archivo debes descargarlo desde Google Cloud Console
    client_secrets_file = "client_secret.json"

    if not os.path.exists(client_secrets_file):
        print(f"❌ Error: No se encontró el archivo '{client_secrets_file}'.")
        print("Deberás ir a https://console.cloud.google.com/, crear un proyecto,")
        print("habilitar la 'YouTube Data API v3', y crear credenciales de OAuth 2.0 para ")
        print("App de Escritorio. Luego descarga el JSON y renómbralo a 'client_secret.json'.")
        return

    print("🔐 Autenticando con tu cuenta de Google/YouTube...")
    
    # Inicia el flujo de autenticación (abrirá el navegador)
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, SCOPES)
    credentials = flow.run_local_server(port=0)
    
    # Construir el servicio de la API de YouTube
    youtube = googleapiclient.discovery.build(
        api_service_name, api_version, credentials=credentials)

    # Cargar historial de videos ya procesados
    videos_procesados = set()
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                videos_procesados = set(json.load(f))
        except:
            pass

    print(f"\n📥 Obteniendo hasta {MAX_VIDEOS_POR_SESION} videos favoritos nuevos...")
    print(f"   (Ya hay {len(videos_procesados)} videos en tu historial de extracciones previas)")
    
    request = youtube.videos().list(
        part="snippet",
        myRating="like", # Recupera los videos marcados con 'Me gusta'
        maxResults=50
    )
    
    videos_favoritos = []

    while request and len(videos_favoritos) < MAX_VIDEOS_POR_SESION:
        try:
            response = request.execute()
            
            for item in response.get("items", []):
                # Detener si ya hemos encontrado la cantidad máxima solicitada
                if len(videos_favoritos) >= MAX_VIDEOS_POR_SESION:
                    break
                    
                video_id = item["id"]
                
                # Si este video id ya fue exportado alguna vez, sáltalo por completo
                if video_id in videos_procesados:
                    continue
                    
                titulo = item["snippet"]["title"]
                descripcion = item["snippet"]["description"]
                
                link = f"https://www.youtube.com/watch?v={video_id}"
                
                # Usar los primeros 100 caracteres de la descripción o un texto alternativo como "comentario"
                comentario = descripcion.replace('\n', ' ')[:100] + "..." if descripcion else "Sin comentario / descripción"
                
                videos_favoritos.append({
                    "id": video_id,
                    "nombre": titulo,
                    "link": link,
                    "comentario": comentario
                })
                
            # Verificar si hay una página siguiente (para seguir recuperando más allá de los primeros 50)
            if 'nextPageToken' in response:
                request = youtube.videos().list(
                    part="snippet",
                    myRating="like",
                    maxResults=50,
                    pageToken=response['nextPageToken']
                )
            else:
                request = None
                
        except googleapiclient.errors.HttpError as e:
            print(f"❌ Ha ocurrido un error HTTP: {e.resp.status} - {e.content}")
            break
            
    if not videos_favoritos:
        print("\n⚠️ No se encontraron videos nuevos para extraer (todos ya estaban en el historial).")
        return
        
    archivo_salida = "mis_videos_favoritos.txt"
    modo_escritura = "a" if os.path.exists(archivo_salida) else "w"
    
    with open(archivo_salida, modo_escritura, encoding="utf-8") as f:
        if modo_escritura == "w":
            f.write("=== TUS VIDEOS FAVORITOS DE YOUTUBE ===\n\n")
        else:
            f.write(f"\n--- Nueva extracción ({len(videos_favoritos)} agregados) ---\n\n")
            
        for i, video in enumerate(videos_favoritos, 1):
            texto_pantalla = f"{i}. {video['nombre']}\n   Enlace: {video['link']}"
            texto_archivo = f"Título: {video['nombre']}\nEnlace: {video['link']}\nComentario/Desc: {video['comentario']}\n\n"
            
            f.write(texto_archivo)
            print(texto_pantalla)
            
            # Agregarlo al historial temporal antes de guardar
            videos_procesados.add(video["id"])
            
    # Guardar el nuevo historial persistente
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(list(videos_procesados), f, indent=4)
        
    print(f"\n✅ ¡Éxito! Se extrajeron {len(videos_favoritos)} nuevos videos.")
    print(f"El total acumulado de videos exportados en el tiempo es de {len(videos_procesados)}.")
    print(f"Los nuevos datos han sido añadidos al archivo: {archivo_salida}")
    print("Recuerda que si ejecutas el comando de nuevo más adelante, sólo buscará los que falten por extraer.")

if __name__ == "__main__":
    main()
