import os
import sys
import time
from pathlib import Path

from dotenv import dotenv_values
from tabulate import tabulate
import datetime

from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount
import re
import pandas as pd
from dotenv import dotenv_values
import signal
import sqlite3
import subprocess
import math

import sys
import logging
import time
import requests
import threading
from typing import Optional
import json

import signal
import paramiko
import os
import random

import telebot
env_vars = dotenv_values('.env')
TOKEN = env_vars['TOKEN']
DATABASE = env_vars['DATABASE']
admin = int(env_vars['admin'])
bot = telebot.TeleBot(TOKEN)
RICHIESTE_URL = env_vars.get('RICHIESTE_URL', 'https://req.emby.at')
BROWSER_URL_TEMPLATE = env_vars.get('BROWSER_URL_TEMPLATE', 'https://{server}.emby.at')

@bot.message_handler(commands=['test'])
def handle_start(message):
    if message.from_user.id == admin:
        bot.send_message(message.chat.id, "Funziona")


def exit_gracefully(signum, frame):
    print("\nInterrotto da tasti Ctrl+C")
    exit(0)

signal.signal(signal.SIGINT, exit_gracefully)

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

def inserisci_movimento(type,user,text,costo,saldo):
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query = "INSERT INTO movimenti (type,date, user, text,costo,saldo) VALUES (?, ?, ?,?,?,?)"
    values = (type, date,user, text,costo,saldo)
    cursor.execute(query, values)                       
    conn.commit()
    conn.close()

def _normalize_server_url(server_url):
    if not server_url:
        return None
    server_url = server_url.strip()
    if not server_url:
        return None
    if not server_url.endswith('/'):
        server_url += '/'
    return server_url

def get_media_server(server):
    conn = sqlite3.connect(DATABASE)
    try:
        df = pd.read_sql_query("SELECT nome, url, api FROM emby WHERE nome = ?", conn, params=(server,))
        if df.empty:
            try:
                df = pd.read_sql_query("SELECT nome, url, api FROM jelly WHERE nome = ?", conn, params=(server,))
            except Exception:
                pass
    finally:
        conn.close()

    if df.empty:
        return None

    return {
        "nome": df.loc[0, "nome"],
        "url": _normalize_server_url(df.loc[0, "url"]),
        "api": df.loc[0, "api"]
    }

def getindirizzi(server):
    server_data = get_media_server(server)
    if not server_data:
        return RICHIESTE_URL, None
    browser = BROWSER_URL_TEMPLATE.format(server=server_data["nome"])
    return RICHIESTE_URL, browser

@bot.message_handler(commands=['ricarica'])
def handle_start(message):
    if message.from_user.id == admin:
        try:
            values = message.text.split()
            id=values[1]
            credito=values[2]
            creditoattuale=getcredito(id)
            bot.send_message(message.chat.id, "Il credito attuale dell'utente è di "+creditoattuale.__str__()+"€")
            bot.send_message(id, "Hai ricevuto una ricarica di "+credito.__str__()+". Il credito precedente era: "+creditoattuale.__str__()+"€")
            setcredito(id, float(creditoattuale)+float(credito))
            inserisci_movimento("ricarica",id,"resellerpanel", float(credito), float(creditoattuale)+float(credito))
            bot.send_message(message.chat.id, "Il credito dell'utente è stato aggiornato a "+(float(creditoattuale)+float(credito)).__str__()+"€")
            bot.send_message(id, "Il tuo credito è stato aggiornato a "+(float(creditoattuale)+float(credito)).__str__()+"€")
        except Exception as e:
            bot.send_message(message.chat.id, e.__str__())

@bot.message_handler(commands=['app'])
def send_app(message):
    try:
        bot.send_message(message.chat.id, "📲 Android Smartphone: http://aftv.news/165220 \n📺 Android TV (Box TV & NVIDIA Shield): http://aftv.news/677110 \n📺Smart TV Samsung e LG: App emby ufficiale\n📺App Downloader Android TV (fire stick): 7557948\n💻MacOS - Infuse: App sotto\n🍎IOS: Safari o Infuse https://apps.apple.com/app/id1136220934?mt=8 \nAltri dispositivi: Google chrome", parse_mode="Markdown")
        bot.send_message(message.chat.id, "Tutorial Android: https://telegra.ph/Tutorial-Emby-Android-01-07\nTutorial Fire Stick: https://telegra.ph/Tutorial-EmbyItaly-Fire-Stick-01-07", parse_mode="Markdown")
        try:
            original_chat_id = "-1001674563881"  # chat da cui inoltrare il messaggio
            original_message_id = 148      # l'id del messaggio che contiene il file
            bot.forward_message(message.chat.id, original_chat_id, original_message_id)
            

        except FileNotFoundError:
            bot.send_message(message.chat.id, "File non trovato")
        try:
            original_message_id = 147      # l'id del messaggio che contiene il file
            bot.forward_message(message.chat.id, original_chat_id, original_message_id)
            
        except FileNotFoundError:
            bot.send_message(message.chat.id, "File non trovato")
        try:
            original_message_id = 152      # l'id del messaggio che contiene il file
            bot.forward_message(message.chat.id, original_chat_id, original_message_id)
            
        except FileNotFoundError:
            bot.send_message(message.chat.id, "File non trovato")
    except Exception as e:
        bot.send_message(message.chat.id, e.__str__())
        
@bot.message_handler(commands=['info'])
def send_info(message):
    try:
        vuoto=0
        #bot.reply_to(message, "Verifica della iscrizione in corso...:")
        id=message.from_user.id

        #bot.send_message(message.chat.id, "Il tuo ID di telegram è: "+id.__str__())
        #print("Il tuo username è: "+get_username(message.from_user.id))
        conn = sqlite3.connect(DATABASE)
        query = "SELECT * FROM User WHERE id="+id.__str__()
        df = pd.read_sql_query(query, conn)
        conn.close()
        print(df)
        if df.empty:
            #bot.send_message(message.chat.id, "Non sei iscritto al servizio")
            vuoto=vuoto+1
        for value in df['invito']:
        # scansiono tutti gli inviti
            mail_value = df.loc[df['invito'] == value, 'pmail'].values[0]
            #print("sto controllando la mail"+mail_value)
            scadenza = df.loc[df['invito'] == value, 'date'].values[0]
        
            date = datetime.datetime.strptime(scadenza, "%Y-%m-%d %H:%M:%S")
            #print("la data di scadenza è"+str(date))
            days = df.loc[df['invito'] == value, 'expiry'].values[0]
            days=int(days)
            #print("i giorni di scadenza sono"+str(days))
            delta = datetime.timedelta(days)
            fine = date + delta
            #attuale = datetime.datetime.now()
            bot.send_message(message.chat.id, "L'invito su Plex per l'utente "+mail_value+" scade il "+fine.__str__())
            
    except Exception as e:
        bot.send_message(message.chat.id, e.__str__())
        
    try:
        
        id=message.from_user.id
        conn = sqlite3.connect(DATABASE)
        query = "SELECT * FROM eUser WHERE id="+id.__str__()
        df = pd.read_sql_query(query, conn)
        conn.close()
        print(df)
        if df.empty:
            vuoto=vuoto+1
        
        utenti = []
        scadenze = []

        for value in df['invito']:
        # scansiono tutti gli inviti
            username = df.loc[df['invito'] == value, 'user'].values[0]
            scadenza = df.loc[df['invito'] == value, 'date'].values[0]
            server = df.loc[df['invito'] == value, 'server'].values[0]
            schermi = df.loc[df['invito'] == value, 'schermi'].values[0]
            if schermi is None or math.isnan(schermi):  # Controlla se è None o NaN
                schermi = 'X'  # Rappresenta un valore "NULL" per il database
            else:
                schermi = int(schermi)  # Converte in intero se è un numero valido

            date = datetime.datetime.strptime(scadenza, "%Y-%m-%d %H:%M:%S")
            
            days = df.loc[df['invito'] == value, 'expiry'].values[0]
            days=int(days)
            
            delta = datetime.timedelta(days)
            fine = date + delta
            
            richieste, browser = getindirizzi(server)
            nomeserver = "💻Indirizzo: " + (browser if browser else "non disponibile")
            
            giorni_rimanenti = (fine - datetime.datetime.now()).days
            
                
            
            utenti.append("Emby username: `"+username+"` \nN. Schermi: "+str(schermi)+"\nScadenza: "+fine.__str__()+"\nGiorni rimanenti: "+str(giorni_rimanenti)+"\n"+nomeserver+"\nRichieste: "+richieste)
            scadenze.append(int((fine-datetime.datetime.now()).days))
            
            #bot.send_message(message.chat.id, "L'invito su Emby per l'utente `"+username+"` scade il "+fine.__str__()+" Quindi fra "+str((fine-datetime.datetime.now()).days)+" giorni sul server "+nomeserver,parse_mode='Markdown')
        
        combinazione = list(zip(scadenze, utenti))

        # Ordina la lista combinata in base alle scadenze (il primo elemento di ciascuna tupla)
        combinazione_ordinata = sorted(combinazione, reverse=True)

        # Estrai gli utenti ordinati
        utenti_ordinati = [utente for _, utente in combinazione_ordinata]

        # Stampa gli utenti ordinati
        for utente in utenti_ordinati:
            #print(utente)
            time.sleep(0.3)
            bot.send_message(message.chat.id, utente,parse_mode='Markdown',disable_web_page_preview=True)
            
    except Exception as e:
        bot.send_message(message.chat.id, e.__str__())

    if vuoto==2:
        bot.send_message(message.chat.id, "Non sei iscritto al servizio, Trovi tutte le informazioni sul canale: https://t.me/+6tqF8ABNsGI2NTU0")  

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Benvenuto nel bot! Per verificare il tuo abbonamento, usa il comando /info. Canale del servizio: https://t.me/+6tqF8ABNsGI2NTU0")
    
    
    
while True:
    try:
        bot.polling()
    except Exception as e:
        print(e)
        logging.info(e)
        time.sleep(15)
        print("bot riavviato")