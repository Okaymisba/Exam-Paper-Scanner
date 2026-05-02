/*
 * utils.js
 * Pure utility functions with no side effects and no dependency on app state.
 * Loaded second, after state.js.
 */

/**
 * HTML-escape a value so it is safe to inject into innerHTML.
 * @param {*} s - Any value; will be coerced to string.
 * @returns {string}
 */
function esc(s) {
  return String(s).replace(/[&<>"']/g,
    m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m])
  );
}

/**
 * Format a number for display: integers are shown without a decimal point,
 * floats are shown with one decimal place.
 * @param {number} n
 * @returns {string}
 */
function fmt(n) {
  return n % 1 === 0 ? String(n) : n.toFixed(1);
}

/**
 * Show or hide the full-screen loading overlay.
 * @param {boolean} show
 * @param {string}  [title]
 * @param {string}  [sub]
 */
function setLoading(show, title = 'Please wait...', sub = '') {
  document.getElementById('loadingOverlay').classList.toggle('hidden', !show);
  document.getElementById('loadingTitle').textContent = title;
  document.getElementById('loadingSub').textContent   = sub;
}

/**
 * Wrapper around fetch() that automatically attaches the Authorization header
 * when authToken is set and always parses the JSON response body.
 * @param {string} path
 * @param {RequestInit} [opts]
 * @returns {Promise<{ ok: boolean, status: number, data: any }>}
 */
async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const res  = await fetch(path, { ...opts, headers });
  const data = await res.json();
  return { ok: res.ok, status: res.status, data };
}

/**
 * Like apiFetch() but sends a FormData body (multipart). Used for image uploads.
 * @param {string}   path
 * @param {FormData} formData
 * @returns {Promise<{ ok: boolean, status: number, data: any }>}
 */
async function apiFetchForm(path, formData) {
  const headers = {};
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const res  = await fetch(path, { method: 'POST', headers, body: formData });
  const data = await res.json();
  return { ok: res.ok, status: res.status, data };
}

/**
 * Display a message inside an alert element.
 * @param {string} id  - Element ID of the alert container.
 * @param {string} msg - Message text to display.
 */
function showAlert(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.classList.remove('hidden');
}

/**
 * Hide an alert element and clear its text.
 * @param {string} id - Element ID of the alert container.
 */
function clearAlert(id) {
  const el = document.getElementById(id);
  el.textContent = '';
  el.classList.add('hidden');
}
