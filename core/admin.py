from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Student,
    Course,
    Enrollment,
    ActivityLog,
    UserProfile,
    CourseMaterial,
    Quiz,
    QuizQuestion,
    QuizAttempt,
    AttendanceSession,
    AttendanceRecord,
    Assignment,
    AssignmentSubmission,
    CourseGrade,
)

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    extra = 0
    max_num = 1
    fields = ("role",)


class StudentInline(admin.StackedInline):
    model = Student
    extra = 0
    max_num = 1
    fields = (
        "student_id", "first_name", "last_name", "email", "phone_number",
        "date_of_birth", "gender", "address", "department",
        "enrollment_date", "is_active",
    )
    readonly_fields = ("student_id", "enrollment_date")


# Replace Django's default Users admin with one that makes RBAC visible.
# Students and professors remain normal Django users, while their role and
# student record can be managed directly from the same Users screen.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = (UserProfileInline, StudentInline)
    list_display = (
        "username",
        "full_name",
        "email",
        "role_display",
        "student_id_display",
        "is_active",
        "is_staff",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "profile__role",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "student_profile__student_id",
    )

    @admin.display(description="Name", ordering="first_name")
    def full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name or "—"

    @admin.display(description="Role", ordering="profile__role")
    def role_display(self, obj):
        if obj.is_superuser:
            return "Admin"
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return "No role"

    @admin.display(description="Student ID", ordering="student_profile__student_id")
    def student_id_display(self, obj):
        try:
            return obj.student_profile.student_id
        except Student.DoesNotExist:
            return "—"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'full_name', 'email', 'department', 'is_active', 'gpa')
    list_filter = ('is_active', 'department', 'gender')
    search_fields = ('student_id', 'first_name', 'last_name', 'email')
    readonly_fields = ('student_id', 'created_at', 'updated_at')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'course_code', 'title', 'credits', 'department', 'instructor',
        'professor', 'capacity', 'enrolled_count', 'available_seats', 'is_active'
    )
    list_filter = ('is_active', 'department')
    search_fields = ('course_code', 'title', 'instructor', 'professor__username', 'professor__email')
    autocomplete_fields = ('professor',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'semester', 'status', 'grade', 'enrollment_date')
    list_filter = ('status', 'semester')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id', 'course__course_code')
    autocomplete_fields = ('student', 'course')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action', 'model_name', 'object_repr')
    list_filter = ('action', 'model_name')
    readonly_fields = [f.name for f in ActivityLog._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at', 'updated_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'material_type', 'is_published', 'created_at')
    list_filter = ('material_type', 'is_published')
    search_fields = ('title', 'course__course_code', 'course__title')
    autocomplete_fields = ('course',)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'duration_minutes', 'is_published', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('title', 'course__course_code', 'course__title')
    autocomplete_fields = ('course',)


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_short', 'quiz', 'correct_option', 'marks')
    list_filter = ('correct_option',)
    search_fields = ('question', 'quiz__title')
    autocomplete_fields = ('quiz',)

    @admin.display(description='Question')
    def question_short(self, obj):
        return obj.question[:80] + ('…' if len(obj.question) > 80 else '')


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'total_marks', 'percentage_display', 'submitted_at')
    list_filter = ('submitted_at',)
    search_fields = ('student__student_id', 'student__first_name', 'student__last_name', 'quiz__title')
    autocomplete_fields = ('student', 'quiz')

    @admin.display(description='Percentage')
    def percentage_display(self, obj):
        return f'{obj.percentage}%'


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'date', 'is_open', 'join_code', 'created_at')
    list_filter = ('is_open', 'date')
    search_fields = ('title', 'join_code', 'course__course_code', 'course__title')
    autocomplete_fields = ('course',)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'attended_at')
    search_fields = ('student__student_id', 'student__first_name', 'student__last_name', 'session__title')
    autocomplete_fields = ('student', 'session')
    readonly_fields = ('attended_at',)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'due_date', 'max_marks', 'is_published', 'created_at')
    list_filter = ('is_published', 'course')
    search_fields = ('title', 'course__course_code', 'course__title')
    autocomplete_fields = ('course',)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at', 'marks', 'percentage_display')
    list_filter = ('assignment__course',)
    search_fields = ('assignment__title', 'student__student_id', 'student__first_name', 'student__last_name')
    autocomplete_fields = ('assignment', 'student')
    readonly_fields = ('submitted_at',)

    @admin.display(description='Percentage')
    def percentage_display(self, obj):
        return f'{obj.percentage}%' if obj.percentage is not None else '—'


@admin.register(CourseGrade)
class CourseGradeAdmin(admin.ModelAdmin):
    list_display = ('course', 'student', 'percentage', 'letter_grade', 'updated_at')
    list_filter = ('course', 'letter_grade')
    search_fields = ('course__course_code', 'student__student_id', 'student__first_name', 'student__last_name')
    autocomplete_fields = ('course', 'student')
