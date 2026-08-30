const state = {
  page: 1,
  pageSize: 10,
  ordering: '-created_at',
  search: '',
  department: '',
  isActive: 'true',
};

const studentModalEl = document.getElementById('studentModal');
const studentModal = new bootstrap.Modal(studentModalEl);

async function loadStudents() {
  const tbody = document.getElementById('studentsTbody');
  tbody.innerHTML = `<tr><td colspan="7"><div class="spinner-overlay"><div class="spinner-border text-primary"></div></div></td></tr>`;
  try {
    const data = await apiRequest('/students/', {
      params: {
        page: state.page,
        page_size: state.pageSize,
        ordering: state.ordering,
        search: state.search,
        department: state.department,
        is_active: state.isActive,
      },
    });
    renderTable(data.results);
    renderPagination(data);
    document.getElementById('resultsSummary').textContent =
      `Showing ${data.results.length} of ${data.count} student(s)`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-danger text-center py-4">${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderTable(rows) {
  const tbody = document.getElementById('studentsTbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><i class="bi bi-person-x"></i><div>No students match these filters.</div></div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(s => `
    <tr>
      <td>
        <div class="d-flex align-items-center gap-2">
          <span class="avatar-circle">${initials(s.full_name)}</span>
          <div>
            <a href="/students/${s.id}/" class="fw-semibold text-decoration-none">${escapeHtml(s.full_name)}</a>
            <div class="text-secondary" style="font-size:.75rem">${escapeHtml(s.student_id)}</div>
          </div>
        </div>
      </td>
      <td>${escapeHtml(s.email)}</td>
      <td>${escapeHtml(s.department || '—')}</td>
      <td>${formatDate(s.enrollment_date)}</td>
      <td>${s.gpa !== null ? `<span class="gpa-pill">${s.gpa.toFixed(2)}</span>` : '<span class="text-secondary">—</span>'}</td>
      <td>${s.is_active ? '<span class="badge text-bg-success">Active</span>' : '<span class="badge text-bg-secondary">Archived</span>'}</td>
      <td class="text-end">
        <div class="btn-group btn-group-sm">
          <a href="/students/${s.id}/" class="btn btn-outline-secondary" title="Transcript"><i class="bi bi-file-earmark-text"></i></a>
          <button class="btn btn-outline-primary" title="Edit" onclick="editStudent(${s.id})"><i class="bi bi-pencil"></i></button>
          ${s.is_active
            ? `<button class="btn btn-outline-danger" title="Archive" onclick="deleteStudent(${s.id}, '${escapeJs(s.full_name)}')"><i class="bi bi-archive"></i></button>`
            : `<button class="btn btn-outline-success" title="Restore" onclick="restoreStudent(${s.id})"><i class="bi bi-arrow-counterclockwise"></i></button>`}
        </div>
      </td>
    </tr>`).join('');
}

function escapeJs(str) { return String(str).replace(/'/g, "\\'"); }

function renderPagination(data) {
  const totalPages = data.total_pages || 1;
  const current = data.current_page || 1;
  const ul = document.getElementById('pagination');
  let html = '';
  const addItem = (label, page, disabled, active) => {
    html += `<li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
      <a class="page-link" href="#" data-page="${page}">${label}</a></li>`;
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
      if (!isNaN(page) && page >= 1 && page <= totalPages) {
        state.page = page;
        loadStudents();
      }
    });
  });
}

// --- Filters / search / sort ---------------------------------------------
document.getElementById('searchInput').addEventListener('input', debounce((e) => {
  state.search = e.target.value;
  state.page = 1;
  loadStudents();
}));
document.getElementById('deptFilter').addEventListener('input', debounce((e) => {
  state.department = e.target.value;
  state.page = 1;
  loadStudents();
}));
document.getElementById('statusFilter').addEventListener('change', (e) => {
  state.isActive = e.target.value;
  state.page = 1;
  loadStudents();
});
document.getElementById('pageSizeSelect').addEventListener('change', (e) => {
  state.pageSize = parseInt(e.target.value, 10);
  state.page = 1;
  loadStudents();
});
document.getElementById('clearFiltersBtn').addEventListener('click', () => {
  document.getElementById('searchInput').value = '';
  document.getElementById('deptFilter').value = '';
  document.getElementById('statusFilter').value = 'true';
  document.getElementById('pageSizeSelect').value = '10';
  Object.assign(state, { page: 1, pageSize: 10, search: '', department: '', isActive: 'true', ordering: '-created_at' });
  document.querySelectorAll('th.sortable').forEach(th => th.classList.remove('sort-active'));
  loadStudents();
});
document.querySelectorAll('th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const field = th.dataset.sort;
    if (state.ordering === field) state.ordering = `-${field}`;
    else if (state.ordering === `-${field}`) state.ordering = field;
    else state.ordering = field;
    document.querySelectorAll('th.sortable').forEach(t => t.classList.remove('sort-active'));
    th.classList.add('sort-active');
    loadStudents();
  });
});
document.getElementById('exportBtn').addEventListener('click', () => {
  downloadFile('/students/export_csv/', {
    search: state.search, department: state.department, is_active: state.isActive,
  }, 'students.csv');
});

// --- Add / Edit modal ------------------------------------------------------
document.getElementById('addStudentBtn').addEventListener('click', () => {
  resetForm();
  document.getElementById('studentModalTitle').textContent = 'Add Student';
  studentModal.show();
});

function resetForm() {
  document.getElementById('studentForm').reset();
  document.getElementById('studentPk').value = '';
  document.getElementById('f_is_active').checked = true;
  document.getElementById('formErrors').classList.add('d-none');
}

async function editStudent(id) {
  try {
    const s = await apiRequest(`/students/${id}/`);
    resetForm();
    document.getElementById('studentModalTitle').textContent = `Edit ${s.full_name}`;
    document.getElementById('studentPk').value = s.id;
    document.getElementById('f_first_name').value = s.first_name;
    document.getElementById('f_last_name').value = s.last_name;
    document.getElementById('f_email').value = s.email;
    document.getElementById('f_phone_number').value = s.phone_number || '';
    document.getElementById('f_date_of_birth').value = s.date_of_birth || '';
    document.getElementById('f_gender').value = s.gender || '';
    document.getElementById('f_department').value = s.department || '';
    document.getElementById('f_enrollment_date').value = s.enrollment_date || '';
    document.getElementById('f_is_active').checked = s.is_active;
    document.getElementById('f_address').value = s.address || '';
    studentModal.show();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

document.getElementById('studentForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pk = document.getElementById('studentPk').value;
  const payload = {
    first_name: document.getElementById('f_first_name').value,
    last_name: document.getElementById('f_last_name').value,
    email: document.getElementById('f_email').value,
    phone_number: document.getElementById('f_phone_number').value,
    date_of_birth: document.getElementById('f_date_of_birth').value || null,
    gender: document.getElementById('f_gender').value,
    department: document.getElementById('f_department').value,
    enrollment_date: document.getElementById('f_enrollment_date').value || undefined,
    is_active: document.getElementById('f_is_active').checked,
    address: document.getElementById('f_address').value,
  };
  const errBox = document.getElementById('formErrors');
  errBox.classList.add('d-none');
  const submitBtn = document.getElementById('studentFormSubmit');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving…';
  try {
    if (pk) {
      await apiRequest(`/students/${pk}/`, { method: 'PATCH', body: payload });
      showToast('Student updated successfully.');
    } else {
      await apiRequest('/students/', { method: 'POST', body: payload });
      showToast('Student added successfully.');
    }
    studentModal.hide();
    loadStudents();
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove('d-none');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Save Student';
  }
});

async function deleteStudent(id, name) {
  if (!confirm(`Archive ${name}? Their records will be preserved and can be restored later.`)) return;
  try {
    await apiRequest(`/students/${id}/`, { method: 'DELETE' });
    showToast(`${name} archived.`, 'warning');
    loadStudents();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function restoreStudent(id) {
  try {
    const s = await apiRequest(`/students/${id}/restore/`, { method: 'POST' });
    showToast(`${s.full_name} restored.`);
    loadStudents();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

loadStudents();
