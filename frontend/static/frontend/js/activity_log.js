const logState = { page: 1, pageSize: 15 };

const actionColors = { create: 'success', update: 'primary', delete: 'danger', restore: 'warning' };

async function loadLog() {
  const tbody = document.getElementById('logTbody');
  tbody.innerHTML = `<tr><td colspan="5"><div class="spinner-overlay"><div class="spinner-border text-primary"></div></div></td></tr>`;
  try {
    const data = await apiRequest('/activity-log/', { params: { page: logState.page, page_size: logState.pageSize } });
    renderLog(data.results);
    renderPagination(data);
    document.getElementById('resultsSummary').textContent = `Showing ${data.results.length} of ${data.count} event(s)`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-4">${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderLog(rows) {
  const tbody = document.getElementById('logTbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state"><i class="bi bi-clock-history"></i><div>No activity recorded yet.</div></div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(a => `
    <tr>
      <td class="text-secondary small">${new Date(a.timestamp).toLocaleString()}</td>
      <td><span class="badge text-bg-${actionColors[a.action] || 'secondary'} text-capitalize">${escapeHtml(a.action)}</span></td>
      <td>${escapeHtml(a.model_name)}</td>
      <td>${escapeHtml(a.object_repr)}</td>
      <td class="text-secondary small">${escapeHtml(a.details || '—')}</td>
    </tr>`).join('');
}

function renderPagination(data) {
  const totalPages = data.total_pages || 1;
  const current = data.current_page || 1;
  const ul = document.getElementById('pagination');
  let html = '';
  const addItem = (label, page, disabled, active) => {
    html += `<li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}"><a class="page-link" href="#" data-page="${page}">${label}</a></li>`;
  };
  addItem('«', current - 1, current === 1, false);
  const start = Math.max(1, current - 2);
  const end = Math.min(totalPages, start + 4);
  for (let p = start; p <= end; p++) addItem(p, p, false, p === current);
  addItem('»', current + 1, current === totalPages, false);
  ul.innerHTML = html;
  ul.querySelectorAll('a.page-link').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const page = parseInt(a.dataset.page, 10);
      if (!isNaN(page) && page >= 1 && page <= totalPages) { logState.page = page; loadLog(); }
    });
  });
}

loadLog();
