let deptChartInstance = null;
let statusChartInstance = null;

async function loadDashboard() {
  try {
    const data = await apiRequest('/dashboard/');

    document.getElementById('statActiveStudents').textContent = data.active_students;
    document.getElementById('statTotalStudents').textContent =
      `${data.total_students} total (${data.archived_students} archived)`;

    document.getElementById('statCourses').textContent = data.active_courses;
    document.getElementById('statTotalCourses').textContent = `${data.total_courses} total`;

    document.getElementById('statEnrollments').textContent = data.total_enrollments;
    document.getElementById('statWaitlisted').textContent = `${data.waitlisted_count} waitlisted`;

    document.getElementById('statAvgGpa').textContent = data.average_gpa !== null ? data.average_gpa.toFixed(2) : '—';

    renderDeptChart(data.students_by_department);
    renderStatusChart(data.enrollments_by_status);
    renderTopCourses(data.top_courses_by_enrollment);
    loadRecentActivity();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function chartColors(n) {
  const palette = ['#4f46e5', '#059669', '#d97706', '#dc2626', '#0891b2', '#7c3aed', '#db2777', '#65a30d'];
  return Array.from({ length: n }, (_, i) => palette[i % palette.length]);
}

function renderDeptChart(rows) {
  const canvas = document.getElementById('deptChart');
  const empty = document.getElementById('deptEmpty');
  if (!rows || rows.length === 0) {
    canvas.classList.add('d-none');
    empty.classList.remove('d-none');
    return;
  }
  canvas.classList.remove('d-none');
  empty.classList.add('d-none');
  if (deptChartInstance) deptChartInstance.destroy();
  deptChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.department),
      datasets: [{ label: 'Students', data: rows.map(r => r.count), backgroundColor: chartColors(rows.length), borderRadius: 6 }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function renderStatusChart(rows) {
  const canvas = document.getElementById('statusChart');
  const empty = document.getElementById('statusEmpty');
  if (!rows || rows.length === 0) {
    canvas.classList.add('d-none');
    empty.classList.remove('d-none');
    return;
  }
  canvas.classList.remove('d-none');
  empty.classList.add('d-none');
  if (statusChartInstance) statusChartInstance.destroy();
  statusChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => r.status.charAt(0).toUpperCase() + r.status.slice(1)),
      datasets: [{ data: rows.map(r => r.count), backgroundColor: chartColors(rows.length) }],
    },
    options: { responsive: true, plugins: { legend: { position: 'bottom' } } },
  });
}

function renderTopCourses(rows) {
  const container = document.getElementById('topCoursesList');
  if (!rows || rows.length === 0) {
    container.innerHTML = '<div class="empty-state"><i class="bi bi-journal-x"></i><div>No courses yet.</div></div>';
    return;
  }
  container.innerHTML = rows.map(c => {
    const pct = c.capacity ? Math.min(100, Math.round((c.active_enrollments / c.capacity) * 100)) : 0;
    return `
      <div class="mb-3">
        <div class="d-flex justify-content-between small mb-1">
          <span class="fw-semibold">${escapeHtml(c.course_code)} — ${escapeHtml(c.title)}</span>
          <span class="text-secondary">${c.active_enrollments}/${c.capacity}</span>
        </div>
        <div class="progress"><div class="progress-bar bg-primary" style="width:${pct}%"></div></div>
      </div>`;
  }).join('');
}

async function loadRecentActivity() {
  const container = document.getElementById('recentActivity');
  try {
    const data = await apiRequest('/activity-log/', { params: { page_size: 6 } });
    const rows = data.results || [];
    if (rows.length === 0) {
      container.innerHTML = '<div class="empty-state"><i class="bi bi-clock-history"></i><div>No activity yet.</div></div>';
      return;
    }
    container.innerHTML = rows.map(a => `
      <div class="d-flex align-items-start gap-2 mb-2 pb-2 border-bottom">
        <span class="badge text-bg-secondary text-capitalize">${escapeHtml(a.action)}</span>
        <div class="flex-grow-1">
          <div class="small"><strong>${escapeHtml(a.model_name)}</strong>: ${escapeHtml(a.object_repr)}</div>
          <div class="text-secondary" style="font-size:.75rem">${new Date(a.timestamp).toLocaleString()}</div>
        </div>
      </div>`).join('');
  } catch (err) {
    container.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
  }
}

document.getElementById('refreshBtn').addEventListener('click', loadDashboard);
loadDashboard();
