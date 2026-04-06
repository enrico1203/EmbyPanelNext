import requests
import json
import sqlite3
from datetime import datetime, timezone, timedelta
import pandas as pd
import funzioniapi as funzioniAPI
import re
import telebot
import random
from dotenv import dotenv_values
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
    
    
