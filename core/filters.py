import django_filters as filters

from .models import Student, Course, Enrollment


class StudentFilter(filters.FilterSet):
    department = filters.CharFilter(field_name='department', lookup_expr='iexact')
    gender = filters.CharFilter(field_name='gender', lookup_expr='iexact')
    is_active = filters.BooleanFilter(field_name='is_active')
    enrolled_after = filters.DateFilter(field_name='enrollment_date', lookup_expr='gte')
    enrolled_before = filters.DateFilter(field_name='enrollment_date', lookup_expr='lte')

    class Meta:
        model = Student
        fields = ['department', 'gender', 'is_active']


class CourseFilter(filters.FilterSet):
    department = filters.CharFilter(field_name='department', lookup_expr='iexact')
    is_active = filters.BooleanFilter(field_name='is_active')
    min_credits = filters.NumberFilter(field_name='credits', lookup_expr='gte')
    max_credits = filters.NumberFilter(field_name='credits', lookup_expr='lte')
    has_seats = filters.BooleanFilter(method='filter_has_seats')
    instructor = filters.CharFilter(field_name='instructor', lookup_expr='icontains')

    class Meta:
        model = Course
        fields = ['department', 'is_active', 'instructor']

    def filter_has_seats(self, queryset, name, value):
        ids = [c.id for c in queryset if c.is_full != value]
        return queryset.filter(id__in=ids)


class EnrollmentFilter(filters.FilterSet):
    status = filters.CharFilter(field_name='status', lookup_expr='iexact')
    semester = filters.CharFilter(field_name='semester', lookup_expr='iexact')
    student = filters.NumberFilter(field_name='student_id')
    course = filters.NumberFilter(field_name='course_id')
    grade = filters.CharFilter(field_name='grade', lookup_expr='iexact')

    class Meta:
        model = Enrollment
        fields = ['status', 'semester', 'student', 'course', 'grade']
