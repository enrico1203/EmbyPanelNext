import requests
import json

def get_user_id(server_ip, api_key, username):
    
    # Endpoint API per ottenere gli utenti
    url = f'{server_ip}/emby/Users'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere la lista degli utenti
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        users = response.json()
        # Trova l'utente con il nome specificato
        user_id = next((user['Id'] for user in users if user['Name'].lower() == username.lower()), None)

        if user_id:
            print(f"L'ID dell'utente '{username}' è: {user_id}")
            return user_id
        else:
            print(f"Utente '{username}' non trovato.")
            return None
    else:
        print("Errore nell'ottenere la lista degli utenti:", response.text)
        #Provo a vedere se il server in question è jelllyfin al posto di emby
        
        url_jellyfin = f'{server_ip}Users'
        headers_jellyfin = {
            'X-Emby-Token': api_key  # Jellyfin utilizza lo stesso header di Emby
        }

        print("url della richiesta: ",url_jellyfin)
        # Effettua la richiesta GET per ottenere la lista degli utenti da Jellyfin
        response = requests.get(url_jellyfin, headers=headers_jellyfin)

        # Controlla se la richiesta ha avuto successo
        if response.status_code == 200:
            users = response.json()
            # Trova l'utente con il nome specificato
            user_id = next((user['Id'] for user in users if user['Name'].lower() == username.lower()), None)

            if user_id:
                print(f"L'ID dell'utente '{username}' è: {user_id}")
                return user_id
            else:
                print(f"Utente '{username}' non trovato.")
                return None
        else:
            print("Errore nell'ottenere la lista degli utenti da Jellyfin:", response.text)
            
        
        
        return None
        


def create_user(server_ip, api_key, username, password):
    url = f'{server_ip}/emby/Users/New'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Dati della richiesta per creare l'utente
    data = {
        "Name": username
    }

    # Effettua la richiesta POST per creare l'utente
    response = requests.post(url, headers=headers, json=data)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        # Estrai l'ID dell'utente appena creato
        user_id = response.json()['Id']
        print(f"ID dell'utente creato: {user_id}")

        # Imposta la password per l'utente creato
        password_url = f'{server_ip}/emby/Users/{user_id}/Password'
        password_data = {
            "NewPw": password
        }

        # Effettua la richiesta POST per impostare la password
        password_response = requests.post(password_url, headers=headers, json=password_data)

        print (password_response.status_code)


    else:
        print("Errore nella creazione dell'utente:", response.text)
        
        #provo a vedere se il server in question è jellyfin al posto di emby
        url_jellyfin = f'{server_ip}Users/New'
        
        headers_jellyfin = {
            'X-Emby-Token': api_key  # Jellyfin utilizza lo stesso header di Emby
        }

        data = {
            "Name": username,
            "Password": password
        }
        # Effettua la richiesta POST per creare l'utente su Jellyfin
        response = requests.post(url_jellyfin, headers=headers_jellyfin, json=data)

        # Controlla se la richiesta ha avuto successo su Jellyfin
        if response.status_code == 200:
            # Estrai l'ID dell'utente appena creato
            user_id = response.json()['Id']
            print(f"ID dell'utente creato su Jellyfin: {user_id}")

            return user_id
        else:
            print("Errore nella creazione dell'utente su Jellyfin:", response.text)



def default_user_policy(server_ip, api_key, user_id,schermi):
    url = f'{server_ip}/emby/Users/{user_id}/Policy'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Dati della richiesta per aggiornare la policy dell'utente
    data = {
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        #"EnableVideoPlaybackTranscoding": True,
        "SimultaneousStreamLimit": schermi,
        "EnableVideoPlaybackTranscoding": True,
        "AllowCameraUpload": False,
        "EnableUserPreferenceAccess": False
    }

    # Effettua la richiesta POST per aggiornare la policy dell'utente
    response = requests.post(url, headers=headers, json=data)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 204:
        print("Policy dell'utente aggiornata con successo.")
        return True
    else:
        print("Errore nell'aggiornare la policy dell'utente:", response.text)
        

def default_user_policy_jellyfin(jf_base_url: str, api_key: str, user_id: str, schermi: int, timeout: int = 10) -> bool:
    if jf_base_url.endswith('/'):
        base = jf_base_url[:-1]
    else:
        base = jf_base_url

    url = f"{base}/Users/{user_id}/Policy"

    headers = {
        "Content-Type": "application/json",
        "X-Emby-Token": api_key
    }

    payload = {
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableVideoPlaybackTranscoding": True,
        "EnableUserPreferenceAccess": False,
        "MaxActiveSessions": int(schermi+2),

        # === REQUIRED FIELDS ===
        "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
        "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider",
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code == 204:
        print("Jellyfin: user policy updated successfully.")
        return True
    else:
        print(f"Jellyfin: failed to update policy ({resp.status_code}). Body: {resp.text}")
        return False


def delete_user(server_ip, api_key, user_id):  # da testare
    base = server_ip.rstrip("/")
    url = f'{base}/emby/Users/{user_id}'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta DELETE per eliminare l'utente
    response = requests.delete(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 204:
        print("Utente eliminato con successo.")
        return True
    else:
        print("Errore nell'eliminare l'utente:", response.text)
        #provo con jellyfin
        url_jellyfin = f'{base}/Users/{user_id}'
        headers_jellyfin = {
            'X-Emby-Token': api_key
        }
        
        response = requests.delete(url_jellyfin, headers=headers_jellyfin)
        
        if response.status_code == 204:
            print("Utente eliminato con successo su Jellyfin.")
            return True
        else:
            print("Errore nell'eliminare l'utente su Jellyfin:", response.text)
        
            return False
    
def disable_user(server_ip, api_key, user_id):  # da testare
    url = f'{server_ip}/emby/Users/{user_id}/Policy'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Dati della richiesta per disabilitare l'utente
    data = {
        "IsDisabled": True
    }

    # Effettua la richiesta POST per disabilitare l'utente
    response = requests.post(url, headers=headers, json=data)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 204:
        print("Utente disabilitato con successo.")
        return True
    else:
        print("Errore nel disabilitare l'utente:", response.text)
        return False
    
def enable_user(server_ip, api_key, user_id,schermi):  # da testare
    url = f'{server_ip}/emby/Users/{user_id}/Policy'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Dati della richiesta per abilitare l'utente
    data = {
        "IsDisabled": False,
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        #"EnableMediaConversion": False,
        "EnableMediaConversion": False,
        "SimultaneousStreamLimit": schermi,
        "AllowCameraUpload": False,
        "EnableUserPreferenceAccess": False
    }

    # Effettua la richiesta POST per abilitare l'utente
    response = requests.post(url, headers=headers, json=data)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 204:
        print("Utente abilitato con successo.")
        return True
    else:
        print("Errore nel abilitare l'utente:", response.text)
        return False
    

def enable_user_jellyfin(server_ip: str, api_key: str, user_id: str, schermi: int) -> bool:
    """
    Abilita un utente Jellyfin e imposta i limiti di sessione.
    """
    base = server_ip.rstrip("/")
    url = f"{base}/Users/{user_id}/Policy"

    headers = {
        "Content-Type": "application/json",
        "X-Emby-Token": api_key
    }

    # Policy di abilitazione per Jellyfin
    data = {
        "IsDisabled": False,
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableUserPreferenceAccess": False,
        "EnableVideoPlaybackTranscoding": True,
        "MaxActiveSessions": int(schermi+2),

        # Campi richiesti da Jellyfin
        "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
        "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider"
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 204:
        print("Utente Jellyfin abilitato con successo.")
        return True
    else:
        print(f"Errore nell'abilitare l'utente: {response.status_code} {response.text}")
        return False
    
def disable_user_jellyfin(server_ip: str, api_key: str, user_id: str, schermi: int) -> bool:
    """
    disabilita un utente Jellyfin e imposta i limiti di sessione.
    """
    base = server_ip.rstrip("/")
    url = f"{base}/Users/{user_id}/Policy"

    headers = {
        "Content-Type": "application/json",
        "X-Emby-Token": api_key
    }

    # Policy di abilitazione per Jellyfin
    data = {
        "IsDisabled": True,
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableUserPreferenceAccess": False,
        "EnableVideoPlaybackTranscoding": True,
        "MaxActiveSessions": int(schermi+2),

        # Campi richiesti da Jellyfin
        "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
        "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider"
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 204:
        print("Utente Jellyfin disabilitato con successo.")
        return True
    else:
        print(f"Errore nell'disabilitazione l'utente: {response.status_code} {response.text}")
        return False

def library_Ids(server_ip, api_key):
    url = f"{server_ip}/emby/Library/SelectableMediaFolders"
    
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    excludeids = [] 
    includeids = [] 
    for item in data:
        name = item["Name"]
        guid = item["Guid"]
        for subfolder in item["SubFolders"]:
            subfolder_name = subfolder["Name"]
            subfolder_id = subfolder["Id"]
            if "4k" in subfolder_name.lower():
                excludeids.append(f"{guid}_{subfolder_id}")
            else:
                includeids.append(f"{guid}")
    exclude_ids = ",".join(excludeids)
    include_ids = ",".join(includeids)
    return exclude_ids, include_ids



def disable4k(username,server_ip, api_key):
    print("entro qui")
    exclude_ids, include_ids = library_Ids(server_ip, api_key)
    url = f"{server_ip}/emby/Users/Query"
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }
    params = {'SortBy': 'Name', 'IsDisabled': 'false'}
    response = requests.get(url, headers=headers, params=params)
    if response.content:
        try:
            user_list = json.loads(response.content.decode('utf-8'))
            for user in user_list['Items']:
                if user['Name'] == username:
                    user_url = url.replace('/Query', '') + '/' + user['Id']
                    response = requests.get(user_url, headers=headers)
                    user_data = json.loads(response.content.decode('utf-8'))
                    print(user_data)
                    user_data['Policy']['EnableAllFolders'] = "false"
                    user_data['Policy']['EnabledFolders'] = include_ids
                    user_data['Policy']['ExcludedSubFolders'] = exclude_ids
                    user_data['Policy']['EnableVideoPlaybackTranscoding'] = "true" 
                    response = requests.post(user_url + '/Policy', headers=headers, json=user_data['Policy'])
                    print(response.text)
                    return True
                    
        except json.JSONDecodeError:
            print("Error: Response content is not valid JSON.")
    else:
        print("Error: Response content is empty.")
        
        
def disable4k_jellyfin(username: str, jf_base_url: str, api_key: str,schermi) -> bool:
    base = jf_base_url.rstrip("/")
    headers = {"X-Emby-Token": api_key, "Content-Type": "application/json"}

    # 1) Lista librerie
    r = requests.get(f"{base}/Library/VirtualFolders", headers=headers)
    if r.status_code != 200:
        print("Errore nel leggere VirtualFolders:", r.text)
        return False
    libs = r.json()

    include_ids = []
    blocked_ids = []
    for lib in libs:
        name = (lib.get("Name") or "").lower()
        lib_id = lib.get("ItemId")
        if not lib_id:
            continue
        if "4k" in name:
            blocked_ids.append(lib_id)
        else:
            include_ids.append(lib_id)

    # 2) Trova utente
    r = requests.get(f"{base}/Users", headers=headers)
    if r.status_code != 200:
        print("Errore nel leggere utenti:", r.text)
        return False
    userlist = r.json()
    user = next((u for u in userlist if u.get("Name","").lower() == username.lower()), None)
    if not user:
        print(f"Utente {username} non trovato")
        return False
    user_id = user["Id"]

    # 3) Costruisci policy (campi richiesti + modifiche)
    policy = {
        "EnableAllFolders": False,
        "EnabledFolders": include_ids,
        "BlockedMediaFolders": blocked_ids,
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableVideoPlaybackTranscoding": True,
        "EnableUserPreferenceAccess": False,
        "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
        "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider",
        "MaxActiveSessions": schermi+2
    }

    # 4) POST policy
    r = requests.post(f"{base}/Users/{user_id}/Policy", headers=headers, json=policy)
    if r.status_code == 204:
        print(f"Policy aggiornata per {username} (4k disabilitato).")
        return True
    else:
        print("Errore nell'aggiornare la policy:", r.status_code, r.text)
        return False

def enable4k_jellyfin(username: str, jf_base_url: str, api_key: str,schermi) -> bool:
    """
    Jellyfin: abilita l’accesso a tutte le librerie (incluso 4k)
    e disabilita la transcodifica video.
    """
    base = jf_base_url.rstrip("/")
    headers = {"X-Emby-Token": api_key, "Content-Type": "application/json"}

    # 1) Trova utente
    r = requests.get(f"{base}/Users", headers=headers)
    if r.status_code != 200:
        print("Errore nel leggere utenti:", r.text)
        return False
    userlist = r.json()
    user = next((u for u in userlist if u.get("Name","").lower() == username.lower()), None)
    if not user:
        print(f"Utente {username} non trovato")
        return False
    user_id = user["Id"]

    # 2) Costruisci policy con tutte le librerie abilitate
    policy = {
        "EnableAllFolders": True,
        "EnabledFolders": [],
        "BlockedMediaFolders": [],
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableVideoPlaybackTranscoding": False,  # <== richiesto
        "EnableUserPreferenceAccess": False,
        "AuthenticationProviderId": "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider",
        "PasswordResetProviderId": "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider",
        "MaxActiveSessions": schermi+2
    }

    # 3) POST policy
    r = requests.post(f"{base}/Users/{user_id}/Policy", headers=headers, json=policy)
    if r.status_code == 204:
        print(f"Policy aggiornata per {username} (4k abilitato).")
        return True
    else:
        print("Errore nell'aggiornare la policy:", r.status_code, r.text)
        return False

def enable4k(username,server_ip, api_key):
    exclude_ids, include_ids = library_Ids(server_ip, api_key)
    
    ids_list = exclude_ids.split(",")

    # Per ogni id, prendi solo la parte prima dell'underscore
    base_ids = [id.split("_")[0] for id in ids_list]

    # Se vuoi evitare duplicati (dato che entrambi gli id hanno la stessa parte iniziale)
    base_ids = list(set(base_ids))

    # Unisci nuovamente gli id con una virgola (o, nel tuo caso, potresti usarli così come sono)
    processed_exclude_ids = ",".join(base_ids)
    allids = include_ids + "," + processed_exclude_ids
    
    url = f"{server_ip}/emby/Users/Query"
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }
    params = {'SortBy': 'Name', 'IsDisabled': 'false'}
    response = requests.get(url, headers=headers, params=params)
    if response.content:
        try:
            user_list = json.loads(response.content.decode('utf-8'))
            for user in user_list['Items']:
                if user['Name'] == username:
                    user_url = url.replace('/Query', '') + '/' + user['Id']
                    response = requests.get(user_url, headers=headers)
                    user_data = json.loads(response.content.decode('utf-8'))
                    user_data['Policy']['EnableAllFolders'] = "false"
                    user_data['Policy']['EnabledFolders'] = allids
                    user_data['Policy']['ExcludedSubFolders'] = ""
                    user_data['Policy']['EnableVideoPlaybackTranscoding'] = "false"  
                    
                    response = requests.post(user_url + '/Policy', headers=headers, json=user_data['Policy'])
                    return True
                    
        except json.JSONDecodeError:
            print("Error: Response content is not valid JSON.")
    else:
        print("Error: Response content is empty.")
    
    

    
    
    
    
    

def get_user_policy(server_ip, api_key, user_id): # da testare
    url = f'{server_ip}/emby/Users/{user_id}/Policy'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere la policy dell'utente
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        policy = response.json()
        print("Policy dell'utente:")
        print(policy)
        return policy
    else:
        print("Errore nell'ottenere la policy dell'utente:", response.text)
        return None
    
def get_user_info(server_ip, api_key, user_id): # da testare
    url = f'{server_ip}/emby/Users/{user_id}'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere le informazioni dell'utente
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        user_info = response.json()
        print("Informazioni dell'utente:")
        print(user_info)
        return user_info
    else:
        print("Errore nell'ottenere le informazioni dell'utente:", response.text)
        return None

def get_user_activity(server_ip, api_key, user_id): # da testare
    url = f'{server_ip}/emby/Users/{user_id}/Activity'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere l'attività dell'utente
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        activity = response.json()
        print("Attività dell'utente:")
        print(activity)
        return activity
    else:
        print("Errore nell'ottenere l'attività dell'utente:", response.text)
        return None
    
def get_user_sessions(server_ip, api_key, user_id): # da testare
    url = f'{server_ip}/emby/Sessions'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere le sessioni dell'utente
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        sessions = response.json()
        user_sessions = [session for session in sessions if session['UserId'] == user_id]
        print("Sessioni dell'utente:")
        print(user_sessions)
        return user_sessions
    else:
        print("Errore nell'ottenere le sessioni dell'utente:", response.text)
        return None

def get_user_devices(server_ip, api_key, user_id): # da testare
    url = f'{server_ip}/emby/Users/{user_id}/Devices'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere i dispositivi dell'utente
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        devices = response.json()
        print("Dispositivi dell'utente:")
        print(devices)
        return devices
    else:
        print("Errore nell'ottenere i dispositivi dell'utente:", response.text)
        return None
    
def get_user_access(server_ip, api_key, user_id): # da testare
    url = f'{server_ip}/emby/Users/{user_id}/AccessSchedule'

    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-Emby-Token': api_key
    }

    # Effettua la richiesta GET per ottenere l'accesso dell'utente
    response = requests.get(url, headers=headers)

    # Controlla se la richiesta ha avuto successo
    if response.status_code == 200:
        access = response.json()
        print("Accesso dell'utente:")
        print(access)
        return access
    else:
        print("Errore nell'ottenere l'accesso dell'utente:", response.text)
        return None
    

def _normalize_base(server_ip: str) -> str:
    # Accetta sia "http://host:8096" sia "http://host:8096/"
    return server_ip.rstrip("/")

def change_password(server_ip: str, api_key: str, username: str, new_password: str, timeout: int = 10) -> bool:
    """
    Cambia la password dell'utente (senza password corrente) usando token admin/API.
    Prova vari payload e content-type per massima compatibilità (Emby/Jellyfin).
    Ritorna True se 200/204, altrimenti False (stampa il motivo).
    """
    try:
        if not isinstance(new_password, str) or len(new_password.strip()) < 5:
            print("Password troppo corta: minimo 5 caratteri.")
            return False

        base = server_ip.rstrip("/")
        headers_json = {
            "Content-Type": "application/json",
            "X-Emby-Token": api_key
        }
        headers_form = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Emby-Token": api_key
        }

        # 1) Risolvi l'ID utente
        user_id = get_user_id(server_ip, api_key, username)
        if not user_id:
            print(f"Utente '{username}' non trovato: impossibile cambiare password.")
            return False

        emby_url = f"{base}/emby/Users/{user_id}/Password"
        jf_url   = f"{base}/Users/{user_id}/Password"

        attempts = [
            # ---- JSON (Emby classico)
            ("JSON Emby: NewPw",        emby_url, headers_json, {"NewPw": new_password}),
            ("JSON Emby: NewPw+Reset",  emby_url, headers_json, {"NewPw": new_password, "ResetPassword": True}),

            # ---- JSON (Jellyfin compat Emby)
            ("JSON JF: NewPw",          jf_url,   headers_json, {"NewPw": new_password}),
            ("JSON JF: NewPw+Reset",    jf_url,   headers_json, {"NewPw": new_password, "ResetPassword": True}),

            # ---- JSON (Jellyfin moderno)
            ("JSON JF modern: NewPassword+Reset=True",  jf_url, headers_json, {"NewPassword": new_password, "ResetPassword": True}),
            ("JSON JF modern: NewPassword+Reset=False", jf_url, headers_json, {"NewPassword": new_password, "ResetPassword": False}),

            # ---- FORM-URLENCODED (alcune build particolari)
            ("FORM Emby: NewPw",        emby_url, headers_form, {"NewPw": new_password}),
            ("FORM JF: NewPw",          jf_url,   headers_form, {"NewPw": new_password}),
            ("FORM JF modern: NewPassword+Reset", jf_url, headers_form, {"NewPassword": new_password, "ResetPassword": "true"}),
        ]

        last_status = None
        last_text = None

        import requests
        for label, url, headers, payload in attempts:
            try:
                if headers is headers_form:
                    resp = requests.post(url, headers=headers, data=payload, timeout=timeout)
                else:
                    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

                last_status, last_text = resp.status_code, resp.text
                if resp.status_code in (200, 204):
                    print(f"[OK] {label} -> {url}")
                    return True
                else:
                    print(f"[FAIL {resp.status_code}] {label} -> {url} | body: {resp.text[:300]}")
            except requests.RequestException as e:
                print(f"[ERR NET] {label} -> {url} | {e}")

        # ---- Ultima ratio: querystring (alcune istanze custom)
        try:
            qs_attempts = [
                (f"{emby_url}?NewPw={requests.utils.quote(new_password)}", headers_json),
                (f"{jf_url}?NewPw={requests.utils.quote(new_password)}", headers_json),
                (f"{jf_url}?NewPassword={requests.utils.quote(new_password)}&ResetPassword=true", headers_json),
            ]
            for url, headers in qs_attempts:
                resp = requests.post(url, headers=headers, timeout=timeout)
                last_status, last_text = resp.status_code, resp.text
                if resp.status_code in (200, 204):
                    print(f"[OK] QS -> {url}")
                    return True
                else:
                    print(f"[FAIL {resp.status_code}] QS -> {url} | body: {resp.text[:300]}")
        except requests.RequestException as e:
            print(f"[ERR NET] QS -> {e}")

        print(f"ERRORE: impossibile aggiornare la password (ultimo stato: {last_status}). Dettagli: {last_text}")
        return False

    except Exception as e:
        print(f"Eccezione in change_password: {e}")
        return False

