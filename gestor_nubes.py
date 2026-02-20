import os
import json
import webbrowser
import sys

# === INTENTO DE IMPORTAR LIBRERÍAS ===
# Si alguna falta, el script advertirá al usuario.
FALTAN_LIBRERIAS = False
try:
    import google_auth_oauthlib.flow
    import googleapiclient.discovery
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
except ImportError:
    FALTAN_LIBRERIAS = True

try:
    import msal
except ImportError:
    FALTAN_LIBRERIAS = True

try:
    import dropbox
except ImportError:
    FALTAN_LIBRERIAS = True

# === ARCHIVOS DE CACHÉ ===
FILE_YOUTUBE = "cache_youtube.json"
FILE_DRIVE = "cache_drive.json"
FILE_ONEDRIVE = "cache_onedrive.json"
FILE_DROPBOX = "cache_dropbox.json"

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

def auth_google(scopes, token_name="token_google.json"):
    creds = None
    if os.path.exists(token_name):
        creds = Credentials.from_authorized_user_file(token_name, scopes)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("client_secret.json"):
                print("\n❌ Faltan Credenciales de Google.")
                print("1. Ve a Google Cloud Console y descarga tus credenciales OAuth 2.0 (App de Escritorio).")
                print("2. Renombra el archivo a 'client_secret.json' y ponlo en esta carpeta.")
                return None
            
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file('client_secret.json', scopes)
            creds = flow.run_local_server(port=0)
        
        with open(token_name, 'w') as token:
            token.write(creds.to_json())
            
    return creds

def extraer_youtube():
    print("\n--- Extrayendo de YouTube ---")
    scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
    creds = auth_google(scopes, "token_youtube.json")
    if not creds: return
    
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    cache_actual = cargar_cache(FILE_YOUTUBE)
    procesados = {item["id"] for item in cache_actual}
    
    request = youtube.videos().list(part="snippet", myRating="like", maxResults=50)
    nuevos = []
    
    while request and len(nuevos) < 50:
        respuesta = request.execute()
        for item in respuesta.get("items", []):
            if len(nuevos) >= 50: break
            vid = item["id"]
            if vid in procesados: continue
            
            titulo = item["snippet"]["title"]
            desc = item["snippet"]["description"] or ""
            link = f"https://www.youtube.com/watch?v={vid}"
            
            nuevos.append({
                "id": vid,
                "nombre": titulo,
                "link": link,
                "origen": "YouTube",
                "comentario": desc.replace('\n', ' ')[:100] + "..."
            })
            procesados.add(vid)
            
        if 'nextPageToken' in respuesta:
            request = youtube.videos().list(part="snippet", myRating="like", maxResults=50, pageToken=respuesta['nextPageToken'])
        else:
            request = None
            
    if nuevos:
        cache_actual.extend(nuevos)
        guardar_cache(FILE_YOUTUBE, cache_actual)
        print(f"✅ Se han extraído {len(nuevos)} videos nuevos. Total en caché: {len(cache_actual)}.")
    else:
        print("⚠️ No se encontraron videos nuevos. (Límite 50 por sesión).")

def extraer_drive():
    print("\n--- Extrayendo de Google Drive ---")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = auth_google(scopes, "token_drive.json")
    if not creds: return
    
    service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
    cache_actual = cargar_cache(FILE_DRIVE)
    procesados = {item["id"] for item in cache_actual}
    
    # Extraer los últimos 100 archivos modificados
    resultados = service.files().list(
        pageSize=100, 
        fields="nextPageToken, files(id, name, webViewLink, mimeType)",
        orderBy="modifiedTime desc"
    ).execute()
    
    items = resultados.get('files', [])
    nuevos = []
    
    for item in items:
        fid = item['id']
        if fid in procesados: continue
        link = item.get('webViewLink', '')
        
        nuevos.append({
            "id": fid,
            "nombre": item.get('name', 'Sin Nombre'),
            "link": link,
            "origen": "Google Drive",
            "comentario": item.get('mimeType', 'Archivo')
        })
        procesados.add(fid)
        
    if nuevos:
        cache_actual.extend(nuevos)
        guardar_cache(FILE_DRIVE, cache_actual)
        print(f"✅ Se han extraído {len(nuevos)} archivos nuevos. Total en caché: {len(cache_actual)}.")
    else:
        print("⚠️ No hay archivos nuevos de Drive para extraer en este bloque.")

def extraer_onedrive():
    print("\n--- Extrayendo de Microsoft OneDrive ---")
    client_id_file = "onedrive_client_id.txt"
    if not os.path.exists(client_id_file):
        print("❌ Faltan Credenciales de Microsoft.")
        print("1. Ve al portal de Azure AD, registra una aplicación (Single Page / Mobile & Desktop).")
        print("2. Copia el 'Client ID' (ID de aplicación o de cliente).")
        print("3. Pégalo dentro de un archivo nuevo llamado 'onedrive_client_id.txt' aquí mismo.")
        return
        
    with open(client_id_file, "r") as f:
        client_id = f.read().strip()
        
    app = msal.PublicClientApplication(client_id, authority="https://login.microsoftonline.com/common")
    scopes = ["Files.Read"]
    
    print("🔐 Abriendo navegador para autenticar en Microsoft...")
    result = app.acquire_token_interactive(scopes=scopes)
    
    if "access_token" in result:
        import requests
        headers = {'Authorization': 'Bearer ' + result['access_token']}
        # Graph API endpoint para los archivos root
        response = requests.get('https://graph.microsoft.com/v1.0/me/drive/root/children', headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('value', [])
            cache_actual = cargar_cache(FILE_ONEDRIVE)
            procesados = {item["id"] for item in cache_actual}
            nuevos = []

            for item in items:
                fid = item['id']
                if fid in procesados: continue
                
                link = item.get('webUrl', '')
                nuevos.append({
                    "id": fid,
                    "nombre": item.get('name', 'Sin Nombre'),
                    "link": link,
                    "origen": "OneDrive",
                    "comentario": "Archivo de OneDrive"
                })
                procesados.add(fid)
                
            if nuevos:
                cache_actual.extend(nuevos)
                guardar_cache(FILE_ONEDRIVE, cache_actual)
                print(f"✅ Se han extraído {len(nuevos)} archivos nuevos. Total en caché: {len(cache_actual)}.")
            else:
                print("⚠️ No hay archivos nuevos en la carpeta raíz de OneDrive.")
        else:
            print(f"❌ Error de API: {response.text}")
    else:
        print("❌ Fallo en la autenticación de Microsoft:", result.get("error_description"))

def extraer_dropbox():
    print("\n--- Extrayendo de Dropbox ---")
    token_file = "dropbox_token.txt"
    if not os.path.exists(token_file):
        print("❌ Falta el Token de Dropbox.")
        print("1. Ve a la Consola de Desarrolladores de Dropbox, crea una App (Scoped access).")
        print("2. En los permisos (Permissions) habilita 'files.content.read' y 'files.metadata.read'.")
        print("3. Haz clic en 'Generate access token'.")
        print("4. Pega ese token largo dentro de un archivo 'dropbox_token.txt' aquí mismo.")
        return
        
    with open(token_file, "r") as f:
        token = f.read().strip()
        
    try:
        dbx = dropbox.Dropbox(token)
        cache_actual = cargar_cache(FILE_DROPBOX)
        procesados = {item["id"] for item in cache_actual}
        nuevos = []
        
        # Obtener lista raíz
        resultado = dbx.files_list_folder('')
        for entry in resultado.entries:
            if isinstance(entry, dropbox.files.FileMetadata) or isinstance(entry, dropbox.files.FolderMetadata):
                fid = entry.id
                if fid in procesados: continue
                
                # Crear link público de lectura si no existe o generarlo para compartir (Opcional, consume API extra)
                # Para simplificar y no spamear la API, usaremos el enlace de la web de Dropbox clásico.
                path = entry.path_display
                link = f"https://www.dropbox.com/home{path}"
                
                nuevos.append({
                    "id": fid,
                    "nombre": entry.name,
                    "link": link,
                    "origen": "Dropbox",
                    "comentario": "Archivo/Directorio"
                })
                procesados.add(fid)
                
        if nuevos:
            cache_actual.extend(nuevos)
            guardar_cache(FILE_DROPBOX, cache_actual)
            print(f"✅ Se han extraído {len(nuevos)} archivos nuevos. Total en caché: {len(cache_actual)}.")
        else:
            print("⚠️ No hay archivos nuevos en la raíz de Dropbox.")
            
    except Exception as e:
        print(f"❌ Error al conectar a Dropbox: {e}")

def navegar_recursos():
    # Consolidar todos los caches
    todos = []
    todos.extend(cargar_cache(FILE_YOUTUBE))
    todos.extend(cargar_cache(FILE_DRIVE))
    todos.extend(cargar_cache(FILE_ONEDRIVE))
    todos.extend(cargar_cache(FILE_DROPBOX))
    
    if not todos:
        print("\n⚠️ No tienes ningún archivo o video extraído en tu caché. Ve a extraer primero.")
        return
        
    print("\n" + "="*80)
    print("🌐 NAVEGADOR MULTI-NUBE EN CACHÉ")
    print(f"Hay un total de {len(todos)} elementos indexados.")
    print("="*80)
    
    termino = input("Escribe una palabra para buscar (o presiona ENTER para ver una lista rápida de 30): ").strip().lower()
    
    resultados = []
    for item in todos:
        if not termino or termino in item['nombre'].lower() or termino in item.get('comentario', '').lower():
            resultados.append(item)
            
    if not resultados:
        print("\n❌ No hay coincidencias.")
        return
        
    print("\nResultados (máximo 30 mostrados):")
    for idx, r in enumerate(resultados[:30]):
        n = r['nombre'][:40] + "..." if len(r['nombre']) > 40 else r['nombre']
        print(f"[{idx}] {r['origen']:12} | {n}")
        
    seleccion = input("\nElige un número para abrir su enlace en tu navegador (o ENTER para cancelar): ").strip()
    if seleccion.isdigit():
        num = int(seleccion)
        if 0 <= num < len(resultados):
            item_sel = resultados[num]
            print(f"🚀 Abriendo: {item_sel['nombre']} ({item_sel['origen']})")
            webbrowser.open(item_sel['link'])
        else:
            print("Número fuera de rango.")

def menu_principal():
    if FALTAN_LIBRERIAS:
        print("\n⚠️ FALTAN LIBRERÍAS DE CONEXIÓN")
        print("Se ha detectado que faltan módulos necesarios de Google, Microsoft o Dropbox.")
        print("Por favor cierra este script e instala las dependencias corriendo este comando en tu terminal:")
        print("pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 msal dropbox requests")
        print("-------------------------------")
        input("Presiona ENTER para continuar de todos modos (algunas opciones podrían fallar)...")

    while True:
        print("\n" + "#"*50)
        print("☁️  EXTRACTOR Y NAVEGADOR DE NUBES Y YOUTUBE")
        print("#"*50)
        print("1. 🔴 Extraer Favoritos de YouTube")
        print("2. 🔺 Extraer Archivos de Google Drive")
        print("3. 🟦 Extraer Archivos de Microsoft OneDrive")
        print("4. 🟦 Extraer Archivos de Dropbox")
        print("5. 🌐 Navegar, Buscar y Abrir archivos guardados")
        print("6. ❌ Salir")
        print("#"*50)
        
        opc = input("Selecciona una opción (1-6): ").strip()
        
        if opc == '1': extraer_youtube()
        elif opc == '2': extraer_drive()
        elif opc == '3': extraer_onedrive()
        elif opc == '4': extraer_dropbox()
        elif opc == '5': navegar_recursos()
        elif opc == '6': break
        else: print("Opción inválida.")

if __name__ == "__main__":
    menu_principal()
