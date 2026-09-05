const TOKEN_KEY = "access_token";
const API_BASE = localStorage.getItem("apiBase") || "http://127.0.0.1:8000";

const els = {
  banner: document.getElementById("banner"),
  auth: document.getElementById("auth"),
  app: document.getElementById("app"),
  session: document.getElementById("session"),
  greeting: document.getElementById("greeting"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  slots: document.getElementById("slots"),
  appointments: document.getElementById("appointments"),
};

function token() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(value) {
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

function errorText(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return fallback;
}

function showBanner(message, ok = false) {
  els.banner.textContent = message;
  els.banner.classList.toggle("hidden", !message);
  els.banner.classList.toggle("ok", Boolean(ok && message));
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (options.auth !== false && token()) {
    headers.Authorization = `Bearer ${token()}`;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!response.ok) {
    throw new Error(errorText(data, `Request failed (${response.status})`));
  }
  return data;
}

function formatWhen(start, end) {
  const from = new Date(start);
  const to = new Date(end);
  if (Number.isNaN(from.getTime())) return start || "Unknown time";
  const day = from.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  const until = Number.isNaN(to.getTime())
    ? ""
    : ` – ${to.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  return `${day}${until}`;
}

function emptyState(container, message) {
  container.innerHTML = `<p class="empty">${message}</p>`;
}

function setSignedIn(user) {
  els.auth.classList.add("hidden");
  els.app.classList.remove("hidden");
  els.session.classList.remove("hidden");
  els.greeting.textContent = user.email || user.user_id;
}

function setSignedOut() {
  setToken(null);
  els.auth.classList.remove("hidden");
  els.app.classList.add("hidden");
  els.session.classList.add("hidden");
  els.greeting.textContent = "";
}

async function loadSlots() {
  const slots = await api("/slots", { auth: false });
  if (!slots.length) {
    emptyState(els.slots, "No available slots.");
    return;
  }
  els.slots.innerHTML = "";
  for (const slot of slots) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div>
        <strong>Slot ${slot.id}</strong>
        <p>${formatWhen(slot.start_time, slot.end_time)}</p>
      </div>
    `;
    const book = document.createElement("button");
    book.type = "button";
    book.textContent = "Book";
    book.addEventListener("click", () => bookSlot(slot.id, book));
    row.appendChild(book);
    els.slots.appendChild(row);
  }
}

async function loadAppointments() {
  const rows = await api("/appointments");
  const mine = (rows || []).filter((row) => row.status !== "cancelled");
  if (!mine.length) {
    emptyState(els.appointments, "You have no appointments.");
    return;
  }
  els.appointments.innerHTML = "";
  for (const appt of mine) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div>
        <strong>#${appt.id}</strong>
        <p>Slot ${appt.slot_id} · ${appt.status}</p>
      </div>
    `;
    if (appt.status === "booked") {
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "danger";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => cancelAppointment(appt.id, cancel));
      row.appendChild(cancel);
    }
    els.appointments.appendChild(row);
  }
}

async function refreshBoard() {
  await Promise.all([loadSlots(), loadAppointments()]);
}

async function bookSlot(slotId, button) {
  button.disabled = true;
  try {
    await api("/appointments", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId }),
    });
    showBanner("Booked.", true);
    await refreshBoard();
  } catch (err) {
    showBanner(err.message);
  } finally {
    button.disabled = false;
  }
}

async function cancelAppointment(id, button) {
  button.disabled = true;
  try {
    await api(`/appointments/${id}`, { method: "DELETE" });
    showBanner("Cancelled.", true);
    await refreshBoard();
  } catch (err) {
    showBanner(err.message);
  } finally {
    button.disabled = false;
  }
}

async function restoreSession() {
  if (!token()) {
    setSignedOut();
    return;
  }
  try {
    const me = await api("/me");
    setSignedIn(me);
    await refreshBoard();
  } catch {
    setSignedOut();
  }
}

async function login() {
  const body = {
    email: els.email.value.trim(),
    password: els.password.value,
  };
  const data = await api("/login", {
    method: "POST",
    body: JSON.stringify(body),
    auth: false,
  });
  setToken(data.access_token);
  const me = await api("/me");
  setSignedIn(me);
  showBanner("Logged in.", true);
  await refreshBoard();
}

document.getElementById("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showBanner("");
  try {
    await login();
  } catch (err) {
    showBanner(err.message);
  }
});

document.getElementById("signup").addEventListener("click", async () => {
  showBanner("");
  try {
    const data = await api("/signup", {
      method: "POST",
      body: JSON.stringify({
        email: els.email.value.trim(),
        password: els.password.value,
      }),
      auth: false,
    });
    if (data.email_confirmation_required) {
      showBanner("Account created. Confirm your email, then log in.", true);
      return;
    }
    await login();
  } catch (err) {
    showBanner(err.message);
  }
});

document.getElementById("logout").addEventListener("click", () => {
  setSignedOut();
  showBanner("Logged out.", true);
});

document.getElementById("refresh-slots").addEventListener("click", async () => {
  try {
    await loadSlots();
  } catch (err) {
    showBanner(err.message);
  }
});

document.getElementById("refresh-appts").addEventListener("click", async () => {
  try {
    await loadAppointments();
  } catch (err) {
    showBanner(err.message);
  }
});

restoreSession();
