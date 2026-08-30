"""
Core data models for the Student Record Management API.

Models:
    Student     - a student's personal + academic record (soft-deletable)
    Course      - a course offering with a seat capacity
    Enrollment  - the link between a Student and a Course for a given semester
    ActivityLog - a lightweight audit trail of create/update/delete actions
"""
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base class adding created/updated timestamps."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


GRADE_POINTS = {
    'A+': 4.0, 'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D': 1.0, 'F': 0.0,
}


class Student(TimeStampedModel):
    """A student record. Deletion is soft (is_active flips to False) so
    historical enrollment / grade data is never silently lost."""

    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('', 'Prefer not to say')]

    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be in the format '+999999999' (9-15 digits)."
    )

    student_id = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, default='')
    address = models.TextField(blank=True)
    department = models.CharField(max_length=100, blank=True)
    enrollment_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True, help_text="Soft-delete flag. False = archived/removed.")
    user = models.OneToOneField('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['email']),
        ]

    def save(self, *args, **kwargs):
        if not self.student_id:
            self.student_id = self._generate_student_id()
        super().save(*args, **kwargs)

    def _generate_student_id(self):
        """Generates ids like STU2026-0001, unique per calendar year."""
        year = timezone.now().year
        prefix = f"STU{year}-"
        last = (
            Student.objects.filter(student_id__startswith=prefix)
            .order_by('-student_id')
            .first()
        )
        next_num = 1
        if last:
            try:
                next_num = int(last.student_id.split('-')[-1]) + 1
            except (ValueError, IndexError):
                next_num = Student.objects.filter(student_id__startswith=prefix).count() + 1
        return f"{prefix}{next_num:04d}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def gpa(self):
        """Cumulative GPA computed from completed, graded enrollments,
        weighted by course credit hours. Returns None if no graded courses."""
        completed = (
            self.enrollments.filter(status='completed')
            .exclude(grade='')
            .exclude(grade__isnull=True)
            .select_related('course')
        )
        total_points, total_credits = 0.0, 0
        for enrollment in completed:
            gp = GRADE_POINTS.get(enrollment.grade)
            if gp is not None:
                total_points += gp * enrollment.course.credits
                total_credits += enrollment.course.credits
        if total_credits == 0:
            return None
        return round(total_points / total_credits, 2)

    @property
    def total_credits_completed(self):
        return sum(
            e.course.credits
            for e in self.enrollments.filter(status='completed').select_related('course')
        )

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"


class Course(TimeStampedModel):
    """A course offering. `capacity` drives automatic waitlisting on the
    Enrollment model."""

    course_code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credits = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    department = models.CharField(max_length=100, blank=True)
    instructor = models.CharField(max_length=150, blank=True)
    professor = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='teaching_courses')
    capacity = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['course_code']
        indexes = [models.Index(fields=['course_code'])]

    @property
    def enrolled_count(self):
        return self.enrollments.filter(status__in=['enrolled', 'completed']).count()

    @property
    def waitlisted_count(self):
        return self.enrollments.filter(status='waitlisted').count()

    @property
    def available_seats(self):
        return max(self.capacity - self.enrolled_count, 0)

    @property
    def is_full(self):
        return self.available_seats <= 0

    def __str__(self):
        return f"{self.course_code} - {self.title}"


class Enrollment(TimeStampedModel):
    """Links a Student to a Course for a given semester. A student may not
    be enrolled in the same course twice within the same semester."""

    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('waitlisted', 'Waitlisted'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    ]
    GRADE_CHOICES = [(g, g) for g in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']] + [('', '—')]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    semester = models.CharField(max_length=20, default='2026-Fall')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='enrolled')
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True, default='')
    enrollment_date = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course', 'semester')
        ordering = ['-enrollment_date', '-id']

    def __str__(self):
        return f"{self.student.student_id} -> {self.course.course_code} ({self.semester})"


class ActivityLog(models.Model):
    """A simple audit trail. A row is written whenever a Student, Course or
    Enrollment is created, updated or deleted through the API."""

    ACTION_CHOICES = [('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('restore', 'Restore')]

    model_name = models.CharField(max_length=50)
    object_repr = models.CharField(max_length=255)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.get_action_display()}] {self.model_name}: {self.object_repr}"

class UserProfile(TimeStampedModel):
    ROLE_CHOICES = [('student','Student'),('professor','Professor'),('admin','Admin')]
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

class CourseMaterial(TimeStampedModel):
    TYPE_CHOICES = [('video','Video'),('note','Note')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    material_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    url = models.URLField(blank=True)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='course_notes/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)

class Quiz(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    is_published = models.BooleanField(default=True)

class QuizQuestion(TimeStampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])
    marks = models.PositiveIntegerField(default=1)

class QuizAttempt(TimeStampedModel):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='quiz_attempts')
    score = models.PositiveIntegerField(default=0)
    total_marks = models.PositiveIntegerField(default=0)
    graded_score = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        unique_together = ('quiz','student')
    @property
    def percentage(self):
        effective = self.graded_score if self.graded_score is not None else self.score
        return round(effective / self.total_marks * 100, 2) if self.total_marks else 0

class AttendanceSession(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_sessions')
    title = models.CharField(max_length=200)
    date = models.DateField(default=timezone.now)
    is_open = models.BooleanField(default=True)
    join_code = models.CharField(max_length=12, unique=True)

class AttendanceRecord(TimeStampedModel):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    attended_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('session','student')


class Assignment(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    max_marks = models.PositiveIntegerField(default=100)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f"{self.course.course_code} - {self.title}"


class AssignmentSubmission(TimeStampedModel):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignment_submissions')
    answer = models.TextField(blank=True)
    file = models.FileField(upload_to='assignment_submissions/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks = models.PositiveIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-submitted_at']

    @property
    def percentage(self):
        if self.marks is None or not self.assignment.max_marks:
            return None
        return round(self.marks / self.assignment.max_marks * 100, 2)


class CourseGrade(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='final_grades')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='course_grades')
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    letter_grade = models.CharField(max_length=2, blank=True, default='')
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('course', 'student')
        ordering = ['student__last_name', 'student__first_name']

    def __str__(self):
        return f"{self.student.student_id} - {self.course.course_code}: {self.letter_grade or self.percentage}"
