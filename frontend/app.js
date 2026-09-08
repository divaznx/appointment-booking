const TOKEN_KEY = "access_token";
const API_BASE =
  localStorage.getItem("apiBase") ||
  (window.location.port === "3000" ? "http://127.0.0.1:8000" : window.location.origin);

const els = {
  banner: document.getElementById("banner"),
  auth: document.getElementById("auth"),
  app: document.getElementById("app"),
  session: document.getElementById("session"),
  greeting: document.getElementById("greeting"),
  slots: document.getElementById("slots"),
  appointments: document.getElementById("appointments"),
  calendar: document.getElementById("calendar"),
  /* Auth elements */
  authTitle: document.getElementById("auth-title"),
  authSubtitle: document.getElementById("auth-subtitle"),
  authTabs: document.getElementById("auth-tabs"),
  authMessage: document.getElementById("auth-message"),
  loginForm: document.getElementById("login-form"),
  signupForm: document.getElementById("signup-form"),
  forgotForm: document.getElementById("forgot-form"),
  loginEmail: document.getElementById("login-email"),
  loginPassword: document.getElementById("login-password"),
  loginBtn: document.getElementById("login-btn"),
  signupEmail: document.getElementById("signup-email"),
  signupPassword: document.getElementById("signup-password"),
  signupConfirm: document.getElementById("signup-confirm"),
  signupBtn: document.getElementById("signup-btn"),
  forgotEmail: document.getElementById("forgot-email"),
  forgotBtn: document.getElementById("forgot-btn"),
  resetForm: document.getElementById("reset-form"),
  resetPassword: document.getElementById("reset-password"),
  resetConfirm: document.getElementById("reset-confirm"),
  resetBtn: document.getElementById("reset-btn"),
};

/* Recovery token extracted from URL hash (Supabase redirects with #access_token=...&type=recovery) */
let recoveryToken = null;

/* ── SVG Icons ───────────────────────────────────────── */
const ICONS = {
  chevronLeft: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>`,
  chevronRight: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>`,
  clock: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`,
  calendar: `<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="3" ry="3"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>`,
  calendarSm: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>`,
};

/* ── Auth token helpers ──────────────────────────────── */

function token() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(value) {
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

/* ── API layer ───────────────────────────────────────── */

function errorText(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return fallback;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (options.auth !== false && token()) {
    headers.Authorization = `Bearer ${token()}`;
  }
  const fetchOpts = { ...options, headers };
  if (options.signal) fetchOpts.signal = options.signal;
  const response = await fetch(`${API_BASE}${path}`, fetchOpts);
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
    const err = new Error(errorText(data, `Request failed (${response.status})`));
    err.status = response.status;
    throw err;
  }
  return data;
}

/* ── UI helpers ──────────────────────────────────────── */

function showBanner(message, ok = false) {
  els.banner.textContent = message;
  els.banner.classList.toggle("hidden", !message);
  els.banner.classList.toggle("ok", Boolean(ok && message));
}

function formatTimeOnly(date) {
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatReadableDate(dateStr) {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/* ── Date helpers ────────────────────────────────────── */

/** Returns "YYYY-MM-DD" in the user's local timezone. */
function toLocalDateStr(isoString) {
  const d = new Date(isoString);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Returns "YYYY-MM-DD" for today in the user's local timezone. */
function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/* ── Session management ──────────────────────────────── */

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

/* ── Calendar state ──────────────────────────────────── */

let calendarYear;
let calendarMonth; // 0-indexed
let selectedDate = null; // "YYYY-MM-DD"
let allSlots = []; // full slot list from API
let slotsAbortController = null; // to cancel in-flight slot requests
let slotDatesWithAvailability = new Set(); // dates that have ≥1 slot

function initCalendarState() {
  const now = new Date();
  calendarYear = now.getFullYear();
  calendarMonth = now.getMonth();
  selectedDate = todayStr();
}

/* ── Modern Calendar rendering ───────────────────────── */

function renderCalendar() {
  const container = els.calendar;
  container.innerHTML = "";

  const wrapper = document.createElement("div");
  wrapper.className = "calendar-wrapper";

  // Navigation bar
  const nav = document.createElement("div");
  nav.className = "calendar-nav";

  const title = document.createElement("div");
  title.className = "calendar-title";
  title.textContent = new Date(calendarYear, calendarMonth).toLocaleString(undefined, {
    month: "long",
    year: "numeric",
  });

  const btnGroup = document.createElement("div");
  btnGroup.className = "calendar-nav-buttons";

  const prevBtn = document.createElement("button");
  prevBtn.type = "button";
  prevBtn.className = "nav-btn";
  prevBtn.innerHTML = ICONS.chevronLeft;
  prevBtn.setAttribute("aria-label", "Previous month");
  prevBtn.addEventListener("click", () => navigateMonth(-1));

  const nextBtn = document.createElement("button");
  nextBtn.type = "button";
  nextBtn.className = "nav-btn";
  nextBtn.innerHTML = ICONS.chevronRight;
  nextBtn.setAttribute("aria-label", "Next month");
  nextBtn.addEventListener("click", () => navigateMonth(1));

  // Disable prev button if viewing the current month or earlier
  const now = new Date();
  const currentYM = now.getFullYear() * 12 + now.getMonth();
  const calYM = calendarYear * 12 + calendarMonth;
  if (calYM <= currentYM) {
    prevBtn.disabled = true;
  }

  btnGroup.appendChild(prevBtn);
  btnGroup.appendChild(nextBtn);
  nav.appendChild(title);
  nav.appendChild(btnGroup);
  wrapper.appendChild(nav);

  // Day-of-week headers
  const grid = document.createElement("div");
  grid.className = "calendar-grid";

  const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  for (const wd of weekdays) {
    const colHdr = document.createElement("div");
    colHdr.className = "calendar-weekday";
    colHdr.textContent = wd;
    grid.appendChild(colHdr);
  }

  // Day cells
  const firstDay = new Date(calendarYear, calendarMonth, 1).getDay(); // 0 = Sun
  const daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
  const today = todayStr();

  // Previous month filler days
  const prevMonthDays = new Date(calendarYear, calendarMonth, 0).getDate();
  for (let i = firstDay - 1; i >= 0; i--) {
    const cell = document.createElement("div");
    cell.className = "calendar-cell other-month";
    cell.textContent = prevMonthDays - i;
    grid.appendChild(cell);
  }

  // Current month active days
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${calendarYear}-${String(calendarMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const cell = document.createElement("div");
    cell.className = "calendar-cell";
    cell.textContent = d;

    if (dateStr === today) cell.classList.add("today");
    if (dateStr === selectedDate) cell.classList.add("selected");

    if (dateStr < today) {
      cell.classList.add("past");
    } else {
      if (slotDatesWithAvailability.has(dateStr)) {
        const dot = document.createElement("span");
        dot.className = "avail-dot";
        cell.appendChild(dot);
      } else if (allSlots.length > 0) {
        cell.classList.add("no-slots");
      }
      cell.addEventListener("click", () => selectDate(dateStr));
    }

    grid.appendChild(cell);
  }

  // Next month filler days to complete grid
  const totalCells = firstDay + daysInMonth;
  const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
  for (let i = 1; i <= remaining; i++) {
    const cell = document.createElement("div");
    cell.className = "calendar-cell other-month";
    cell.textContent = i;
    grid.appendChild(cell);
  }

  wrapper.appendChild(grid);

  // Modern legend
  const legend = document.createElement("div");
  legend.className = "calendar-legend";
  legend.innerHTML = `
    <span class="legend-item"><span class="legend-dot"></span> Available slots</span>
    <span>Click a date to view times</span>
  `;
  wrapper.appendChild(legend);

  container.appendChild(wrapper);
}

/* ── Calendar navigation ─────────────────────────────── */

function navigateMonth(delta) {
  calendarMonth += delta;
  if (calendarMonth > 11) {
    calendarMonth = 0;
    calendarYear++;
  } else if (calendarMonth < 0) {
    calendarMonth = 11;
    calendarYear--;
  }

  // Don't allow navigating before current month
  const now = new Date();
  const currentYM = now.getFullYear() * 12 + now.getMonth();
  const calYM = calendarYear * 12 + calendarMonth;
  if (calYM < currentYM) {
    calendarYear = now.getFullYear();
    calendarMonth = now.getMonth();
  }

  renderCalendar();
}

/* ── Date selection ──────────────────────────────────── */

function selectDate(dateStr) {
  selectedDate = dateStr;
  renderCalendar();
  renderFilteredSlots();
}

/* ── Slot data management ────────────────────────────── */

function buildAvailabilitySet() {
  slotDatesWithAvailability = new Set();
  for (const slot of allSlots) {
    slotDatesWithAvailability.add(toLocalDateStr(slot.start_time));
  }
}

function slotsForDate(dateStr) {
  if (!dateStr) return [];
  return allSlots.filter((slot) => toLocalDateStr(slot.start_time) === dateStr);
}

async function loadAllSlots() {
  if (slotsAbortController) {
    slotsAbortController.abort();
  }
  slotsAbortController = new AbortController();

  els.slots.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <span>Loading available slots…</span>
    </div>
  `;

  try {
    allSlots = await api("/slots", { auth: false, signal: slotsAbortController.signal });
    buildAvailabilitySet();

    // If today has no slots, but future dates do, default select the earliest date with slots
    if (allSlots.length > 0 && !slotDatesWithAvailability.has(selectedDate)) {
      const sortedDates = Array.from(slotDatesWithAvailability).sort();
      if (sortedDates.length > 0 && sortedDates[0] >= todayStr()) {
        selectedDate = sortedDates[0];
      }
    }

    renderCalendar();
    renderFilteredSlots();
  } catch (err) {
    if (err.name === "AbortError") return;
    allSlots = [];
    buildAvailabilitySet();
    renderCalendar();
    els.slots.innerHTML = `
      <div class="empty-state">
        <p class="empty-state-title">Failed to load slots</p>
        <p class="empty-state-text">${err.message}</p>
      </div>
    `;
    showBanner(err.message);
  } finally {
    slotsAbortController = null;
  }
}

/* ── Slot rendering ──────────────────────────────────── */

function renderFilteredSlots() {
  const filtered = slotsForDate(selectedDate);
  const formattedDate = formatReadableDate(selectedDate);

  if (!filtered.length) {
    els.slots.innerHTML = `
      <div class="slots-section-header">
        <span class="slots-date-label">${ICONS.calendarSm} ${formattedDate}</span>
        <span class="slot-badge">0 slots</span>
      </div>
      <div class="empty-state">
        ${ICONS.calendar}
        <div class="empty-state-title">No slots available on this date</div>
        <p class="empty-state-text">Please pick another date highlighted with a dot in the calendar above.</p>
      </div>
    `;
    return;
  }

  // Sort chronologically
  filtered.sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

  let html = `
    <div class="slots-section-header">
      <span class="slots-date-label">${ICONS.calendarSm} ${formattedDate}</span>
      <span class="slot-badge">${filtered.length} slot${filtered.length === 1 ? "" : "s"} available</span>
    </div>
    <div class="slots-grid">
  `;

  els.slots.innerHTML = html;
  const gridContainer = document.createElement("div");
  gridContainer.className = "slots-grid";

  for (const slot of filtered) {
    const from = new Date(slot.start_time);
    const to = new Date(slot.end_time);
    const timeDisplay = `${formatTimeOnly(from)} – ${formatTimeOnly(to)}`;
    const durationMinutes = Math.round((to - from) / 60000);

    const card = document.createElement("div");
    card.className = "slot-card";
    card.innerHTML = `
      <div>
        <div class="slot-time-primary">${ICONS.clock} ${formatTimeOnly(from)}</div>
        <p class="slot-time-secondary">Until ${formatTimeOnly(to)} · ${durationMinutes} mins</p>
      </div>
    `;

    const bookBtn = document.createElement("button");
    bookBtn.type = "button";
    bookBtn.textContent = "Book";
    bookBtn.addEventListener("click", () => bookSlot(slot.id, bookBtn));
    card.appendChild(bookBtn);

    gridContainer.appendChild(card);
  }

  els.slots.appendChild(gridContainer);
}

/* ── Booking ─────────────────────────────────────────── */

async function bookSlot(slotId, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Booking…";

  try {
    await api("/appointments", {
      method: "POST",
      body: JSON.stringify({ slot_id: slotId }),
    });
    showBanner("Appointment successfully booked!", true);
    await refreshBoard();
  } catch (err) {
    if (err.status === 409) {
      showBanner("Sorry, this slot was just booked by someone else. Please choose another time.");
      await loadAllSlots();
    } else {
      showBanner(err.message);
    }
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

/* ── Appointments ────────────────────────────────────── */

async function loadAppointments() {
  const rows = await api("/appointments");
  const mine = (rows || []).filter((row) => row.status !== "cancelled");

  if (!mine.length) {
    els.appointments.innerHTML = `
      <div class="empty-state">
        ${ICONS.calendar}
        <div class="empty-state-title">No upcoming appointments</div>
        <p class="empty-state-text">Select an available date and time slot to book your first appointment.</p>
      </div>
    `;
    return;
  }

  els.appointments.innerHTML = "";
  for (const appt of mine) {
    const card = document.createElement("div");
    card.className = "appt-card";
    card.innerHTML = `
      <div>
        <div class="appt-title">Appointment #${appt.id}</div>
        <p class="appt-meta">
          <span>Slot ${appt.slot_id}</span>
          <span class="status-badge">${appt.status}</span>
        </p>
      </div>
    `;

    if (appt.status === "booked") {
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "danger";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", () => cancelAppointment(appt.id, cancel));
      card.appendChild(cancel);
    }

    els.appointments.appendChild(card);
  }
}

async function cancelAppointment(id, button) {
  const origText = button.textContent;
  button.disabled = true;
  button.textContent = "Cancelling…";

  try {
    await api(`/appointments/${id}`, { method: "DELETE" });
    showBanner("Appointment cancelled.", true);
    await refreshBoard();
  } catch (err) {
    showBanner(err.message);
  } finally {
    button.disabled = false;
    button.textContent = origText;
  }
}

/* ── Board refresh ───────────────────────────────────── */

async function refreshBoard() {
  await Promise.all([loadAllSlots(), loadAppointments()]);
}

/* ── Session restore ─────────────────────────────────── */

async function restoreSession() {
  initCalendarState();
  renderCalendar();

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

/* ── Auth message helpers ────────────────────────────── */

function showAuthMessage(message, type = "error") {
  els.authMessage.textContent = message;
  els.authMessage.className = `auth-message ${type}`;
  els.authMessage.classList.remove("hidden");
}

function hideAuthMessage() {
  els.authMessage.classList.add("hidden");
  els.authMessage.className = "auth-message hidden";
  els.authMessage.textContent = "";
}

function clearFieldErrors() {
  document.querySelectorAll(".field-error").forEach((el) => (el.textContent = ""));
  document.querySelectorAll(".input-error").forEach((el) => el.classList.remove("input-error"));
}

function setFieldError(inputId, message) {
  const input = document.getElementById(inputId);
  const errorEl = document.getElementById(`${inputId}-error`);
  if (input) input.classList.add("input-error");
  if (errorEl) errorEl.textContent = message;
}

/* ── Auth tab switching ─────────────────────────────── */

function switchAuthTab(tab) {
  hideAuthMessage();
  clearFieldErrors();

  // Toggle forms
  els.loginForm.classList.toggle("hidden", tab !== "login");
  els.signupForm.classList.toggle("hidden", tab !== "signup");
  els.forgotForm.classList.toggle("hidden", tab !== "forgot");
  els.resetForm.classList.toggle("hidden", tab !== "reset");

  // Toggle tabs visibility (hide tabs on forgot/reset)
  els.authTabs.classList.toggle("hidden", tab === "forgot" || tab === "reset");

  // Update tab active states
  els.authTabs.querySelectorAll(".auth-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  // Update title & subtitle
  const titles = {
    login: ["Log in to your account", "Welcome back! Please enter your details."],
    signup: ["Create your account", "Start booking appointments in minutes."],
    forgot: ["Reset your password", "Enter your email and we\u2019ll send you a reset link."],
    reset: ["Set new password", "Enter your new password below."],
  };
  const [title, subtitle] = titles[tab] || titles.login;
  els.authTitle.textContent = title;
  els.authSubtitle.textContent = subtitle;
}

/* ── Friendly error mapping ─────────────────────────── */

function friendlyAuthError(message) {
  const msg = (message || "").toLowerCase();
  if (msg.includes("invalid login") || msg.includes("invalid email or password")) {
    return "Invalid email or password.";
  }
  if (msg.includes("email not confirmed") || msg.includes("not confirmed")) {
    return "Please verify your email before signing in.";
  }
  if (msg.includes("already registered") || msg.includes("already been registered")) {
    return "An account with this email already exists.";
  }
  if (msg.includes("rate limit") || msg.includes("too many")) {
    return "Too many attempts. Please try again later.";
  }
  if (msg.includes("weak password") || msg.includes("should be at least")) {
    return "Password must be at least 8 characters.";
  }
  if (msg.includes("signup is disabled")) {
    return "Sign up is currently disabled. Please contact support.";
  }
  return message || "Something went wrong. Please try again.";
}

/* ── Login ───────────────────────────────────────────── */

async function login() {
  const email = els.loginEmail.value.trim();
  const password = els.loginPassword.value;

  clearFieldErrors();
  hideAuthMessage();

  let valid = true;
  if (!email) {
    setFieldError("login-email", "Email is required.");
    valid = false;
  }
  if (!password) {
    setFieldError("login-password", "Password is required.");
    valid = false;
  }
  if (!valid) return;

  els.loginBtn.disabled = true;
  els.loginBtn.textContent = "Signing in\u2026";

  try {
    const data = await api("/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      auth: false,
    });
    setToken(data.access_token);
    const me = await api("/me");
    setSignedIn(me);
    showBanner("Logged in.", true);
    await refreshBoard();
  } catch (err) {
    showAuthMessage(friendlyAuthError(err.message));
  } finally {
    els.loginBtn.disabled = false;
    els.loginBtn.textContent = "Sign in";
  }
}

/* ── Signup ──────────────────────────────────────────── */

async function signup() {
  const email = els.signupEmail.value.trim();
  const password = els.signupPassword.value;
  const confirm = els.signupConfirm.value;

  clearFieldErrors();
  hideAuthMessage();

  let valid = true;
  if (!email) {
    setFieldError("signup-email", "Email is required.");
    valid = false;
  }
  if (!password) {
    setFieldError("signup-password", "Password is required.");
    valid = false;
  } else if (password.length < 8) {
    setFieldError("signup-password", "Password must be at least 8 characters.");
    valid = false;
  }
  if (!confirm) {
    setFieldError("signup-confirm", "Please confirm your password.");
    valid = false;
  } else if (password && confirm !== password) {
    setFieldError("signup-confirm", "Passwords do not match.");
    valid = false;
  }
  if (!valid) return;

  els.signupBtn.disabled = true;
  els.signupBtn.textContent = "Creating account\u2026";

  try {
    const data = await api("/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      auth: false,
    });

    if (data.email_confirmation_required) {
      showAuthMessage(
        "Account created! We\u2019ve sent a verification email to " + email + ". Please verify your email before signing in.",
        "success"
      );
      // Reset the signup form and switch to login tab after a moment
      els.signupForm.reset();
      setTimeout(() => switchAuthTab("login"), 100);
      // Re-show the success message since tab switch clears it
      setTimeout(() => {
        showAuthMessage(
          "Account created! We\u2019ve sent a verification email to " + email + ". Please verify your email before signing in.",
          "success"
        );
      }, 150);
      return;
    }

    // Auto-confirm is on: log the user in immediately
    els.signupBtn.textContent = "Signing in\u2026";
    els.loginEmail.value = email;
    els.loginPassword.value = password;
    await login();
  } catch (err) {
    showAuthMessage(friendlyAuthError(err.message));
  } finally {
    els.signupBtn.disabled = false;
    els.signupBtn.textContent = "Create account";
  }
}

/* ── Forgot password ────────────────────────────────── */

async function forgotPassword() {
  const email = els.forgotEmail.value.trim();

  clearFieldErrors();
  hideAuthMessage();

  if (!email) {
    setFieldError("forgot-email", "Email is required.");
    return;
  }

  els.forgotBtn.disabled = true;
  els.forgotBtn.textContent = "Sending\u2026";

  try {
    await api("/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
      auth: false,
    });
    showAuthMessage(
      "If an account exists for that email, we\u2019ve sent a password reset link. Check your inbox.",
      "success"
    );
  } catch (err) {
    // Always show success to not leak info about accounts
    showAuthMessage(
      "If an account exists for that email, we\u2019ve sent a password reset link. Check your inbox.",
      "success"
    );
  } finally {
    els.forgotBtn.disabled = false;
    els.forgotBtn.textContent = "Send reset link";
  }
}

/* ── Reset password (from email link) ────────────────── */

async function resetPassword() {
  const password = els.resetPassword.value;
  const confirm = els.resetConfirm.value;

  clearFieldErrors();
  hideAuthMessage();

  let valid = true;
  if (!password) {
    setFieldError("reset-password", "Password is required.");
    valid = false;
  } else if (password.length < 8) {
    setFieldError("reset-password", "Password must be at least 8 characters.");
    valid = false;
  }
  if (!confirm) {
    setFieldError("reset-confirm", "Please confirm your password.");
    valid = false;
  } else if (password && confirm !== password) {
    setFieldError("reset-confirm", "Passwords do not match.");
    valid = false;
  }
  if (!valid) return;

  if (!recoveryToken) {
    showAuthMessage("Invalid or expired reset link. Please request a new one.");
    return;
  }

  els.resetBtn.disabled = true;
  els.resetBtn.textContent = "Updating\u2026";

  try {
    await api("/reset-password", {
      method: "POST",
      body: JSON.stringify({ access_token: recoveryToken, new_password: password }),
      auth: false,
    });
    recoveryToken = null;
    // Clear the hash from the URL
    history.replaceState(null, "", window.location.pathname);
    showAuthMessage("Password updated successfully! You can now log in with your new password.", "success");
    els.resetForm.reset();
    setTimeout(() => switchAuthTab("login"), 100);
    setTimeout(() => {
      showAuthMessage("Password updated successfully! You can now log in with your new password.", "success");
    }, 150);
  } catch (err) {
    showAuthMessage(friendlyAuthError(err.message));
  } finally {
    els.resetBtn.disabled = false;
    els.resetBtn.textContent = "Set new password";
  }
}

/* ── Recovery token detection ────────────────────────── */

function checkRecoveryToken() {
  const hash = window.location.hash;
  if (!hash) return false;

  // Parse hash fragment: #access_token=...&type=recovery&...
  const params = new URLSearchParams(hash.substring(1));
  const accessToken = params.get("access_token");
  const type = params.get("type");

  if (accessToken && type === "recovery") {
    recoveryToken = accessToken;
    switchAuthTab("reset");
    return true;
  }
  return false;
}

/* ── Event listeners ─────────────────────────────────── */

// Auth tab clicks
els.authTabs.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-tab]");
  if (tab) switchAuthTab(tab.dataset.tab);
});

// Login form submit
els.loginForm.addEventListener("submit", (e) => {
  e.preventDefault();
  login();
});

// Signup form submit
els.signupForm.addEventListener("submit", (e) => {
  e.preventDefault();
  signup();
});

// Forgot password form submit
els.forgotForm.addEventListener("submit", (e) => {
  e.preventDefault();
  forgotPassword();
});

// Link: switch to signup
document.getElementById("switch-to-signup").addEventListener("click", (e) => {
  e.preventDefault();
  switchAuthTab("signup");
});

// Link: switch to login
document.getElementById("switch-to-login").addEventListener("click", (e) => {
  e.preventDefault();
  switchAuthTab("login");
});

// Link: forgot password
document.getElementById("forgot-link").addEventListener("click", (e) => {
  e.preventDefault();
  switchAuthTab("forgot");
});

// Link: back to login from forgot
document.getElementById("back-to-login").addEventListener("click", (e) => {
  e.preventDefault();
  switchAuthTab("login");
});

// Link: back to login from reset
document.getElementById("reset-back-to-login").addEventListener("click", (e) => {
  e.preventDefault();
  recoveryToken = null;
  history.replaceState(null, "", window.location.pathname);
  switchAuthTab("login");
});

// Reset password form submit
els.resetForm.addEventListener("submit", (e) => {
  e.preventDefault();
  resetPassword();
});

// Clear field errors on input
document.querySelectorAll(".auth-input-group input").forEach((input) => {
  input.addEventListener("input", () => {
    input.classList.remove("input-error");
    const errorEl = document.getElementById(`${input.id}-error`);
    if (errorEl) errorEl.textContent = "";
  });
});

// Logout
document.getElementById("logout").addEventListener("click", () => {
  setSignedOut();
  showBanner("Logged out.", true);
});

document.getElementById("refresh-slots").addEventListener("click", async () => {
  try {
    await loadAllSlots();
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

// Listen for hash changes in case recovery link is loaded or pasted in an open tab
window.addEventListener("hashchange", () => {
  checkRecoveryToken();
});

// Check for password recovery token in URL before restoring session
if (!checkRecoveryToken()) {
  restoreSession();
}
