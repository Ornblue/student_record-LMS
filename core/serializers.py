"""
Serializers: validate incoming data and shape outgoing JSON.
"""
from datetime import date

from django.utils import timezone
from rest_framework import serializers

from .models import Student, Course, Enrollment, ActivityLog, CourseMaterial, Quiz, QuizQuestion, QuizAttempt, AttendanceSession, AttendanceRecord, Assignment, AssignmentSubmission, CourseGrade


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------
class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    gpa = serializers.SerializerMethodField()
    active_enrollment_count = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'first_name', 'last_name', 'full_name', 'email',
            'phone_number', 'date_of_birth', 'gender', 'address', 'department',
            'enrollment_date', 'is_active', 'gpa', 'active_enrollment_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'student_id', 'created_at', 'updated_at']

    def get_gpa(self, obj):
        return obj.gpa

    def get_active_enrollment_count(self, obj):
        return obj.enrollments.filter(status__in=['enrolled', 'completed']).count()

    def validate_first_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("First name cannot be blank.")
        return value.strip().title()

    def validate_last_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Last name cannot be blank.")
        return value.strip().title()

    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        if value and (date.today().year - value.year) > 120:
            raise serializers.ValidationError("Please provide a realistic date of birth.")
        return value

    def validate_email(self, value):
        return value.strip().lower()


class StudentListSerializer(serializers.ModelSerializer):
    """Lighter-weight serializer for list endpoints."""
    full_name = serializers.CharField(read_only=True)
    gpa = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'full_name', 'email', 'department',
            'is_active', 'enrollment_date', 'gpa',
        ]

    def get_gpa(self, obj):
        return obj.gpa


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------
class CourseSerializer(serializers.ModelSerializer):
    enrolled_count = serializers.IntegerField(read_only=True)
    available_seats = serializers.IntegerField(read_only=True)
    waitlisted_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'course_code', 'title', 'description', 'credits', 'department',
            'instructor', 'professor', 'capacity', 'is_active', 'enrolled_count',
            'available_seats', 'waitlisted_count', 'is_full',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_course_code(self, value):
        return value.strip().upper()

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("Capacity must be at least 1.")
        return value

    def validate(self, attrs):
        # Prevent shrinking capacity below the number of already-active enrollments.
        instance = getattr(self, 'instance', None)
        new_capacity = attrs.get('capacity')
        if instance and new_capacity is not None:
            active = instance.enrollments.filter(status__in=['enrolled', 'completed']).count()
            if new_capacity < active:
                raise serializers.ValidationError({
                    'capacity': f"Cannot set capacity below {active}; that many students are already enrolled."
                })
        return attrs


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_code = serializers.CharField(source='student.student_id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            'id', 'student', 'student_name', 'student_code', 'course', 'course_title',
            'course_code', 'semester', 'status', 'grade', 'enrollment_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'enrollment_date', 'created_at', 'updated_at']

    def validate(self, attrs):
        student = attrs.get('student') or getattr(self.instance, 'student', None)
        course = attrs.get('course') or getattr(self.instance, 'course', None)
        semester = attrs.get('semester') or getattr(self.instance, 'semester', None)
        status_val = attrs.get('status') or getattr(self.instance, 'status', 'enrolled')
        grade = attrs.get('grade', getattr(self.instance, 'grade', ''))

        if student and not student.is_active:
            raise serializers.ValidationError({'student': 'Cannot enroll an inactive/archived student.'})

        if course and not course.is_active:
            raise serializers.ValidationError({'course': 'Cannot enroll in an inactive course.'})

        # Duplicate enrollment guard (unique_together also enforces this at the DB level).
        qs = Enrollment.objects.filter(student=student, course=course, semester=semester)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if student and course and semester and qs.exists():
            raise serializers.ValidationError(
                f"{student} is already enrolled in {course} for {semester}."
            )

        if status_val == 'completed' and not grade:
            raise serializers.ValidationError({'grade': 'A grade is required to mark an enrollment as completed.'})

        if grade and status_val not in ('completed',):
            raise serializers.ValidationError({'status': 'Status must be "completed" when a grade is assigned.'})

        # Auto-waitlist: if requesting "enrolled" but the course has no seats left, force waitlist.
        if status_val == 'enrolled' and course:
            active_count = course.enrollments.filter(status__in=['enrolled', 'completed'])
            if self.instance:
                active_count = active_count.exclude(pk=self.instance.pk)
            if active_count.count() >= course.capacity:
                attrs['status'] = 'waitlisted'

        return attrs


class BulkEnrollSerializer(serializers.Serializer):
    """Enroll many students into a single course/semester in one request."""
    student_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.filter(is_active=True))
    semester = serializers.CharField(max_length=20)

    def validate_student_ids(self, value):
        found = set(Student.objects.filter(id__in=value, is_active=True).values_list('id', flat=True))
        missing = set(value) - found
        if missing:
            raise serializers.ValidationError(f"No active student found for id(s): {sorted(missing)}")
        return value


class GradeUpdateSerializer(serializers.Serializer):
    grade = serializers.ChoiceField(choices=[g for g, _ in Enrollment.GRADE_CHOICES if g])


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ['id', 'model_name', 'object_repr', 'action', 'details', 'timestamp']

class CourseMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseMaterial
        fields = ['id','course','title','material_type','url','content','file','description','is_published','created_at','updated_at']
        read_only_fields = ['id','created_at','updated_at']

    def validate(self, attrs):
        material_type = attrs.get('material_type', getattr(self.instance, 'material_type', None))
        url = (attrs.get('url', getattr(self.instance, 'url', '')) or '').strip()
        content = (attrs.get('content', getattr(self.instance, 'content', '')) or '').strip()

        if not (attrs.get('title', getattr(self.instance, 'title', '')) or '').strip():
            raise serializers.ValidationError({'title': 'A material title is required.'})

        if material_type == 'video' and not url:
            raise serializers.ValidationError({'url': 'A valid video URL is required for video materials.'})

        if material_type == 'note' and not url and not content and not attrs.get('file', getattr(self.instance, 'file', None)):
            raise serializers.ValidationError({'content': 'Add note content, a note URL, or upload a note file.'})

        return attrs

class QuizQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model=QuizQuestion
        fields=['id','quiz','question','option_a','option_b','option_c','option_d','correct_option','marks','created_at','updated_at']
        read_only_fields=['id','created_at','updated_at']

class QuizSerializer(serializers.ModelSerializer):
    questions=QuizQuestionSerializer(many=True,read_only=True)
    class Meta:
        model=Quiz
        fields=['id','course','title','description','duration_minutes','is_published','questions','created_at','updated_at']
        read_only_fields=['id','created_at','updated_at']

class QuizAttemptSerializer(serializers.ModelSerializer):
    percentage=serializers.FloatField(read_only=True)
    student_name=serializers.CharField(source='student.full_name', read_only=True)
    quiz_title=serializers.CharField(source='quiz.title', read_only=True)
    class Meta:
        model=QuizAttempt
        fields=['id','quiz','quiz_title','student','student_name','score','total_marks','graded_score','feedback','percentage','submitted_at','created_at']
        read_only_fields=['id','student','score','total_marks','percentage','submitted_at','created_at']

class AttendanceSessionSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = AttendanceSession
        fields = ['id','course','course_title','title','date','is_open','join_code','created_at','updated_at']
        read_only_fields = ['id','course_title','join_code','created_at','updated_at']

class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name=serializers.CharField(source='student.full_name',read_only=True)
    class Meta:
        model=AttendanceRecord
        fields=['id','session','student','student_name','attended_at']
        read_only_fields=['id','student','attended_at']

class AssignmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    submission_count = serializers.SerializerMethodField()
    class Meta:
        model = Assignment
        fields = ['id','course','course_title','title','description','due_date','max_marks','is_published','submission_count','created_at','updated_at']
        read_only_fields = ['id','course_title','submission_count','created_at','updated_at']

    def get_submission_count(self, obj):
        return obj.submissions.count()


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    assignment_max_marks = serializers.IntegerField(source='assignment.max_marks', read_only=True)
    percentage = serializers.FloatField(read_only=True)
    class Meta:
        model = AssignmentSubmission
        fields = ['id','assignment','assignment_title','assignment_max_marks','student','student_name','answer','file','submitted_at','marks','percentage','feedback','created_at','updated_at']
        read_only_fields = ['id','student','submitted_at','percentage','created_at','updated_at']


class CourseGradeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    class Meta:
        model = CourseGrade
        fields = ['id','course','course_title','student','student_name','percentage','letter_grade','feedback','created_at','updated_at']
        read_only_fields = ['id','course_title','student_name','created_at','updated_at']

    def validate_percentage(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('Percentage must be between 0 and 100.')
        return value

    def validate(self, attrs):
        course = attrs.get('course', getattr(self.instance, 'course', None))
        student = attrs.get('student', getattr(self.instance, 'student', None))
        if course and student and not Enrollment.objects.filter(student=student, course=course, status__in=['enrolled','completed']).exists():
            raise serializers.ValidationError({'student': 'The student is not enrolled in this course.'})
        return attrs
