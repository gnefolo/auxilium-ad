# Deploy — Backend su Render, Frontend su Vercel

## 1. Backend (Render)

1. Crea un repository Git con il contenuto di questa cartella (`Dashboard AD/`) e caricalo su GitHub.
2. Su [render.com](https://render.com): **New > Web Service**, collega il repository.
   - Se usi il file `render.yaml` incluso: **New > Blueprint** e Render legge automaticamente la configurazione.
   - Altrimenti, configura a mano:
     - **Root Directory**: `backend`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Imposta le variabili d'ambiente (**Environment**), obbligatorie prima di andare live:
   - `ADMIN_USERNAME` — utente per il login alla dashboard
   - `ADMIN_PASSWORD` — password (sceglila robusta: sarà l'unico accesso alla dashboard)
   - `AUTH_SECRET_KEY` — stringa segreta lunga e casuale (con `render.yaml` viene generata automaticamente)
4. Dopo il primo deploy, copia l'URL pubblico assegnato da Render (es. `https://auxilium-backend.onrender.com`).

**Limite importante**: il database è SQLite su disco locale del servizio. Sul piano gratuito di Render il disco **non è persistente tra i deploy** (viene ricreato da zero a ogni nuovo deploy). I dati "reali" (bilanci, Elenco Servizi, tavole ISTAT) si riseminano automaticamente all'avvio — nessun problema. Ma i dati inseriti a mano nella dashboard (progetti "Calcolo SROI", valori di outcome nella pagina SROI) **andrebbero persi ad ogni nuovo deploy**. Se questi dati devono persistere, serve un disco persistente Render (a pagamento) o migrare a un database gestito (es. Postgres, anche gratuito su Render) — non ancora implementato in questo progetto.

## 2. Frontend (Vercel)

1. Prima di pubblicare, apri `frontend/app.js` e sostituisci il placeholder:
   ```js
   : 'https://REPLACE-WITH-RENDER-URL.onrender.com/api';
   ```
   con l'URL reale del backend Render ottenuto al passo precedente (con `/api` alla fine).
2. Su [vercel.com](https://vercel.com): **Add New > Project**, collega lo stesso repository (o uno separato solo con la cartella `frontend/`).
   - **Root Directory**: `frontend`
   - Nessun build command necessario (è un sito statico).
3. Deploy. Vercel assegna un URL pubblico (es. `https://auxilium-dashboard.vercel.app`).

## 3. Accesso

La dashboard è protetta da login (utente/password impostati come variabili d'ambiente su Render). Il token di sessione dura 12 ore.
