import requests
import json
import sqlite3
import importlib
import os
import sys
from datetime import datetime, timezone, timedelta
import pandas as pd
import funzioniapi as funzioniAPI
import re
from urllib.parse import urlparse
import random
from dotenv import dotenv_values

def _import_real_telebot():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    removed = []
    for entry in ("", project_dir):
        while entry in sys.path:
            sys.path.remove(entry)
            removed.append(entry)
    try:
        return importlib.import_module("telebot")
    finally:
        for entry in reversed(removed):
            sys.path.insert(0, entry)

telebot = _import_real_telebot()
env_vars = dotenv_values('.env')
DATABASE = env_vars['DATABASE']
TOKEN = env_vars['TOKEN']


bot = telebot.TeleBot(TOKEN)
embylog= int(env_vars['IDCANALELOG'])


def invia_messaggio(chat_id, messaggio):
    try:
        print(f"[INFO] Inviando messaggio a {chat_id}: {messaggio}")
        bot.send_message(chat_id, messaggio)
    except Exception as e:
        print(f"[ERRORE] Impossibile inviare messaggio a {chat_id}: {e}")
        
def inserisci_movimento(type,user,text,costo,saldo):
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = "INSERT INTO movimenti (type,date, user, text,costo,saldo) VALUES (?, ?, ?,?,?,?)"
    values = (type, date,user, text,costo,saldo)
    cursor.execute(query, values)                       
    conn.commit()
    conn.close()

def AggiungiEliminati(valori):
    try:
        if not valori or len(valori) < 4:
            return False
        idtelegram, username, expiry, server = valori
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        dataeliminazione = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "INSERT INTO eliminati (idtelegram, username, expiry, server, dataeliminazione) VALUES (?, ?, ?, ?, ?)"
        cursor.execute(query, (idtelegram, username, expiry, server, dataeliminazione))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(e)
        return False


def get_servername(server):
    nomeserver = ""
    porta = ""
    porta_https = 443
    indirizzoweb = ""
    indirizzoweb_https = ""
    richieste = "https://req.emby.at"

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM emby WHERE nome = ?", (server,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT url FROM jelly WHERE nome = ?", (server,))
            row = cursor.fetchone()
        conn.close()
        if row:
            indirizzoweb = row[0]
    except Exception as e:
        print(e)

    if indirizzoweb:
        parsed = urlparse(indirizzoweb)
        nomeserver = parsed.hostname or ""
        if parsed.port:
            porta = parsed.port
        elif parsed.scheme == "https":
            porta = 443
        elif parsed.scheme == "http":
            porta = 80
    if server and re.match(r'^[ej]\d+$', str(server)):
        indirizzoweb_https = f"https://{server}.emby.at"

    return nomeserver, richieste, porta, indirizzoweb, indirizzoweb_https, porta_https

def getmaster(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT idmaster FROM subseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    if df.empty:
        return None
    else:
        return df.loc[0, 'idmaster']
    
def getcredito(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM reseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    credito = df['credito'].values[0]
    credito = float(credito)
    return credito

def getsubcredito(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM subseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    credito = df['credito'].values[0]
    credito = float(credito)
    return credito

def getmaster(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT idmaster FROM subseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    if df.empty:
        return None
    else:
        return df.loc[0, 'idmaster']
    
def setcredito(id, nuovocredito):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Query per aggiornare il credito
        query = "UPDATE reseller SET credito = ? WHERE idtelegram = ?"
        cursor.execute(query, (nuovocredito, id))
        
        # Conferma l'aggiornamento
        conn.commit()
        
        # Chiudi la connessione
        conn.close()
        print(f"Credito aggiornato per ID {id} a {nuovocredito}")
        
    except Exception as e:
        print(f"Errore durante l'aggiornamento del credito: {str(e)}")
        
def setsubcredito(id, nuovocredito):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Query per aggiornare il credito
        query = "UPDATE subseller SET credito = ? WHERE idtelegram = ?"
        cursor.execute(query, (nuovocredito, id))
        
        # Conferma l'aggiornamento
        conn.commit()
        
        # Chiudi la connessione
        conn.close()
        print(f"Credito aggiornato per ID {id} a {nuovocredito}")
        
    except Exception as e:
        print(f"Errore durante l'aggiornamento del credito: {str(e)}")


def get_user_count(username):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        if username == "superadmin":
            count_query = "SELECT COUNT(*) FROM euser"
            cursor.execute(count_query)
        else:
            count_query = "SELECT COUNT(*) FROM euser WHERE id=?"
            cursor.execute(count_query, (username,))
        user_count = cursor.fetchone()[0]
        return user_count
    except Exception as e:
        print(e)
        return -1

def get_jellyuser_count(username):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        if username == "superadmin":
            count_query = "SELECT COUNT(*) FROM juser"
            cursor.execute(count_query)
        else:
            count_query = "SELECT COUNT(*) FROM juser WHERE id=?"
            cursor.execute(count_query, (username,))
        user_count = cursor.fetchone()[0]
        return user_count
    except Exception as e:
        print(e)
        return -1
    
def get_eliminati_count(username):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        if username == "superadmin":
            count_query = "SELECT COUNT(*) FROM eliminati"
            cursor.execute(count_query)
        else:
            count_query = "SELECT COUNT(*) FROM eliminati WHERE idtelegram=?"
            cursor.execute(count_query, (username,))
        user_count = cursor.fetchone()[0]
        return user_count
    except Exception as e:
        print(e)
        return -1

def get_gatto():
    url = "https://api.thecatapi.com/v1/images/search"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
    # Stampa la risposta ottenuta
        print(data)
        data = response.json()
        # Estrai l'URL dell'immagine dalla risposta JSON
        image_url = data[0]['url']
        # Invia l'immagine come risposta al messaggio
        return image_url
    else:
        print("Errore nella richiesta:", response.status_code)

def getincremento(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT incremento FROM subseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df['incremento'].values[0]

def calcola_prezzo(base_price, incremento):
    # Calcola il prezzo incrementato aggiungendo la percentuale
    return base_price + (base_price * incremento / 100)

def get_servizio_emby_da_server(server):
    conn = sqlite3.connect(DATABASE)
    try:
        row = conn.execute('SELECT tipo FROM emby WHERE nome = ?', (str(server),)).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    tipo = str(row[0]).strip().lower()
    if tipo == 'normale':
        return 'emby_normale'
    if tipo == 'premium':
        return 'emby_premium'
    return None

def get_prezzo_mensile(servizio, streaming):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query = """
        SELECT prezzo_mensile
        FROM prezzi
        WHERE servizio = ? AND streaming = ?
        ORDER BY rowid DESC
        LIMIT 1
    """
    cursor.execute(query, (servizio, int(streaming)))
    row = cursor.fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    return float(row[0])

def get_prezzi_servizio(servizio):
    prezzi = {}
    for schermi in range(1, 5):
        prezzi[schermi] = get_prezzo_mensile(servizio, schermi)
    return prezzi

def set_prezzo_mensile(servizio, streaming, prezzo_mensile):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    update_query = "UPDATE prezzi SET prezzo_mensile = ? WHERE servizio = ? AND streaming = ?"
    cursor.execute(update_query, (prezzo_mensile, servizio, int(streaming)))
    if cursor.rowcount == 0:
        insert_query = "INSERT INTO prezzi (servizio, streaming, prezzo_mensile) VALUES (?, ?, ?)"
        cursor.execute(insert_query, (servizio, int(streaming), prezzo_mensile))
    conn.commit()
    conn.close()

def calcola_costo_da_prezzo_mensile(servizio, schermi, giorni):
    prezzo_mensile = get_prezzo_mensile(servizio, schermi)
    if prezzo_mensile is None:
        raise ValueError(f"Prezzo non configurato per {servizio} con {schermi} schermi")
    return prezzo_mensile * (int(giorni) / 30.416)

def isreseller(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM reseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    if df.empty:
        return False
    else:
        return True

def issubseller(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM subseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    if df.empty:
        return False
    else:
        return True

def get4kstatus(username):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM eUser WHERE user='"+username+"'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    status = df.iloc[0]["4k"]
    if str(status).lower() == "true":
        return True
    elif str(status).lower() == "false":
        return False

def getjelly4kstatus(username):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM jUser WHERE user='"+username+"'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    status = df.iloc[0]["4k"]
    if str(status).lower() == "true":
        return True
    elif str(status).lower() == "false":
        return False

def emby_getdevices(username):
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(
        "SELECT device FROM devices WHERE user = ?",
        conn,
        params=(username,)
    )
    conn.close()
    if df.empty:
        return []
    return sorted(df['device'].dropna().unique().tolist())

def get_serverip(server):
    conn=sqlite3.connect(DATABASE)
    query="SELECT url,api FROM emby WHERE nome='"+server+"'"
    #restituisco url e api
    df=pd.read_sql_query(query, conn)
    conn.close()
    return str(df['url'].values[0]), str(df['api'].values[0])

def get_jellyserverip(server):
    conn=sqlite3.connect(DATABASE)
    query="SELECT url,api FROM jelly WHERE nome='"+server+"'"
    #restituisco url e api
    df=pd.read_sql_query(query, conn)
    conn.close()
    return str(df['url'].values[0]), str(df['api'].values[0])
    

def check_serverpieno(server):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM eUser WHERE server = ?", (server,))
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT capienza FROM emby WHERE nome = ?", (server,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        return user_count >= row[0]
    # Se il server non è in DB, considera pieno per sicurezza
    return True

def get_posti_disponibili_emby():
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT nome, capienza FROM emby WHERE capienza IS NOT NULL AND capienza > 0")
        servers = cursor.fetchall()
        disponibili = 0
        for nome, cap in servers:
            cursor.execute("SELECT COUNT(*) FROM eUser WHERE server = ?", (nome,))
            count = cursor.fetchone()[0]
            disponibili += max(cap - count, 0)
        conn.close()
        return disponibili
    except Exception as e:
        print(e)
        return 0


def cancella_utente(user):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query='SELECT server FROM eUser WHERE user = "'+user+'"'

    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    server = result[0]  # Estrarre il valore del campo server
    
    server_ip, api_key = get_serverip(server)
    print(server_ip, api_key)
    userid=funzioniAPI.get_user_id(server_ip, api_key, user)
    print(userid)
    status=funzioniAPI.delete_user(server_ip, api_key,userid)
    
    if status==True or userid==None:
        try:
            eliminato = None
            try:
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute("SELECT id, user, expiry, server FROM eUser WHERE user = ?", (user,))
                eliminato = cursor.fetchone()
                conn.close()
            except Exception as e:
                print(e)

            query="DELETE FROM eUser WHERE user='"+user+"'"
            #bot.send_message(message.chat.id, query)
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            try:
                cursor.execute(query)
                conn.commit()
                if eliminato:
                    AggiungiEliminati(eliminato)
                

            except Exception as e:
                print(e)

            query = "DELETE FROM bloccati WHERE user = '"+user+"'"
            #bot.send_message(message.chat.id, query
            # Connessione al database ed esecuzione della query
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()
            
            
        except Exception as e:
            print(e)
            return False
    else:
        return False
    return True


def jcancella_utente(user):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query='SELECT server FROM jUser WHERE user = "'+user+'"'

    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    server = result[0]  # Estrarre il valore del campo server
    
    server_ip, api_key = get_jellyserverip(server)
    print(server_ip, api_key)
    userid=funzioniAPI.get_user_id(server_ip, api_key, user)
    print(userid)
    status=funzioniAPI.delete_user(server_ip, api_key,userid)
    
    if status==True or userid==None:
        try:
            eliminato = None
            try:
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute("SELECT id, user, expiry, server FROM jUser WHERE user = ?", (user,))
                eliminato = cursor.fetchone()
                conn.close()
            except Exception as e:
                print(e)

            query="DELETE FROM jUser WHERE user='"+user+"'"
            #bot.send_message(message.chat.id, query)
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            try:
                cursor.execute(query)
                conn.commit()
                if eliminato:
                    AggiungiEliminati(eliminato)
                

            except Exception as e:
                print(e)

            query = "DELETE FROM bloccati WHERE user = '"+user+"'"
            #bot.send_message(message.chat.id, query
            # Connessione al database ed esecuzione della query
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()
            
            
        except Exception as e:
            print(e)
            return False
    else:
        return False
    return True


def togli4k_utente(user):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query='SELECT server FROM eUser WHERE user = "'+user+'"'

        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()
        server = result[0]  # Estrarre il valore del campo server
        server_ip, api_key = get_serverip(server)

        status=funzioniAPI.disable4k(user, server_ip, api_key)
        print(status)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query = "UPDATE eUser SET `4k` = 'false' WHERE user = '" + user + "'"
        cursor.execute(query)
        result = cursor.fetchone()
        conn.commit()
        conn.close()
    except Exception as e:
        print(e)
        return False
        
    return status          

def metti4k_utente(user):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query='SELECT server FROM eUser WHERE user = "'+user+'"'

    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    server = result[0]  # Estrarre il valore del campo server
    server_ip, api_key = get_serverip(server)
    
    status=funzioniAPI.enable4k(user, server_ip, api_key)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query = "UPDATE eUser SET `4k` = 'true' WHERE user = '" + user + "'"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.commit()
    conn.close()
    return status      

def jtogli4k_utente(user):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        query = 'SELECT server, schermi FROM jUser WHERE user = ?'
        cursor.execute(query, (user,))
        result = cursor.fetchone()
        conn.close()

        if result:
            server, schermi = result  # unpack diretto delle due colonne
            server_ip, api_key = get_jellyserverip(server)

            status = funzioniAPI.disable4k_jellyfin(user, server_ip, api_key, schermi)
        else:
            status = None
        print(f"User {user} non trovato nel database")
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query = "UPDATE jUser SET `4k` = 'false' WHERE user = '" + user + "'"
        cursor.execute(query)
        result = cursor.fetchone()
        conn.commit()
        conn.close()
    except Exception as e:
        print(e)
        return False
        
    return status          

def jmetti4k_utente(user):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    query = 'SELECT server, schermi FROM jUser WHERE user = ?'
    cursor.execute(query, (user,))
    result = cursor.fetchone()
    conn.close()

    if result:
        server, schermi = result  # unpack diretto delle due colonne
        server_ip, api_key = get_jellyserverip(server)

        status = funzioniAPI.enable4k_jellyfin(user, server_ip, api_key, schermi)
    else:
        status = None
    print(f"User {user} non trovato nel database")
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    query = "UPDATE jUser SET `4k` = 'true' WHERE user = '" + user + "'"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.commit()
    conn.close()
    return status   

def getscadenzausername(username):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT user, date, expiry FROM eUser WHERE user = ?"
    
    # Eseguo la query e ottengo i dati per l'username specifico
    df = pd.read_sql_query(query, conn, params=(username,))
    conn.close()
    
    # Controllo se l'utente esiste
    if df.empty:
        return None  # L'utente non è presente nel database
    
    # Estrai la data e i giorni di expiry
    created_date = datetime.strptime(df.loc[0, 'date'], '%Y-%m-%d %H:%M:%S')   # Formato della data nel database
    expiry_days = int(df.loc[0, 'expiry'])
    
    # Calcolo della data di scadenza
    expiry_date = created_date + timedelta(days=expiry_days)
    return expiry_date

def getscadenzausernamejelly(username):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT user, date, expiry FROM jUser WHERE user = ?"
    
    # Eseguo la query e ottengo i dati per l'username specifico
    df = pd.read_sql_query(query, conn, params=(username,))
    conn.close()
    
    # Controllo se l'utente esiste
    if df.empty:
        return None  # L'utente non è presente nel database
    
    # Estrai la data e i giorni di expiry
    created_date = datetime.strptime(df.loc[0, 'date'], '%Y-%m-%d %H:%M:%S')   # Formato della data nel database
    expiry_days = int(df.loc[0, 'expiry'])
    
    # Calcolo della data di scadenza
    expiry_date = created_date + timedelta(days=expiry_days)
    return expiry_date

def rinnova(reseller, username, giorni, schermi):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query = 'SELECT server FROM eUser WHERE user = "' + username + '"'
        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()
        server = result[0]  # Estrarre il valore del campo server
    except Exception as e:
        return "Errore nel recupero del server: " + str(e)

    incremento = 0
    try:
        if reseller == "superadmin":
            creditoattuale = 0
        else:
            if issubseller(reseller):
                creditoattuale = getsubcredito(reseller)
                incremento = getincremento(reseller)
            else:
                creditoattuale = getcredito(reseller)
    except Exception as e:
        return "Errore nel calcolo del credito: " + str(e)

    try:
        if int(giorni) < 1:
            return "Numero di giorni non valido"
        if int(schermi) < 1 or int(schermi) > 4:
            return "schermi non validi"
        servizio = get_servizio_emby_da_server(server)
        if not servizio:
            return "Server non riconosciuto per il calcolo prezzi"
        costo = calcola_costo_da_prezzo_mensile(servizio, int(schermi), int(giorni))
        costonormale = costo
        costo = calcola_prezzo(costo, incremento)
    except Exception as e:
        return "Errore nel calcolo del costo: " + str(e)

    try:
        if (creditoattuale - costo) < -75:
            return "debito troppo alto"
        else:
                
            scadenza = getscadenzausername(username)
            scadenza_str = scadenza.strftime('%Y-%m-%d %H:%M:%S')
                
            oggi = datetime.now()
                
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT schermi FROM eUser WHERE user = ?", (username,))
            result = cursor.fetchone()
            conn.close()

            if result:
                schermi_precedenti = result[0]
            else:
                schermi_precedenti = 1  # oppure un valore di default se l'utente non viene trovato
                
            if schermi_precedenti==None:
                schermi_precedenti=1
                
            if schermi_precedenti < schermi:
                print("gli schermi di adesso sono di più")
                giorni_mancanti = (scadenza - oggi).days
                if giorni_mancanti >= 15:
                    return "Errore: Mancano {} giorni alla scadenza, non è possibile aumentare il numero di schermi se non a meno di 15 giorni dalla scadenza".format(giorni_mancanti)


            if oggi > scadenza:
                giorni_passati = (oggi - scadenza).days
                print("ho aggiunto dei giorni perchè era scaduto:"+str(giorni_passati))
            else:
                giorni_passati = 0
            
            giorni=giorni+giorni_passati
            
            query = "UPDATE eUser SET expiry = expiry + " + str(giorni) + " WHERE user = '" + username + "'"
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()

            # Aggiorna il numero di schermi
            query = "UPDATE eUser SET schermi = " + str(schermi) + " WHERE user = '" + username + "'"
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()

            server_ip, api_key = get_serverip(server)

            userid = funzioniAPI.get_user_id(server_ip, api_key, username)
            status = funzioniAPI.enable_user(server_ip, api_key, userid, schermi)
            query = "DELETE FROM bloccati WHERE user = '" + username + "'"
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()

            if reseller=="superadmin":
                print("non pago")
                invia_messaggio(embylog, "ho rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server))
            else:
                if issubseller(reseller):
                    setsubcredito(reseller, float(creditoattuale) - float(costo))
                    idmaster = getmaster(reseller)
                    creditoattualemaster = getcredito(idmaster)
                    tempcredito = float(creditoattualemaster) + float(costo - costonormale)
                    setcredito(int(idmaster), float(tempcredito))
                    inserisci_movimento("commissione", int(idmaster), username, costo-costonormale, creditoattualemaster + (costo-costonormale))
                    invia_messaggio(idmaster, "Il tuo reseller " + str(reseller) + " ha rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server))
                    invia_messaggio(idmaster, "hai guadagnato " + (costo - costonormale).__str__() + "€")
                    invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server)+ " hai guadagnato " + (costo - costonormale).__str__() + "€")
                elif isreseller(reseller):
                    setcredito(reseller, float(creditoattuale) - float(costo))
                    invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server))

            if get4kstatus(username):
                status = funzioniAPI.enable4k(username, server_ip, api_key)
                print("4k messi")
            else:
                status = funzioniAPI.disable4k(username, server_ip, api_key)
                print("4k tolti")

            scadenza = getscadenzausername(username)
            scadenza_str = scadenza.strftime('%Y-%m-%d %H:%M:%S')

            report_message = (
                "📊 *Report Operazione*\n\n"
                "💰 Credito attuale: {:.2f}€\n"
                "💸 Costo operazione: {:.2f}€\n"
                "✅ Utente *{}* esteso con successo\n"
                "🗓️ Nuova scadenza: {}\n"
                "🔮 Credito residuo: {:.2f}€\n"
                "<a href='https://res.emby.at/utente/{}'>https://res.emby.at/utente/{}</a>"

                
            ).format(creditoattuale, costo, username, scadenza_str, creditoattuale - costo,username,username)
            
            inserisci_movimento("rinnovo", reseller, username, costo, creditoattuale - costo)
            return report_message
    except Exception as e:
        return "Errore durante l'aggiornamento e le operazioni finali: " + str(e)

def jrinnova(reseller, username, giorni, schermi):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query = 'SELECT server FROM jUser WHERE user = "' + username + '"'
        cursor.execute(query)
        result = cursor.fetchone()
        conn.close()
        server = result[0]  # Estrarre il valore del campo server
    except Exception as e:
        return "Errore nel recupero del server: " + str(e)

    incremento = 0
    try:
        if reseller == "superadmin":
            creditoattuale = 0
        else:
            if issubseller(reseller):
                creditoattuale = getsubcredito(reseller)
                incremento = getincremento(reseller)
            else:
                creditoattuale = getcredito(reseller)
    except Exception as e:
        return "Errore nel calcolo del credito: " + str(e)

    try:
        if int(giorni) < 1:
            return "Numero di giorni non valido"
        if int(schermi) < 1 or int(schermi) > 4:
            return "schermi non validi"
        costo = calcola_costo_da_prezzo_mensile("jellyfin", int(schermi), int(giorni))
        costonormale = costo
        costo = calcola_prezzo(costo, incremento)
    except Exception as e:
        return "Errore nel calcolo del costo: " + str(e)

    try:
        if (creditoattuale - costo) < -75:
            return "debito troppo alto"
        else:
                
            scadenza = getscadenzausernamejelly(username)
            scadenza_str = scadenza.strftime('%Y-%m-%d %H:%M:%S')
                
            oggi = datetime.now()
                
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT schermi FROM jUser WHERE user = ?", (username,))
            result = cursor.fetchone()
            conn.close()

            if result:
                schermi_precedenti = result[0]
            else:
                schermi_precedenti = 1  # oppure un valore di default se l'utente non viene trovato
                
            if schermi_precedenti==None:
                schermi_precedenti=1
                
            if schermi_precedenti < schermi:
                print("gli schermi di adesso sono di più")
                giorni_mancanti = (scadenza - oggi).days
                if giorni_mancanti >= 15:
                    return "Errore: Mancano {} giorni alla scadenza, non è possibile aumentare il numero di schermi se non a meno di 15 giorni dalla scadenza".format(giorni_mancanti)

            if oggi > scadenza:
                giorni_passati = (oggi - scadenza).days
                print("ho aggiunto dei giorni perchè era scaduto:"+str(giorni_passati))
            else:
                giorni_passati = 0
            
            giorni=giorni+giorni_passati
            
            query = "UPDATE jUser SET expiry = expiry + " + str(giorni) + " WHERE user = '" + username + "'"
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()

            # Aggiorna il numero di schermi
            query = "UPDATE jUser SET schermi = " + str(schermi) + " WHERE user = '" + username + "'"
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()

            server_ip, api_key = get_jellyserverip(server)

            userid = funzioniAPI.get_user_id(server_ip, api_key, username)
            status = funzioniAPI.enable_user_jellyfin(server_ip, api_key, userid, schermi)
            query = "DELETE FROM bloccati WHERE user = '" + username + "'"
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            conn.close()

            if reseller=="superadmin":
                print("non pago")
                invia_messaggio(embylog, "ho rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server))
            else:
                if issubseller(reseller):
                    setsubcredito(reseller, float(creditoattuale) - float(costo))
                    idmaster = getmaster(reseller)
                    creditoattualemaster = getcredito(idmaster)
                    tempcredito = float(creditoattualemaster) + float(costo - costonormale)
                    setcredito(int(idmaster), float(tempcredito))
                    inserisci_movimento("commissione", int(idmaster), username, costo-costonormale, creditoattualemaster + (costo-costonormale))
                    invia_messaggio(idmaster, "Il tuo reseller " + str(reseller) + " ha rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server))
                    invia_messaggio(idmaster, "hai guadagnato " + (costo - costonormale).__str__() + "€")
                    invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server)+ " hai guadagnato " + (costo - costonormale).__str__() + "€")
                elif isreseller(reseller):
                    setcredito(reseller, float(creditoattuale) - float(costo))
                    invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha rinnovato l'utente " + str(username) + " con " + str(schermi) + " schermi e " + str(giorni) + " giorni di scadenza" + " sul server " + str(server))

            if getjelly4kstatus(username):
                status = funzioniAPI.enable4k_jellyfin(username, server_ip, api_key,schermi)
                print("4k messi")
            else:
                status = funzioniAPI.disable4k_jellyfin(username, server_ip, api_key,schermi)
                print("4k tolti")

            scadenza = getscadenzausernamejelly(username)
            scadenza_str = scadenza.strftime('%Y-%m-%d %H:%M:%S')

            report_message = (
                "📊 *Report Operazione*\n\n"
                "💰 Credito attuale: {:.2f}€\n"
                "💸 Costo operazione: {:.2f}€\n"
                "✅ Utente *{}* esteso con successo\n"
                "🗓️ Nuova scadenza: {}\n"
                "🔮 Credito residuo: {:.2f}€\n"
                "<a href='https://res.emby.at/jutente/{}'>https://res.emby.at/jutente/{}</a>"

                
            ).format(creditoattuale, costo, username, scadenza_str, creditoattuale - costo,username,username)
            
            inserisci_movimento("rinnovo", reseller, username, costo, creditoattuale - costo)
            return report_message
    except Exception as e:
        return "Errore durante l'aggiornamento e le operazioni finali: " + str(e)

def jsblocca_utente(username):
    try:
        # Recupera server e schermi dal database api key e userid
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query = 'SELECT server, schermi FROM jUser WHERE user = ?'
        cursor.execute(query, (username,))
        result = cursor.fetchone()
        conn.close()
        if not result:
            print(f"User {username} non trovato nel database")
            return False
        server, schermi = result  # unpack diretto delle due colonne
        server_ip, api_key = get_jellyserverip(server)  
        userid = funzioniAPI.get_user_id(server_ip, api_key, username)
        if userid is None:
            print(f"User ID per {username} non trovato sul server Jellyfin")
            return False
        # Prima disabilita e poi riabilita l'utente per applicare le modifiche
        
        
        status = funzioniAPI.disable_user_jellyfin(server_ip, api_key, userid, schermi)
        status = funzioniAPI.enable_user_jellyfin(server_ip, api_key, userid, schermi)

        return True
    except Exception as e:
        print(e)
        return False

def getserverpredef(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM reseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df['server'].values[0]

def getsubserverpredef(id):
    conn = sqlite3.connect(DATABASE)
    query = "SELECT * FROM subseller WHERE idtelegram="+id.__str__()
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df['server'].values[0]

def creavenditore(venditore_id, password):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM reseller WHERE idtelegram = ?"
        cursor.execute(query, (venditore_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            return "Il venditore esiste già."
        
        # controllo che non sia un subseller
        query = "SELECT COUNT(*) FROM subseller WHERE idtelegram = ?"
        cursor.execute(query, (venditore_id,))
        count_subseller = cursor.fetchone()[0]
        if count_subseller > 0:
            return "Il venditore è già un subseller."
        
        # Inserimento del nuovo venditore
        query = "INSERT INTO reseller (idtelegram, password) VALUES (?, ?)"
        cursor.execute(query, (venditore_id, password))
        conn.commit()
        
        return "Venditore creato con successo."
    except Exception as e:
        return f"Errore durante la creazione del venditore: {str(e)}"
    finally:
        conn.close()

def getservermenousato():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT nome FROM emby WHERE LOWER(tipo) = 'normale'")
    servers = [row[0] for row in cursor.fetchall()]
    counts = {}
    for server in servers:
        cursor.execute("SELECT COUNT(*) FROM euser WHERE server = ?", (server,))
        counts[server] = cursor.fetchone()[0]
    conn.close()
    return min(counts, key=counts.get) if counts else None

def getserverpremium_casuale():
    """Restituisce un server premium con limite='no' scelto casualmente, o None se non disponibile."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT nome FROM emby WHERE LOWER(tipo) = 'premium' AND LOWER(limite) = 'no'")
    servers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return random.choice(servers) if servers else None
    

def creautente(reseller,username,password,servertype,expiry,schermi,adminselect,adminidtelegram):
    prob_e6 = 0.2  # Probabilità di scelta del server e6
        # Scelta casuale in base alla probabilità
    print(servertype)
    if servertype=="normale":
        #server = "e6" if random.random() < prob_e6 else "e0"
        server = getservermenousato()
    else:
        if(reseller=="superadmin"):
            server=adminselect
        else:
            server = getserverpremium_casuale()
            if server is None:
                return "Nessun server premium disponibile al momento"
        
    incremento=0
    if reseller=="superadmin":
        creditoattuale=0
    else:
        if issubseller(reseller):
            creditoattuale=getsubcredito(reseller)
            incremento=getincremento(reseller)
        else:
            creditoattuale=getcredito(reseller)
    
        
    if int(schermi) < 1 or int(schermi) > 4:
        return "numero di schermi non valido"

    if int(expiry)<=3:
        costo=0
        costonormale=0
    else:
        servizio = get_servizio_emby_da_server(server)
        if not servizio:
            return "Server non riconosciuto per il calcolo prezzi"
        costo = calcola_costo_da_prezzo_mensile(servizio, int(schermi), int(expiry))
        costonormale=costo
        costo=calcola_prezzo(costo, incremento)
    
    #controllo se il server è pieno
    pieno = check_serverpieno(server)
    if pieno:
        return "server pieno, scegli un altro server o riprova più tardi"

    if (creditoattuale-costo)<-75:
            return "debito troppo alto"
    else:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            query = """
                SELECT COUNT(*) 
                FROM (
                    SELECT user FROM eUser
                    UNION ALL
                    SELECT user FROM jUser
                ) 
                WHERE user = ? COLLATE NOCASE
            """
            cursor.execute(query, (username,))
            print(query)
            #cursor.execute(query)
    
            count = cursor.fetchone()[0]
            conn.close()
    
            server_ip, api_key = get_serverip(server)
    
            if count > 0:
                return "l'utente esiste già. scegli un username diverso"
            else:
                funzioniAPI.create_user(server_ip, api_key, username, password)
                idemby=funzioniAPI.get_user_id(server_ip, api_key, username)
    
                if idemby==None:
                    return "errore comunicazione con server emby forse è offline? contattami subito"
                else:
                    setup=funzioniAPI.default_user_policy(server_ip, api_key, idemby, schermi)
                    if setup==True:
                            
                        conn = sqlite3.connect(DATABASE)
                        cursor = conn.cursor()
                        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        query = "INSERT INTO eUser (id, user, date, expiry, server, schermi, password) VALUES (?, ?, ?, ?, ?, ?, ?)"
                        if reseller=="superadmin":
                            values = (adminidtelegram, username, date, expiry, server, schermi, password)

                        else:
                            values = (reseller, username, date, expiry, server, schermi, password)
                        
                        cursor.execute(query, values)                       
                        conn.commit()
                            #bot.send_message(message.chat.id, "query eseguita")
                        conn.close()
                        status=funzioniAPI.disable4k(username, server_ip, api_key)

                        if reseller=="superadmin":
                            print("gratis")
                        else:
                            if issubseller(reseller):
                                setsubcredito(reseller, float(creditoattuale)-float(costo))
                                idmaster=getmaster(reseller)
                                creditoattualemaster=getcredito(idmaster)
                                tempcredito=float(creditoattualemaster)+float(costo-costonormale)
                                setcredito(int(idmaster), float(tempcredito))
                                #bot.send_message(idmaster, "Il tuo reseller "+get_username(id_telegram)+" ha creato un nuovo utente "+user+" con "+schermi+" schermi e "+expiry+" giorni di scadenza"+ "sul server "+server)
                                #bot.send_message(idmaster, "hai guadagnato "+(costo-costonormale).__str__()+"€")
                                inserisci_movimento("commissione", int(idmaster), username, costo-costonormale, creditoattualemaster + (costo-costonormale))
                                invia_messaggio(idmaster, "Il tuo reseller " + str(reseller) + " ha creato un nuovo utente " + str(username) + " con " + str(schermi) + " schermi e " + str(expiry) + " giorni di scadenza" + " sul server " + str(server))
                                invia_messaggio(idmaster, "hai guadagnato " + (costo - costonormale).__str__() + "€")
                                invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha creato un nuovo utente " + str(username) + " con " + str(schermi) + " schermi e " + str(expiry) + " giorni di scadenza" + " sul server " + str(server)+ " hai guadagnato " + (costo - costonormale).__str__() + "€")
                            else:
                                setcredito(reseller, float(creditoattuale)-float(costo))
                                invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha creato un nuovo utente " + str(username) + " con " + str(schermi) + " schermi e " + str(expiry) + " giorni di scadenza" + " sul server " + str(server))
                            
                        report_message = (
                            "📊 *Operazione Completata*\n\n"
                            "💰 Credito attuale: {:.2f}€\n"
                            "💸 Costo operazione: {:.2f}€\n"
                            "🔮 Credito residuo: {:.2f}€\n"
                            "<a href='https://res.emby.at/utente/{}'>https://res.emby.at/utente/{}</a>"
                        ).format(creditoattuale, costo, creditoattuale - costo, username, username)
                        
                        inserisci_movimento("crea", reseller, username+"", costo,creditoattuale - costo)
                        return report_message
                    
def creautentejelly(reseller,username,password,expiry,schermi,adminselect,adminidtelegram):
    
    if(reseller=="superadmin"):
        server=adminselect
    else:
        if issubseller(reseller):
            server="j2"
        elif isreseller(reseller):
            server="j2"
        
    incremento=0
    costo=0
    if reseller=="superadmin":
        creditoattuale=0
    else:
        if issubseller(reseller):
            creditoattuale=getsubcredito(reseller)
            incremento=getincremento(reseller)
        else:
            creditoattuale=getcredito(reseller)
    
        
    if int(schermi) < 1 or int(schermi) > 4:
        return "numero di schermi non valido"

    if int(expiry)<=3:
        costo=0
        costonormale=0
    else:
        costo = calcola_costo_da_prezzo_mensile("jellyfin", int(schermi), int(expiry))
        costonormale=costo
        costo=calcola_prezzo(costo, incremento)
        

    if (creditoattuale-costo)<-75:
            return "debito troppo alto"
    else:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            query = """
                SELECT COUNT(*) 
                FROM (
                    SELECT user FROM eUser
                    UNION ALL
                    SELECT user FROM jUser
                ) 
                WHERE user = ? COLLATE NOCASE
            """
            cursor.execute(query, (username,))
            #cursor.execute(query)
            
            count = cursor.fetchone()[0]
            
            conn.close()
    
            server_ip, api_key = get_jellyserverip(server)
    
            if count > 0:
                return "l'utente esiste già. scegli un username diverso"
            else:
                funzioniAPI.create_user(server_ip, api_key, username, password)
                idemby=funzioniAPI.get_user_id(server_ip, api_key, username)

                if idemby==None:
                    return "errore comunicazione con server emby forse è offline? contattami subito"
                else:
                    setup=funzioniAPI.default_user_policy_jellyfin(server_ip, api_key, idemby, schermi)
                    if setup==True:
                            
                        conn = sqlite3.connect(DATABASE)
                        cursor = conn.cursor()
                        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        query = "INSERT INTO jUser (id, user, date, expiry, server, schermi, password) VALUES (?, ?, ?, ?, ?, ?, ?)"
                        if reseller=="superadmin":
                            values = (adminidtelegram, username, date, expiry, server, schermi, password)

                        else:
                            values = (reseller, username, date, expiry, server, schermi, password)
                        
                        cursor.execute(query, values)                       
                        conn.commit()
                            #bot.send_message(message.chat.id, "query eseguita")
                        conn.close()
                        status=funzioniAPI.disable4k_jellyfin(username, server_ip, api_key, schermi)

                        if reseller=="superadmin":
                            print("gratis")
                        else:
                            if issubseller(reseller):
                                setsubcredito(reseller, float(creditoattuale)-float(costo))
                                idmaster=getmaster(reseller)
                                creditoattualemaster=getcredito(idmaster)
                                tempcredito=float(creditoattualemaster)+float(costo-costonormale)
                                setcredito(int(idmaster), float(tempcredito))
                                #bot.send_message(idmaster, "Il tuo reseller "+get_username(id_telegram)+" ha creato un nuovo utente "+user+" con "+schermi+" schermi e "+expiry+" giorni di scadenza"+ "sul server "+server)
                                #bot.send_message(idmaster, "hai guadagnato "+(costo-costonormale).__str__()+"€")
                                inserisci_movimento("commissione", int(idmaster), username, costo-costonormale, creditoattualemaster + (costo-costonormale))
                                invia_messaggio(idmaster, "Il tuo reseller " + str(reseller) + " ha creato un nuovo utente " + str(username) + " con " + str(schermi) + " schermi e " + str(expiry) + " giorni di scadenza" + " sul server " + str(server))
                                invia_messaggio(idmaster, "hai guadagnato " + (costo - costonormale).__str__() + "€")
                                invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha creato un nuovo utente " + str(username) + " con " + str(schermi) + " schermi e " + str(expiry) + " giorni di scadenza" + " sul server " + str(server)+ " hai guadagnato " + (costo - costonormale).__str__() + "€")
                            else:
                                setcredito(reseller, float(creditoattuale)-float(costo))
                                invia_messaggio(embylog, "Il tuo reseller " + str(reseller) + " ha creato un nuovo utente " + str(username) + " con " + str(schermi) + " schermi e " + str(expiry) + " giorni di scadenza" + " sul server " + str(server))
                            
                        report_message = (
                            "📊 *Operazione Completata*\n\n"
                            "💰 Credito attuale: {:.2f}€\n"
                            "💸 Costo operazione: {:.2f}€\n"
                            "🔮 Credito residuo: {:.2f}€\n"
                            "<a href='https://res.emby.at/jutente/{}'>https://res.emby.at/jutente/{}</a>"
                        ).format(creditoattuale, costo, creditoattuale - costo, username, username)
                        
                        inserisci_movimento("creaj", reseller, username+"", costo,creditoattuale - costo)
                        return report_message
                    
def cambia_password(username: str, new_password: str) -> bool | str:
    """
    Cambia la password di un utente Emby (dato lo username).
    - Valida minimamente la nuova password.
    - Recupera server, risolve (url, api_key) e delega a funzioniAPI.change_password.
    Ritorna:
      - True se tutto ok
      - string di errore descrittivo in caso di problemi
    """
    try:
        # Validazione minimale lato server
        if not isinstance(new_password, str) or len(new_password.strip()) < 5:
            return "La password deve contenere almeno 5 caratteri."
        if " " in new_password:
            return "La password non può contenere spazi."

        # Recupera il server dell'utente dalla tabella eUser
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT server FROM eUser WHERE user = ?", (username,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return f"Utente {username} non trovato o non autorizzato."

        server = row[0]
        server_ip, api_key = get_serverip(server)

        # Esegue il cambio password via API (gestisce sia Emby che Jellyfin-compatible)
        ok = funzioniAPI.change_password(server_ip, api_key, username, new_password)
        if ok:
            return True
        else:
            return "Impossibile aggiornare la password su Emby (API)."

    except Exception as e:
        return f"Errore durante il cambio password: {e}"

def jcambia_password(username: str, new_password: str) -> bool | str:
    """
    Cambia la password di un utente Jellyfin (dato lo username in jUser).
    Usa get_jellyserverip e la stessa funzione funzioniAPI.change_password.
    """
    try:
        if not isinstance(new_password, str) or len(new_password.strip()) < 5:
            return "La password deve contenere almeno 5 caratteri."
        if " " in new_password:
            return "La password non può contenere spazi."

        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        cur.execute("SELECT server FROM jUser WHERE user = ?", (username,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return f"Utente {username} non trovato su Jellyfin."

        server = row[0]
        server_ip, api_key = get_jellyserverip(server)

        ok = funzioniAPI.change_password(server_ip, api_key, username, new_password)
        if ok:
            return True
        else:
            return "Impossibile aggiornare la password su Jellyfin (API)."

    except Exception as e:
        return f"Errore durante il cambio password Jellyfin: {e}"
