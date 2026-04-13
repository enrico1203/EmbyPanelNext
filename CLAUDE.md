# CLAUDE.md

## Panoramica

`EmbyPanelNext` e un pannello full-stack per la gestione di reseller, utenti streaming e server `Emby`, `Jellyfin` e `Plex`.

Il progetto include:
- un frontend React/Vite per dashboard, liste utenti, provisioning, gestione reseller e pagine admin
- un backend FastAPI con SQLAlchemy/PostgreSQL
- un container scheduler separato che esegue task Python pianificate
- un tunnel `cloudflared` per esposizione pubblica

Il dominio del codice e fortemente orientato al business:
- ruoli: `admin`, `master`, `reseller`
- credito espresso in `crediti`
- utenti finali distribuiti tra Emby/Jellyfin/Plex
- storico movimenti in tabella `movimenti`

## Stack tecnologico

### Backend
- Python 3.13
- FastAPI
- Uvicorn
- SQLAlchemy 2.x
- PostgreSQL via `psycopg2`
- Pydantic v2
- JWT con `python-jose`
- `passlib` per hashing password, con fallback legacy su password in chiaro
- `requests` e `httpx` per API esterne
- `plexapi` per Plex

### Scheduler / automazioni
- APScheduler
- Paramiko
- Selenium
- script Python in `backend/scripts/`

### Frontend
- React 19
- TypeScript
- Vite
- React Router
- Axios
- Framer Motion
- Lucide React
- CSS globale custom in `frontend/src/index.css`

### Runtime / deploy
- Docker Compose
- Nginx per servire il frontend e fare da reverse proxy verso il backend
- Cloudflare Tunnel (`cloudflared`)

## Struttura cartelle principali

```text
.
├── backend/
│   ├── main.py
│   ├── auth.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── provisioning.py
│   ├── embyapi.py
│   ├── jellyapi.py
│   ├── plexapi.py
│   ├── telegram_logger.py
│   ├── scheduler_catalog.py
│   ├── scheduler_store.py
│   ├── scheduler_worker.py
│   ├── routers/
│   └── scripts/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── contexts/
│   │   ├── pages/
│   │   ├── App.tsx
│   │   └── index.css
│   ├── Dockerfile
│   └── nginx.conf
├── reference/
├── schedules.json
├── docker-compose.yml
└── .env
```

## Componenti principali

### Backend
- `backend/main.py`
  - carica `.env`
  - inizializza FastAPI
  - registra tutti i router
  - esegue `Base.metadata.create_all()`

- `backend/database.py`
  - crea engine SQLAlchemy da `DATABASE_URL`
  - espone `SessionLocal` e `get_db()`

- `backend/models.py`
  - definisce i modelli SQLAlchemy principali

- `backend/provisioning.py`
  - contiene la logica business di creazione utenti, costi, scelta server, credito e logging

- `backend/embyapi.py`, `backend/jellyapi.py`, `backend/plexapi.py`
  - wrapper interni per i tre servizi
  - non sono API pubbliche FastAPI, ma moduli Python richiamabili dal backend

- `backend/routers/`
  - `auth_router.py`: login, `/auth/me`
  - `dashboard_router.py`: statistiche dashboard, messaggi da `.env`, limiti mensili, Plex slots
  - `reseller_router.py`: reseller subordinati, ricariche, password, statistiche, movimenti
  - `users_router.py`: liste e dettaglio utenti, rinnovi, 4K, note, password, delete
  - `provisioning_router.py`: creazione utenti Emby/Jelly/Plex
  - `prezzi_router.py`: gestione admin prezzi e lettura prezzi autenticata
  - `admin_router.py`: configurazioni, gestione utenti/server, funzioni admin
  - `movimenti_router.py`: movimenti
  - `scheduler_router.py`: gestione scheduler da pannello
  - `inconsistenze_router.py`: confronto DB vs server e risoluzione inconsistenze
  - `testapi_router.py`: pagina admin per testare funzioni backend

### Scheduler
- `backend/scheduler_worker.py`
  - microservizio FastAPI separato
  - usa APScheduler
  - esegue script in thread separati
  - aggiorna lo stato in `schedules.json`

- `backend/scheduler_catalog.py`
  - catalogo task disponibili

- `backend/scheduler_store.py`
  - persistenza JSON con file locking

- `backend/scripts/`
  - contiene task come `devices2`, `verificapremiere`, `telegram_test`, `bloccautentiemby`, `bloccautentijelly`

### Frontend
- `frontend/src/App.tsx`
  - routing principale

- `frontend/src/contexts/AuthContext.tsx`
  - gestione token JWT in `localStorage`
  - caricamento `/auth/me`

- `frontend/src/api/client.ts`
  - client Axios condiviso
  - aggiunge `Authorization: Bearer ...`
  - su `401` redirige a `/login` salvo il login stesso

- `frontend/src/components/`
  - layout shell (`Layout`, `Sidebar`, `TopBar`, `ProtectedRoute`)

- `frontend/src/pages/`
  - una pagina per area funzionale
  - il progetto privilegia pagine autonome, con tipi e logica locale

## Variabili d'ambiente

### Backend / core
- `DATABASE_URL`
- `SECRET_KEY`
- `CAT_API_KEY`
- `MESSAGGIO`
- `RICARICHEMENSILI`
- `RICHIESTE`

### Scheduler / integrazione interna
- `SCHEDULER_INTERNAL_URL`
- `SCHEDULER_SHARED_SECRET`
- `SCHEDULES_FILE`

### Telegram / logging
- `TELEGRAM_TOKEN` oppure `TOKEN`
- `TELEGRAM_CHANNEL_ID` oppure `IDCANALELOG`

### Script specifici
- `ROOT_PASSWORD` oppure `rootpassword`

### Frontend
- `VITE_API_URL`
  - opzionale
  - default: `/api`

## Avvio progetto

### Modalita consigliata: Docker Compose

Prerequisiti:
- Docker
- Docker Compose
- un PostgreSQL gia raggiungibile dal `DATABASE_URL`
  - nota: il database Postgres non e definito nel `docker-compose.yml` di questo repo

Comandi principali:

```bash
docker compose build
docker compose up -d
```

Servizi:
- `nextbackend` -> FastAPI su `9091`
- `nextfrontend` -> Nginx/frontend su `9090`
- `nextscheduler` -> scheduler interno su `9092`
- `nextcloudflared` -> tunnel pubblico

Health check utile:

```bash
curl http://127.0.0.1:9091/health
```

### Sviluppo locale senza Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 9091
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Scheduler locale:

```bash
cd backend
pip install -r requirements-scheduler.txt
uvicorn scheduler_worker:app --host 0.0.0.0 --port 9092
```

## Decisioni architetturali importanti

- Il backend usa router per dominio funzionale, non un unico file monolitico.
- La logica business e concentrata in `backend/provisioning.py` e nei wrapper API dedicati, non nei router.
- Le integrazioni Emby/Jellyfin/Plex sono incapsulate in moduli Python interni.
- Il frontend usa route protette a livello globale, ma molti controlli di ruolo sono fatti direttamente dentro le pagine.
- Il frontend e una SPA servita da Nginx; `/api/*` viene proxato al backend.
- Il progetto usa `Base.metadata.create_all()` invece di un sistema di migrazioni.
- Lo scheduler e un container separato con stato persistito in `schedules.json`.
- Le notifiche Telegram fanno parte del dominio applicativo, non solo del logging tecnico.
- La piattaforma usa prezzi in `crediti`, non in euro, anche se alcuni messaggi storici potrebbero ancora riflettere la terminologia legacy.

## Struttura del database

### Tabelle ORM principali

#### `public.reseller`
- `id` `INTEGER` PK
- `username` `VARCHAR(50)` unique
- `master` `INTEGER`
- `password` `TEXT`
- `credito` `FLOAT`
- `idtelegram` `BIGINT`
- `ruolo` `VARCHAR(20)`

#### `public.prezzi`
- `servizio` `VARCHAR(50)` PK composita
- `streaming` `INTEGER` PK composita
- `prezzo_mensile` `FLOAT`

#### `public.movimenti`
- `id` `INTEGER` PK
- `date` `TIMESTAMP`
- `type` `TEXT`
- `user` `TEXT`
- `text` `TEXT`
- `costo` `NUMERIC(15,4)`
- `saldo` `NUMERIC(15,4)`

#### `public.plex`
- `nome` `TEXT` PK
- `url` `TEXT`
- `token` `TEXT`
- `capienza` `INTEGER`

#### `public.emby`
- `nome` `TEXT` PK
- `url` `TEXT`
- `https` `TEXT`
- `api` `TEXT`
- `user` `TEXT`
- `password` `TEXT`
- `percorso` `TEXT`
- `tipo` `TEXT`
- `limite` `TEXT`
- `capienza` `INTEGER`

#### `public.jelly`
- `nome` `TEXT` PK
- `url` `TEXT`
- `https` `TEXT`
- `api` `TEXT`

#### `public.euser`
- `invito` `INTEGER` PK
- `id` reseller owner
- `user`
- `date`
- `expiry`
- `server`
- `schermi`
- `4k`
- `download`
- `password`
- `nota`

#### `public.juser`
- schema equivalente a `euser`

#### `public.puser`
- `invito` `INTEGER` PK
- `id` reseller owner
- `pmail`
- `date`
- `expiry`
- `nschermi`
- `server`
- `fromuser`
- `nota`

### Tabelle usate ma non modellate in ORM

#### `public.devices`
- usata per salvare i dispositivi Emby
- popolata dallo script `devices2`
- letta con SQL raw per il dettaglio utente Emby

## Convenzioni di codice adottate

### Generali
- naming misto italiano/inglese, con forte orientamento al dominio business
- testo UI principalmente in italiano
- molta logica pagina-specifica tenuta vicino alla pagina stessa

### Backend
- i router stanno in `backend/routers/`
- i modelli stanno in `backend/models.py`
- gli schemi Pydantic stanno in `backend/schemas.py`
- le funzioni di integrazione esterna stanno in moduli dedicati (`embyapi.py`, `jellyapi.py`, `plexapi.py`)
- per le scadenze si usa spesso `date + expiry`
- i crediti sono normalmente quantizzati a 2 decimali
- il backend accetta ancora alcuni fallback legacy su password in chiaro

### Frontend
- componenti funzionali e hook soltanto
- tipi/interfacce spesso locali al file pagina
- `Axios` centralizzato in `src/api/client.ts`
- check di ruolo spesso fatti dentro la pagina con `Navigate`
- CSS globale condiviso in `src/index.css`
- molte pagine usano stato locale, `useEffect`, `useMemo` e stili inline per dettagli visivi

## TODO / problemi aperti noti

- Manca un sistema di migrazioni DB: `create_all()` non basta per evoluzioni schema complesse.
- Alcune password sono ancora gestite in chiaro per compatibilita legacy.
- Il token di `cloudflared` e presente nel `docker-compose.yml`; idealmente dovrebbe stare fuori dal repo.
- Diverse liste caricano dataset completi e filtrano lato frontend; la paginazione lato backend sarebbe utile.
- `devices` non e modellata via ORM, quindi richiede attenzione nelle modifiche schema.
- Il progetto dipende pesantemente da servizi esterni e da automazioni remote; errori su Emby/Jellyfin/Plex/SSH/Selenium possono creare stati temporaneamente inconsistenti.
- In frontend esistono ancora funzionalita parziali o placeholder in alcune pagine secondarie.

## Note utili per un AI assistant

- Prima di cambiare logica business, controlla sempre i router e `provisioning.py`: molte regole di dominio sono duplicate tra creazione, rinnovo e dashboard.
- Prima di toccare il database, verifica se la tabella e modellata in ORM oppure usata via SQL raw.
- Se modifichi qualcosa che dipende dal `.env`, ricrea almeno il container interessato con `--force-recreate`.
- Se modifichi il frontend, ricordati che in produzione viene servito da Nginx e proxato su `/api`.
- La cartella `reference/` contiene il progetto legacy da cui sono state portate varie logiche e script.
