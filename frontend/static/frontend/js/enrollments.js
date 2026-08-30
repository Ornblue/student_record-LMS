const enState = {
  page: 1,
  pageSize: 10,
  ordering: '-enrollment_date',
  search: '',
  status: '',
  semester: '',
};

const enrollmentModal = new bootstrap.Modal(document.getElementById('enrollmentModal'));
const bulkModal = new bootstrap.Modal(document.getElementById('bulkModal'));
const gradeModal = new bootstrap.Modal(document.getElementById('gradeModal'));

async function loadEnrollments() {
  const tbody = document.getElementById('enrollmentsTbody');
  tbody.innerHTML = `<tr><td colspan="6"><div class="spinner-overlay"><div class="spinner-border text-primary"></div></div></td></tr>`;
  try {
    const data = await apiRequest('/enrollments/', {
      params: {
        page: enState.page, page_size: enState.pageSize, ordering: enState.ordering,
        search: enState.search, status: enState.status, semester: enState.semester,
      },
    });
    renderTable(data.results);
    renderPagination(data);
    document.getElementById('resultsSummary').textContent = `Showing ${data.results.length} of ${data.count} enrollment(s)`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger text-center py-4">${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderTable(rows) {
  const tbody = document.getElementById('enrollmentsTbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><i class="bi bi-clipboard-x"></i><div>No enrollments match these filters.</div></div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(e => `
    <tr>
      <td>
        <div class="fw-semibold">${escapeHtml(e.student_name)}</div>
        <div class="text-secondary" style="font-size:.75rem">${escapeHtml(e.student_code)}</div>
      </td>
      <td>
        <div class="fw-semibold">${escapeHtml(e.course_code)}</div>
        <div class="text-secondary" style="font-size:.75rem">${escapeHtml(e.course_title)}</div>
      </td>
      <td>${escapeHtml(e.semester)}</td>
      <td>${statusBadge(e.status)}</td>
      <td>${e.grade ? `<span class="badge text-bg-light border">${escapeHtml(e.grade)}</span>` : '<span class="text-secondary">—</span>'}</td>
      <td class="text-end">
        <div class="btn-group btn-group-sm">
          ${e.status !== 'completed' ? `<button class="btn btn-outline-success" title="Assign grade" onclick="openGradeModal(${e.id}, '${escapeJs(e.student_name)}', '${escapeJs(e.course_code)}')"><i class="bi bi-award"></i></button>` : ''}
          <button class="btn btn-outline-danger" title="Remove" onclick="deleteEnrollment(${e.id})"><i class="bi bi-trash"></i></button>
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
      if (!isNaN(page) && page >= 1 && page <= totalPages) { enState.page = page; loadEnrollments(); }
    });
  });
}

document.getElementById('searchInput').addEventListener('input', debounce((e) => { enState.search = e.target.value; enState.page = 1; loadEnrollments(); }));
document.getElementById('statusFilter').addEventListener('change', (e) => { enState.status = e.target.value; enState.page = 1; loadEnrollments(); });
document.getElementById('semesterFilter').addEventListener('input', debounce((e) => { enState.semester = e.target.value; enState.page = 1; loadEnrollments(); }));
document.getElementById('pageSizeSelect').addEventListener('change', (e) => { enState.pageSize = parseInt(e.target.value, 10); enState.page = 1; loadEnrollments(); });
document.getElementById('clearFiltersBtn').addEventListener('click', () => {
  document.getElementById('searchInput').value = '';
  document.getElementById('statusFilter').value = '';
  document.getElementById('semesterFilter').value = '';
  document.getElementById('pageSizeSelect').value = '10';
  Object.assign(enState, { page: 1, pageSize: 10, search: '', status: '', semester: '' });
  loadEnrollments();
});
document.querySelectorAll('th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const field = th.dataset.sort;
    if (enState.ordering === field) enState.ordering = `-${field}`;
    else if (enState.ordering === `-${field}`) enState.ordering = field;
    else enState.ordering = field;
    document.querySelectorAll('th.sortable').forEach(t => t.classList.remove('sort-active'));
    th.classList.add('sort-active');
    loadEnrollments();
  });
});
document.getElementById('exportBtn').addEventListener('click', () => {
  downloadFile('/enrollments/export_csv/', { status: enState.status, semester: enState.semester }, 'enrollments.csv');
});

async function deleteEnrollment(id) {
  if (!confirm('Remove this enrollment record?')) return;
  try {
    await apiRequest(`/enrollments/${id}/`, { method: 'DELETE' });
    showToast('Enrollment removed.', 'warning');
    loadEnrollments();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// --- Populate student / course dropdowns ----------------------------------
async function populateSelect(selectEl, path, labelFn) {
  selectEl.innerHTML = '<option value="">Loading…</option>';
  try {
    const data = await apiRequest(path, { params: { page_size: 200, is_active: true } });
    const rows = data.results || [];
    selectEl.innerHTML = rows.length
      ? rows.map(r => `<option value="${r.id}">${escapeHtml(labelFn(r))}</option>`).join('')
      : '<option value="">No active records found</option>';
  } catch (err) {
    selectEl.innerHTML = '<option value="">Failed to load</option>';
  }
}

// --- New Enrollment ---------------------------------------------------------
document.getElementById('addEnrollmentBtn').addEventListener('click', async () => {
  document.getElementById('enrollmentForm').reset();
  document.getElementById('e_semester').value = '2026-Fall';
  document.getElementById('enrollFormErrors').classList.add('d-none');
  enrollmentModal.show();
  await Promise.all([
    populateSelect(document.getElementById('e_student'), '/students/', s => `${s.student_id} — ${s.full_name}`),
    populateSelect(document.getElementById('e_course'), '/courses/', c => `${c.course_code} — ${c.title} (${c.available_seats} seats left)`),
  ]);
});

document.getElementById('enrollmentForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errBox = document.getElementById('enrollFormErrors');
  errBox.classList.add('d-none');
  const submitBtn = document.getElementById('enrollFormSubmit');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Enrolling…';
  try {
    const result = await apiRequest('/enrollments/', {
      method: 'POST',
      body: {
        student: parseInt(document.getElementById('e_student').value, 10),
        course: parseInt(document.getElementById('e_course').value, 10),
        semester: document.getElementById('e_semester').value,
      },
    });
    showToast(result.status === 'waitlisted' ? 'Course is full — student was waitlisted.' : 'Student enrolled successfully.',
              result.status === 'waitlisted' ? 'warning' : 'success');
    enrollmentModal.hide();
    loadEnrollments();
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove('d-none');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Enroll';
  }
});

// --- Bulk Enroll -------------------------------------------------------------
document.getElementById('bulkEnrollBtn').addEventListener('click', async () => {
  document.getElementById('bulkForm').reset();
  document.getElementById('b_semester').value = '2026-Fall';
  document.getElementById('bulkFormErrors').classList.add('d-none');
  bulkModal.show();
  await Promise.all([
    populateSelect(document.getElementById('b_course'), '/courses/', c => `${c.course_code} — ${c.title} (${c.available_seats} seats left)`),
    populateSelect(document.getElementById('b_students'), '/students/', s => `${s.student_id} — ${s.full_name}`),
  ]);
});

document.getElementById('bulkForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errBox = document.getElementById('bulkFormErrors');
  errBox.classList.add('d-none');
  const selected = Array.from(document.getElementById('b_students').selectedOptions).map(o => parseInt(o.value, 10)).filter(Boolean);
  if (selected.length === 0) {
    errBox.textContent = 'Select at least one student.';
    errBox.classList.remove('d-none');
    return;
  }
  const submitBtn = document.getElementById('bulkFormSubmit');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Enrolling…';
  try {
    const result = await apiRequest('/enrollments/bulk_enroll/', {
      method: 'POST',
      body: {
        student_ids: selected,
        course: parseInt(document.getElementById('b_course').value, 10),
        semester: document.getElementById('b_semester').value,
      },
    });
    showToast(`Enrolled ${result.created_count} student(s); skipped ${result.skipped_count} duplicate(s).`);
    bulkModal.hide();
    loadEnrollments();
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove('d-none');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Enroll Selected';
  }
});

// --- Set Grade -----------------------------------------------------------
function openGradeModal(enrollmentId, studentName, courseCode) {
  document.getElementById('g_enrollment_id').value = enrollmentId;
  document.getElementById('g_context').textContent = `${studentName} — ${courseCode}`;
  document.getElementById('g_grade').value = '';
  gradeModal.show();
}

document.getElementById('gradeForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('g_enrollment_id').value;
  const grade = document.getElementById('g_grade').value;
  try {
    await apiRequest(`/enrollments/${id}/set_grade/`, { method: 'POST', body: { grade } });
    showToast('Grade saved and enrollment marked completed.');
    gradeModal.hide();
    loadEnrollments();
  } catch (err) {
    showToast(err.message, 'danger');
  }
});

loadEnrollments();
