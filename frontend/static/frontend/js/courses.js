const cState = {
  page: 1,
  pageSize: 12,
  ordering: 'course_code',
  search: '',
  department: '',
  hasSeats: '',
};

const courseModal = new bootstrap.Modal(document.getElementById('courseModal'));
const rosterModal = new bootstrap.Modal(document.getElementById('rosterModal'));

async function loadCourses() {
  const grid = document.getElementById('coursesGrid');
  grid.innerHTML = `<div class="col-12"><div class="spinner-overlay"><div class="spinner-border text-primary"></div></div></div>`;
  try {
    const data = await apiRequest('/courses/', {
      params: {
        page: cState.page, page_size: cState.pageSize, ordering: cState.ordering,
        search: cState.search, department: cState.department, has_seats: cState.hasSeats,
      },
    });
    renderGrid(data.results);
    renderPagination(data);
    document.getElementById('resultsSummary').textContent = `Showing ${data.results.length} of ${data.count} course(s)`;
  } catch (err) {
    grid.innerHTML = `<div class="col-12 text-danger text-center py-4">${escapeHtml(err.message)}</div>`;
  }
}

function renderGrid(rows) {
  const grid = document.getElementById('coursesGrid');
  if (!rows || rows.length === 0) {
    grid.innerHTML = `<div class="col-12"><div class="empty-state"><i class="bi bi-journal-x"></i><div>No courses match these filters.</div></div></div>`;
    return;
  }
  grid.innerHTML = rows.map(c => {
    const pct = c.capacity ? Math.min(100, Math.round((c.enrolled_count / c.capacity) * 100)) : 0;
    const barColor = c.is_full ? 'bg-danger' : pct > 75 ? 'bg-warning' : 'bg-success';
    return `
    <div class="col-md-6 col-xl-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <span class="badge text-bg-light border">${escapeHtml(c.course_code)}</span>
            ${c.is_active ? '' : '<span class="badge text-bg-secondary ms-1">Inactive</span>'}
            ${c.is_full ? '<span class="badge text-bg-danger ms-1">Full</span>' : ''}
          </div>
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary" title="Roster" onclick="viewRoster(${c.id})"><i class="bi bi-people"></i></button>
            <button class="btn btn-outline-primary" title="Edit" onclick="editCourse(${c.id})"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-outline-danger" title="Delete" onclick="deleteCourse(${c.id}, '${escapeJs(c.course_code)}')"><i class="bi bi-trash"></i></button>
          </div>
        </div>
        <h6 class="fw-bold mt-2 mb-1">${escapeHtml(c.title)}</h6>
        <div class="text-secondary small mb-2">${escapeHtml(c.department || '—')} &middot; ${c.credits} credits</div>
        <div class="text-secondary small mb-2"><i class="bi bi-person-badge"></i> ${escapeHtml(c.instructor || 'TBA')}</div>
        <div class="mt-auto">
          <div class="d-flex justify-content-between small mb-1">
            <span>Seats</span><span>${c.enrolled_count}/${c.capacity} ${c.waitlisted_count ? `(+${c.waitlisted_count} waitlisted)` : ''}</span>
          </div>
          <div class="progress"><div class="progress-bar ${barColor}" style="width:${pct}%"></div></div>
        </div>
      </div>
    </div>`;
  }).join('');
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
      if (!isNaN(page) && page >= 1 && page <= totalPages) { cState.page = page; loadCourses(); }
    });
  });
}

document.getElementById('searchInput').addEventListener('input', debounce((e) => { cState.search = e.target.value; cState.page = 1; loadCourses(); }));
document.getElementById('deptFilter').addEventListener('input', debounce((e) => { cState.department = e.target.value; cState.page = 1; loadCourses(); }));
document.getElementById('seatsFilter').addEventListener('change', (e) => { cState.hasSeats = e.target.value; cState.page = 1; loadCourses(); });
document.getElementById('clearFiltersBtn').addEventListener('click', () => {
  document.getElementById('searchInput').value = '';
  document.getElementById('deptFilter').value = '';
  document.getElementById('seatsFilter').value = '';
  Object.assign(cState, { page: 1, search: '', department: '', hasSeats: '' });
  loadCourses();
});
document.getElementById('exportBtn').addEventListener('click', () => {
  downloadFile('/courses/export_csv/', { search: cState.search, department: cState.department }, 'courses.csv');
});

document.getElementById('addCourseBtn').addEventListener('click', () => {
  resetCourseForm();
  document.getElementById('courseModalTitle').textContent = 'Add Course';
  courseModal.show();
});

function resetCourseForm() {
  document.getElementById('courseForm').reset();
  document.getElementById('coursePk').value = '';
  document.getElementById('f_is_active').checked = true;
  document.getElementById('formErrors').classList.add('d-none');
}

async function editCourse(id) {
  try {
    const c = await apiRequest(`/courses/${id}/`);
    resetCourseForm();
    document.getElementById('courseModalTitle').textContent = `Edit ${c.course_code}`;
    document.getElementById('coursePk').value = c.id;
    document.getElementById('f_course_code').value = c.course_code;
    document.getElementById('f_title').value = c.title;
    document.getElementById('f_credits').value = c.credits;
    document.getElementById('f_capacity').value = c.capacity;
    document.getElementById('f_is_active').checked = c.is_active;
    document.getElementById('f_department').value = c.department || '';
    document.getElementById('f_instructor').value = c.instructor || '';
    document.getElementById('f_description').value = c.description || '';
    courseModal.show();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

document.getElementById('courseForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pk = document.getElementById('coursePk').value;
  const payload = {
    course_code: document.getElementById('f_course_code').value,
    title: document.getElementById('f_title').value,
    credits: parseInt(document.getElementById('f_credits').value, 10),
    capacity: parseInt(document.getElementById('f_capacity').value, 10),
    is_active: document.getElementById('f_is_active').checked,
    department: document.getElementById('f_department').value,
    instructor: document.getElementById('f_instructor').value,
    description: document.getElementById('f_description').value,
  };
  const errBox = document.getElementById('formErrors');
  errBox.classList.add('d-none');
  const submitBtn = document.getElementById('courseFormSubmit');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving…';
  try {
    if (pk) {
      await apiRequest(`/courses/${pk}/`, { method: 'PATCH', body: payload });
      showToast('Course updated successfully.');
    } else {
      await apiRequest('/courses/', { method: 'POST', body: payload });
      showToast('Course added successfully.');
    }
    courseModal.hide();
    loadCourses();
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove('d-none');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = 'Save Course';
  }
});

async function deleteCourse(id, code) {
  if (!confirm(`Permanently delete course ${code}? This will also remove its enrollment records.`)) return;
  try {
    await apiRequest(`/courses/${id}/`, { method: 'DELETE' });
    showToast(`${code} deleted.`, 'warning');
    loadCourses();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function viewRoster(id) {
  document.getElementById('rosterBody').innerHTML = `<div class="spinner-overlay"><div class="spinner-border text-primary"></div></div>`;
  rosterModal.show();
  try {
    const data = await apiRequest(`/courses/${id}/roster/`);
    document.getElementById('rosterModalTitle').textContent = `${data.course.course_code} — ${data.course.title} Roster`;
    if (data.roster.length === 0) {
      document.getElementById('rosterBody').innerHTML = `<div class="empty-state"><i class="bi bi-people"></i><div>No students enrolled yet.</div></div>`;
      return;
    }
    document.getElementById('rosterBody').innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm table-hover">
          <thead><tr><th>Student</th><th>Email</th><th>Semester</th><th>Status</th><th>Grade</th></tr></thead>
          <tbody>
            ${data.roster.map(r => `
              <tr>
                <td>${escapeHtml(r.student_name)}<div class="text-secondary" style="font-size:.75rem">${escapeHtml(r.student_id)}</div></td>
                <td>${escapeHtml(r.email)}</td>
                <td>${escapeHtml(r.semester)}</td>
                <td>${statusBadge(r.status)}</td>
                <td>${r.grade ? escapeHtml(r.grade) : '—'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch (err) {
    document.getElementById('rosterBody').innerHTML = `<div class="alert alert-danger">${escapeHtml(err.message)}</div>`;
  }
}

loadCourses();
