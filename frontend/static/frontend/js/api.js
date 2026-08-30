/**
 * Small shared helper library used by every page's JS file.
 * Talks to the DRF API mounted at /api/.
 */
const API_BASE = '/api';

/** Wraps fetch(), parses JSON, and throws a normalized Error on failure. */
async function apiRequest(path, { method = 'GET', body = null, params = null, _retry = true } = {}) {
  let url = `${API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') qs.append(k, v);
    });
    const qsStr = qs.toString();
    if (qsStr) url += (url.includes('?') ? '&' : '?') + qsStr;
  }

  const access = localStorage.getItem('access') || localStorage.getItem('access_token') || localStorage.getItem('jwt_access');
  const options = {
    method,
    headers: { 'Content-Type': 'application/json', ...(access ? {Authorization:`Bearer ${access}`} : {}) },
  };
  if (body !== null) options.body = JSON.stringify(body);

  let response;
  try {
    response = await fetch(url, options);
  } catch (networkErr) {
    throw new Error('Network error: could not reach the API. Is the Django server running?');
  }

  // JWT access tokens expire. Silently refresh once, then retry the original
  // request. This prevents "Authentication credentials were not provided"
  // after a portal has been left open for a while.
  if (response.status === 401 && _retry && path !== '/auth/login/' && path !== '/auth/register/' && path !== '/auth/token/refresh/') {
    const refresh = localStorage.getItem('refresh');
    if (refresh) {
      try {
        const rr = await fetch(`${API_BASE}/auth/token/refresh/`, {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({refresh})
        });
        const rd = await rr.json().catch(() => ({}));
        if (rr.ok && rd.access) {
          localStorage.setItem('access', rd.access);
          localStorage.setItem('access_token', rd.access);
          return apiRequest(path, {method, body, params, _retry:false});
        }
      } catch (_) {}
    }
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    localStorage.removeItem('user');
    throw new Error('Your session has expired. Please sign in again.');
  }

  if (response.status === 204) return null;

  let data = null;
  const text = await response.text();
  if (text) {
    try { data = JSON.parse(text); } catch (e) { data = null; }
  }

  if (!response.ok) {
    const message = extractErrorMessage(data) || `Request failed (HTTP ${response.status})`;
    const err = new Error(message);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

/** Flattens the {success:false, errors:{...}} shape from core/exceptions.py into one string. */
function extractErrorMessage(data) {
  if (!data) return null;
  const errors = data.errors !== undefined ? data.errors : data;
  if (typeof errors === 'string') return errors;
  if (Array.isArray(errors)) return errors.join(' ');
  if (typeof errors === 'object') {
    const parts = [];
    for (const [field, val] of Object.entries(errors)) {
      const msg = Array.isArray(val) ? val.join(' ') : val;
      parts.push(field === 'non_field_errors' || field === 'detail' ? msg : `${field}: ${msg}`);
    }
    return parts.join(' | ');
  }
  return null;
}

/** Toast notification helper (Bootstrap toasts). type: success | danger | warning | info */
function showToast(message, type = 'success') {
  const stack = document.getElementById('toastStack');
  if (!stack) { alert(message); return; }
  const icons = { success: 'bi-check-circle-fill', danger: 'bi-x-octagon-fill',
                  warning: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
  const el = document.createElement('div');
  el.className = `toast align-items-center text-bg-${type} border-0`;
  el.setAttribute('role', 'alert');
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body"><i class="bi ${icons[type] || icons.info} me-2"></i>${escapeHtml(message)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  stack.appendChild(el);
  const toast = new bootstrap.Toast(el, { delay: 4500 });
  toast.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function debounce(fn, delay = 350) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d)) return value;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function initials(name) {
  if (!name) return '?';
  return name.split(' ').filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('');
}

function statusBadge(status) {
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  return `<span class="badge badge-status-${status}">${label}</span>`;
}

async function downloadFile(path, params, filename) {
  let url = `${API_BASE}${path}`;
  const qs = new URLSearchParams(params || {});
  const qsStr = qs.toString();
  if (qsStr) url += `?${qsStr}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}
