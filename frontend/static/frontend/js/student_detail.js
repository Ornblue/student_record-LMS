async function loadTranscript() {
  const container = document.getElementById('detailContent');
  try {
    const data = await apiRequest(`/students/${STUDENT_PK}/transcript/`);
    const s = data.student;

    const rows = data.enrollments.map(e => `
      <tr>
        <td><strong>${escapeHtml(e.course_code)}</strong></td>
        <td>${escapeHtml(e.course_title)}</td>
        <td>${e.credits}</td>
        <td>${escapeHtml(e.semester)}</td>
        <td>${statusBadge(e.status)}</td>
        <td>${e.grade ? `<span class="badge text-bg-light border">${escapeHtml(e.grade)}</span>` : '—'}</td>
        <td>${e.grade_points !== null && e.grade_points !== undefined ? e.grade_points.toFixed(1) : '—'}</td>
      </tr>`).join('');

    container.innerHTML = `
      <div class="card p-4 mb-3">
        <div class="d-flex justify-content-between flex-wrap gap-3">
          <div class="d-flex align-items-center gap-3">
            <span class="avatar-circle" style="width:56px;height:56px;font-size:1.2rem">${initials(s.full_name)}</span>
            <div>
              <h3 class="fw-bold mb-0">${escapeHtml(s.full_name)}</h3>
              <div class="text-secondary">${escapeHtml(s.student_id)} &middot; ${escapeHtml(s.email)}</div>
              <div class="text-secondary small">${escapeHtml(s.department || 'No department')} ${s.is_active ? '' : '&middot; <span class="text-danger">Archived</span>'}</div>
            </div>
          </div>
          <div class="text-end">
            <div class="text-secondary small">Cumulative GPA</div>
            <div class="display-6 fw-bold text-primary">${data.gpa !== null ? data.gpa.toFixed(2) : '—'}</div>
            <div class="text-secondary small">${data.total_credits_completed} credits completed</div>
          </div>
        </div>
      </div>

      <div class="card p-4">
        <h6 class="fw-bold mb-3">Course History</h6>
        <div class="table-responsive">
          <table class="table table-hover align-middle">
            <thead><tr><th>Code</th><th>Title</th><th>Credits</th><th>Semester</th><th>Status</th><th>Grade</th><th>Grade Pts</th></tr></thead>
            <tbody>${rows || `<tr><td colspan="7" class="text-center text-secondary py-4">No enrollments yet.</td></tr>`}</tbody>
          </table>
        </div>
      </div>`;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">${escapeHtml(err.message)}</div>`;
  }
}

loadTranscript();
