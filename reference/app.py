from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import timedelta, datetime
from datetime import timezone
import os
import sys
import atexit
import subprocess
import emby
from markupsafe import Markup
import logging
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import plex as plexpi
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
import importlib
from dotenv import dotenv_values
import funzioniapi
env_vars = dotenv_values('.env')

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

#####################################################
# Configurazione del bot Telegram
TOKEN = env_vars['TOKEN']
bot = telebot.TeleBot(TOKEN)
# ID del canale Telegram dove inviare i messaggi di log
embylog= int(env_vars['IDCANALELOG'])
#percorso del database SQLite
DATABASE = env_vars['DATABASE']
SUPERPASSWORD=env_vars['SUPERPASSWORD']
#################################################



def invia_messaggio(chat_id, messaggio):
    try:
        print(f"[INFO] Inviando messaggio a {chat_id}: {messaggio}")
        bot.send_message(chat_id, messaggio)
    except Exception as e:
        print(f"[ERRORE] Impossibile inviare messaggio a {chat_id}: {e}")

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,  # Imposta il livello minimo di log (può essere DEBUG, INFO, WARNING, etc.)
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

import pandas as pd
import numpy as np
import json
import threading

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_OK = True
except ImportError:
    APSCHEDULER_OK = False

app = Flask(__name__)
app.secret_key = '\x12\x98\tb|\xca\t\x9a\xef\xb5\xa9z'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# ─── Migrazione DB: aggiunge colonna formatodata se non esiste ────────────────
def _migrate_db():
    conn = sqlite3.connect(DATABASE)
    for table in ('reseller', 'subseller'):
        try:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN formatodata TEXT DEFAULT NULL')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # colonna già esistente
    conn.close()

_migrate_db()

# ─── Formato data utente ──────────────────────────────────────────────────────
DATE_FORMAT_OPTIONS = [
    ('%d/%m/%Y', 'GG/MM/AAAA', '16/03/2026'),
    ('%d-%m-%Y', 'GG-MM-AAAA', '16-03-2026'),
    ('%d/%m/%y', 'GG/MM/AA',   '16/03/26'),
    ('%d.%m.%Y', 'GG.MM.AAAA', '16.03.2026'),
    ('%Y-%m-%d', 'AAAA-MM-GG', '2026-03-16'),
    ('%Y/%m/%d', 'AAAA/MM/GG', '2026/03/16'),
    ('%m/%d/%Y', 'MM/GG/AAAA', '03/16/2026'),
]
_VALID_DATE_FORMATS = {f[0] for f in DATE_FORMAT_OPTIONS}

def _load_date_format(user_id):
    """Legge formatodata da DB per l'utente corrente."""
    if not user_id or user_id == 'superadmin':
        return '%Y-%m-%d'
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT formatodata FROM reseller WHERE idtelegram=?', (str(user_id),)
    ).fetchone()
    if not row:
        row = conn.execute(
            'SELECT formatodata FROM subseller WHERE idtelegram=?', (str(user_id),)
        ).fetchone()
    conn.close()
    if row and row[0] and row[0] in _VALID_DATE_FORMATS:
        return row[0]
    return '%Y-%m-%d'

def get_user_date_format():
    """Restituisce il formato data dell'utente in sessione."""
    if 'date_format' not in session:
        session['date_format'] = _load_date_format(session.get('user'))
    return session['date_format']

# ─── Preferenze copia info ────────────────────────────────────────────────────
def _load_preferenze(user_id):
    """Legge la colonna preferenze da DB per l'utente corrente."""
    if not user_id or user_id == 'superadmin':
        return ''
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT preferenze FROM reseller WHERE idtelegram=?', (str(user_id),)
    ).fetchone()
    if not row:
        row = conn.execute(
            'SELECT preferenze FROM subseller WHERE idtelegram=?', (str(user_id),)
        ).fetchone()
    conn.close()
    return (row[0] or '') if row else ''

def get_user_preferenze():
    """Restituisce le preferenze copia dell'utente in sessione."""
    if 'copy_prefs' not in session:
        session['copy_prefs'] = _load_preferenze(session.get('user'))
    return session['copy_prefs']

# ─── Scheduler schedulazioni ────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEDULES_FILE = os.path.join(_BASE_DIR, 'schedules.json')
_sched_lock = threading.Lock()
_bg_scheduler = None

# Catalogo script disponibili (aggiungi qui i nuovi script)
SCRIPTS_CATALOG = {
    "telegram_test": {
        "name": "Test Telegram",
        "description": "Invia il messaggio FUNZIONA al chat ID configurato",
        "script": "scripts/telegram_test.py",
        "timeout": 30,
    },
    "devices2": {
        "name": "Calcola Dispositivi",
        "description": "Scarica activitylog.db via SSH dai server Emby e aggiorna la tabella devices",
        "script": "scripts/devices2.py",
        "timeout": 120,
    },
    "notifichescadenza": {
        "name": "Notifiche Scadenza",
        "description": "Invia notifica Telegram agli utenti Plex/Emby/Jellyfin che scadono entro 4 giorni",
        "script": "scripts/notifichescadenza.py",
        "timeout": 120,
    },
    "bloccaemby": {
        "name": "Blocca Emby Scaduti",
        "description": "Disabilita automaticamente su Emby gli utenti con abbonamento scaduto e li inserisce in tabella bloccati",
        "script": "scripts/bloccaemby.py",
        "timeout": 120,
    },
    "verificapremiere": {
        "name": "Verifica Premiere",
        "description": "Controlla lo stato Emby Premiere su ogni server via Selenium e aggiorna il campo 'limite' nel database",
        "script": "scripts/verificapremiere.py",
        "timeout": 1800,
    },
}

def load_schedules():
    """Carica la configurazione schedulazioni dal file JSON."""
    with _sched_lock:
        if os.path.exists(SCHEDULES_FILE):
            try:
                with open(SCHEDULES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        else:
            data = {}
        # Assicura che tutti gli script del catalogo siano presenti
        for sid in SCRIPTS_CATALOG:
            if sid not in data:
                data[sid] = {
                    "interval_hours": 0,
                    "enabled": False,
                    "last_run": None,
                    "last_status": None,
                    "last_output": None,
                }
        return data

def save_schedules(data):
    """Salva la configurazione schedulazioni nel file JSON."""
    with _sched_lock:
        with open(SCHEDULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def run_script_now(script_id):
    """Esegue uno script e aggiorna lo stato nel JSON."""
    if script_id not in SCRIPTS_CATALOG:
        return
    script_rel = SCRIPTS_CATALOG[script_id]["script"]
    script_path = os.path.join(_BASE_DIR, script_rel)
    if not os.path.exists(script_path):
        logging.error(f"[Scheduler] Script non trovato: {script_path}")
        return
    script_timeout = SCRIPTS_CATALOG[script_id].get("timeout", 120)
    try:
        sub_env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, encoding='utf-8', timeout=script_timeout,
            cwd=_BASE_DIR, env=sub_env
        )
        ok = result.returncode == 0
        output = (result.stdout + result.stderr).strip()[:500]
        status = "success" if ok else "error"
        logging.info(f"[Scheduler] {script_id} → {status}: {output[:100]}")
    except subprocess.TimeoutExpired:
        mins = script_timeout // 60
        status, output = "error", f"Timeout ({mins}min)"
        logging.error(f"[Scheduler] {script_id} timeout after {script_timeout}s")
    except Exception as e:
        status, output = "error", str(e)
        logging.error(f"[Scheduler] {script_id} eccezione: {e}")

    data = load_schedules()
    data[script_id]["last_run"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data[script_id]["last_status"] = status
    data[script_id]["last_output"] = output
    save_schedules(data)

def _refresh_scheduler_jobs():
    """Aggiorna i job del BackgroundScheduler in base alla configurazione corrente."""
    global _bg_scheduler
    if not APSCHEDULER_OK or _bg_scheduler is None:
        return
    data = load_schedules()
    for sid in SCRIPTS_CATALOG:
        job_id = f"sched_{sid}"
        hours = int(data.get(sid, {}).get("interval_hours", 0))
        # Rimuovi job esistente
        try:
            _bg_scheduler.remove_job(job_id)
        except Exception:
            pass
        # Aggiungi solo se ore > 0
        if hours > 0:
            _bg_scheduler.add_job(
                run_script_now,
                trigger=IntervalTrigger(hours=hours),
                id=job_id,
                args=[sid],
                replace_existing=True,
            )
            logging.info(f"[Scheduler] Job '{sid}' programmato ogni {hours}h")

def init_bg_scheduler():
    """Avvia il BackgroundScheduler e carica i job salvati."""
    global _bg_scheduler
    if not APSCHEDULER_OK:
        logging.warning("[Scheduler] APScheduler non installato — schedulazioni disabilitate")
        return
    _bg_scheduler = BackgroundScheduler(daemon=True)
    _bg_scheduler.start()
    _refresh_scheduler_jobs()
    atexit.register(lambda: _bg_scheduler.shutdown(wait=False))
    logging.info("[Scheduler] BackgroundScheduler avviato")
# ─── Fine Scheduler ──────────────────────────────────────────────────────────

_telebot_process = None

def _stop_telebot_background():
    global _telebot_process
    if _telebot_process and _telebot_process.poll() is None:
        try:
            _telebot_process.terminate()
        except Exception:
            pass
    _telebot_process = None

def start_telebot_background():
    global _telebot_process
    if _telebot_process and _telebot_process.poll() is None:
        return

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
    if not os.path.exists(script_path):
        logging.warning("bot.py non trovato, avvio bot saltato.")
        return

    kwargs = {
        "args": [sys.executable, script_path],
        "cwd": os.path.dirname(script_path),
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        _telebot_process = subprocess.Popen(**kwargs)
        atexit.register(_stop_telebot_background)
        logging.info("bot.py avviato in background.")
    except Exception as e:
        logging.error(f"Errore avvio bot.py in background: {e}")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def refresh_credito():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    try:
        if session['user'] == "superadmin":
            session['saldo'] = 99999
            session['user_type'] = "superadmin"
        elif emby.isreseller(session['user']):
            session['saldo'] = round(emby.getcredito(session['user']), 2)
            session['user_type'] = "reseller"
        elif emby.issubseller(session['user']):
            session['saldo'] = round(emby.getsubcredito(session['user']), 2)
            session['user_type'] = "subseller"
    except:
        session['saldo'] = 0
        session['user_type'] = "error"

SERVIZI_PREZZI = [
    ("emby_normale", "Emby Normale"),
    ("emby_premium", "Emby Premium"),
    ("jellyfin", "Jellyfin"),
    ("plex", "Plex"),
]

def get_prezzi_mensili_per_utente(servizio):
    incremento = 0
    if session.get('user_type') == 'subseller':
        incremento = emby.getincremento(session['user'])

    prezzi = []
    for schermi in range(1, 5):
        prezzo_base = emby.get_prezzo_mensile(servizio, schermi)
        prezzo = float(prezzo_base) if prezzo_base is not None else 0.0
        if incremento:
            prezzo = emby.calcola_prezzo(prezzo, incremento)
        prezzi.append(round(prezzo, 2))
    return prezzi

def get_plex_schermi_per_utente(username):
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT nschermi FROM user WHERE pmail = ?"
        params = (username,)
    else:
        query = "SELECT nschermi FROM user WHERE pmail = ? AND id = ?"
        params = (username, session['user'])
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return None
    try:
        schermi = int(df.iloc[0]['nschermi'])
    except Exception:
        schermi = 1
    return min(max(schermi, 1), 4)

    
def check_credentials(username, password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM reseller WHERE idtelegram = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    
    if user is None:
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM subseller WHERE idtelegram = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
    
    if username=="superadmin" and password==SUPERPASSWORD:
        return "superadmin"
    
    logging.info(f"Utente {username} ha effettuato l'accesso")
    return user

# Rende tutte le sessioni permanenti e aggiorna il timeout ad ogni richiesta
@app.before_request
def make_session_permanent():
    session.permanent = True
    session.modified = True

# Funzione per controllare se la sessione è scaduta (30 minuti dal'ultimo accesso)
def session_timeout():
    if 'last_active' in session:
        now = datetime.now(timezone.utc).timestamp()
        if now - session['last_active'] > app.config['PERMANENT_SESSION_LIFETIME'].total_seconds():
            session.clear()
            flash('Sessione scaduta. Effettua nuovamente il login.', 'warning')
            return True
    session['last_active'] = datetime.now(timezone.utc).timestamp()
    return False

@app.route('/')
def index():
    if 'user' in session:
        logging.info("Accesso alla pagina di login da parte di"+session['user'])
        return redirect(url_for('dashboard'))

    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = check_credentials(username, password)
        if user:
            session['user'] = username
            session['last_active'] = datetime.now(timezone.utc).timestamp()
            
            refresh_credito()
            logging.info(f"Accesso effettuato per l'utente {username}")
            return redirect(url_for('dashboard'))
        else:
            flash('Credenziali non valide', 'danger')
            logging.critical(f"Tentativo di accesso fallito per l'utente {username} con password {password}")
    return render_template('login2.html')

@app.route('/logout')
def logout():
    logging.info("Logout effettuato per l'utente"+session['user'])
    session.clear()
    return redirect(url_for('login'))


@app.route('/preferenze', methods=['GET', 'POST'])
def preferenze():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()

    if request.method == 'POST':
        form_type = request.form.get('form_type', 'dateformat')
        user_id = session['user']

        if form_type == 'dateformat':
            fmt = request.form.get('formatodata', '%Y-%m-%d')
            if fmt not in _VALID_DATE_FORMATS:
                fmt = '%Y-%m-%d'
            if user_id != 'superadmin':
                conn = sqlite3.connect(DATABASE)
                user_type = session.get('user_type')
                if user_type == 'reseller':
                    conn.execute('UPDATE reseller SET formatodata=? WHERE idtelegram=?', (fmt, str(user_id)))
                elif user_type == 'subseller':
                    conn.execute('UPDATE subseller SET formatodata=? WHERE idtelegram=?', (fmt, str(user_id)))
                conn.commit()
                conn.close()
            session['date_format'] = fmt

        elif form_type == 'copyprefs':
            # Formato: frase_emby|campiemby|frase_plex|campiplex|frase_jelly|campijellyfin
            frase_emby  = request.form.get('frase_emby',  '').strip()
            frase_plex  = request.form.get('frase_plex',  '').strip()
            frase_jelly = request.form.get('frase_jelly', '').strip()
            emby_fields  = ','.join(request.form.getlist('campiemby'))
            plex_fields  = ','.join(request.form.getlist('campiplex'))
            jelly_fields = ','.join(request.form.getlist('campijellyfin'))
            prefs_val = f"{frase_emby}|{emby_fields}|{frase_plex}|{plex_fields}|{frase_jelly}|{jelly_fields}"
            if user_id != 'superadmin':
                conn = sqlite3.connect(DATABASE)
                user_type = session.get('user_type')
                if user_type == 'reseller':
                    conn.execute('UPDATE reseller SET preferenze=? WHERE idtelegram=?', (prefs_val, str(user_id)))
                elif user_type == 'subseller':
                    conn.execute('UPDATE subseller SET preferenze=? WHERE idtelegram=?', (prefs_val, str(user_id)))
                conn.commit()
                conn.close()
            session['copy_prefs'] = prefs_val

        flash('Preferenze salvate con successo', 'success')
        return redirect(url_for('preferenze'))

    current_fmt   = get_user_date_format()
    current_prefs = get_user_preferenze()
    return render_template('preferenze.html',
                           date_format_options=DATE_FORMAT_OPTIONS,
                           current_format=current_fmt,
                           current_prefs=current_prefs)


@app.route('/dashboard')
def dashboard():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    chart_range = request.args.get("range", "all")
    user_count = emby.get_user_count(session['user'])+ plexpi.get_user_count(session['user']) + emby.get_jellyuser_count(session['user'])
    utenti_eliminati = emby.get_eliminati_count(session['user'])
    refresh_credito()
    overrides = {"p1": 50, "p2": 98, "p3": 99, "p4": 40}
    statoplex=plexpi.get_statoserver(default_max=99,max_overrides=overrides)
    posti_disponibili_emby = emby.get_posti_disponibili_emby()
    
    gatto = emby.get_gatto()
    
    # Query per ottenere la crescita utenti considerando anche le eliminazioni
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        df_crea_emby = pd.read_sql_query("SELECT date AS event_date FROM eUser", conn)
        df_crea_jelly = pd.read_sql_query("SELECT date AS event_date FROM jUser", conn)
        df_crea_plex = pd.read_sql_query("SELECT date AS event_date FROM user", conn)
        df_eliminati = pd.read_sql_query("SELECT dataeliminazione AS event_date FROM eliminati", conn)
    else:
        df_crea_emby = pd.read_sql_query(
            "SELECT date AS event_date FROM eUser WHERE id=?",
            conn,
            params=(session['user'],)
        )
        df_crea_jelly = pd.read_sql_query(
            "SELECT date AS event_date FROM jUser WHERE id=?",
            conn,
            params=(session['user'],)
        )
        df_crea_plex = pd.read_sql_query(
            "SELECT date AS event_date FROM User WHERE id=?",
            conn,
            params=(session['user'],)
        )
        df_eliminati = pd.read_sql_query(
            "SELECT dataeliminazione AS event_date FROM eliminati WHERE idtelegram=?",
            conn,
            params=(session['user'],)
        )

    conn.close()

    df_crea_emby["delta"] = 1
    df_crea_jelly["delta"] = 1
    df_crea_plex["delta"] = 1
    df_eliminati["delta"] = -1

    df_events = pd.concat(
        [df_crea_emby, df_crea_jelly, df_crea_plex, df_eliminati],
        ignore_index=True
    )

    df_events["event_date"] = pd.to_datetime(df_events["event_date"], errors="coerce")
    df_events = df_events.dropna(subset=["event_date"])
    df_events["event_day"] = df_events["event_date"].dt.date

    df_grouped = df_events.groupby("event_day")["delta"].sum().reset_index(name="count")
    df_grouped = df_grouped.sort_values("event_day")
    if chart_range in ("30", "90", "180"):
        range_days = int(chart_range)
        start_date = (datetime.now() - timedelta(days=range_days)).date()
        df_grouped = df_grouped[df_grouped["event_day"] >= start_date]
    else:
        chart_range = "all"
    df_grouped["cumulative"] = df_grouped["count"].cumsum()
    
    # Crea il grafico con Matplotlib
    

    plt.figure(figsize=(8,4))
    plt.plot(df_grouped['event_day'], df_grouped['cumulative'], marker='o', linestyle='-', color='blue')
    plt.xlabel('Data di creazione')
    plt.ylabel('Numero cumulativo utenti')
    plt.title('Andamento crescita utenti')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    chart_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close()
    
    logging.info("Accesso alla dashboard da parte di " + session['user'])
    return render_template('dash.html', page='Dashboard', user_count=user_count,utenti_eliminati=utenti_eliminati, posti_disponibili_emby=posti_disponibili_emby, gatto=gatto, chart=chart_base64,statoplex=statoplex, chart_range=chart_range)   


@app.route('/lista')
def lista():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla lista da parte di"+session['user'])
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT user, date, expiry, server,schermi,`4k` FROM euser"
    else:
        query = "SELECT user, date, expiry, server,schermi,`4k` FROM euser WHERE id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Converte 'date' in datetime
    df['date'] = pd.to_datetime(df['date'], format="%Y-%m-%d %H:%M:%S")
    
    # Converti 'expiry' in numerico e gestisci errori
    df['expiry'] = pd.to_numeric(df['expiry'], errors='coerce')
    df['schermi'] = pd.to_numeric(df['schermi'], errors='coerce')
    df['4k'] = df['4k'].apply(lambda x: '✅' if x == "true" else '❌')

    # Imposta un limite massimo ragionevole per 'expiry' (es. 10000 giorni)
    MAX_EXPIRY_DAYS = 10000
    df['expiry'] = df['expiry'].clip(upper=MAX_EXPIRY_DAYS)
    
    # Calcola la data di scadenza come datetime
    try:
        df['expiration_dt'] = df['date'] + pd.to_timedelta(df['expiry'], unit='D')
    except OverflowError as e:
        print("OverflowError durante il calcolo della scadenza:", e)
        df['expiration_dt'] = pd.NaT

    # Calcola quanti giorni mancano dalla data di oggi (normalizzando la data corrente)
    today = pd.Timestamp.now().normalize()
    df['days_left'] = (df['expiration_dt'] - today).dt.days

    # Formattta la data di scadenza e, se mancano esattamente 7 giorni, aggiunge l'emoji ❗
    
    conditions = [
    df['days_left'] < -3,
    df['days_left'] < 1,
    df['days_left'] <= 3,
    df['days_left'] <= 7
    ]
    choices = ['☠️', '‼️','🚨', '⚠️']

    #     Applica np.select per ottenere l'emoji corrispondente a ogni riga
    emoji = np.select(conditions, choices, default='')
    
    df['expiration'] = df['expiration_dt'].dt.strftime(get_user_date_format()) + emoji

    print(df)
    # Seleziona le colonne da visualizzare (+ _ord nascosta per ordinamento DataTables)
    display_df = df[['user', 'expiration', 'server', 'schermi', '4k', 'days_left']].copy()

    display_df = display_df.rename(columns={
        'user': 'Username',
        'expiration': 'Scadenza',
        'server': 'Server',
        'schermi': 'Schermi',
        '4k': '4k',
        'days_left': '_ord'
    })

    user_count = len(display_df)
    display_df['Username'] = display_df['Username'].apply(
        lambda x: Markup(f'<a href="/utente/{x}">{x}</a>')
    )
    table_html = display_df.to_html(
        classes='table table-striped table-hove table-bordered dataTable',
        index=False,
        border=0,
        table_id="myTable",
        escape=False
    )

    return render_template('lista.html', page='Lista', table_html=table_html, user_count=user_count)

@app.route('/listajelly')
def listajelly():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla lista da parte di"+session['user'])
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT user, date, expiry, server,schermi,`4k` FROM juser"
    else:
        query = "SELECT user, date, expiry, server,schermi,`4k` FROM juser WHERE id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Converte 'date' in datetime
    df['date'] = pd.to_datetime(df['date'], format="%Y-%m-%d %H:%M:%S")
    
    # Converti 'expiry' in numerico e gestisci errori
    df['expiry'] = pd.to_numeric(df['expiry'], errors='coerce')
    df['schermi'] = pd.to_numeric(df['schermi'], errors='coerce')
    df['4k'] = df['4k'].apply(lambda x: '✅' if x == "true" else '❌')

    # Imposta un limite massimo ragionevole per 'expiry' (es. 10000 giorni)
    MAX_EXPIRY_DAYS = 10000
    df['expiry'] = df['expiry'].clip(upper=MAX_EXPIRY_DAYS)
    
    # Calcola la data di scadenza come datetime
    try:
        df['expiration_dt'] = df['date'] + pd.to_timedelta(df['expiry'], unit='D')
    except OverflowError as e:
        print("OverflowError durante il calcolo della scadenza:", e)
        df['expiration_dt'] = pd.NaT

    # Calcola quanti giorni mancano dalla data di oggi (normalizzando la data corrente)
    today = pd.Timestamp.now().normalize()
    df['days_left'] = (df['expiration_dt'] - today).dt.days

    # Formattta la data di scadenza e, se mancano esattamente 7 giorni, aggiunge l'emoji ❗
    
    conditions = [
    df['days_left'] < -3,
    df['days_left'] < 1,
    df['days_left'] <= 3,
    df['days_left'] <= 7
    ]
    choices = ['☠️', '‼️','🚨', '⚠️']

    #     Applica np.select per ottenere l'emoji corrispondente a ogni riga
    emoji = np.select(conditions, choices, default='')
    
    df['expiration'] = df['expiration_dt'].dt.strftime(get_user_date_format()) + emoji

    print(df)
    # Seleziona le colonne da visualizzare (+ _ord nascosta per ordinamento DataTables)
    display_df = df[['user', 'expiration', 'server', 'schermi', '4k', 'days_left']].copy()

    display_df = display_df.rename(columns={
        'user': 'Username',
        'expiration': 'Scadenza',
        'server': 'Server',
        'schermi': 'Schermi',
        '4k': '4k',
        'days_left': '_ord'
    })

    user_count = len(display_df)
    display_df['Username'] = display_df['Username'].apply(
        lambda x: Markup(f'<a href="/jutente/{x}">{x}</a>')
    )
    table_html = display_df.to_html(
        classes='table table-striped table-hove table-bordered dataTable',
        index=False,
        border=0,
        table_id="myTable",
        escape=False
    )
    
    return render_template('listajelly.html', page='Lista', table_html=table_html, user_count=user_count)

@app.route('/listaPLEX')
def listaPLEX():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla listaplex da parte di"+session['user'])
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT pmail,date,expiry,nschermi,server FROM user"
    else:
        query = "SELECT pmail,date,expiry,nschermi,server FROM User WHERE id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Converte 'date' in datetime
    df['date'] = pd.to_datetime(df['date'], format="%Y-%m-%d %H:%M:%S")
    
    # Converti 'expiry' in numerico e gestisci errori
    df['expiry'] = pd.to_numeric(df['expiry'], errors='coerce')
    df['nschermi'] = pd.to_numeric(df['nschermi'], errors='coerce')
    

    # Imposta un limite massimo ragionevole per 'expiry' (es. 10000 giorni)
    MAX_EXPIRY_DAYS = 10000
    df['expiry'] = df['expiry'].clip(upper=MAX_EXPIRY_DAYS)
    
    # Calcola la data di scadenza come datetime
    try:
        df['expiration_dt'] = df['date'] + pd.to_timedelta(df['expiry'], unit='D')
    except OverflowError as e:
        print("OverflowError durante il calcolo della scadenza:", e)
        df['expiration_dt'] = pd.NaT

    # Calcola quanti giorni mancano dalla data di oggi (normalizzando la data corrente)
    today = pd.Timestamp.now().normalize()
    df['days_left'] = (df['expiration_dt'] - today).dt.days

    # Formattta la data di scadenza e, se mancano esattamente 7 giorni, aggiunge l'emoji ❗
    
    conditions = [
    df['days_left'] < -3,
    df['days_left'] < 1,
    df['days_left'] <= 3,
    df['days_left'] <= 7
    ]
    choices = ['☠️', '‼️','🚨', '⚠️']

    #     Applica np.select per ottenere l'emoji corrispondente a ogni riga
    emoji = np.select(conditions, choices, default='')
    
    df['expiration'] = df['expiration_dt'].dt.strftime(get_user_date_format()) + emoji

    print(df)
    # Seleziona le colonne da visualizzare (+ _ord nascosta per ordinamento DataTables)
    display_df = df[['pmail', 'expiration', 'server', 'nschermi', 'days_left']].copy()

    display_df = display_df.rename(columns={
        'pmail': 'Username',
        'expiration': 'Scadenza',
        'server': 'Server',
        'nschermi': 'Schermi',
        'days_left': '_ord'
    })
    
    user_count = len(display_df)
    display_df['Username'] = display_df['Username'].apply(
        lambda x: Markup(f'<a href="/putente/{x}">{x}</a>')
    )
    table_html = display_df.to_html(
        classes='table table-striped table-hove table-bordered dataTable',
        index=False,
        border=0,
        table_id="myTable",
        escape=False
    )
    
    return render_template('plista.html', page='pLista', table_html=table_html, user_count=user_count)

@app.route('/putente/<username>')
def putente(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla pagina utente con username "+username+" da parte di"+session['user'])
    # Qui puoi definire le opzioni per l'utente specifico, ad esempio:
    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT pmail,date,expiry,nschermi,server,nota FROM user WHERE pmail='" + username + "'"
    else:
        query = "SELECT pmail,date,expiry,nschermi,server,nota FROM User WHERE pmail='" + username + "' AND id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    row = df.iloc[0]
    
    
    date_val     = row['date']
    expiry_val   = row['expiry']
    server_val   = row['server']
    schermi_val = row['nschermi']
    nota_val = row['nota']

    date = datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S")
    

    days=int(expiry_val)
    
    print(days)
    delta = timedelta(days)
    fine = date + delta
    giorni_rimanenti = (fine - datetime.now()).days
    
    richieste="https://res.emby.at"
    if server_val=="p2":
        richieste="https://preq2.emby.at/"
    if server_val=="p3":
        richieste="https://preq3.emby.at/"
    
    # Passa tutte le variabili al template
    _fmt = get_user_date_format()
    return render_template('user_plexoptions.html',
                            username=username,
                            date_val=date.strftime(_fmt),
                            expiry_val=fine.strftime(_fmt),
                            richieste=richieste,
                            giorni_rimanenti=giorni_rimanenti,
                            server_val=server_val,
                            nota_val=nota_val,
                            schermi_val=schermi_val,
                            copy_prefs=get_user_preferenze()
                            )

@app.route('/rinnova_plex/<username>', methods=['GET', 'POST'])
def rinnova_plex(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()

    schermi_plex = get_plex_schermi_per_utente(username)
    if schermi_plex is None:
        return f"Utente {username} non esistente o non autorizzato", 404

    prezzo_mensile_plex = emby.get_prezzo_mensile("plex", schermi_plex)
    
    if request.method == 'POST':
        try:
            # Ottieni il numero di giorni dal form
            days = int(request.form.get('renew_days'))
            if days < 0:
                return "Numero di giorni non valido", 400

            # Esegui la query per aggiornare la scadenza dell'utente
            if session['user'] == "superadmin":
                plexpi.rinnova(username, days)
                invia_messaggio(embylog, "Rinnovo Plex di "+str(username)+" da parte di "+str(session['user'])+" per "+str(days)+" giorni")

            
            if session['user_type'] == "reseller":
                if prezzo_mensile_plex is None:
                    return f"Prezzo Plex non configurato per {schermi_plex} schermi. Configuralo dalla pagina Prezzi.", 400
                
                creditoattuale=emby.getcredito(session['user'])
                costo = float(prezzo_mensile_plex) * (days / 30.416)
                #incremento del 50%
                #costo = costo * 1.5
                print("reseller rinnova plex!")
                if(float(creditoattuale)-float(costo))>0:
                    status=plexpi.rinnova(username, days)
                    if status == True:
                        emby.setcredito(session['user'], creditoattuale-costo)
                        emby.inserisci_movimento("rinnovo plex", session['user'], username, costo, creditoattuale - costo)
                        invia_messaggio(embylog, "Rinnovo Plex di "+str(username)+" da parte di "+str(session['user'])+" per "+str(days)+" giorni, ha pagato "+str(costo)+" euro, ora ha "+str(creditoattuale-costo)+" euro di credito")
                    else:
                        return "Errore durante il rinnovo: " + status, 400
                    
            if session['user_type'] == "subseller":
                if prezzo_mensile_plex is None:
                    return f"Prezzo Plex non configurato per {schermi_plex} schermi. Configuralo dalla pagina Prezzi.", 400
                creditoattuale=emby.getsubcredito(session['user'])
                incremento = emby.getincremento(session['user'])
                costonormale = float(prezzo_mensile_plex) * (days / 30.416)
                costo = emby.calcola_prezzo(costonormale, incremento)
                #sconto del 50%
                #costo = costo * 0.5
                #costonormale = costonormale * 0.5
                
                if(float(creditoattuale)-float(costo))>0:
                    status=plexpi.rinnova(username, days)
                    if status == True:
                        emby.setsubcredito(session['user'], creditoattuale-costo)
                        master=emby.getmaster(session['user'])
                        creditomaster=emby.getcredito(master)
                        emby.setcredito(int(master), float(creditomaster+(costo-costonormale)))
                        emby.inserisci_movimento("rinnovo plex", session['user'], username, costo, creditoattuale - costo)
                        emby.inserisci_movimento("commissioneplex", int(master), username, costo-costonormale, creditomaster + (costo-costonormale))
                        invia_messaggio(embylog, "Rinnovo Plex di "+str(username)+" da parte di "+str(session['user'])+" per "+str(days)+" giorni, ha pagato "+str(costo)+" euro, ora ha "+str(creditoattuale-costo)+" euro di credito")
                        invia_messaggio(master, "Hai ricevuto una commissione di "+str(costo-costonormale)+" euro per il rinnovo di "+str(username)+" da parte di "+str(session['user']))

                    else:
                        return "Errore durante il rinnovo: " + status, 400
            
            
            # Se l'operazione ha successo, reindirizza alla pagina dell'utente (ad esempio, la pagina Plex delle opzioni)
            return redirect(url_for('putente', username=username))
        except Exception as e:
            return "Errore durante il rinnovo: " + str(e), 400
        
    if session['user_type']=="subseller":
        incremento = emby.getincremento(session['user'])
    else:
        incremento = 0
    return render_template(
        'rinnova_plex.html',
        username=username,
        incremento=incremento,
        prezzo_mensile=round(float(prezzo_mensile_plex), 2) if prezzo_mensile_plex is not None else 0,
        schermi_plex=schermi_plex
    )

@app.route('/crea_plexuser', methods=['GET', 'POST'])
def crea_plexuser():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    is_superadmin = session.get('user') == 'superadmin'
    current_user = session.get('user')

    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            # Per sicurezza, i non-superadmin non possono scegliere l'idtelegram
            idtelegram = request.form.get('idtelegram', '').strip() if is_superadmin else current_user
            if not email:
                return render_template('report_plexuser.html',
                                       report_message="Errore: il campo email è obbligatorio.",
                                       username=""), 400
            if not email.lower().endswith('@gmail.com'):
                return render_template('report_plexuser.html',
                                       report_message="Errore: è accettata solo un'email Gmail (@gmail.com).",
                                       username=""), 400
            if not idtelegram:
                return render_template('report_plexuser.html',
                                       report_message="Errore: il campo ID Telegram è obbligatorio.",
                                       username=""), 400
            
            # Verifica che l'email non esista già
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user WHERE pmail = ?", (email,))
            existing_user = cursor.fetchone()
            conn.close()
            
            if existing_user:
                return render_template('report_plexuser.html', 
                                       report_message="Errore: l'email è già registrata.", 
                                       username=""), 400
            
            # Recupera le informazioni del Plex server
            
            #server = "p2"
            server=plexpi.servermenousato()
            print(server)
            conn = sqlite3.connect(DATABASE)
            df = pd.read_sql_query("SELECT * FROM plex", conn)
            conn.close()
            
            # Ottieni URL e token dal DataFrame in modo sicuro
            try:
                purl = df.loc[df['nome'] == server, 'url'].values[0]
                ptoken = df.loc[df['nome'] == server, 'token'].values[0]
            except IndexError:
                return render_template('report_plexuser.html', 
                                       report_message="Errore: dati Plex non trovati.", 
                                       username=""), 500
            
            # Inizializza il PlexServer e ottieni le sezioni della libreria
            plex = PlexServer(purl, ptoken)
            libraries = plex.library.sections()
            Plex_LIBS = libraries
            
            # Invia l'invito (la logica di sendinvite va personalizzata)
            result = plexpi.sendinvite(email, ptoken, purl, Plex_LIBS)
            
            if result == "True":
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Inserisci il nuovo utente nella tabella user
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                query = "INSERT INTO user (id, pmail, date, expiry, server, fromuser) VALUES (?, ?, ?, ?, ?, ?)"
                # Nota: modifica i campi secondo la tua struttura; qui usiamo session['user'] come id e fromuser
                cursor.execute(query, (idtelegram, email, now, 2, server, session['user']))
                conn.commit()
                conn.close()
                report = "Utente Plex creato con successo!"
                invia_messaggio(embylog, "Creato utente Plex "+str(email)+" da parte di "+str(session['user']))
            else:
                report = "ATTENZIONE: Tutti i server plex sono al momento PIENI, riprova più tardi o attendi che qualche utente venga rimosso. In alternativa puoi creare un account Emby"
            
            return render_template('report_plexuser.html', report_message=report, username=email)
        
        except Exception as e:
            return render_template('report_plexuser.html', 
                                   report_message=f"Errore durante la creazione dell'utente Plex: {str(e)}", 
                                   username=""), 500
    
    return render_template('crea_plexuser.html', is_superadmin=is_superadmin, current_user=current_user)


@app.route('/cancella_plex/<username>')
def cancella_plex(username):
    # Placeholder: implementa la logica per la cancellazione Plex qui.
    server=plexpi.getuserver(username)

    try:
        
        query = "SELECT * FROM plex"
        conn = sqlite3.connect(DATABASE)
        df = pd.read_sql_query(query, conn)
        conn.close()
        ptoken = df.loc[df['nome'] == server, 'token'].values[0]
        print(ptoken)
        account = MyPlexAccount(token=ptoken)
        result1=plexpi.plexremove(account, username)
        result2=plexpi.plexremoveinvite(account, username)
        
        if result1 == "True" or result2 == "True":
            print("Plex removido")
            
            eliminato = None
            try:
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute("SELECT id, pmail, expiry, server FROM User WHERE pmail = ? AND server = ?", (username, server))
                eliminato = cursor.fetchone()
                conn.close()
            except Exception as e:
                print(e)

            query="DELETE FROM User WHERE pmail='"+username+"' AND server='"+server+"'"
            #bot.send_message(message.chat.id, query)
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            try:
                cursor.execute(query)
                conn.commit()
                conn.close()
                if eliminato:
                    emby.AggiungiEliminati(eliminato)
                invia_messaggio(embylog, "Cancellazione dell'utente Plex "+str(username)+" da parte di "+str(session['user']))
                logging.info("Cancellazione dell'utente Plex " + username + " da parte di " + session['user'])
                return redirect(url_for('listaPLEX'))        
            except Exception as e:
                print(e)
                return "Errore durante la cancellazione: " + str(e), 400
            
    except Exception as e:
        print(e)
        return "Errore durante la cancellazione: " + str(e), 400
    return f"l'utente {username} non non si era registrato su plex e non è possibile eliminarlo automaticamente.\n ricordo che è obbligatorio che la mail sia registrata su app.plex.tv prima di invitarlo\n Posso accettare qualche errore ma se si verifica spesso verranno presi prvvedimenti", 200

@app.route('/utente/<username>')
def utente(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla pagina utente con username "+username+" da parte di"+session['user'])
    # Qui puoi definire le opzioni per l'utente specifico, ad esempio:
    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM eUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM eUser WHERE user='" + username + "' AND id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    row = df.iloc[0]
    
    
    date_val     = row['date']
    expiry_val   = row['expiry']
    server_val   = row['server']
    schermi_val = row['schermi']
    k4_val       = row['4k']      # Non puoi usare una variabile che inizia con un numero, quindi rinomino
    download_val = row['download']
    password_val = row['password']
    nota_val = row['nota']


    date = datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S")

    days=int(expiry_val)

    delta = timedelta(days)
    fine = date + delta
    giorni_rimanenti = (fine - datetime.now()).days
    nomeserver, richieste, porta, indirizzoweb, indirizzoweb_https, porta_https = emby.get_servername(server_val)
    
    if k4_val == "true":
        k4_val = "✅ Abilitato"
    else:
        k4_val = "❌ Disabilitato"
    
    if download_val == "true":
        download_val = "✅ Abilitato"
    else:
        download_val = "❌ Disabilitato"
    # Passa tutte le variabili al template
    _fmt = get_user_date_format()
    devices = emby.emby_getdevices(username)
    return render_template('user_options.html',
                            username=username,
                            date_val=date.strftime(_fmt),
                            expiry_val=fine.strftime(_fmt),
                            giorni_rimanenti=giorni_rimanenti,
                            server_val=server_val,
                            nomeserver=nomeserver,
                            richieste=richieste,
                            porta=porta,
                            indirizzoweb=indirizzoweb,
                            indirizzoweb_https=indirizzoweb_https,
                            porta_https=porta_https,
                            schermi_val=schermi_val,
                            k4_val=k4_val,
                            nota_val=nota_val,
                            download_val=download_val,
                            password_val=password_val,
                            devices=devices,
                            devices_count=len(devices),
                            copy_prefs=get_user_preferenze())
    
    #return render_template('user_options.html', username=username)


@app.route('/jutente/<username>')
def jutente(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla pagina utente con username "+username+" da parte di"+session['user'])
    # Qui puoi definire le opzioni per l'utente specifico, ad esempio:
    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM jUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM jUser WHERE user='" + username + "' AND id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    row = df.iloc[0]
    
    
    date_val     = row['date']
    expiry_val   = row['expiry']
    server_val   = row['server']
    schermi_val = row['schermi']
    k4_val       = row['4k']      
    download_val = row['download']
    password_val = row['password']
    nota_val = row['nota']


    date = datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S")

    days=int(expiry_val)

    delta = timedelta(days)
    fine = date + delta
    giorni_rimanenti = (fine - datetime.now()).days
    nomeserver, richieste, porta, indirizzoweb, indirizzoweb_https, porta_https = emby.get_servername(server_val)
    
    if k4_val == "true":
        k4_val = "✅ Abilitato"
    else:
        k4_val = "❌ Disabilitato"
    
    if download_val == "true":
        download_val = "✅ Abilitato"
    else:
        download_val = "❌ Disabilitato"
    # Passa tutte le variabili al template
    _fmt = get_user_date_format()
    return render_template('user_jellyoptions.html',
                            username=username,
                            date_val=date.strftime(_fmt),
                            expiry_val=fine.strftime(_fmt),
                            giorni_rimanenti=giorni_rimanenti,
                            server_val=server_val,
                            nomeserver=nomeserver,
                            richieste=richieste,
                            porta=porta,
                            indirizzoweb=indirizzoweb,
                            indirizzoweb_https=indirizzoweb_https,
                            porta_https=porta_https,
                            schermi_val=schermi_val,
                            k4_val=k4_val,
                            nota_val=nota_val,
                            download_val=download_val,
                            password_val=password_val,
                            copy_prefs=get_user_preferenze())
    
    #return render_template('user_options.html', username=username)

@app.route('/crea', methods=['GET', 'POST'])
def crea():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    
    if request.method == 'POST':
        # Ottieni i dati dal form
        username = request.form.get('username_custom')
        password = request.form.get('password_custom')
        server_type = request.form.get('server_type')
        expiry_days = request.form.get('expiry_days')
        streaming = request.form.get('streaming')
        server_value = request.form.get('server_value') if session['user_type'] == 'superadmin' else None
        idtelegram = request.form.get('idtelegram') if session['user_type'] == 'superadmin' else 1

        print(username)
        # Validazione lato server
        if not username or len(username) < 3:
            return "Username deve contenere almeno 3 caratteri", 400
        if not is_username_valid(username):
            return "Username deve contenere solo lettere e numeri, senza spazi o caratteri speciali", 400
        if not is_password_valid(password):
            return "Password deve contenere almeno 5 caratteri e almeno un numero", 400
        
        try:
            expiry_days = int(expiry_days)
            if expiry_days < 1:
                return "Scadenza in giorni deve essere maggiore di 0", 400
            streaming = int(streaming)
        except ValueError:
            return "Valori numerici non validi", 400
        
        try:
            if session['user']=="superadmin":
                status=emby.creautente(session['user'],username,password,server_type,expiry_days,streaming,server_value,idtelegram)
            elif emby.isreseller(session['user']) or emby.issubseller(session['user']):
                status=emby.creautente(session['user'],username,password,server_type,expiry_days,streaming,server_value,idtelegram)     
            else:
                status="non sei autorizzato se leggi questo è davvero grave. guarda che traccio tutto"
                
            
            return render_template('rinnova_report.html', report_message=status)
        except Exception as e:
            logging.exception("Errore nella creazione dell'utente: " + str(e))
            return "Errore nella creazione dell'utente: " + str(e), 500
    
    
    
    
    prezzi_premium = get_prezzi_mensili_per_utente("emby_premium")
    prezzi_normale = get_prezzi_mensili_per_utente("emby_normale")

    usertype=session['user_type']

    conn = get_db_connection()
    emby_servers = [row['nome'] for row in conn.execute("SELECT nome FROM emby ORDER BY nome").fetchall()]
    conn.close()

    return render_template(
        'crea.html',
        usertype=usertype,
        emby_servers=emby_servers,
        prezzo1prem=prezzi_premium[0],
        prezzo2prem=prezzi_premium[1],
        prezzo3prem=prezzi_premium[2],
        prezzo4prem=prezzi_premium[3],
        prezzo1norm=prezzi_normale[0],
        prezzo2norm=prezzi_normale[1],
        prezzo3norm=prezzi_normale[2],
        prezzo4norm=prezzi_normale[3]
    )

@app.route('/creajelly', methods=['GET', 'POST'])
def creajelly():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    
    if request.method == 'POST':
        # Ottieni i dati dal form
        username = request.form.get('username_custom')
        password = request.form.get('password_custom')
        expiry_days = request.form.get('expiry_days')
        streaming = request.form.get('streaming')
        server_value = request.form.get('server_value') if session['user_type'] == 'superadmin' else None
        idtelegram = request.form.get('idtelegram') if session['user_type'] == 'superadmin' else 1

        print(username)
        # Validazione lato server
        if not username or len(username) < 3:
            return "Username deve contenere almeno 3 caratteri", 400
        if not is_username_valid(username):
            return "Username deve contenere solo lettere e numeri, senza spazi o caratteri speciali", 400
        if not is_password_valid(password):
            return "Password deve contenere almeno 5 caratteri e almeno un numero", 400
        
        try:
            expiry_days = int(expiry_days)
            if expiry_days < 1:
                return "Scadenza in giorni deve essere maggiore di 0", 400
            streaming = int(streaming)
        except ValueError:
            return "Valori numerici non validi", 400
        
        try:
            if session['user']=="superadmin":
                status=emby.creautentejelly(session['user'],username,password,expiry_days,streaming,server_value,idtelegram)
            elif emby.isreseller(session['user']) or emby.issubseller(session['user']):
                status=emby.creautentejelly(session['user'],username,password,expiry_days,streaming,server_value,idtelegram)     
            else:
                status="non sei autorizzato se leggi questo è davvero grave. guarda che traccio tutto"
                
            
            return render_template('rinnova_report.html', report_message=status)
        except Exception as e:
            logging.exception("Errore nella creazione dell'utente: " + str(e))
            return "Errore nella creazione dell'utente: " + str(e), 500
    
    
    
    
    prezzi_jelly = get_prezzi_mensili_per_utente("jellyfin")

    usertype=session['user_type']

    conn = get_db_connection()
    jelly_servers = [row['nome'] for row in conn.execute("SELECT nome FROM jelly ORDER BY nome").fetchall()]
    conn.close()

    return render_template(
        'creajelly.html',
        usertype=usertype,
        jelly_servers=jelly_servers,
        prezzo1=prezzi_jelly[0],
        prezzo2=prezzi_jelly[1],
        prezzo3=prezzi_jelly[2],
        prezzo4=prezzi_jelly[3]
    )


@app.route('/rinnova/<username>')
def rinnova(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla pagina rinnova con username "+username+" da parte di"+session['user'])
    # Qui puoi definire le opzioni per l'utente specifico, ad esempio:
    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM eUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM eUser WHERE user='" + username + "' AND id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    row = df.iloc[0]
    
    
    date_val     = row['date']
    expiry_val   = row['expiry']
    server_val   = row['server']
    schermi_val = row['schermi']
    k4_val       = row['4k']      # Non puoi usare una variabile che inizia con un numero, quindi rinomino
    download_val = row['download']
    password_val = row['password']


    date = datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S")

    days=int(expiry_val)

    delta = timedelta(days)
    fine = date + delta
    giorni_rimanenti = (fine - datetime.now()).days
    nomeserver, richieste, porta, indirizzoweb, indirizzoweb_https, porta_https = emby.get_servername(server_val)
    
    servizio_emby = emby.get_servizio_emby_da_server(server_val)
    if not servizio_emby:
        return "Server non riconosciuto per il calcolo prezzi", 400
    prezzi_emby = get_prezzi_mensili_per_utente(servizio_emby)
                
    return render_template('rinnova.html',
                            username=username,
                            date_val=date_val,
                            expiry_val=fine,
                            usertype=session['user_type'],
                            giorni_rimanenti=giorni_rimanenti,
                            schermi_val=schermi_val,
                            prezzo1=prezzi_emby[0],
                            prezzo2=prezzi_emby[1],
                            prezzo3=prezzi_emby[2],
                            prezzo4=prezzi_emby[3]
                            )

@app.route('/rinnova_submit/<username>', methods=['POST'])
def rinnova_submit(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Richiesta di rinnovo per utente " + username + " da parte di " + session['user'])
    
    # Recupera i dati dal form
    try:
        renew_days = int(request.form.get('renew_days'))
        new_schermi = int(request.form.get('schermi'))
    except (ValueError, TypeError):
        return "Valori non validi forniti", 400
    
    # Recupera i dati dell'utente
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM eUser WHERE user=?"
        df = pd.read_sql_query(query, conn, params=(username,))
    else:
        query = "SELECT * FROM eUser WHERE user=? AND id=?"
        df = pd.read_sql_query(query, conn, params=(username, session['user']))
    conn.close()
    
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    # Esegue il rinnovo e cattura eventuali errori o report
    try:
        report_message = emby.rinnova(session['user'], username, renew_days, new_schermi)
    except Exception as e:
        logging.exception("Errore durante il rinnovo per utente " + username)
        report_message = "Errore durante il rinnovo: " + str(e)
    
    logging.info(f"Rinnovo eseguito per {username}: {renew_days} giorni, {new_schermi} schermi")
    
    # Rende la pagina report con il messaggio ottenuto
    return render_template('rinnova_report.html', report_message=report_message)

@app.route('/jrinnova/<username>')
def jrinnova(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla pagina rinnova con username "+username+" da parte di"+session['user'])
    # Qui puoi definire le opzioni per l'utente specifico, ad esempio:
    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM jUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM jUser WHERE user='" + username + "' AND id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    row = df.iloc[0]
    
    
    date_val     = row['date']
    expiry_val   = row['expiry']
    server_val   = row['server']
    schermi_val = row['schermi']
    k4_val       = row['4k']      # Non puoi usare una variabile che inizia con un numero, quindi rinomino
    download_val = row['download']
    password_val = row['password']


    date = datetime.strptime(date_val, "%Y-%m-%d %H:%M:%S")

    days=int(expiry_val)

    delta = timedelta(days)
    fine = date + delta
    giorni_rimanenti = (fine - datetime.now()).days
    nomeserver, richieste, porta, indirizzoweb, indirizzoweb_https, porta_https = emby.get_servername(server_val)
    
    prezzi_jelly = get_prezzi_mensili_per_utente("jellyfin")
                
    return render_template('jrinnova.html',
                            username=username,
                            date_val=date_val,
                            expiry_val=fine,
                            usertype=session['user_type'],
                            giorni_rimanenti=giorni_rimanenti,
                            schermi_val=schermi_val,
                            prezzo1=prezzi_jelly[0],
                            prezzo2=prezzi_jelly[1],
                            prezzo3=prezzi_jelly[2],
                            prezzo4=prezzi_jelly[3]
                            )

@app.route('/jrinnova_submit/<username>', methods=['POST'])
def jrinnova_submit(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Richiesta di rinnovo per utente " + username + " da parte di " + session['user'])
    
    # Recupera i dati dal form
    try:
        renew_days = int(request.form.get('renew_days'))
        new_schermi = int(request.form.get('schermi'))
    except (ValueError, TypeError):
        return "Valori non validi forniti", 400
    
    # Recupera i dati dell'utente
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM jUser WHERE user=?"
        df = pd.read_sql_query(query, conn, params=(username,))
    else:
        query = "SELECT * FROM jUser WHERE user=? AND id=?"
        df = pd.read_sql_query(query, conn, params=(username, session['user']))
    conn.close()
    
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    # Esegue il rinnovo e cattura eventuali errori o report
    try:
        report_message = emby.jrinnova(session['user'], username, renew_days, new_schermi)
    except Exception as e:
        logging.exception("Errore durante il rinnovo per utente " + username)
        report_message = "Errore durante il rinnovo: " + str(e)
    
    logging.info(f"Rinnovo eseguito per {username}: {renew_days} giorni, {new_schermi} schermi")
    
    # Rende la pagina report con il messaggio ottenuto
    return render_template('jrinnova_report.html', report_message=report_message)

#route per jsblocca
@app.route('/jsblocca/<username>')
def jsblocca(username):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    logging.info("Accesso alla pagina sblocca con username "+username+" da parte di"+session['user'])
    # Qui puoi definire le opzioni per l'utente specifico, ad esempio:
    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM jUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM jUser WHERE user='" + username + "' AND id=" + session['user']
    
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"
    
    status=emby.jsblocca_utente(username)
    if status:
        logging.info(f"L'utente {username} è stato sbloccato con successo da parte di"+session['user'])
        invia_messaggio(embylog, "Sblocco dell'utente jelly "+str(username)+" da parte di "+str(session['user']))
        return f"L'utente {username} è stato sbloccato con successo."
    else:
        logging.error(f"Errore durante lo sblocco dell'utente {username} da parte di"+session['user'])
        return f"Errore durante lo sblocco dell'utente {username}."
    

@app.route('/cancella/<username>')
def cancella(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        logging.info("Accesso alla pagina di cancella con username "+username+" da parte di"+session['user'])

        # Restituisco un HTML parziale per il popup di conferma
        return render_template("confirm_cancella.html", username=username)

@app.route('/cancella_confirm/<username>')
def cancella_confirm(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()

        #controllo se l'utente username è tra i reseller della sessionea attiva
        conn = sqlite3.connect(DATABASE)
        if session['user'] == "superadmin":
            query = "SELECT * FROM eUser WHERE user='" + username + "'"
        else:
            query = "SELECT * FROM eUser WHERE user='" + username + "' AND id=" + session['user']

        df = pd.read_sql_query(query, conn)
        print(df)
        conn.close()
        if df.empty:
            return f"Utente {username} non esistente o non autorizzato"

        status=emby.cancella_utente(username)
        if status:
            logging.info(f"L'utente {username} è stato cancellato con successo da parte di"+session['user'])
            invia_messaggio(embylog, "Cancellazione dell'utente "+str(username)+" da parte di "+str(session['user']))
            return f"L'utente {username} è stato cancellato con successo."
        else:
            logging.error(f"Errore durante la cancellazione dell'utente {username} da parte di"+session['user'])
            return f"Errore durante la cancellazione dell'utente {username}."

@app.route('/togli4k_confirm/<username>')
def togli4k_confirm(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()

        #controllo se l'utente username è tra i reseller della sessionea attiva
        conn = sqlite3.connect(DATABASE)
        if session['user'] == "superadmin":
            query = "SELECT * FROM eUser WHERE user='" + username + "'"
        else:
            query = "SELECT * FROM eUser WHERE user='" + username + "' AND id=" + session['user']

        df = pd.read_sql_query(query, conn)
        print(df)
        conn.close()
        if df.empty:
            return f"Utente {username} non esistente o non autorizzato"

        status=emby.togli4k_utente(username)
        if status:
            logging.info(f"i 4k sono stati tolti con successo all'utente {username} da parte di"+session['user'])
            invia_messaggio(embylog, "Togli 4k all'utente "+str(username)+" da parte di "+str(session['user']))
            return f"L'utente {username} non ha più 4K."
        else:
            logging.error(f"Errore durante il toglimento dei 4k all'utente {username} da parte di"+session['user'])
            return f"Errore durante la toglimento4k dell'utente {username}. Probabilmente è scaudo e bloccato su emby, se non viene rinnovato a breve sarà eliminato"

@app.route('/togli4k/<username>')
def togli4k(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        logging.info("Accesso alla pagina di togli4k con username "+username+" da parte di"+session['user'])

        # Restituisco un HTML parziale per il popup di conferma
        return render_template("confirm_togli4K.html", username=username)

@app.route('/metti4k_confirm/<username>')
def metti4k_confirm(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()

        #controllo se l'utente username è tra i reseller della sessionea attiva
        conn = sqlite3.connect(DATABASE)
        if session['user'] == "superadmin":
            query = "SELECT * FROM eUser WHERE user='" + username + "'"
        else:
            query = "SELECT * FROM eUser WHERE user='" + username + "' AND id=" + session['user']

        df = pd.read_sql_query(query, conn)
        print(df)
        conn.close()
        if df.empty:
            return f"Utente {username} non esistente o non autorizzato"

        status=emby.metti4k_utente(username)
        if status:
            logging.info(f"i 4k sono stati messi con successo all'utente {username} da parte di"+session['user'])
            invia_messaggio(embylog, "Metti 4k all'utente "+str(username)+" da parte di "+str(session['user']))
            return f"L'utente {username} può usare i 4k. Attenzione, può causare buffering. In caso disattivare"
        else:
            logging.error(f"Errore durante il mettimento dei 4k all'utente {username} da parte di"+session['user'])
            return f"Errore durante il mettimento dell'utente {username}. Probabilmente è scaudo e bloccato su emby, se non viene rinnovato a breve sarà eliminato"

@app.route('/metti4k/<username>')
def metti4k(username):
       # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        logging.info("Accesso alla pagina di metti4k con username "+username+" da parte di"+session['user'])

        # Restituisco un HTML parziale per il popup di conferma
        return render_template("confirm_metti4k.html", username=username)


@app.route('/jcancella/<username>')
def jcancella(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        logging.info("Accesso alla pagina di cancella con username "+username+" da parte di"+session['user'])

        # Restituisco un HTML parziale per il popup di conferma
        return render_template("jconfirm_cancella.html", username=username)

@app.route('/jcancella_confirm/<username>')
def jcancella_confirm(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()

        #controllo se l'utente username è tra i reseller della sessionea attiva
        conn = sqlite3.connect(DATABASE)
        if session['user'] == "superadmin":
            query = "SELECT * FROM jUser WHERE user='" + username + "'"
        else:
            query = "SELECT * FROM jUser WHERE user='" + username + "' AND id=" + session['user']

        df = pd.read_sql_query(query, conn)
        print(df)
        conn.close()
        if df.empty:
            return f"Utente {username} non esistente o non autorizzato"

        status=emby.jcancella_utente(username)
        if status:
            logging.info(f"L'utente {username} è stato cancellato con successo da parte di"+session['user'])
            invia_messaggio(embylog, "Cancellazione dell'utente "+str(username)+" da parte di "+str(session['user']))
            return f"L'utente {username} è stato cancellato con successo."
        else:
            logging.error(f"Errore durante la cancellazione dell'utente {username} da parte di"+session['user'])
            return f"Errore durante la cancellazione dell'utente {username}."

@app.route('/jtogli4k_confirm/<username>')
def jtogli4k_confirm(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()

        #controllo se l'utente username è tra i reseller della sessionea attiva
        conn = sqlite3.connect(DATABASE)
        if session['user'] == "superadmin":
            query = "SELECT * FROM jUser WHERE user='" + username + "'"
        else:
            query = "SELECT * FROM jUser WHERE user='" + username + "' AND id=" + session['user']

        df = pd.read_sql_query(query, conn)
        print(df)
        conn.close()
        if df.empty:
            return f"Utente {username} non esistente o non autorizzato"

        status=emby.jtogli4k_utente(username)
        if status:
            logging.info(f"i 4k sono stati tolti con successo all'utente {username} da parte di"+session['user'])
            invia_messaggio(embylog, "Togli 4k all'utente "+str(username)+" da parte di "+str(session['user']))
            return f"L'utente {username} non ha più 4K."
        else:
            logging.error(f"Errore durante il toglimento dei 4k all'utente {username} da parte di"+session['user'])
            return f"Errore durante la toglimento4k dell'utente {username}. Probabilmente è scaudo e bloccato su emby, se non viene rinnovato a breve sarà eliminato"

@app.route('/jtogli4k/<username>')
def jtogli4k(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        logging.info("Accesso alla pagina di togli4k con username "+username+" da parte di"+session['user'])

        # Restituisco un HTML parziale per il popup di conferma
        return render_template("jconfirm_togli4K.html", username=username)

@app.route('/jmetti4k_confirm/<username>')
def jmetti4k_confirm(username):
    # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        print("metti4k confirm")

        #controllo se l'utente username è tra i reseller della sessionea attiva
        conn = sqlite3.connect(DATABASE)
        if session['user'] == "superadmin":
            query = "SELECT * FROM jUser WHERE user='" + username + "'"
        else:
            query = "SELECT * FROM jUser WHERE user='" + username + "' AND id=" + session['user']

        df = pd.read_sql_query(query, conn)
        print(df)
        conn.close()
        if df.empty:
            return f"Utente {username} non esistente o non autorizzato"

        status=emby.jmetti4k_utente(username)
        print(status)
        if status:
            logging.info(f"i 4k sono stati messi con successo all'utente {username} da parte di"+session['user'])
            invia_messaggio(embylog, "Metti 4k all'utente "+str(username)+" da parte di "+str(session['user']))
            return f"L'utente {username} può usare i 4k. Attenzione, può causare buffering. In caso disattivare"
        else:
            logging.error(f"Errore durante il mettimento dei 4k all'utente {username} da parte di"+session['user'])
            return f"Errore durante il mettimento dell'utente {username}. Probabilmente è scaudo e bloccato su emby, se non viene rinnovato a breve sarà eliminato"

@app.route('/jmetti4k/<username>')
def jmetti4k(username):
       # Controllo autenticazione e sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    else:
        refresh_credito()
        logging.info("Accesso alla pagina di metti4k con username "+username+" da parte di"+session['user'])

        # Restituisco un HTML parziale per il popup di conferma
        return render_template("jconfirm_metti4k.html", username=username)

@app.route('/passwordch/<username>', methods=['GET', 'POST'])
def passwordch(username):
    # Richiede login valido e sessione attiva
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    logging.info("Accesso a passwordch per username %s da parte di %s", username, session['user'])

    # Verifica che l'utente sia gestibile dal venditore corrente
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM eUser WHERE user=?"
        df = pd.read_sql_query(query, conn, params=(username,))
    else:
        query = "SELECT * FROM eUser WHERE user=? AND id=?"
        df = pd.read_sql_query(query, conn, params=(username, session['user']))
    conn.close()

    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"

    if request.method == 'POST':
        new_password = (request.form.get('new_password') or "").strip()

        # Validazioni essenziali
        if len(new_password) < 5:
            flash('La password deve avere almeno 5 caratteri.', 'warning')
            return render_template('passwordch.html', username=username)

        try:
            # 1) Cambia password su Emby tramite il tuo modulo "emby"
            #    Implementa questa funzione nel modulo "emby" se non esiste già.
            #    Dovrebbe usare l’API Emby /Users/{userId}/Password (o equivalente)
            #    e restituire True/False o un messaggio d’errore.
            status = emby.cambia_password(username, new_password)

            if status is True:
                # 2) Aggiorna anche la password nella tabella locale (per coerenza UI)
                conn = sqlite3.connect(DATABASE)
                cur = conn.cursor()
                cur.execute("UPDATE eUser SET password=? WHERE user=?", (new_password, username))
                conn.commit()
                conn.close()

                # 3) Notifiche / Log
                invia_messaggio(embylog, f"Cambiata password Emby di {username} da parte di {session['user']}")
                logging.info("Password cambiata per %s da parte di %s", username, session['user'])
                flash('Password aggiornata con successo.', 'success')

                # Torna alla pagina utente
                return redirect(url_for('utente', username=username))
            else:
                # Se il tuo emby.cambia_password ritorna una stringa di errore, mostrala
                err = status if isinstance(status, str) else "Impossibile aggiornare la password su Emby."
                logging.error("Errore cambio password per %s: %s", username, err)
                flash(f"Errore: {err}", 'danger')
                return render_template('passwordch.html', username=username)

        except Exception as e:
            logging.exception("Eccezione durante cambio password per %s", username)
            flash(f"Errore durante l'aggiornamento della password: {e}", 'danger')
            return render_template('passwordch.html', username=username)

    # GET: mostra il form semplice con Nuova Password e bottoni Conferma/Annulla
    return render_template('passwordch.html', username=username)

@app.route('/jpasswordch/<username>', methods=['GET', 'POST'])
def jpasswordch(username):
    # Richiede login valido e sessione attiva
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    logging.info("Accesso a jpasswordch per username %s da parte di %s", username, session['user'])

    # Verifica che l'utente Jellyfin appartenga al venditore corrente
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM jUser WHERE user=?"
        df = pd.read_sql_query(query, conn, params=(username,))
    else:
        query = "SELECT * FROM jUser WHERE user=? AND id=?"
        df = pd.read_sql_query(query, conn, params=(username, session['user']))
    conn.close()

    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"

    if request.method == 'POST':
        new_password = (request.form.get('new_password') or "").strip()

        # Validazioni essenziali
        if len(new_password) < 5:
            flash('La password deve avere almeno 5 caratteri.', 'warning')
            return render_template('jpasswordch.html', username=username)

        try:
            # 1) Cambia password su Jellyfin tramite il tuo modulo "emby"
            status = emby.jcambia_password(username, new_password)

            if status is True:
                # 2) Aggiorna la password nel DB locale per coerenza con l’interfaccia
                conn = sqlite3.connect(DATABASE)
                cur = conn.cursor()
                cur.execute("UPDATE jUser SET password=? WHERE user=?", (new_password, username))
                conn.commit()
                conn.close()

                # 3) Notifiche / Log
                invia_messaggio(embylog, f"[J] Cambiata password di {username} da parte di {session['user']}")
                logging.info("[J] Password cambiata per %s da parte di %s", username, session['user'])
                flash('Password Jellyfin aggiornata con successo.', 'success')

                # Torna alla pagina utente Jellyfin
                return redirect(url_for('jutente', username=username))
            else:
                err = status if isinstance(status, str) else "Impossibile aggiornare la password su Jellyfin."
                logging.error("[J] Errore cambio password per %s: %s", username, err)
                flash(f"Errore: {err}", 'danger')
                return render_template('jpasswordch.html', username=username)

        except Exception as e:
            logging.exception("[J] Eccezione durante cambio password per %s", username)
            flash(f"Errore durante l'aggiornamento della password: {e}", 'danger')
            return render_template('jpasswordch.html', username=username)

    # GET: mostra il form con Nuova Password + Conferma/Annulla
    return render_template('jpasswordch.html', username=username)


@app.route('/modificanota/<username>', methods=['GET', 'POST'])
def modificanota(username):
    # controllo sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))

    logging.info(f"Accesso a modificanota for user={username} by {session['user']}")
    refresh_credito()

    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM eUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM eUser WHERE user='" + username + "' AND id=" + session['user']
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"


    if request.method == 'POST':
        # legge il nuovo testo
        nuova_nota = request.form.get('nota', '').strip()
        # aggiorna il DB (usa il placeholder giusto per il tuo DB!)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("UPDATE eUser SET nota=? WHERE user=?", (nuova_nota, username))
        conn.commit()
        conn.close()
        # mostra un messaggio di successo
        flash('Nota aggiornata con successo!', 'success')
        # invia un messaggio al log
        invia_messaggio(embylog, "Nota aggiornata per l'utente "+str(username)+" da parte di "+str(session['user']))
        logging.info(f"Nota aggiornata per l'utente {username} da parte di {session['user']}")
        # reindirizza alla pagina utente
        return redirect(f"https://res.emby.at/utente/{username}")

    else:
        # GET: pesca la nota esistente
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # Per avere i nomi delle colonne come chiavi
        cur = conn.cursor()
        cur.execute("SELECT nota FROM eUser WHERE user=?", (username,))
        row = cur.fetchone()
        if row is None or row['nota'] is None:
            nota_val = ""
        else:
            nota_val = row['nota']
        print(nota_val)
        conn.close()
        # mostra il form
        return render_template(
            'modificanota.html',
            username=username,
            nota=nota_val
        )
        
@app.route('/modificanota_plex/<username>', methods=['GET', 'POST'])
def modificanota_plex(username):
    # controllo sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))

    logging.info(f"Accesso a modificanota_plex for user={username} by {session['user']}")
    refresh_credito()

    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM User WHERE pmail='" + username + "'"
    else:
        query = "SELECT * FROM User WHERE pmail='" + username + "' AND id=" + session['user']
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"


    if request.method == 'POST':
        # legge il nuovo testo
        nuova_nota = request.form.get('nota', '').strip()
        # aggiorna il DB (usa il placeholder giusto per il tuo DB!)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("UPDATE User SET nota=? WHERE pmail=?", (nuova_nota, username))
        conn.commit()
        conn.close()
        # mostra un messaggio di successo
        flash('Nota aggiornata con successo!', 'success')
        # invia un messaggio al log
        invia_messaggio(embylog, "Nota aggiornata per l'utente "+str(username)+" da parte di "+str(session['user']))
        logging.info(f"Nota aggiornata per l'utente {username} da parte di {session['user']}")
        # reindirizza alla pagina utente
        return redirect(f"https://res.emby.at/putente/{username}")

    else:
        # GET: pesca la nota esistente
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # Per avere i nomi delle colonne come chiavi
        cur = conn.cursor()
        cur.execute("SELECT nota FROM User WHERE pmail=?", (username,))
        row = cur.fetchone()
        if row is None or row['nota'] is None:
            nota_val = ""
        else:
            nota_val = row['nota']
        print(nota_val)
        conn.close()
        # mostra il form
        return render_template(
            'pmodificanota.html',
            username=username,
            nota=nota_val
        )

@app.route('/modificanota_jelly/<username>', methods=['GET', 'POST'])
def modificanota_jelly(username):
    # controllo sessione
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))

    logging.info(f"Accesso a modificanota for user={username} by {session['user']}")
    refresh_credito()

    #controllo se l'utente username è tra i reseller della sessionea attiva
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = "SELECT * FROM JUser WHERE user='" + username + "'"
    else:
        query = "SELECT * FROM JUser WHERE user='" + username + "' AND id=" + session['user']
    df = pd.read_sql_query(query, conn)
    print(df)
    conn.close()
    if df.empty:
        return f"Utente {username} non esistente o non autorizzato"


    if request.method == 'POST':
        # legge il nuovo testo
        nuova_nota = request.form.get('nota', '').strip()
        # aggiorna il DB (usa il placeholder giusto per il tuo DB!)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("UPDATE jUser SET nota=? WHERE user=?", (nuova_nota, username))
        conn.commit()
        conn.close()
        # mostra un messaggio di successo
        flash('Nota aggiornata con successo!', 'success')
        # invia un messaggio al log
        invia_messaggio(embylog, "Nota aggiornata per l'utente "+str(username)+" da parte di "+str(session['user']))
        logging.info(f"Nota aggiornata per l'utente {username} da parte di {session['user']}")
        # reindirizza alla pagina utente
        return redirect(f"https://res.emby.at/jutente/{username}")

    else:
        # GET: pesca la nota esistente
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row  # Per avere i nomi delle colonne come chiavi
        cur = conn.cursor()
        cur.execute("SELECT nota FROM jUser WHERE user=?", (username,))
        row = cur.fetchone()
        if row is None or row['nota'] is None:
            nota_val = ""
        else:
            nota_val = row['nota']
        print(nota_val)
        conn.close()
        # mostra il form
        return render_template(
            'jmodificanota.html',
            username=username,
            nota=nota_val
        )
        
@app.route('/subseller')
def subseller():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    
    refresh_credito()
    
    # Definisci la query in base al tipo di utente
    if session['user_type'] == "superadmin":
        query = "SELECT idtelegram, nome,credito, incremento FROM subseller"
        params = ()
    elif session['user_type'] == "reseller":
        query = "SELECT idtelegram, nome,credito, incremento FROM subseller WHERE idmaster=?"
        params = (session['user'],)
    elif session['user_type'] == "subseller":
        return "Il tuo master è: " + str(emby.getmaster(session['user']))
    
    # Esegui la query e crea il DataFrame
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Trasforma la colonna idtelegram in link cliccabili
    df['idtelegram'] = df['idtelegram'].apply(
        lambda x: f'<a href="/subseller/{x}">{x}</a>'
    )
    
    # Converte il DataFrame in HTML con classi Bootstrap e non esegue l'escape
    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    
    logging.info("Accesso alla pagina subseller da parte di " + session['user'])
    return render_template('subseller.html', page='subseller', table_html=table_html)


@app.route('/subseller/<idtelegram>')
def subseller_detail(idtelegram):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    # Esegui una query per ottenere i dettagli del reseller
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query("SELECT * FROM subseller WHERE idtelegram=?", conn, params=(idtelegram,))
    conn.close()
    
    if df.empty:
        data = f"Nessun dato trovato per idtelegram: {idtelegram}"
    else:
        data = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    
    return render_template('subseller_detail.html', idtelegram=idtelegram, data=data)


@app.route('/ricaricasubseller/<idtelegram>', methods=['GET', 'POST'])
def ricaricasubseller(idtelegram):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
            if amount <= 0:
                raise ValueError("Importo non valido")
            idres = session['user']
            idsub = idtelegram
            
            # Recupera il credito attuale del reseller e del sub reseller
            if idres=="superadmin":
                creditoseller=9999
            else:
                creditoseller = emby.getcredito(idres)
            creditoseller_before = float(creditoseller)
            if creditoseller_before < amount:
                return "Credito non sufficiente. Contattami per ricaricare"
            else:
                creditoattuale = emby.getsubcredito(idsub)
                credito_sub_before = float(creditoattuale)
                # Aggiorna il credito del sub reseller
                emby.setsubcredito(int(idsub), credito_sub_before + amount)
                # Aggiorna il credito del reseller
                creditoseller_after = creditoseller_before - amount
                if idres=="superadmin":
                    print("bello gratis")
                else:
                    emby.setcredito(idres, creditoseller_after)
                credito_sub_after = credito_sub_before + amount
                
                emby.inserisci_movimento("ricaricasub",idres,idsub,amount,creditoseller_after)
                emby.inserisci_movimento("ricarica",idsub,"ricarica",amount,credito_sub_after)
                invia_messaggio(embylog, "Ricarica di "+str(amount)+" euro a "+str(idsub)+" da parte di "+str(session['user']))
            report_message = (
                "<div class='card'>"
                "  <div class='card-header bg-success text-white'>Operazione Completata</div>"
                "  <div class='card-body'>"
                "    <p><strong>Importo caricato:</strong> {:.2f}€</p>"
                "    <p><strong>Credito del reseller prima:</strong> {:.2f}€</p>"
                "    <p><strong>Credito del reseller attuale:</strong> {:.2f}€</p>"
                "    <p><strong>Credito del sub reseller prima:</strong> {:.2f}€</p>"
                "    <p><strong>Credito del sub reseller attuale:</strong> {:.2f}€</p>"
                "  </div>"
                "  <div class='card-footer'>"
                "    <a href='{}' class='btn btn-primary'><i class='bi bi-arrow-left'></i> Torna a Dettagli</a>"
                "  </div>"
                "</div>"
            ).format(
                amount,
                creditoseller_before,
                creditoseller_after,
                credito_sub_before,
                credito_sub_after,
                url_for('subseller_detail', idtelegram=idtelegram)
            )
            
            return render_template('ricarica_report.html', idtelegram=idtelegram, report_message=report_message)
        except Exception as e:
            return "Errore nella ricarica: " + str(e), 400
    
    return render_template('ricaricasubseller.html', idtelegram=idtelegram)


@app.route('/modificaincremento/<idtelegram>', methods=['GET', 'POST'])
@app.route('/modifica_incremento_subseller/<idtelegram>', methods=['GET', 'POST'])
def modifica_incremento_subseller(idtelegram):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    
    if request.method == 'POST':
        try:
            nuovo_incremento = float(request.form.get('incremento'))
            if nuovo_incremento <= 0:
                raise ValueError("Incremento deve essere maggiore di 0")
            
            # Esegui la query per aggiornare l'incremento per il reseller con idtelegram
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            query = "UPDATE subseller SET incremento = ? WHERE idtelegram = ?"
            cursor.execute(query, (nuovo_incremento, idtelegram))
            conn.commit()
            conn.close()
            invia_messaggio(embylog, "Modificato incremento a "+str(nuovo_incremento)+" per "+str(idtelegram)+" da parte di "+str(session['user']))
            # Redirect alla pagina subseller
            return redirect(url_for('subseller'))
        except Exception as e:
            return "Errore nell'aggiornamento: " + str(e), 400
    
    # Per GET mostra il form di modifica
    return render_template('modifica_incremento_subseller.html', idtelegram=idtelegram)

@app.route('/modifica_password_subseller/<idtelegram>', methods=['GET', 'POST'])
def modifica_password_subseller(idtelegram):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()

    # Autorizzazione: superadmin o reseller master del subseller
    if session.get('user_type') not in ("superadmin", "reseller"):
        return redirect(url_for('dashboard'))
    if session.get('user_type') == "reseller":
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM subseller WHERE idtelegram = ? AND idmaster = ?",
            (idtelegram, session['user'])
        )
        allowed = cursor.fetchone() is not None
        conn.close()
        if not allowed:
            return "Non sei autorizzato a modificare questo reseller", 403

    if request.method == 'POST':
        try:
            nuova_password = (request.form.get('password') or '').strip()
            if not is_password_valid(nuova_password):
                raise ValueError("Password non valida: minimo 5 caratteri e almeno un numero")

            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            query = "UPDATE subseller SET password = ? WHERE idtelegram = ?"
            cursor.execute(query, (nuova_password, idtelegram))
            conn.commit()
            updated = cursor.rowcount
            conn.close()

            if updated == 0:
                return f"Nessun subseller trovato con idtelegram {idtelegram}", 404

            invia_messaggio(embylog, "Modificata password subseller " + str(idtelegram) + " da parte di " + str(session['user']))
            invia_messaggio(idtelegram, "La tua password subseller è stata aggiornata.")
            flash("Password aggiornata con successo.", "success")
            return redirect(url_for('subseller_detail', idtelegram=idtelegram))
        except Exception as e:
            flash("Errore nell'aggiornamento password: " + str(e), "danger")
            return render_template('modifica_password_subseller.html', idtelegram=idtelegram, suggested_password=generate_password(10))

    return render_template('modifica_password_subseller.html', idtelegram=idtelegram, suggested_password=generate_password(10))

import random
def generate_password(length=12):
    # Definiamo i caratteri consentiti: lettere minuscole, maiuscole e cifre
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    password = ''.join(random.choice(chars) for _ in range(length))
    return password

def is_password_valid(password):
    if not password or len(password) < 5:
        return False
    return re.search(r"\d", password) is not None

def is_username_valid(username):
    if not username:
        return False
    return re.fullmatch(r"[A-Za-z0-9]+", username) is not None

@app.route('/creasubseller', methods=['GET', 'POST'])
def creasubseller():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    
    if request.method == 'POST':
        idtelegram = request.form.get('idtelegram', '').strip()
        if not idtelegram:
            return "Il campo Id telegram è obbligatorio", 400
        if not re.fullmatch(r'\d{3,}', idtelegram):
            return "Il campo Id telegram deve essere numerico e di almeno 3 cifre", 400
        
        if emby.isreseller(idtelegram) or emby.issubseller(idtelegram):
            return "esiste già"
        else:
                        # Inserisci il subseller nel database
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
                        # Genera una password casuale
            password = generate_password()
                        
            insert_query = "INSERT INTO subseller (idtelegram, idmaster, incremento, credito, server,password) VALUES (?, ?, ?, ?, ?,?)"
            cursor.execute(insert_query, (idtelegram, session['user'], 15, 0, "e5",password))

            conn.commit()
            conn.close()
            logging.info(f"Utente {session['user']} ha creato un subseller")

            invia_messaggio(embylog, "Creato subseller "+str(idtelegram)+" da parte di "+str(session['user']))
        return redirect(url_for('subseller'))
    
    return render_template('creasubseller.html')


@app.route('/visualizzausersub/<idtelegram>')
@app.route('/visualizzautentisub/<idtelegram>')
def visualizza_utenti_sub(idtelegram):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    # Esegui una query per ottenere gli utenti associati al reseller
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query("SELECT user, date, expiry FROM eUser WHERE id = ?", conn, params=(idtelegram,))
    conn.close()
    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    return render_template('visualizzautentisub.html', idtelegram=idtelegram, table_html=table_html)


@app.route('/visualizzausersubjelly/<idtelegram>')
@app.route('/visualizzautentisubjelly/<idtelegram>')
def visualizza_utenti_sub_jelly(idtelegram):
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query("SELECT user, date, expiry FROM jUser WHERE id = ?", conn, params=(idtelegram,))
    conn.close()
    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    return render_template('visualizzautentisubjelly.html', idtelegram=idtelegram, table_html=table_html)

def _require_superadmin():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))
    return None

@app.route('/reseller')
def reseller():
    auth = _require_superadmin()
    if auth:
        return auth

    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(
        "SELECT idtelegram, credito, server, password, nome FROM reseller ORDER BY idtelegram",
        conn
    )
    conn.close()

    if 'credito' in df.columns:
        df['credito'] = pd.to_numeric(df['credito'], errors='coerce').map(
            lambda x: "" if pd.isna(x) else f"{x:.4f}"
        )

    if 'idtelegram' in df.columns:
        df['idtelegram'] = df['idtelegram'].apply(
            lambda x: f'<a href="/reseller/{x}">{x}</a>'
        )

    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    logging.info("Accesso alla pagina reseller da parte di " + session['user'])
    return render_template('reseller.html', page='reseller', table_html=table_html)

@app.route('/reseller/<idtelegram>')
def reseller_detail(idtelegram):
    auth = _require_superadmin()
    if auth:
        return auth

    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query("SELECT * FROM reseller WHERE idtelegram = ?", conn, params=(idtelegram,))
    conn.close()

    if 'credito' in df.columns:
        df['credito'] = pd.to_numeric(df['credito'], errors='coerce').map(
            lambda x: "" if pd.isna(x) else f"{x:.4f}"
        )

    if df.empty:
        data = f"Nessun dato trovato per idtelegram: {idtelegram}"
    else:
        data = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)

    return render_template('reseller_detail.html', idtelegram=idtelegram, data=data)

@app.route('/ricaricaseller/<idtelegram>', methods=['GET', 'POST'])
@app.route('/ricaricareseller/<idtelegram>', methods=['GET', 'POST'])
def ricaricareseller(idtelegram):
    auth = _require_superadmin()
    if auth:
        return auth

    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
            if amount <= 0:
                raise ValueError("Importo non valido")

            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT credito FROM reseller WHERE idtelegram = ?", (idtelegram,))
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return f"Nessun reseller trovato con idtelegram {idtelegram}", 404

            credito_before = float(row[0] or 0)
            credito_after = credito_before + amount

            cursor.execute("UPDATE reseller SET credito = ? WHERE idtelegram = ?", (credito_after, idtelegram))
            conn.commit()
            conn.close()

            emby.inserisci_movimento("ricarica", idtelegram, "ricarica", amount, credito_after)
            invia_messaggio(embylog, "Ricarica di " + str(amount) + " euro a " + str(idtelegram) + " da parte di " + str(session['user']))
            invia_messaggio(idtelegram, f"Hai ricevuto una ricarica di {amount:.2f} euro. Il tuo credito attuale e' {credito_after:.2f} euro.")

            report_message = (
                "<div class='card'>"
                "  <div class='card-header bg-success text-white'>Operazione Completata</div>"
                "  <div class='card-body'>"
                "    <p><strong>Importo caricato:</strong> {:.2f}€</p>"
                "    <p><strong>Credito prima:</strong> {:.2f}€</p>"
                "    <p><strong>Credito attuale:</strong> {:.2f}€</p>"
                "  </div>"
                "  <div class='card-footer'>"
                "    <a href='{}' class='btn btn-primary'><i class='bi bi-arrow-left'></i> Torna a Dettagli</a>"
                "  </div>"
                "</div>"
            ).format(
                amount,
                credito_before,
                credito_after,
                url_for('reseller_detail', idtelegram=idtelegram)
            )

            return render_template('ricarica_report_reseller.html', idtelegram=idtelegram, report_message=report_message)
        except Exception as e:
            return "Errore nella ricarica: " + str(e), 400

    return render_template('ricaricareseller.html', idtelegram=idtelegram)

@app.route('/modificapasswordreseller/<idtelegram>', methods=['GET', 'POST'])
@app.route('/modifica_password_reseller/<idtelegram>', methods=['GET', 'POST'])
def modifica_password_reseller(idtelegram):
    auth = _require_superadmin()
    if auth:
        return auth

    if request.method == 'POST':
        try:
            nuova_password = (request.form.get('password') or '').strip()
            if not is_password_valid(nuova_password):
                raise ValueError("Password non valida: minimo 5 caratteri e almeno un numero")

            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            query = "UPDATE reseller SET password = ? WHERE idtelegram = ?"
            cursor.execute(query, (nuova_password, idtelegram))
            conn.commit()
            updated = cursor.rowcount
            conn.close()

            if updated == 0:
                return f"Nessun reseller trovato con idtelegram {idtelegram}", 404

            invia_messaggio(embylog, "Modificata password reseller " + str(idtelegram) + " da parte di " + str(session['user']))
            invia_messaggio(idtelegram, "La tua password reseller e' stata aggiornata.")
            flash("Password aggiornata con successo.", "success")
            return redirect(url_for('reseller_detail', idtelegram=idtelegram))
        except Exception as e:
            flash("Errore nell'aggiornamento password: " + str(e), "danger")
            return render_template('modifica_password_reseller.html', idtelegram=idtelegram, suggested_password=generate_password(10))

    return render_template('modifica_password_reseller.html', idtelegram=idtelegram, suggested_password=generate_password(10))

@app.route('/visualizzautentireseller/<idtelegram>')
def visualizza_utenti_reseller(idtelegram):
    auth = _require_superadmin()
    if auth:
        return auth

    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(
        "SELECT user, date, expiry, server, schermi, `4k` FROM eUser WHERE id = ?",
        conn,
        params=(idtelegram,)
    )
    conn.close()
    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    return render_template('visualizzautentireseller_emby.html', idtelegram=idtelegram, table_html=table_html)

@app.route('/visualizzautentiresellerjelly/<idtelegram>')
def visualizza_utenti_reseller_jelly(idtelegram):
    auth = _require_superadmin()
    if auth:
        return auth

    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(
        "SELECT user, date, expiry, server, schermi, `4k` FROM jUser WHERE id = ?",
        conn,
        params=(idtelegram,)
    )
    conn.close()
    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    return render_template('visualizzautentireseller_jelly.html', idtelegram=idtelegram, table_html=table_html)

@app.route('/visualizzautentiresellerplex/<idtelegram>')
def visualizza_utenti_reseller_plex(idtelegram):
    auth = _require_superadmin()
    if auth:
        return auth

    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(
        "SELECT pmail AS user, date, expiry, server, nschermi AS schermi FROM `User` WHERE id = ?",
        conn,
        params=(idtelegram,)
    )
    conn.close()
    table_html = df.to_html(classes='table table-striped table-bordered', index=False, border=0, escape=False)
    return render_template('visualizzautentireseller_plex.html', idtelegram=idtelegram, table_html=table_html)

@app.route('/movimenti')
def movimenti():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    
    conn = sqlite3.connect(DATABASE)
    if session['user'] == "superadmin":
        query = """
            SELECT id, date, type, user, text, costo, saldo 
            FROM movimenti 
            ORDER BY date ASC
        """
        df = pd.read_sql_query(query, conn)
    else:
        query = """
            SELECT id, date, type, user, text, costo, saldo 
            FROM movimenti 
            WHERE user=? 
            ORDER BY date ASC
        """
        df = pd.read_sql_query(query, conn, params=(session['user'],))
    conn.close()
    
    for col in ("costo", "saldo"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    formatters = {
        "costo": lambda x: "" if pd.isna(x) else f"{x:.3f}",
        "saldo": lambda x: "" if pd.isna(x) else f"{x:.3f}",
    }
    table_html = df.to_html(
        classes="table table-striped table-bordered",
        index=False,
        border=0,
        escape=False,
        table_id="myTable",
        formatters=formatters,
    )

    return render_template('movimenti.html', table_html=table_html)

@app.route('/prezzi', methods=['GET', 'POST'])
def prezzi():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))

    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            for servizio, _label in SERVIZI_PREZZI:
                for schermi in range(1, 5):
                    field_name = f"{servizio}_{schermi}"
                    raw_value = (request.form.get(field_name) or "").strip().replace(",", ".")
                    if raw_value == "":
                        emby.set_prezzo_mensile(servizio, schermi, None)
                        continue

                    prezzo_val = float(raw_value)
                    if prezzo_val < 0:
                        raise ValueError(f"Prezzo negativo non valido per {servizio} {schermi} schermi")
                    emby.set_prezzo_mensile(servizio, schermi, prezzo_val)

            flash("Prezzario aggiornato con successo.", "success")
        except Exception as e:
            flash(f"Errore nel salvataggio prezzi: {e}", "danger")
        return redirect(url_for('prezzi'))

    prezzi_data = {}
    for servizio, _label in SERVIZI_PREZZI:
        prezzi_data[servizio] = emby.get_prezzi_servizio(servizio)

    return render_template('adminpages/prezzi.html', servizi=SERVIZI_PREZZI, prezzi_data=prezzi_data)

@app.route('/impostazioni')
def impostazioni():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))

    refresh_credito()
    # Controlla se l'utente in sessione è 'superadmin'
    if session.get('user') == 'superadmin':
        pwd = generate_password(10)
        return render_template('adminpages/impostazioni.html', password=pwd)
    # Altrimenti rimanda alla dashboard
    return redirect(url_for('dashboard'))

@app.route('/verificautentiemby', methods=['GET', 'POST'])
def verificautentiemby():
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    emby_servers = [row['nome'] for row in conn.execute("SELECT nome FROM emby ORDER BY nome").fetchall()]

    ctx = dict(emby_servers=emby_servers)

    if request.method == 'POST':
        server_nome = request.form.get('server_nome')
        ctx['selected_server'] = server_nome
        ctx['risultato'] = True

        row = conn.execute(
            "SELECT url, api FROM emby WHERE nome = ?", (server_nome,)
        ).fetchone()
        conn.close()

        if not row:
            ctx['errore'] = f"Server '{server_nome}' non trovato nel database."
            return render_template('adminpages/verificautentiemby.html', **ctx)

        base_url = row['url'].rstrip('/')
        api_key = row['api']

        try:
            import requests as req
            r = req.get(f"{base_url}/Users", headers={'X-Emby-Token': api_key}, timeout=10)
            r.raise_for_status()
            emby_users = {u['Name'].lower() for u in r.json() if u.get('Name')}
        except Exception as e:
            ctx['errore'] = f"Errore chiamata API Emby: {e}"
            return render_template('adminpages/verificautentiemby.html', **ctx)

        conn2 = get_db_connection()
        db_rows = conn2.execute(
            "SELECT user, expiry, schermi, nota FROM eUser WHERE server = ?", (server_nome,)
        ).fetchall()
        conn2.close()

        db_users = {r['user'].lower() for r in db_rows}

        ctx['solo_emby'] = sorted(emby_users - db_users)
        ctx['solo_db'] = [r for r in db_rows if r['user'].lower() not in emby_users]

        return render_template('adminpages/verificautentiemby.html', **ctx)

    conn.close()
    return render_template('adminpages/verificautentiemby.html', **ctx)


@app.route('/verificautentijelly', methods=['GET', 'POST'])
def verificautentijelly():
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    jelly_servers = [row['nome'] for row in conn.execute("SELECT nome FROM jelly ORDER BY nome").fetchall()]

    ctx = dict(jelly_servers=jelly_servers)

    if request.method == 'POST':
        server_nome = request.form.get('server_nome')
        ctx['selected_server'] = server_nome
        ctx['risultato'] = True

        row = conn.execute(
            "SELECT url, api FROM jelly WHERE nome = ?", (server_nome,)
        ).fetchone()
        conn.close()

        if not row:
            ctx['errore'] = f"Server '{server_nome}' non trovato nel database."
            return render_template('adminpages/verificautentijelly.html', **ctx)

        base_url = row['url'].rstrip('/')
        api_key = row['api']

        try:
            import requests as req
            r = req.get(f"{base_url}/Users", headers={'X-Emby-Token': api_key}, timeout=10)
            r.raise_for_status()
            jelly_users = {u['Name'].lower() for u in r.json() if u.get('Name')}
        except Exception as e:
            ctx['errore'] = f"Errore chiamata API Jellyfin: {e}"
            return render_template('adminpages/verificautentijelly.html', **ctx)

        conn2 = get_db_connection()
        db_rows = conn2.execute(
            "SELECT user, expiry, schermi, nota FROM jUser WHERE server = ?", (server_nome,)
        ).fetchall()
        conn2.close()

        db_users = {r['user'].lower() for r in db_rows}

        ctx['solo_jelly'] = sorted(jelly_users - db_users)
        ctx['solo_db'] = [r for r in db_rows if r['user'].lower() not in jelly_users]

        return render_template('adminpages/verificautentijelly.html', **ctx)

    conn.close()
    return render_template('adminpages/verificautentijelly.html', **ctx)


@app.route('/ricarica_venditore', methods=['POST'])
def ricarica_venditore():
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    venditore_id = request.form['venditore_id']
    importo = request.form['importo']
    # TODO: qui la tua query SQL per ricaricare
    creditoattuale = emby.getcredito(venditore_id)
    credito_before = float(creditoattuale)
    emby.setcredito(int(venditore_id), credito_before + float(importo))
    creditoseller_after = emby.getcredito(venditore_id)
    emby.inserisci_movimento("ricarica",venditore_id,"ricarica",float(importo),creditoseller_after)
    invia_messaggio(embylog, "Ricarica di "+str(importo)+" euro a "+str(venditore_id)+" da parte di "+str(session['user']))
    invia_messaggio(venditore_id, f"Hai ricevuto una ricarica di {importo} euro. Il tuo credito attuale è {creditoseller_after} euro.")
    # es. db.execute("UPDATE venditori SET saldo = saldo + ? WHERE telegram_id = ?", (importo, venditore_id))
    flash(f"Venditore {venditore_id} ricaricato di {importo}. credito attuale: {creditoseller_after}", "success")
    return redirect(url_for('impostazioni'))

@app.route('/crea_venditore', methods=['POST'])
def crea_venditore():
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    venditore_id = request.form['venditore_id']
    password = request.form['password']
    # TODO: qui la tua query SQL per creare
    emby.creavenditore(venditore_id, password)
    invia_messaggio(embylog, "Creato venditore "+str(venditore_id)+" con password "+str(password)+" da parte di "+str(session['user']))
    invia_messaggio(venditore_id, f"sei stato creato come venditore con ID {venditore_id} e password {password}. Accedi per iniziare a vendere: https://res.emby.at.")
    # es. db.execute("INSERT INTO venditori (telegram_id, password) VALUES (?, ?)", (venditore_id, password))
    flash(f"Venditore {venditore_id} creato con password {password}.", "success")
    return redirect(url_for('impostazioni'))

def _to_int_or_none(value):
    value = (value or "").strip()
    if value == "":
        return None
    return int(value)

def _to_float_or_none(value):
    value = (value or "").strip().replace(",", ".")
    if value == "":
        return None
    return float(value)

@app.route('/impostazionireseller', methods=['GET', 'POST'])
def impostazioni_reseller():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_rowids = request.form.getlist('old_rowid[]')
        ids = request.form.getlist('idtelegram[]')
        crediti = request.form.getlist('credito[]')
        servers = request.form.getlist('server[]')
        passwords = request.form.getlist('password[]')
        nomi = request.form.getlist('nome[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(old_rowids), len(ids))
            for i in range(count):
                rowid_raw = (old_rowids[i] if i < len(old_rowids) else "").strip()
                id_raw = (ids[i] if i < len(ids) else "").strip()
                credito_raw = (crediti[i] if i < len(crediti) else "").strip()
                server = (servers[i] if i < len(servers) else "").strip()
                password = (passwords[i] if i < len(passwords) else "").strip()
                nome = (nomi[i] if i < len(nomi) else "").strip()

                if rowid_raw and rowid_raw in delete_keys:
                    cursor.execute("DELETE FROM reseller WHERE rowid = ?", (int(rowid_raw),))
                    continue

                if not any([id_raw, credito_raw, server, password, nome]):
                    continue

                id_val = _to_int_or_none(id_raw)
                credito_val = _to_float_or_none(credito_raw)
                if id_val is None:
                    raise ValueError(f"Riga {i + 1}: idtelegram obbligatorio")

                if rowid_raw:
                    cursor.execute(
                        """
                        UPDATE reseller
                        SET idtelegram = ?, credito = ?, server = ?, password = ?, nome = ?
                        WHERE rowid = ?
                        """,
                        (
                            id_val,
                            credito_val,
                            server or None,
                            password or None,
                            nome or None,
                            int(rowid_raw),
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO reseller (idtelegram, credito, server, password, nome)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            id_val,
                            credito_val,
                            server or None,
                            password or None,
                            nome or None,
                        ),
                    )

            conn.commit()
            flash("Tabella reseller aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio reseller: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_reseller'))

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT rowid, idtelegram, credito, server, password, nome FROM reseller ORDER BY idtelegram"
    ).fetchall()
    conn.close()
    return render_template('adminpages/impostazionireseller.html', rows=rows)

@app.route('/impostazionisubseller', methods=['GET', 'POST'])
def impostazioni_subseller():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_rowids = request.form.getlist('old_rowid[]')
        ids = request.form.getlist('idtelegram[]')
        idmasters = request.form.getlist('idmaster[]')
        incrementi = request.form.getlist('incremento[]')
        crediti = request.form.getlist('credito[]')
        servers = request.form.getlist('server[]')
        passwords = request.form.getlist('password[]')
        nomi = request.form.getlist('nome[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(old_rowids), len(ids))
            for i in range(count):
                rowid_raw = (old_rowids[i] if i < len(old_rowids) else "").strip()
                id_raw = (ids[i] if i < len(ids) else "").strip()
                idmaster_raw = (idmasters[i] if i < len(idmasters) else "").strip()
                incremento_raw = (incrementi[i] if i < len(incrementi) else "").strip()
                credito_raw = (crediti[i] if i < len(crediti) else "").strip()
                server = (servers[i] if i < len(servers) else "").strip()
                password = (passwords[i] if i < len(passwords) else "").strip()
                nome = (nomi[i] if i < len(nomi) else "").strip()

                if rowid_raw and rowid_raw in delete_keys:
                    cursor.execute("DELETE FROM subseller WHERE rowid = ?", (int(rowid_raw),))
                    continue

                if not any([id_raw, idmaster_raw, incremento_raw, credito_raw, server, password, nome]):
                    continue

                id_val = _to_int_or_none(id_raw)
                idmaster_val = _to_int_or_none(idmaster_raw)
                incremento_val = _to_float_or_none(incremento_raw)
                credito_val = _to_float_or_none(credito_raw)
                if id_val is None:
                    raise ValueError(f"Riga {i + 1}: idtelegram obbligatorio")

                if rowid_raw:
                    cursor.execute(
                        """
                        UPDATE subseller
                        SET idtelegram = ?, idmaster = ?, incremento = ?, credito = ?, server = ?, password = ?, nome = ?
                        WHERE rowid = ?
                        """,
                        (
                            id_val,
                            idmaster_val,
                            incremento_val,
                            credito_val,
                            server or None,
                            password or None,
                            nome or None,
                            int(rowid_raw),
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO subseller (idtelegram, idmaster, incremento, credito, server, password, nome)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            id_val,
                            idmaster_val,
                            incremento_val,
                            credito_val,
                            server or None,
                            password or None,
                            nome or None,
                        ),
                    )

            conn.commit()
            flash("Tabella subseller aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio subseller: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_subseller'))

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT rowid, idtelegram, idmaster, incremento, credito, server, password, nome FROM subseller ORDER BY idmaster, idtelegram"
    ).fetchall()
    conn.close()
    return render_template('adminpages/impostazionisubseller.html', rows=rows)

@app.route('/impostazioniemby')
def impostazioni_emby():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    rows = conn.execute(
        "SELECT nome, url, api, user, password, percorso FROM emby ORDER BY nome"
    ).fetchall()
    conn.close()
    return render_template('adminpages/impostazioniemby.html', rows=rows)

@app.route('/impostazioniemby', methods=['POST'])
def impostazioni_emby_save():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    old_nomi = request.form.getlist('old_nome[]')
    nomi = request.form.getlist('nome[]')
    urls = request.form.getlist('url[]')
    apis = request.form.getlist('api[]')
    users = request.form.getlist('user[]')
    passwords = request.form.getlist('password[]')
    percorsi = request.form.getlist('percorso[]')
    delete_keys = set(request.form.getlist('delete_keys[]'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        count = max(len(nomi), len(old_nomi))
        for i in range(count):
            old_nome = (old_nomi[i] if i < len(old_nomi) else "").strip()
            nome = (nomi[i] if i < len(nomi) else "").strip()
            url = (urls[i] if i < len(urls) else "").strip()
            api = (apis[i] if i < len(apis) else "").strip()
            userv = (users[i] if i < len(users) else "").strip()
            password = (passwords[i] if i < len(passwords) else "").strip()
            percorso = (percorsi[i] if i < len(percorsi) else "").strip()

            if old_nome and old_nome in delete_keys:
                cursor.execute("DELETE FROM emby WHERE nome = ?", (old_nome,))
                continue

            if not nome:
                continue

            if old_nome and old_nome != nome:
                cursor.execute("DELETE FROM emby WHERE nome = ?", (old_nome,))

            cursor.execute(
                """
                INSERT INTO emby (nome, url, api, user, password, percorso)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(nome) DO UPDATE SET
                    url = excluded.url,
                    api = excluded.api,
                    user = excluded.user,
                    password = excluded.password,
                    percorso = excluded.percorso
                """,
                (
                    nome,
                    url or None,
                    api or None,
                    userv or None,
                    password or None,
                    percorso or None,
                ),
            )

        conn.commit()
        flash("Tabella server Emby aggiornata con successo.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Errore salvataggio server Emby: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('impostazioni_emby'))

@app.route('/impostazioniplex', methods=['GET', 'POST'])
def impostazioni_plex():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_nomi = request.form.getlist('old_nome[]')
        nomi = request.form.getlist('nome[]')
        urls = request.form.getlist('url[]')
        tokens = request.form.getlist('token[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(nomi), len(old_nomi))
            for i in range(count):
                old_nome = (old_nomi[i] if i < len(old_nomi) else "").strip()
                nome = (nomi[i] if i < len(nomi) else "").strip()
                url = (urls[i] if i < len(urls) else "").strip()
                token = (tokens[i] if i < len(tokens) else "").strip()

                if old_nome and old_nome in delete_keys:
                    cursor.execute("DELETE FROM plex WHERE nome = ?", (old_nome,))
                    continue

                if not nome and not url and not token:
                    continue

                if not nome or not url or not token:
                    raise ValueError(f"Riga {i + 1}: nome, url e token sono obbligatori")

                if old_nome and old_nome != nome:
                    cursor.execute("DELETE FROM plex WHERE nome = ?", (old_nome,))

                cursor.execute(
                    """
                    INSERT INTO plex (nome, url, token)
                    VALUES (?, ?, ?)
                    ON CONFLICT(nome) DO UPDATE SET
                        url = excluded.url,
                        token = excluded.token
                    """,
                    (nome, url, token),
                )

            conn.commit()
            flash("Tabella server Plex aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio server Plex: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_plex'))

    conn = get_db_connection()
    rows = conn.execute("SELECT nome, url, token FROM plex ORDER BY nome").fetchall()
    conn.close()
    return render_template('adminpages/impostazioniplex.html', rows=rows)

@app.route('/impostazionijelly', methods=['GET', 'POST'])
def impostazioni_jelly():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_nomi = request.form.getlist('old_nome[]')
        nomi = request.form.getlist('nome[]')
        urls = request.form.getlist('url[]')
        apis = request.form.getlist('api[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(nomi), len(old_nomi))
            for i in range(count):
                old_nome = (old_nomi[i] if i < len(old_nomi) else "").strip()
                nome = (nomi[i] if i < len(nomi) else "").strip()
                url = (urls[i] if i < len(urls) else "").strip()
                api = (apis[i] if i < len(apis) else "").strip()

                if old_nome and old_nome in delete_keys:
                    cursor.execute("DELETE FROM jelly WHERE nome = ?", (old_nome,))
                    continue

                if not nome:
                    continue

                if old_nome and old_nome != nome:
                    cursor.execute("DELETE FROM jelly WHERE nome = ?", (old_nome,))

                cursor.execute(
                    """
                    INSERT INTO jelly (nome, url, api)
                    VALUES (?, ?, ?)
                    ON CONFLICT(nome) DO UPDATE SET
                        url = excluded.url,
                        api = excluded.api
                    """,
                    (nome, url or None, api or None),
                )

            conn.commit()
            flash("Tabella server Jellyfin aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio server Jellyfin: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_jelly'))

    conn = get_db_connection()
    rows = conn.execute("SELECT nome, url, api FROM jelly ORDER BY nome").fetchall()
    conn.close()
    return render_template('adminpages/impostazionijelly.html', rows=rows)

@app.route('/impostazioniutentiplex', methods=['GET', 'POST'])
def impostazioni_utenti_plex():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_inviti = request.form.getlist('old_invito[]')
        inviti = request.form.getlist('invito[]')
        ids = request.form.getlist('id[]')
        pmails = request.form.getlist('pmail[]')
        dates = request.form.getlist('date[]')
        expiries = request.form.getlist('expiry[]')
        nschermis = request.form.getlist('nschermi[]')
        servers = request.form.getlist('server[]')
        fromusers = request.form.getlist('fromuser[]')
        note = request.form.getlist('nota[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(inviti), len(old_inviti))
            for i in range(count):
                old_invito_raw = (old_inviti[i] if i < len(old_inviti) else "").strip()
                invito_raw = (inviti[i] if i < len(inviti) else "").strip()
                id_raw = (ids[i] if i < len(ids) else "").strip()
                pmail = (pmails[i] if i < len(pmails) else "").strip()
                date_val = (dates[i] if i < len(dates) else "").strip()
                expiry_raw = (expiries[i] if i < len(expiries) else "").strip()
                nschermi_raw = (nschermis[i] if i < len(nschermis) else "").strip()
                server = (servers[i] if i < len(servers) else "").strip()
                fromuser_raw = (fromusers[i] if i < len(fromusers) else "").strip()
                nota = (note[i] if i < len(note) else "").strip()

                if old_invito_raw and old_invito_raw in delete_keys:
                    cursor.execute('DELETE FROM "User" WHERE invito = ?', (int(old_invito_raw),))
                    continue

                if not any([invito_raw, id_raw, pmail, date_val, expiry_raw, nschermi_raw, server, fromuser_raw, nota]):
                    continue

                old_invito = _to_int_or_none(old_invito_raw)
                invito = _to_int_or_none(invito_raw)
                id_val = _to_int_or_none(id_raw)
                expiry = _to_int_or_none(expiry_raw)
                nschermi = _to_int_or_none(nschermi_raw)
                fromuser = _to_int_or_none(fromuser_raw)

                if old_invito is not None and invito is None:
                    invito = old_invito

                if old_invito is not None and invito is not None and old_invito != invito:
                    cursor.execute('DELETE FROM "User" WHERE invito = ?', (old_invito,))

                cursor.execute(
                    '''
                    INSERT INTO "User" (invito, id, pmail, date, expiry, nschermi, server, fromuser, nota)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(invito) DO UPDATE SET
                        id = excluded.id,
                        pmail = excluded.pmail,
                        date = excluded.date,
                        expiry = excluded.expiry,
                        nschermi = excluded.nschermi,
                        server = excluded.server,
                        fromuser = excluded.fromuser,
                        nota = excluded.nota
                    ''',
                    (
                        invito,
                        id_val,
                        pmail or None,
                        date_val or None,
                        expiry,
                        nschermi,
                        server or None,
                        fromuser,
                        nota or None,
                    ),
                )

            conn.commit()
            flash("Tabella utenti Plex aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio utenti Plex: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_utenti_plex'))

    conn = get_db_connection()
    rows = conn.execute(
        'SELECT invito, id, pmail, date, expiry, nschermi, server, fromuser, nota FROM "User" ORDER BY invito DESC'
    ).fetchall()
    conn.close()
    return render_template('adminpages/impostazioniutentiplex.html', rows=rows)

@app.route('/impostazioniutentiemby', methods=['GET', 'POST'])
def impostazioni_utenti_emby():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_inviti = request.form.getlist('old_invito[]')
        inviti = request.form.getlist('invito[]')
        ids = request.form.getlist('id[]')
        users = request.form.getlist('user[]')
        dates = request.form.getlist('date[]')
        expiries = request.form.getlist('expiry[]')
        servers = request.form.getlist('server[]')
        schermi_list = request.form.getlist('schermi[]')
        k4_list = request.form.getlist('k4[]')
        download_list = request.form.getlist('download[]')
        passwords = request.form.getlist('password[]')
        note = request.form.getlist('nota[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(inviti), len(old_inviti))
            for i in range(count):
                old_invito_raw = (old_inviti[i] if i < len(old_inviti) else "").strip()
                invito_raw = (inviti[i] if i < len(inviti) else "").strip()
                id_raw = (ids[i] if i < len(ids) else "").strip()
                user_val = (users[i] if i < len(users) else "").strip()
                date_val = (dates[i] if i < len(dates) else "").strip()
                expiry_raw = (expiries[i] if i < len(expiries) else "").strip()
                server = (servers[i] if i < len(servers) else "").strip()
                schermi_raw = (schermi_list[i] if i < len(schermi_list) else "").strip()
                k4 = (k4_list[i] if i < len(k4_list) else "").strip().lower()
                download = (download_list[i] if i < len(download_list) else "").strip().lower()
                password = (passwords[i] if i < len(passwords) else "").strip()
                nota = (note[i] if i < len(note) else "").strip()

                if old_invito_raw and old_invito_raw in delete_keys:
                    cursor.execute('DELETE FROM "eUser" WHERE invito = ?', (int(old_invito_raw),))
                    continue

                if not any([invito_raw, id_raw, user_val, date_val, expiry_raw, server, schermi_raw, k4, download, password, nota]):
                    continue

                old_invito = _to_int_or_none(old_invito_raw)
                invito = _to_int_or_none(invito_raw)
                id_val = _to_int_or_none(id_raw)
                expiry = _to_int_or_none(expiry_raw)
                schermi = _to_int_or_none(schermi_raw)

                if k4 not in ("true", "false"):
                    k4 = "false"
                if download not in ("true", "false"):
                    download = "false"

                if old_invito is not None and invito is None:
                    invito = old_invito

                if old_invito is not None and invito is not None and old_invito != invito:
                    cursor.execute('DELETE FROM "eUser" WHERE invito = ?', (old_invito,))

                cursor.execute(
                    '''
                    INSERT INTO "eUser" (invito, id, user, date, expiry, server, schermi, "4k", "download", password, nota)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(invito) DO UPDATE SET
                        id = excluded.id,
                        user = excluded.user,
                        date = excluded.date,
                        expiry = excluded.expiry,
                        server = excluded.server,
                        schermi = excluded.schermi,
                        "4k" = excluded."4k",
                        "download" = excluded."download",
                        password = excluded.password,
                        nota = excluded.nota
                    ''',
                    (
                        invito,
                        id_val,
                        user_val or None,
                        date_val or None,
                        expiry,
                        server or None,
                        schermi,
                        k4,
                        download,
                        password or None,
                        nota or None,
                    ),
                )

            conn.commit()
            flash("Tabella utenti Emby aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio utenti Emby: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_utenti_emby'))

    conn = get_db_connection()
    rows = conn.execute(
        'SELECT invito, id, user, date, expiry, server, schermi, "4k", "download", password, nota FROM "eUser" ORDER BY invito DESC'
    ).fetchall()
    conn.close()
    return render_template('adminpages/impostazioniutentiemby.html', rows=rows)

@app.route('/impostazioniutentijelly', methods=['GET', 'POST'])
def impostazioni_utenti_jelly():
    if 'user' not in session or session_timeout():
        return redirect(url_for('login'))
    refresh_credito()
    if session.get('user') != 'superadmin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        old_inviti = request.form.getlist('old_invito[]')
        inviti = request.form.getlist('invito[]')
        ids = request.form.getlist('id[]')
        users = request.form.getlist('user[]')
        dates = request.form.getlist('date[]')
        expiries = request.form.getlist('expiry[]')
        servers = request.form.getlist('server[]')
        schermi_list = request.form.getlist('schermi[]')
        k4_list = request.form.getlist('k4[]')
        download_list = request.form.getlist('download[]')
        passwords = request.form.getlist('password[]')
        note = request.form.getlist('nota[]')
        delete_keys = set(request.form.getlist('delete_keys[]'))

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            count = max(len(inviti), len(old_inviti))
            for i in range(count):
                old_invito_raw = (old_inviti[i] if i < len(old_inviti) else "").strip()
                invito_raw = (inviti[i] if i < len(inviti) else "").strip()
                id_raw = (ids[i] if i < len(ids) else "").strip()
                user_val = (users[i] if i < len(users) else "").strip()
                date_val = (dates[i] if i < len(dates) else "").strip()
                expiry_raw = (expiries[i] if i < len(expiries) else "").strip()
                server = (servers[i] if i < len(servers) else "").strip()
                schermi_raw = (schermi_list[i] if i < len(schermi_list) else "").strip()
                k4 = (k4_list[i] if i < len(k4_list) else "").strip().lower()
                download = (download_list[i] if i < len(download_list) else "").strip().lower()
                password = (passwords[i] if i < len(passwords) else "").strip()
                nota = (note[i] if i < len(note) else "").strip()

                if old_invito_raw and old_invito_raw in delete_keys:
                    cursor.execute('DELETE FROM "jUser" WHERE invito = ?', (int(old_invito_raw),))
                    continue

                if not any([invito_raw, id_raw, user_val, date_val, expiry_raw, server, schermi_raw, k4, download, password, nota]):
                    continue

                old_invito = _to_int_or_none(old_invito_raw)
                invito = _to_int_or_none(invito_raw)
                id_val = _to_int_or_none(id_raw)
                expiry = _to_int_or_none(expiry_raw)
                schermi = _to_int_or_none(schermi_raw)

                if k4 not in ("true", "false"):
                    k4 = "false"
                if download not in ("true", "false"):
                    download = "false"

                if old_invito is not None and invito is None:
                    invito = old_invito

                if old_invito is not None and invito is not None and old_invito != invito:
                    cursor.execute('DELETE FROM "jUser" WHERE invito = ?', (old_invito,))

                cursor.execute(
                    '''
                    INSERT INTO "jUser" (invito, id, user, date, expiry, server, schermi, "4k", "download", password, nota)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(invito) DO UPDATE SET
                        id = excluded.id,
                        user = excluded.user,
                        date = excluded.date,
                        expiry = excluded.expiry,
                        server = excluded.server,
                        schermi = excluded.schermi,
                        "4k" = excluded."4k",
                        "download" = excluded."download",
                        password = excluded.password,
                        nota = excluded.nota
                    ''',
                    (
                        invito,
                        id_val,
                        user_val or None,
                        date_val or None,
                        expiry,
                        server or None,
                        schermi,
                        k4,
                        download,
                        password or None,
                        nota or None,
                    ),
                )

            conn.commit()
            flash("Tabella utenti Jellyfin aggiornata con successo.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Errore salvataggio utenti Jellyfin: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('impostazioni_utenti_jelly'))

    conn = get_db_connection()
    rows = conn.execute(
        'SELECT invito, id, user, date, expiry, server, schermi, "4k", "download", password, nota FROM "jUser" ORDER BY invito DESC'
    ).fetchall()
    conn.close()
    return render_template('adminpages/impostazioniutentijelly.html', rows=rows)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULAZIONI (solo superadmin)
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/schedulazioni')
def schedulazioni():
    auth = _require_superadmin()
    if auth:
        return auth
    data = load_schedules()
    # Costruisci lista arricchita con info dal catalogo
    scripts = []
    for sid, cat in SCRIPTS_CATALOG.items():
        entry = dict(cat)
        entry['id'] = sid
        sched = data.get(sid, {})
        entry['interval_hours'] = sched.get('interval_hours', 0)
        entry['enabled'] = sched.get('enabled', False)
        entry['last_run'] = sched.get('last_run')
        entry['last_status'] = sched.get('last_status')
        entry['last_output'] = sched.get('last_output')
        # Calcola prossima esecuzione se schedulato
        entry['next_run'] = None
        if APSCHEDULER_OK and _bg_scheduler:
            job = _bg_scheduler.get_job(f"sched_{sid}")
            if job and job.next_run_time:
                entry['next_run'] = job.next_run_time.strftime("%d/%m/%Y %H:%M:%S")
        scripts.append(entry)
    return render_template('schedulazioni.html', scripts=scripts, apscheduler_ok=APSCHEDULER_OK)


@app.route('/schedulazioni/avvia/<script_id>', methods=['POST'])
def schedulazioni_avvia(script_id):
    auth = _require_superadmin()
    if auth:
        return auth
    if script_id not in SCRIPTS_CATALOG:
        flash("Script non trovato.", "danger")
        return redirect(url_for('schedulazioni'))
    run_script_now(script_id)
    data = load_schedules()
    status = data.get(script_id, {}).get('last_status', 'unknown')
    if status == 'success':
        flash(f"Script «{SCRIPTS_CATALOG[script_id]['name']}» eseguito con successo.", "success")
    else:
        output = data.get(script_id, {}).get('last_output', '')
        flash(f"Script «{SCRIPTS_CATALOG[script_id]['name']}» terminato con errore: {output}", "danger")
    return redirect(url_for('schedulazioni'))


@app.route('/schedulazioni/intervallo/<script_id>', methods=['POST'])
def schedulazioni_intervallo(script_id):
    auth = _require_superadmin()
    if auth:
        return auth
    if script_id not in SCRIPTS_CATALOG:
        flash("Script non trovato.", "danger")
        return redirect(url_for('schedulazioni'))
    try:
        hours = int(request.form.get('interval_hours', 0))
        if hours < 0:
            hours = 0
    except (ValueError, TypeError):
        hours = 0
    data = load_schedules()
    data[script_id]['interval_hours'] = hours
    data[script_id]['enabled'] = hours > 0
    save_schedules(data)
    _refresh_scheduler_jobs()
    name = SCRIPTS_CATALOG[script_id]['name']
    if hours > 0:
        flash(f"«{name}» schedulato ogni {hours} ore.", "success")
    else:
        flash(f"«{name}» schedulazione disabilitata.", "info")
    return redirect(url_for('schedulazioni'))


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Avvia il server in ascolto su tutte le interfacce (0.0.0.0)
    logging.info("Server avviato")
    debug_mode = True
    if (not debug_mode) or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_telebot_background()
        init_bg_scheduler()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug_mode)
