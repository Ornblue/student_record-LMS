# Student Record Management + LMS Portal

Django + Django REST Framework project with JWT authentication, RBAC and a complete student/professor learning portal.

## Roles
- **Student**: view enrolled courses, videos, notes, take tests, submit assignments, mark attendance, view grades.
- **Professor**: create and manage their own courses, publish videos/notes, create tests/questions, create assignments, open/close attendance, view submissions, grade tests/assignments, and publish final overall grades.
- **Admin**: full Django admin access.

- ## 🎥 Project Demonstration

[▶️ Watch the Project Demonstration](demo/demonstration.mp4)

## Fresh setup (macOS/Linux)
```bash
cd ~/Downloads
unzip -q student_record_management_api_RBAC_JWT_LMS_FINAL.zip
cd student_record_api
python3.14 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
rm -f db.sqlite3
python manage.py migrate
python manage.py seed_data
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

### Demo accounts after `seed_data`
- Professor: `professor1` / `Professor@123`
- Student: `student1` / `Student@123`
- Student: `student2` / `Student@123`

## Professor workflow
1. Sign in as professor.
2. Create a course; it is automatically assigned to the professor.
3. Publish video/notes.
4. Create a test and add MCQ questions.
5. Create assignments.
6. Open attendance and give the generated code to students.
7. Open the student/performance section to see quiz, assignment and attendance performance.
8. Grade assignment submissions and test attempts.
9. Save a final percentage/letter grade for each student.

### Overall grade calculation
The portal displays a calculated overall score using:
- Tests/quizzes: **50%**
- Assignments: **40%**
- Attendance: **10%**

The professor can then publish/override the final percentage and letter grade.

## Student workflow
1. Register as Student or sign in.
2. Open enrolled courses.
3. Watch videos/read notes.
4. Submit assignments.
5. Take tests.
6. Mark attendance directly from the portal using the professor's active-class code.
7. View quiz, assignment, attendance and final overall grades.
