# Frontend

Minimal HTML/CSS/JS client for the appointment API. No npm.

## Run

1. In `backend/.env`, set:

   `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`

2. Start the API from `backend/`:

   `uvicorn app.main:app --reload --port 8000`

3. Serve this folder:

   `python -m http.server 3000`

4. Open [http://127.0.0.1:3000](http://127.0.0.1:3000)

The UI calls `http://127.0.0.1:8000` by default. Override with `localStorage.apiBase` in the browser console if needed.
