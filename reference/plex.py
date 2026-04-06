from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount
import re
import paramiko
from dotenv import dotenv_values
env_vars = dotenv_values('.env')
DATABASE = env_vars['DATABASE']

import sqlite3

def plexremoveinvite(account, plexname):
    try:
        
        account.cancelInvite(plexname)
        print(plexname +' invite removed from plex')
        return "True"
    except Exception as e:
        print(e)
        return e.__str__()

def plexremove(account, plexname):
    try:
        account.removeFriend(user=plexname)
        
        print(plexname +' has been removed from plex')
        return "True"
    except Exception as e:
        print(e)
        return e.__str__()

def verifyemail(addressToVerify):
    regex = '^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,})$'
    match = re.match(regex, addressToVerify.lower())
    if match == None: 
        return False
    else:
        return True

def sendinvite(mail,PLEX_TOKEN,PLEX_URL,Plex_LIBS):
    print("Invio invito a: " + mail)
    try:
        account = MyPlexAccount(token=PLEX_TOKEN)
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)

        account.inviteFriend(user=mail, server=plex, sections=Plex_LIBS, allowSync=False,allowCameraUpload=False, allowChannels=False, filterMovies=None,filterTelevision=None, filterMusic=None)
        print(mail +' has been added to plex')
        return "True"
    except Exception as e:
        print(e)
        return e.__str__()
    
def rinnova(username,days):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        # Esempio: aggiorna il campo expiry sommando i giorni (assicurati che expiry sia gestito come intero o come logica appropriata)
        query = "UPDATE user SET expiry = expiry + ? WHERE pmail = ?"
        cursor.execute(query, (days, username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(e)
        return False
    return True

def servermenousato():
    
    return 'p1'  # o None oppure ['p2', 'p3']
    
def get_user_count(username):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        if username == "superadmin":
            count_query = "SELECT COUNT(*) FROM user"
            cursor.execute(count_query)
        else:
            count_query = "SELECT COUNT(*) FROM user WHERE id=?"
            cursor.execute(count_query, (username,))
        user_count = cursor.fetchone()[0]
        return user_count
    except Exception as e:
        print(e)
        return -1

def getuserver(username):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        # Esempio: aggiorna il campo expiry sommando i giorni (assicurati che expiry sia gestito come intero o come logica appropriata)
        query = "SELECT server FROM user WHERE pmail = ?"
        cursor.execute(query, (username,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
        else:
            return None
    except Exception as e:
        print(e)
        return None
    
    
#scorro tutti i server quindi query al db dentro la tabella plex per ogni riga nella colonna nome faccio una select count dentro la tabella 
#User dove nome=server e prendo il valore della count come risultato e genero una stringa in questo modo: Server p1 ha X utenti \n Server p2 ha x utenti ecc
def get_statoserver(default_max: int = 99, max_overrides: dict = None) -> str:
    """
    Ritorna una stringa con il numero di posti disponibili per ogni server presente nella tabella 'plex'.

    Args:
        db_path: Percorso al file SQLite.
        default_max: Numero massimo di utenti per server di default (default=99).
        max_overrides: Dizionario opzionale con override dei massimi per server, es. {"p1": 80, "p2": 98}.

    Returns:
        Una stringa con righe nel formato:
        Server <nome> ha <posti_disponibili> posti disponibili\n
    """
    # Connessione al database
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Ottieni tutti i nomi dei server dalla tabella 'plex'
    cursor.execute("SELECT nome FROM plex")
    servers = [row[0] for row in cursor.fetchall()]

    messages = []
    for server in servers:
        # Conta gli utenti corrispondenti al nome del server
        cursor.execute(
            'SELECT COUNT(*) FROM "User" WHERE server = ?',
            (server,)
        )
        used = cursor.fetchone()[0]

        # Determina massimo per il server
        max_slots = max_overrides.get(server, default_max) if max_overrides else default_max
        # Calcola posti disponibili
        available = max_slots - used
        if available < 0:
            available = 0

        messages.append(f"Server {server} ha {available} posti disponibili")

    # Chiudi la connessione e restituisci il risultato
    conn.close()
    return "\n".join(messages)