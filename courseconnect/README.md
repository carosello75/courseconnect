# CourseConnect

Un boilerplate minimale per una web app Flask pronta allo sviluppo locale e al deploy (compatibile con piattaforme tipo Heroku/Render).

## Caratteristiche
- Server Python Flask con rendering di `templates/index.html`
- Endpoint di health check `GET /api/health`
- Esempio di API in‑memory per corsi (`/api/courses`)
- Config di deploy tramite `Procfile` e `runtime.txt`

## Requisiti
- Python 3.11+

## Avvio rapido (sviluppo locale)
```bash
python -m venv .venv
.venv/Scripts/activate  # Windows PowerShell
pip install -r requirements.txt
python app.py
```
App in ascolto su `http://localhost:5000`.

## Struttura
```
courseconnect/
├── README.md
├── app.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── .gitattributes
└── templates/
    └── index.html
```

## Deploy
- Heroku/Render: usa `web: gunicorn app:app` dal `Procfile` e la versione Python da `runtime.txt`.
- Assicurati che le variabili d'ambiente (se necessarie) siano configurate.

## API
- `GET /api/health` → stato del servizio
- `GET /api/courses` → lista corsi
- `POST /api/courses` → crea un corso (JSON: `{ "title": string }`)



📋 RIEPILOGO AGGIORNAMENTI:
🔄 FILE DA SOSTITUIRE:
1. app.py (SOSTITUIRE COMPLETAMENTE)

GitHub → courseconnect → app.py → Edit
Cancella tutto il contenuto esistente
Incolla il nuovo app.py completo
Commit: "🚀 Complete social network with chat + media upload"

2. requirements.txt (SOSTITUIRE COMPLETAMENTE)

GitHub → courseconnect → requirements.txt → Edit
Cancella tutto e incolla le nuove dipendenze
Commit: "📦 Update dependencies for chat and media"

3. Procfile (SOSTITUIRE COMPLETAMENTE)

GitHub → courseconnect → Procfile → Edit
Sostituisci con: web: gunicorn --worker-class eventlet -w 1 app:app
Commit: "⚙️ Update Procfile for SocketIO support"

🆕 FILE DA CREARE:
4. templates/chat.html (NUOVO FILE)

GitHub → courseconnect → "Add file" → "Create new file"
Nome: templates/chat.html
Incolla tutto il codice HTML della chat che ti ho dato prima
Commit: "💬 Add real-time chat interface"


🎉 COSA AVRAI DOPO GLI AGGIORNAMENTI:
✅ SOCIAL NETWORK COMPLETO:
🎪 Homepage moderna con accoglienza ospiti
👥 Sistema utenti con registrazione/login
📱 Feed post con like in tempo reale
🔗 Commenti (API pronta, UI da attivare)
🎨 Design professionale dark theme
💬 CHAT REAL-TIME:
🏠 6 chat rooms di default (Generale, Dev, Design, Marketing, Q&A, Progetti)
⚡ Messaggi istantanei con WebSocket
👀 Typing indicators ("Marco sta scrivendo...")
🎨 Interface bellissima tipo Discord
📱 Mobile responsive perfetto
📸 UPLOAD MEDIA (API Pronte):
🖼️ Upload immagini (PNG, JPG, GIF, WEBP)
🎥 Upload video (MP4, AVI, MOV, WEBM)
🔧 Resize automatico per ottimizzazione
💾 Storage locale su Render
🗄️ DATABASE RICCO:
📊 6 tabelle relazionali (Users, Posts, Comments, Likes, ChatRooms, ChatMessages)
👤 Admin user automatico (admin/admin123)
👥 3 utenti esempio (marco_dev, sofia_design, luca_marketing - password: password123)
📝 6 post di esempio con contenuti reali
💬 6 chat rooms già popolate

🚀 PROCESSO DI AGGIORNAMENTO (10 minuti):
STEP 1: Aggiorna GitHub (5 min)

app.py → Sostituisci completamente
requirements.txt → Sostituisci
Procfile → Sostituisci
templates/chat.html → Crea nuovo file

STEP 2: Deploy Automatico (3 min)

Render rileva i cambiamenti
Build automatico con nuove dipendenze
SocketIO e Pillow vengono installati
Database si aggiorna con nuove tabelle

STEP 3: Testa (2 min)

Homepage: Registrazione/login
Feed: Crea post, metti like
Chat: /chat → Messaggi real-time
Upload: API /api/upload/image pronte


🔥 RISULTATO FINALE:
UN SOCIAL NETWORK PROFESSIONALE COMPLETO:
🎯 Level Portfolio - Progetto serio da mostrare
🏢 Production Ready - Codice scalabile e robusto
📱 Full-Stack - Frontend + Backend + Database + Real-time
🌟 Modern Tech Stack - Flask + SocketIO + SQLite + Responsive Design

📞 SUPPORTO:
🔧 Se hai problemi durante l'aggiornamento:

Build fails: Controlla che requirements.txt sia copiato correttamente
Chat non funziona: Verifica che Procfile usi eventlet
Database errors: Render ricreerà le tabelle automaticamente

✅ Test di Funzionamento:

/health → Deve mostrare status database
Homepage → Registrazione deve funzionare
/chat → Chat rooms devono caricarsi
Like post → Contatori devono aggiornarsi


🚀 Inizia con l'aggiornamento dell'app.py e poi gli altri file!
Il tuo CourseConnect diventerà un social network completo degno di portfolio aziendale! 🌟✨RiprovaClaude può commettere errori. Verifica sempre le risposte con attenzione.Ricerca Sonnet 4

