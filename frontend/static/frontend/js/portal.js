const $ = id => document.getElementById(id);
function escapeJs(value){ return String(value ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' '); }
function asList(value){ if(Array.isArray(value)) return value; if(value && Array.isArray(value.results)) return value.results; return []; }

function portalError(message) {
  const el = $('portalError');
  el.textContent = message;
  el.classList.remove('d-none');
}
function clearPortalError(){ $('portalError').classList.add('d-none'); }

async function init(){
  clearPortalError();
  if(!localStorage.getItem('access') && !localStorage.getItem('access_token') && !localStorage.getItem('jwt_access')){ window.location.assign('/'); return; }
  const me = await apiRequest('/auth/me/');
  $('who').textContent = `${me.name} · ${me.role}${me.student_code ? ' · ' + me.student_code : ''}`;
  if(me.role === 'student') { $('student').classList.remove('d-none'); await loadStudent(); }
  else if(me.role === 'professor') { $('professor').classList.remove('d-none'); await loadProfessor(); }
  else { portalError('This portal is for students and professors. Administrators should use Django Admin.'); }
}

function courseHeader(c){
  return `<div class="d-flex justify-content-between align-items-start mb-3"><div><span class="badge text-bg-light border">${escapeHtml(c.course_code)}</span><h5 class="mt-2 mb-1">${escapeHtml(c.title)}</h5><div class="text-secondary small">${escapeHtml(c.department || '—')} · ${c.credits} credits</div></div><span class="badge text-bg-primary">${c.enrolled_count || 0} enrolled</span></div>`;
}

async function loadStudent(){
  const myCourses = asList(await apiRequest('/my-courses/'));
  $('studentCourses').innerHTML = myCourses.length ? myCourses.map(c => `<div class="border rounded p-3 mb-2">${courseHeader(c)}<div>${escapeHtml(c.description || 'No description')}</div></div>`).join('') : '<div class="empty-state">You are not enrolled in any course yet.</div>';

  const sessionsResponse = await apiRequest('/attendance-sessions/');
  const sessions = asList(sessionsResponse);
  const open = sessions.filter(s => s.is_open);
  $('sessions').innerHTML = '<option value="">Select an active class</option>' + open.map(s => `<option value="${s.id}">${escapeHtml(s.course_title)} — ${escapeHtml(s.title)} (${escapeHtml(formatDate(s.date))})</option>`).join('');
  updateAttendanceButton();
  $('sessions').onchange = updateAttendanceButton;
  $('code').oninput = () => { $('code').value = $('code').value.toUpperCase(); updateAttendanceButton(); };
  $('mark').onclick = markAttendance;

  const records = await apiRequest('/attendance-records/');
  const attendanceRecords = asList(records);
  $('attendanceHistory').innerHTML = attendanceRecords.length ? attendanceRecords.map(r => `<div class="border-bottom py-2"><b>${escapeHtml(r.student_name || 'Present')}</b><div>Session #${r.session} · ${formatDate(r.attended_at)}</div></div>`).join('') : '<span class="text-secondary">No attendance records yet.</span>';

  let learning = '';
  let gradeHtml = '';
  for(const c of myCourses){
    let [materials, assignments, quizzes, perf] = await Promise.all([
      apiRequest('/materials/', {params:{course:c.id}}).catch(()=>[]),
      apiRequest('/assignments/', {params:{course:c.id}}).catch(()=>[]),
      apiRequest('/quizzes/', {params:{course:c.id}}).catch(()=>[]),
      apiRequest(`/courses/${c.id}/performance/`).catch(()=>null),
    ]);
    materials=asList(materials).filter(x=>x.course===c.id);
    assignments=asList(assignments).filter(x=>x.course===c.id);
    quizzes=asList(quizzes).filter(x=>x.course===c.id);
    learning += `<div class="border rounded p-3 mb-4"><h5>${escapeHtml(c.course_code)} — ${escapeHtml(c.title)}</h5>`;
    learning += `<h6 class="mt-3">Videos & Notes</h6>`;
    learning += materials.length ? materials.map(m => materialStudentHtml(m)).join('') : '<div class="text-secondary small">No published materials.</div>';
    learning += `<h6 class="mt-3">Assignments</h6>`;
    learning += assignments.length ? assignments.map(a => assignmentStudentHtml(a)).join('') : '<div class="text-secondary small">No assignments.</div>';
    learning += `<h6 class="mt-3">Tests</h6>`;
    learning += quizzes.length ? quizzes.map(q => quizStudentHtml(q)).join('') : '<div class="text-secondary small">No tests.</div>';
    learning += '</div>';
    if(perf && perf.students && perf.students.length){
      const r=perf.students[0];
      gradeHtml += `<div class="border rounded p-3 mb-2"><b>${escapeHtml(c.course_code)} — ${escapeHtml(c.title)}</b><div class="row mt-2"><div class="col-md-3">Quiz avg: <strong>${r.quiz_average ?? '—'}%</strong></div><div class="col-md-3">Assignments: <strong>${r.assignment_average ?? '—'}%</strong></div><div class="col-md-3">Attendance: <strong>${r.attendance_percentage ?? '—'}%</strong></div><div class="col-md-3">Overall: <strong>${r.final_percentage ?? r.calculated_overall ?? '—'}%</strong> ${r.letter_grade ? '('+escapeHtml(r.letter_grade)+')':''}</div></div>${r.feedback ? `<div class="small text-secondary mt-2">${escapeHtml(r.feedback)}</div>`:''}</div>`;
    }
  }
  $('studentLearning').innerHTML = learning || '<div class="empty-state">No learning content yet.</div>';
  $('studentGrades').innerHTML = gradeHtml || '<div class="text-secondary">No grades have been published yet.</div>';
}

function materialStudentHtml(m){
  if(m.material_type==='video') return `<div class="border rounded p-2 mb-2"><i class="bi bi-play-circle me-2"></i><b>${escapeHtml(m.title)}</b>${m.description ? `<div class="small text-secondary">${escapeHtml(m.description)}</div>`:''}<a class="btn btn-sm btn-outline-primary mt-2" target="_blank" rel="noopener" href="${escapeHtml(m.url)}">Watch video</a></div>`;
  return `<div class="border rounded p-2 mb-2"><i class="bi bi-file-text me-2"></i><b>${escapeHtml(m.title)}</b>${m.content ? `<div class="mt-2" style="white-space:pre-wrap">${escapeHtml(m.content)}</div>`:''}${m.url ? `<a class="btn btn-sm btn-outline-secondary mt-2" target="_blank" rel="noopener" href="${escapeHtml(m.url)}">Open note</a>`:''}</div>`;
}
function assignmentStudentHtml(a){
  return `<div class="border rounded p-3 mb-2"><div class="d-flex justify-content-between"><b>${escapeHtml(a.title)}</b><span class="badge text-bg-light border">${a.max_marks} marks</span></div><div class="small text-secondary">Due: ${a.due_date ? new Date(a.due_date).toLocaleString() : 'No deadline'}</div><p class="mt-2 mb-2">${escapeHtml(a.description||'')}</p><textarea class="form-control assignment-answer" id="ans-${a.id}" rows="2" placeholder="Write your submission"></textarea><button class="btn btn-sm btn-primary mt-2" onclick="submitAssignment(${a.id})">Submit assignment</button></div>`;
}
function quizStudentHtml(q){
  return `<div class="border rounded p-3 mb-3"><div class="d-flex justify-content-between"><b>${escapeHtml(q.title)}</b><span class="small text-secondary">${q.duration_minutes} min</span></div><div class="small text-secondary mb-2">${escapeHtml(q.description||'')}</div>${q.questions.map(x=>`<div class="mb-3"><b>${escapeHtml(x.question)}</b><div class="mt-1">${['A','B','C','D'].map(o=>`<label class="d-block"><input type="radio" name="quiz-${q.id}-${x.id}" value="${o}"> ${o}. ${escapeHtml(x['option_'+o.toLowerCase()])}</label>`).join('')}</div></div>`).join('')}<button class="btn btn-sm btn-primary" onclick="submitQuiz(${q.id})">Submit test</button><span id="quiz-result-${q.id}" class="ms-2"></span></div>`;
}

function updateAttendanceButton(){ $('mark').disabled = !($('sessions').value && $('code').value.trim()); }
async function markAttendance(){
  const id=$('sessions').value, code=$('code').value.trim().toUpperCase();
  if(!id || !code) return;
  $('mark').disabled=true;
  try{ await apiRequest(`/attendance-sessions/${id}/mark_attendance/`,{method:'POST',body:{join_code:code}}); $('attendanceStatus').innerHTML='<div class="alert alert-success py-2">Attendance marked successfully.</div>'; $('code').value=''; await loadStudent(); }
  catch(e){ $('attendanceStatus').innerHTML=`<div class="alert alert-danger py-2">${escapeHtml(e.message)}</div>`; updateAttendanceButton(); }
}
async function submitAssignment(id){
  const answer=document.getElementById(`ans-${id}`).value.trim();
  if(!answer){showToast('Write your assignment answer first.','warning');return;}
  try{await apiRequest(`/assignments/${id}/submit/`,{method:'POST',body:{answer}});showToast('Assignment submitted successfully.');await loadStudent();}
  catch(e){showToast(e.message,'danger');}
}
async function submitQuiz(id){
  const inputs=document.querySelectorAll(`input[name^="quiz-${id}-"]`), answers={};
  inputs.forEach(i=>{if(i.checked){const qid=i.name.split('-')[2];answers[qid]=i.value;}});
  try{const r=await apiRequest(`/quizzes/${id}/submit/`,{method:'POST',body:{answers}});document.getElementById(`quiz-result-${id}`).textContent=`Score: ${r.score}/${r.total_marks} (${r.percentage}%)`;showToast('Test submitted.');}
  catch(e){showToast(e.message,'danger');}
}

async function loadProfessor(){
  $('createCourse').onclick=createCourse;
  await refreshProfessorCourses();
}
async function refreshProfessorCourses(){
  const myCourses=asList(await apiRequest('/my-courses/'));
  $('profCourses').innerHTML=myCourses.length?myCourses.map(profCourseHtml).join(''):'<div class="empty-state">No courses yet. Create your first course above.</div>';
  for(const c of myCourses){ await hydrateProfessorCourse(c.id); }
}
function profCourseHtml(c){
  return `<div class="card mb-4" data-prof-course-id="${c.id}"><div class="card-body"><div class="d-flex justify-content-between align-items-start"><div>${courseHeader(c)}<div class="text-secondary small">Course owner: you</div></div><button class="btn btn-outline-danger btn-sm" onclick="deleteProfessorCourse(${c.id},'${escapeJs(c.course_code)}')">Delete</button></div>
  <div class="row g-3 mt-2">
    <div class="col-lg-6"><div class="border rounded p-3 h-100"><h6><i class="bi bi-play-btn me-1"></i>Publish material</h6><input id="mt-${c.id}" class="form-control mb-2" placeholder="Title"><select id="mtype-${c.id}" class="form-select mb-2"><option value="video">Video</option><option value="note">Note</option></select><input id="murl-${c.id}" class="form-control mb-2" placeholder="Video/note URL"><textarea id="mcontent-${c.id}" class="form-control mb-2" placeholder="Note content"></textarea><button class="btn btn-primary btn-sm" onclick="publishMaterial(${c.id})">Publish</button><div id="materials-${c.id}" class="mt-3"></div></div></div>
    <div class="col-lg-6"><div class="border rounded p-3 h-100"><h6><i class="bi bi-file-earmark-text me-1"></i>Create assignment</h6><input id="at-${c.id}" class="form-control mb-2" placeholder="Assignment title"><textarea id="ad-${c.id}" class="form-control mb-2" placeholder="Instructions"></textarea><div class="row g-2"><div class="col-6"><input id="am-${c.id}" type="number" min="1" class="form-control" value="100" placeholder="Max marks"></div><div class="col-6"><input id="due-${c.id}" type="datetime-local" class="form-control"></div></div><button class="btn btn-primary btn-sm mt-2" onclick="createAssignment(${c.id})">Add assignment</button><div id="assignments-${c.id}" class="mt-3"></div></div></div>
    <div class="col-lg-6"><div class="border rounded p-3 h-100"><h6><i class="bi bi-ui-checks me-1"></i>Create test</h6><input id="qt-${c.id}" class="form-control mb-2" placeholder="Test title"><input id="qd-${c.id}" class="form-control mb-2" placeholder="Description"><div class="row g-2"><div class="col-6"><input id="qdur-${c.id}" type="number" min="1" class="form-control" value="30" placeholder="Minutes"></div></div><button class="btn btn-primary btn-sm mt-2" onclick="createQuiz(${c.id})">Create test</button><div id="quizzes-${c.id}" class="mt-3"></div></div></div>
    <div class="col-lg-6"><div class="border rounded p-3 h-100"><h6><i class="bi bi-calendar-check me-1"></i>Attendance</h6><input id="st-${c.id}" class="form-control mb-2" value="Today's class" placeholder="Session title"><button class="btn btn-primary btn-sm" onclick="openAttendance(${c.id})">Open attendance</button><div id="attendance-${c.id}" class="mt-3"></div></div></div>
  </div>
  <div class="border rounded p-3 mt-3"><h6><i class="bi bi-people me-1"></i>Students, test grades & overall grades</h6><div id="performance-${c.id}"></div></div>
  </div></div>`;
}
async function hydrateProfessorCourse(id){
  let [materials, assignments, quizzes, sessions, performance] = await Promise.all([
    apiRequest('/materials/',{params:{course:id}}).catch(()=>[]), apiRequest('/assignments/',{params:{course:id}}).catch(()=>[]), apiRequest('/quizzes/',{params:{course:id}}).catch(()=>[]), apiRequest('/attendance-sessions/',{params:{course:id}}).catch(()=>[]), apiRequest(`/courses/${id}/performance/`).catch(()=>null)
  ]);
  materials=asList(materials).filter(x=>x.course===id);
  assignments=asList(assignments).filter(x=>x.course===id);
  quizzes=asList(quizzes).filter(x=>x.course===id);
  sessions=asList(sessions).filter(x=>x.course===id);
  $('materials-'+id).innerHTML=materials.map(m=>`<div class="small border-top pt-2 mt-2"><b>${escapeHtml(m.title)}</b> · ${m.material_type}</div>`).join('') || '<span class="small text-secondary">No materials.</span>';
  $('assignments-'+id).innerHTML=assignments.map(a=>`<div class="small border-top pt-2 mt-2"><b>${escapeHtml(a.title)}</b> · ${a.max_marks} marks <button class="btn btn-sm btn-outline-secondary float-end" onclick="viewAssignmentSubmissions(${a.id})">View submissions</button></div>`).join('') || '<span class="small text-secondary">No assignments.</span>';
  $('quizzes-'+id).innerHTML=quizzes.map(q=>`<div class="small border-top pt-2 mt-2"><b>${escapeHtml(q.title)}</b> <button class="btn btn-sm btn-outline-secondary float-end" onclick="viewQuizAttempts(${q.id})">View/grade tests</button><button class="btn btn-sm btn-outline-primary me-1 float-end" onclick="addQuestion(${q.id})">Add question</button></div>`).join('') || '<span class="small text-secondary">No tests.</span>';
  $('attendance-'+id).innerHTML=sessions.map(s=>`<div class="small border-top pt-2 mt-2"><b>${escapeHtml(s.title)}</b> · Code <strong>${escapeHtml(s.join_code)}</strong> · ${s.is_open?'<span class="badge text-bg-success">OPEN</span>':'<span class="badge text-bg-secondary">CLOSED</span>'}${s.is_open?` <button class="btn btn-sm btn-outline-secondary float-end" onclick="closeAttendance(${s.id})">Close</button>`:''}</div>`).join('') || '<span class="small text-secondary">No attendance sessions.</span>';
  renderPerformance(id,performance);
}
function renderPerformance(id,data){
  if(!data || !data.students.length){$('performance-'+id).innerHTML='<span class="text-secondary">No enrolled students yet.</span>';return;}
  $('performance-'+id).innerHTML=`<div class="small text-secondary mb-2">Calculated overall = quizzes 50% + assignments 40% + attendance 10%. You can publish a final grade below.</div><div class="table-responsive"><table class="table table-sm align-middle"><thead><tr><th>Student</th><th>Quiz</th><th>Assignments</th><th>Attendance</th><th>Calculated</th><th>Final %</th><th>Letter</th><th>Action</th></tr></thead><tbody>${data.students.map(r=>`<tr><td><b>${escapeHtml(r.student_name)}</b><div class="text-secondary">${escapeHtml(r.student_id)}</div></td><td>${r.quiz_average??'—'}%</td><td>${r.assignment_average??'—'}%</td><td>${r.attendance_percentage??'—'}%</td><td><b>${r.calculated_overall??'—'}%</b></td><td><input id="fg-${id}-${r.enrollment_id}" class="form-control form-control-sm" type="number" min="0" max="100" value="${r.final_percentage??r.calculated_overall??''}"></td><td><input id="fl-${id}-${r.enrollment_id}" class="form-control form-control-sm" maxlength="2" value="${escapeHtml(r.letter_grade||'')}"></td><td><button class="btn btn-sm btn-primary" onclick="saveFinalGrade(${id},${r.enrollment_id},${r.student_pk})">Save</button></td></tr>`).join('')}</tbody></table></div>`;
  // Store data for student IDs because the API needs numeric Student PK.
  data.students.forEach(r=>{const btn=document.querySelector(`#performance-${id} button[onclick*="${escapeJs(r.student_id)}"]`); if(btn) btn.dataset.studentCode=r.student_id;});
  window._performanceData=window._performanceData||{}; window._performanceData[id]=data.students;
}
async function saveFinalGrade(courseId,enrollmentId,studentPk){
  const pct=parseFloat($(`fg-${courseId}-${enrollmentId}`).value);
  if(isNaN(pct)||pct<0||pct>100){showToast('Final percentage must be 0-100.','warning');return;}
  const letter=$(`fl-${courseId}-${enrollmentId}`).value.trim().toUpperCase();
  try{
    const existing=await apiRequest('/course-grades/').catch(()=>[]);
    const rows=asList(existing).filter(x=>x.course===courseId && x.student===studentPk);
    const payload={course:courseId,student:studentPk,percentage:pct,letter_grade:letter,feedback:''};
    if(rows.length) await apiRequest(`/course-grades/${rows[0].id}/`,{method:'PATCH',body:payload});
    else await apiRequest('/course-grades/',{method:'POST',body:payload});
    showToast('Final grade saved.');
    await hydrateProfessorCourse(courseId);
  }catch(e){showToast(e.message,'danger');}
}

async function createCourse(){
  const code=$('newCode').value.trim().toUpperCase(), title=$('newTitle').value.trim();
  const credits=parseInt($('newCredits').value)||0, capacity=parseInt($('newCapacity').value)||0;
  if(!code||!title||credits<1||capacity<1){showToast('Enter course code, title, credits and capacity.','warning');return;}
  const payload={course_code:code,title,credits,capacity,department:$('newDepartment').value.trim(),description:$('newDescription').value.trim(),is_active:true};
  const btn=$('createCourse'); btn.disabled=true;
  try{
    const created=await apiRequest('/courses/',{method:'POST',body:payload});
    showToast(`${created.course_code} created and assigned to you.`);
    ['newCode','newTitle','newDepartment','newDescription'].forEach(id=>$(id).value='');
    // Immediately render the API response, then load its complete management workspace.
    const existing=Array.from(document.querySelectorAll('[data-prof-course-id]')).map(x=>x.dataset.profCourseId);
    if(!existing.includes(String(created.id))){
      const empty=$('profCourses').querySelector('.empty-state'); if(empty) $('profCourses').innerHTML='';
      $('profCourses').insertAdjacentHTML('beforeend',profCourseHtml(created));
    }
    await hydrateProfessorCourse(created.id);
    await refreshProfessorCourses();
  }catch(e){showToast(e.message,'danger');}
  finally{btn.disabled=false;}
}
async function deleteProfessorCourse(id,code){if(!confirm(`Delete ${code}?`))return;try{await apiRequest(`/courses/${id}/`,{method:'DELETE'});showToast('Course deleted.','warning');await refreshProfessorCourses();}catch(e){showToast(e.message,'danger');}}
async function publishMaterial(course){const title=$(`mt-${course}`).value.trim(),type=$(`mtype-${course}`).value,url=$(`murl-${course}`).value.trim(),content=$(`mcontent-${course}`).value.trim();if(!title||((type==='video')&&!url)||((type==='note')&&!url&&!content)){showToast('Complete the material fields.','warning');return}try{await apiRequest('/materials/',{method:'POST',body:{course,title,material_type:type,url,content,is_published:true}});showToast('Material published.');await hydrateProfessorCourse(course);}catch(e){showToast(e.message,'danger');}}
async function createAssignment(course){const title=$(`at-${course}`).value.trim();if(!title){showToast('Enter an assignment title.','warning');return}const payload={course,title,description:$(`ad-${course}`).value,max_marks:parseInt($(`am-${course}`).value)||100,is_published:true};const due=$(`due-${course}`).value;if(due)payload.due_date=new Date(due).toISOString();try{await apiRequest('/assignments/',{method:'POST',body:payload});showToast('Assignment created.');await hydrateProfessorCourse(course);}catch(e){showToast(e.message,'danger');}}
async function createQuiz(course){const title=$(`qt-${course}`).value.trim();if(!title){showToast('Enter a test title.','warning');return}try{await apiRequest('/quizzes/',{method:'POST',body:{course,title,description:$(`qd-${course}`).value,duration_minutes:parseInt($(`qdur-${course}`).value)||30,is_published:true}});showToast('Test created. Add questions next.');await hydrateProfessorCourse(course);}catch(e){showToast(e.message,'danger');}}
async function addQuestion(quiz){const question=prompt('Question text:');if(!question)return;const a=prompt('Option A:');const b=prompt('Option B:');const c=prompt('Option C:');const d=prompt('Option D:');const correct=(prompt('Correct option (A/B/C/D):')||'A').toUpperCase();const marks=parseInt(prompt('Marks:','1'))||1;if(!a||!b||!c||!d||!['A','B','C','D'].includes(correct))return showToast('Invalid question details.','warning');try{await apiRequest('/questions/',{method:'POST',body:{quiz,question,option_a:a,option_b:b,option_c:c,option_d:d,correct_option:correct,marks}});showToast('Question added.');}catch(e){showToast(e.message,'danger');}}
async function openAttendance(course){const title=$(`st-${course}`).value.trim()||"Today's class";try{const s=await apiRequest('/attendance-sessions/',{method:'POST',body:{course,title,is_open:true}});showToast(`Attendance open. Code: ${s.join_code}`);alert(`Attendance is OPEN\n\nCode: ${s.join_code}\n\nGive this code to students.`);await hydrateProfessorCourse(course);}catch(e){showToast(e.message,'danger');}}
async function closeAttendance(id){try{await apiRequest(`/attendance-sessions/${id}/close/`,{method:'POST'});showToast('Attendance closed.');await refreshProfessorCourses();}catch(e){showToast(e.message,'danger');}}
async function viewAssignmentSubmissions(id){
  try{
    const rows=await apiRequest(`/assignments/${id}/submissions/`);
    if(!rows.length){ alert('No submissions yet.'); return; }
    const text=rows.map(r=>`Submission #${r.id} · ${r.student_name} · ${r.marks??'NOT GRADED'}/${r.assignment_title}`).join('\n');
    const chosen=prompt(`Submissions:\n${text}\n\nEnter submission ID to grade:`);
    if(!chosen)return;
    const row=rows.find(x=>String(x.id)===chosen.trim());
    if(!row){alert('Invalid submission ID.');return;}
    const marks=prompt(`Marks (0-${row.assignment_max_marks}):`,String(row.marks??''));
    if(marks===null)return;
    const feedback=prompt('Feedback (optional):','')||'';
    await apiRequest(`/assignment-submissions/${row.id}/grade/`,{method:'PATCH',body:{marks:parseInt(marks),feedback}});
    showToast('Assignment graded.');
  }catch(e){showToast(e.message,'danger');}
}
async function viewQuizAttempts(id){
  try{
    const all=await apiRequest('/quiz-attempts/');
    const rows=asList(all).filter(r=>r.quiz===id);
    if(!rows.length){alert('No test attempts yet.');return;}
    const summary=rows.map(r=>`Attempt #${r.id} · ${r.student_name || ('Student #'+r.student)} · ${r.score}/${r.total_marks} · ${r.percentage}%`).join('\n');
    const chosen=prompt(`Attempts:\n${summary}\n\nEnter attempt ID to grade:`);
    if(!chosen)return;
    const row=rows.find(r=>String(r.id)===chosen.trim());
    if(!row){alert('Invalid attempt ID.');return;}
    const score=prompt(`New score (0-${row.total_marks}):`,String(row.graded_score??row.score));
    if(score===null)return;
    const feedback=prompt('Feedback (optional):','')||'';
    await apiRequest(`/quiz-attempts/${row.id}/grade/`,{method:'PATCH',body:{graded_score:parseInt(score),feedback}});
    showToast('Test grade saved.');
  }catch(e){showToast(e.message,'danger');}
}

$('logout').onclick=()=>{localStorage.clear();location.href='/'};
init().catch(e=>{portalError(e.message||'Please sign in again.');localStorage.clear();});
