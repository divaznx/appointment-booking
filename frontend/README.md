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

## Calendar Date Selector

The "Available slots" section includes a calendar date picker. Users select a date to
view only the slots available on that day.

- Navigate between months using the ‹/› buttons.
- Today's date is highlighted with an accent border.
- The selected date is filled with the accent colour.
- Past dates are greyed out and non-selectable.
- Dates with available slots show a small dot indicator.
- If no slots exist for the selected date, a clear empty-state message is shown.
- Booking a slot refreshes both the calendar availability and the slot list.
- A 409 conflict (slot taken by another user) shows a friendly message and auto-refreshes.
