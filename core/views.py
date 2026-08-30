"""
API views. Uses DRF ModelViewSets for the standard CRUD + search/filter/
sort/pagination surface, plus a handful of @action endpoints and one plain
APIView for the analytics dashboard that power the "unique features"
described in the README (GPA/transcripts, waitlisting, CSV export, bulk
enrollment, an audit trail, and soft delete/restore).
"""
import csv

from django.db.models import Count, Q
from django.db import transaction, IntegrityError
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from secrets import token_urlsafe
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, filters as drf_filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Student, Course, Enrollment, ActivityLog, GRADE_POINTS, UserProfile,
    CourseMaterial, Quiz, QuizQuestion, QuizAttempt, AttendanceSession, AttendanceRecord, Assignment, AssignmentSubmission, CourseGrade
)
from .serializers import (
    StudentSerializer, StudentListSerializer, CourseSerializer,
    EnrollmentSerializer, BulkEnrollSerializer, GradeUpdateSerializer,
    ActivityLogSerializer, CourseMaterialSerializer, QuizSerializer,
    QuizQuestionSerializer, QuizAttemptSerializer, AttendanceSessionSerializer,
    AttendanceRecordSerializer, AssignmentSerializer, AssignmentSubmissionSerializer,
    CourseGradeSerializer,
)
from .filters import StudentFilter, CourseFilter, EnrollmentFilter


def log_activity(model_name, obj, action_name, details=''):
    ActivityLog.objects.create(
        model_name=model_name,
        object_repr=str(obj),
        action=action_name,
        details=details,
    )


class StudentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    """
    Full CRUD for students, plus:
      - GET  /api/students/{id}/transcript/  -> GPA + full course history
      - POST /api/students/{id}/restore/     -> undo a soft delete
      - GET  /api/students/export_csv/       -> download all students as CSV
      - DELETE .../?hard=true                -> permanently delete instead of archiving
    """
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser: return qs
        try:
            r=self.request.user.profile.role
            if r=='student': return qs.filter(user=self.request.user)
            if r=='professor': return qs.filter(enrollments__course__professor=self.request.user).distinct()
        except Exception: pass
        return qs.none()
    filterset_class = StudentFilter
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'email', 'student_id', 'department']
    ordering_fields = ['first_name', 'last_name', 'enrollment_date', 'created_at', 'department']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return StudentListSerializer
        return StudentSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        log_activity('Student', instance, 'create')

    def perform_update(self, serializer):
        instance = serializer.save()
        log_activity('Student', instance, 'update')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        hard = str(request.query_params.get('hard', 'false')).lower() == 'true'
        if hard:
            repr_str = str(instance)
            instance.delete()
            log_activity('Student', repr_str, 'delete', details='hard delete')
        else:
            instance.is_active = False
            instance.save(update_fields=['is_active', 'updated_at'])
            log_activity('Student', instance, 'delete', details='soft delete (archived)')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        student = self.get_object()
        student.is_active = True
        student.save(update_fields=['is_active', 'updated_at'])
        log_activity('Student', student, 'restore')
        return Response(StudentSerializer(student).data)

    @action(detail=True, methods=['get'])
    def transcript(self, request, pk=None):
        student = self.get_object()
        enrollments = student.enrollments.select_related('course').order_by('-enrollment_date')
        data = [{
            'course_code': e.course.course_code,
            'course_title': e.course.title,
            'credits': e.course.credits,
            'semester': e.semester,
            'status': e.status,
            'grade': e.grade,
            'grade_points': GRADE_POINTS.get(e.grade),
        } for e in enrollments]
        return Response({
            'student': StudentSerializer(student).data,
            'gpa': student.gpa,
            'total_credits_completed': student.total_credits_completed,
            'enrollments': data,
        })

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="students.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student ID', 'First Name', 'Last Name', 'Email', 'Phone',
                          'Department', 'Enrollment Date', 'Active', 'GPA'])
        for s in self.filter_queryset(self.get_queryset()):
            writer.writerow([s.student_id, s.first_name, s.last_name, s.email,
                              s.phone_number, s.department, s.enrollment_date,
                              s.is_active, s.gpa if s.gpa is not None else ''])
        return response


class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    """
    Full CRUD for courses, plus:
      - GET  /api/courses/{id}/roster/   -> enrolled/waitlisted students for the course
      - GET  /api/courses/export_csv/    -> download all courses as CSV
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser: return qs
        try:
            r=self.request.user.profile.role
            if r=='professor': return qs.filter(professor=self.request.user)
            if r=='student': return qs.filter(enrollments__student__user=self.request.user).distinct()
        except Exception: pass
        return qs.none()
    filterset_class = CourseFilter
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ['course_code', 'title', 'department', 'instructor']
    ordering_fields = ['course_code', 'title', 'credits', 'capacity', 'created_at']
    ordering = ['course_code']

    def perform_create(self, serializer):
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        if self.request.user.is_staff or self.request.user.is_superuser:
            instance = serializer.save()
        elif role == 'professor':
            # A professor owns every course they create. Never trust a client-
            # supplied professor id; it is deliberately overwritten here.
            instance = serializer.save(professor=self.request.user)
        else:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only professors and administrators can create courses.')
        log_activity('Course', instance, 'create')

    def create(self, request, *args, **kwargs):
        # Return the newly-created course immediately. The professor portal uses
        # this response to insert the course into its workspace, so it does not
        # depend on a second query or stale browser state to display a new course.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        if not (self.request.user.is_staff or self.request.user.is_superuser or
                (getattr(getattr(self.request.user, 'profile', None), 'role', None) == 'professor'
                 and serializer.instance.professor_id == self.request.user.id)):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have permission to modify this course.')
        if getattr(getattr(self.request.user, 'profile', None), 'role', None) == 'professor' and not (self.request.user.is_staff or self.request.user.is_superuser):
            serializer.validated_data.pop('professor', None)
        instance = serializer.save()
        log_activity('Course', instance, 'update')

    def perform_destroy(self, instance):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only administrators can delete courses.')
        repr_str = str(instance)
        instance.delete()
        log_activity('Course', repr_str, 'delete')

    @action(detail=True, methods=['get'])
    def roster(self, request, pk=None):
        course = self.get_object()
        enrollments = course.enrollments.select_related('student').order_by('status', 'student__last_name')
        data = [{
            'student_id': e.student.student_id,
            'student_name': e.student.full_name,
            'email': e.student.email,
            'status': e.status,
            'grade': e.grade,
            'semester': e.semester,
        } for e in enrollments]
        return Response({'course': CourseSerializer(course).data, 'roster': data})

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="courses.csv"'
        writer = csv.writer(response)
        writer.writerow(['Code', 'Title', 'Credits', 'Department', 'Instructor',
                          'Capacity', 'Enrolled', 'Available Seats', 'Active'])
        for c in self.filter_queryset(self.get_queryset()):
            writer.writerow([c.course_code, c.title, c.credits, c.department, c.instructor,
                              c.capacity, c.enrolled_count, c.available_seats, c.is_active])
        return response


class EnrollmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    """
    Full CRUD for enrollments, plus:
      - POST /api/enrollments/bulk_enroll/     -> enroll many students in one course
      - POST /api/enrollments/{id}/set_grade/  -> assign a grade and mark completed
      - GET  /api/enrollments/export_csv/      -> download all enrollments as CSV
    """
    queryset = Enrollment.objects.select_related('student', 'course').all()
    serializer_class = EnrollmentSerializer
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser: return qs
        try:
            r=self.request.user.profile.role
            if r=='professor': return qs.filter(course__professor=self.request.user)
            if r=='student': return qs.filter(student__user=self.request.user)
        except Exception: pass
        return qs.none()
    filterset_class = EnrollmentFilter
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id',
                      'course__course_code', 'course__title', 'semester']
    ordering_fields = ['enrollment_date', 'semester', 'status', 'created_at']
    ordering = ['-enrollment_date']

    def perform_create(self, serializer):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only administrators can create enrollments.')
        instance = serializer.save()
        log_activity('Enrollment', instance, 'create')

    def perform_update(self, serializer):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only administrators can edit enrollments. Use the grading action for course grades.')
        instance = serializer.save()
        log_activity('Enrollment', instance, 'update')

    def perform_destroy(self, instance):
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only administrators can delete enrollments.')
        repr_str = str(instance)
        instance.delete()
        log_activity('Enrollment', repr_str, 'delete')

    @action(detail=False, methods=['post'])
    def bulk_enroll(self, request):
        serializer = BulkEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.validated_data['course']
        semester = serializer.validated_data['semester']
        student_ids = serializer.validated_data['student_ids']

        created, skipped = [], []
        for sid in student_ids:
            if Enrollment.objects.filter(student_id=sid, course=course, semester=semester).exists():
                skipped.append(sid)
                continue
            active_count = course.enrollments.filter(status__in=['enrolled', 'completed']).count()
            enroll_status = 'enrolled' if active_count < course.capacity else 'waitlisted'
            enrollment = Enrollment.objects.create(
                student_id=sid, course=course, semester=semester, status=enroll_status
            )
            created.append(enrollment.id)

        log_activity('Enrollment', f"{course.course_code}/{semester}", 'create',
                     details=f"bulk_enroll: {len(created)} created, {len(skipped)} skipped (duplicates)")
        return Response({
            'success': True,
            'created_count': len(created),
            'skipped_count': len(skipped),
            'created_enrollment_ids': created,
            'skipped_student_ids': skipped,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def set_grade(self, request, pk=None):
        enrollment = self.get_object()
        if not (request.user.is_staff or request.user.is_superuser or (getattr(getattr(request.user,'profile',None),'role',None)=='professor' and enrollment.course.professor_id==request.user.id)):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only the assigned professor or an administrator can set grades.')
        serializer = GradeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment.grade = serializer.validated_data['grade']
        enrollment.status = 'completed'
        enrollment.save(update_fields=['grade', 'status', 'updated_at'])
        log_activity('Enrollment', enrollment, 'update', details=f"grade set to {enrollment.grade}")
        return Response(EnrollmentSerializer(enrollment).data)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="enrollments.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student ID', 'Student Name', 'Course Code', 'Course Title',
                          'Semester', 'Status', 'Grade', 'Enrollment Date'])
        for e in self.filter_queryset(self.get_queryset()):
            writer.writerow([e.student.student_id, e.student.full_name, e.course.course_code,
                              e.course.title, e.semester, e.status, e.grade, e.enrollment_date])
        return response


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    """Read-only audit trail of create/update/delete actions."""
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    filter_backends = [drf_filters.OrderingFilter]
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    """Aggregate analytics used by the frontend dashboard's stat cards and
    charts."""

    def get(self, request):
        students = Student.objects.all()
        courses = Course.objects.all()
        enrollments = Enrollment.objects.all()

        by_department = list(
            students.filter(is_active=True).exclude(department='')
            .values('department').annotate(count=Count('id')).order_by('-count')
        )
        by_status = list(
            enrollments.values('status').annotate(count=Count('id')).order_by('-count')
        )

        gpas = [s.gpa for s in students.filter(is_active=True) if s.gpa is not None]
        avg_gpa = round(sum(gpas) / len(gpas), 2) if gpas else None

        top_courses = list(
            courses.annotate(
                active_enrollments=Count('enrollments', filter=Q(enrollments__status__in=['enrolled', 'completed']))
            ).order_by('-active_enrollments')[:5].values('course_code', 'title', 'active_enrollments', 'capacity')
        )

        return Response({
            'total_students': students.count(),
            'active_students': students.filter(is_active=True).count(),
            'archived_students': students.filter(is_active=False).count(),
            'total_courses': courses.count(),
            'active_courses': courses.filter(is_active=True).count(),
            'total_enrollments': enrollments.count(),
            'waitlisted_count': enrollments.filter(status='waitlisted').count(),
            'average_gpa': avg_gpa,
            'students_by_department': by_department,
            'enrollments_by_status': by_status,
            'top_courses_by_enrollment': top_courses,
            'generated_at': timezone.now(),
        })

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        email = str(request.data.get('email', '')).strip().lower()
        password = request.data.get('password', '')
        first_name = str(request.data.get('first_name', '')).strip()
        last_name = str(request.data.get('last_name', '')).strip()
        role = str(request.data.get('role', 'student')).strip().lower()
        department = str(request.data.get('department', '')).strip()

        if role not in ('student', 'professor'):
            return Response(
                {'detail': 'Public registration is available only for students and professors.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not username or not email or not password:
            return Response(
                {'detail': 'Username, email and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(password) < 8:
            return Response(
                {'detail': 'Password must contain at least 8 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(username=username).exists():
            return Response({'detail': 'Username is already in use.'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email).exists():
            return Response({'detail': 'Email is already registered.'}, status=status.HTTP_400_BAD_REQUEST)
        if role == 'student' and Student.objects.filter(email__iexact=email).exists():
            return Response({'detail': 'A student record already exists for this email.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the complete application account atomically. Any database
        # failure rolls back the User, Profile and Student together.
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username, email=email, password=password,
                    first_name=first_name, last_name=last_name,
                )
                UserProfile.objects.create(user=user, role=role)
                student = None
                if role == 'student':
                    student = Student.objects.create(
                        user=user, email=email, first_name=first_name or username,
                        last_name=last_name, department=department,
                    )
        except IntegrityError:
            return Response({'detail': 'Could not create the account because the username, email, or student record already exists. Please use different details.'}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Registration successful.',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': role,
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'student_id': student.student_id if student else None,
            },
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = str(request.data.get('username', '')).strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response(
                {'detail': 'Username and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look the user up explicitly and verify the password. This is more
        # reliable for this local username/password API than depending on a
        # configured authentication backend, and still uses Django's secure
        # password hashing through check_password().
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            return Response({'detail': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({'detail': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'detail': 'This account is inactive.'}, status=status.HTTP_403_FORBIDDEN)

        # Public registration creates a UserProfile. For older accounts that
        # were created before RBAC was added, repair the profile automatically
        # when we can unambiguously identify them as students or admins.
        try:
            role = user.profile.role
        except UserProfile.DoesNotExist:
            if user.is_staff or user.is_superuser:
                role = 'admin'
            elif Student.objects.filter(user=user).exists():
                role = 'student'
                UserProfile.objects.create(user=user, role=role)
            else:
                return Response(
                    {'detail': 'No application role configured for this account. Please register again or ask an administrator to assign a role.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        refresh = RefreshToken.for_user(user)
        student = getattr(user, 'student_profile', None)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': role,
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'student_id': student.student_id if student else None,
            },
        })

class MeView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        u=request.user; s=getattr(u,'student_profile',None)
        try: role=u.profile.role
        except Exception: role='admin' if u.is_staff else None
        return Response({'id':u.id,'username':u.username,'role':role,'student_id':s.id if s else None,
                         'student_code':s.student_id if s else None,'name':s.full_name if s else (u.get_full_name() or u.username),'email':u.email})

class MyCoursesView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        if request.user.is_staff or request.user.is_superuser:
            qs=Course.objects.all()
        else:
            role=getattr(getattr(request.user,'profile',None),'role',None)
            if role=='professor':
                # Professor courses are determined by the actual FK, not by a
                # cached role value or a separate profile table. This guarantees
                # that a course created moments ago appears immediately.
                qs=Course.objects.filter(professor=request.user)
            elif role=='student':
                qs=Course.objects.filter(enrollments__student__user=request.user, enrollments__status__in=['enrolled','completed']).distinct()
            else:
                qs=Course.objects.none()
        return Response(CourseSerializer(qs.order_by('course_code'),many=True).data)


class CoursePerformanceView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, course_id):
        course=get_object_or_404(Course, pk=course_id)
        role=getattr(getattr(request.user,'profile',None),'role',None)
        if role=='professor' and course.professor_id!=request.user.id and not request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied; raise PermissionDenied('You are not assigned to this course.')
        if role=='student' and not Enrollment.objects.filter(course=course,student__user=request.user,status__in=['enrolled','completed']).exists():
            from rest_framework.exceptions import PermissionDenied; raise PermissionDenied('You are not enrolled in this course.')
        enrollments=course.enrollments.select_related('student').filter(status__in=['enrolled','completed'])
        if role == 'student':
            enrollments = enrollments.filter(student__user=request.user)
        rows=[]
        for e in enrollments:
            student=e.student
            quiz_attempts=QuizAttempt.objects.filter(student=student,quiz__course=course,submitted_at__isnull=False)
            quiz_pcts=[a.percentage for a in quiz_attempts]
            assignments=AssignmentSubmission.objects.filter(student=student,assignment__course=course,marks__isnull=False)
            asg_pcts=[a.percentage for a in assignments if a.percentage is not None]
            attendance_total=AttendanceSession.objects.filter(course=course).count()
            attendance_present=AttendanceRecord.objects.filter(session__course=course,student=student).count()
            attendance_pct=(attendance_present/attendance_total*100) if attendance_total else None
            parts=[]; weights=[]
            if quiz_pcts: parts.append(sum(quiz_pcts)/len(quiz_pcts));weights.append(0.5)
            if asg_pcts: parts.append(sum(asg_pcts)/len(asg_pcts));weights.append(0.4)
            if attendance_pct is not None: parts.append(attendance_pct);weights.append(0.1)
            overall=round(sum(v*w for v,w in zip(parts,weights))/sum(weights),2) if weights else None
            final=CourseGrade.objects.filter(course=course,student=student).first()
            rows.append({'student_pk':student.id,'student_id':student.student_id,'student_name':student.full_name,'email':student.email,'enrollment_id':e.id,'quiz_average':round(sum(quiz_pcts)/len(quiz_pcts),2) if quiz_pcts else None,'assignment_average':round(sum(asg_pcts)/len(asg_pcts),2) if asg_pcts else None,'attendance_percentage':round(attendance_pct,2) if attendance_pct is not None else None,'calculated_overall':overall,'final_percentage':float(final.percentage) if final else None,'letter_grade':final.letter_grade if final else e.grade,'feedback':final.feedback if final else ''})
        return Response({'course':CourseSerializer(course).data,'weights':{'quizzes':50,'assignments':40,'attendance':10},'students':rows})

def check_professor(request,course_id):
    course=get_object_or_404(Course,pk=course_id)
    if request.user.is_staff or request.user.is_superuser: return course
    if getattr(getattr(request.user,'profile',None),'role',None)=='professor' and course.professor_id==request.user.id: return course
    from rest_framework.exceptions import PermissionDenied
    raise PermissionDenied('You are not assigned to this course.')

class CourseMaterialViewSet(viewsets.ModelViewSet):
    queryset=CourseMaterial.objects.all(); serializer_class=CourseMaterialSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:return qs
        try:
            return qs.filter(course__professor=self.request.user) if self.request.user.profile.role=='professor' else qs.filter(course__enrollments__student__user=self.request.user,is_published=True).distinct()
        except Exception:return qs.none()
    def _require_professor(self):
        if not (self.request.user.is_staff or self.request.user.is_superuser or getattr(getattr(self.request.user,'profile',None),'role',None)=='professor'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only professors can manage course materials.')
    def perform_create(self,serializer): serializer.save(course=check_professor(self.request,serializer.validated_data['course'].id))
    def perform_update(self,serializer): check_professor(self.request,serializer.instance.course_id); serializer.save()
    def perform_destroy(self,instance): check_professor(self.request,instance.course_id); instance.delete()

class QuizViewSet(viewsets.ModelViewSet):
    queryset=Quiz.objects.prefetch_related('questions'); serializer_class=QuizSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:return qs
        try:return qs.filter(course__professor=self.request.user) if self.request.user.profile.role=='professor' else qs.filter(course__enrollments__student__user=self.request.user,is_published=True).distinct()
        except Exception:return qs.none()
    def perform_create(self,serializer): serializer.save(course=check_professor(self.request,serializer.validated_data['course'].id))
    def perform_update(self,serializer): check_professor(self.request,serializer.instance.course_id); serializer.save()
    def perform_destroy(self,instance): check_professor(self.request,instance.course_id); instance.delete()
    @action(detail=True,methods=['post'])
    def submit(self,request,pk=None):
        quiz=self.get_object()
        if getattr(getattr(request.user,'profile',None),'role',None)!='student': return Response({'detail':'Only students can submit quizzes.'},status=403)
        student=get_object_or_404(Student,user=request.user)
        if not Enrollment.objects.filter(student=student,course=quiz.course,status__in=['enrolled','completed']).exists(): return Response({'detail':'You are not enrolled in this course.'},status=403)
        attempt,_=QuizAttempt.objects.get_or_create(quiz=quiz,student=student)
        if attempt.submitted_at:return Response({'detail':'Quiz already submitted.'},status=400)
        answers=request.data.get('answers',{}); score=total=0
        for q in quiz.questions.all():
            total+=q.marks
            if str(answers.get(str(q.id),'')).upper()==q.correct_option: score+=q.marks
        attempt.score=score;attempt.total_marks=total;attempt.submitted_at=timezone.now();attempt.save()
        return Response(QuizAttemptSerializer(attempt).data)

class QuizQuestionViewSet(viewsets.ModelViewSet):
    queryset=QuizQuestion.objects.select_related('quiz','quiz__course'); serializer_class=QuizQuestionSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:return qs
        try:return qs.filter(quiz__course__professor=self.request.user) if self.request.user.profile.role=='professor' else qs.filter(quiz__course__enrollments__student__user=self.request.user,quiz__is_published=True).distinct()
        except Exception:return qs.none()
    def perform_create(self,serializer):
        quiz=serializer.validated_data['quiz'];check_professor(self.request,quiz.course_id);serializer.save()
    def perform_update(self,serializer):
        check_professor(self.request,serializer.instance.quiz.course_id); serializer.save()
    def perform_destroy(self,instance):
        check_professor(self.request,instance.quiz.course_id); instance.delete()


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.select_related('course').all()
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        if role == 'professor':
            return qs.filter(course__professor=self.request.user)
        if role == 'student':
            return qs.filter(course__enrollments__student__user=self.request.user,
                             course__enrollments__status__in=['enrolled','completed'],
                             is_published=True).distinct()
        return qs.none()

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        check_professor(self.request, course.id)
        serializer.save(course=course)

    def perform_update(self, serializer):
        check_professor(self.request, serializer.instance.course_id)
        serializer.save()

    def perform_destroy(self, instance):
        check_professor(self.request, instance.course_id)
        instance.delete()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        assignment = self.get_object()
        if getattr(getattr(request.user, 'profile', None), 'role', None) != 'student':
            return Response({'detail': 'Only students can submit assignments.'}, status=403)
        student = get_object_or_404(Student, user=request.user)
        if not Enrollment.objects.filter(student=student, course=assignment.course,
                                         status__in=['enrolled','completed']).exists():
            return Response({'detail': 'You are not enrolled in this course.'}, status=403)
        if assignment.due_date and timezone.now() > assignment.due_date:
            return Response({'detail': 'The assignment deadline has passed.'}, status=400)
        answer = str(request.data.get('answer', '')).strip()
        if not answer and not request.FILES.get('file'):
            return Response({'detail': 'Provide an answer or upload a file.'}, status=400)
        defaults = {'answer': answer}
        if request.FILES.get('file'):
            defaults['file'] = request.FILES['file']
        submission, _ = AssignmentSubmission.objects.update_or_create(
            assignment=assignment, student=student, defaults=defaults
        )
        return Response(AssignmentSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        check_professor(request, assignment.course_id)
        return Response(AssignmentSubmissionSerializer(
            assignment.submissions.select_related('student').all(), many=True
        ).data)


class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
    queryset = AssignmentSubmission.objects.select_related('assignment','student','assignment__course')
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        if role == 'professor':
            return qs.filter(assignment__course__professor=self.request.user)
        if role == 'student':
            return qs.filter(student__user=self.request.user)
        return qs.none()

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Use the assignment submit endpoint to submit an assignment.')

    def perform_update(self, serializer):
        check_professor(self.request, serializer.instance.assignment.course_id)
        serializer.save()

    def perform_destroy(self, instance):
        check_professor(self.request, instance.assignment.course_id)
        instance.delete()

    @action(detail=True, methods=['patch'])
    def grade(self, request, pk=None):
        submission = self.get_object()
        check_professor(request, submission.assignment.course_id)
        marks = request.data.get('marks')
        if marks is None:
            return Response({'detail': 'Marks are required.'}, status=400)
        try:
            marks = int(marks)
        except (TypeError, ValueError):
            return Response({'detail': 'Marks must be a number.'}, status=400)
        if marks < 0 or marks > submission.assignment.max_marks:
            return Response({'detail': f'Marks must be between 0 and {submission.assignment.max_marks}.'}, status=400)
        submission.marks = marks
        submission.feedback = str(request.data.get('feedback','')).strip()
        submission.save(update_fields=['marks','feedback','updated_at'])
        return Response(AssignmentSubmissionSerializer(submission).data)


class CourseGradeViewSet(viewsets.ModelViewSet):
    queryset = CourseGrade.objects.select_related('course','student')
    serializer_class = CourseGradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        if role == 'professor':
            return qs.filter(course__professor=self.request.user)
        if role == 'student':
            return qs.filter(student__user=self.request.user)
        return qs.none()

    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        check_professor(self.request, course.id)
        serializer.save()

    def perform_update(self, serializer):
        check_professor(self.request, serializer.instance.course_id)
        serializer.save()

    def perform_destroy(self, instance):
        check_professor(self.request, instance.course_id)
        instance.delete()


class AttendanceSessionViewSet(viewsets.ModelViewSet):
    queryset = AttendanceSession.objects.select_related('course')
    serializer_class = AttendanceSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return qs
        role = getattr(getattr(self.request.user, 'profile', None), 'role', None)
        if role == 'professor':
            return qs.filter(course__professor=self.request.user)
        if role == 'student':
            return qs.filter(
                course__enrollments__student__user=self.request.user,
                course__enrollments__status__in=['enrolled', 'completed'],
            ).distinct()
        return qs.none()

    def create(self, request, *args, **kwargs):
        # Handle creation explicitly instead of passing the same `course`
        # field through serializer.save(). This makes the professor/course
        # ownership check deterministic and avoids the previous 500.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = check_professor(request, serializer.validated_data['course'].pk)

        join_code = token_urlsafe(8).replace('-', '').replace('_', '').upper()[:10]
        while AttendanceSession.objects.filter(join_code=join_code).exists():
            join_code = token_urlsafe(8).replace('-', '').replace('_', '').upper()[:10]

        session = AttendanceSession.objects.create(
            course=course,
            title=serializer.validated_data['title'],
            date=serializer.validated_data.get('date') or timezone.localdate(),
            is_open=serializer.validated_data.get('is_open', True),
            join_code=join_code,
        )
        output = self.get_serializer(session)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        check_professor(self.request, serializer.instance.course_id)
        serializer.save()

    def perform_destroy(self, instance):
        check_professor(self.request, instance.course_id)
        instance.delete()

    @action(detail=True,methods=['post'])
    def mark_attendance(self,request,pk=None):
        session=self.get_object()
        if not session.is_open:return Response({'detail':'Attendance is closed.'},status=400)
        if getattr(getattr(request.user,'profile',None),'role',None)!='student':return Response({'detail':'Only students can mark attendance.'},status=403)
        if request.data.get('join_code','').strip().upper()!=session.join_code:return Response({'detail':'Invalid attendance code.'},status=400)
        student=get_object_or_404(Student,user=request.user)
        if not Enrollment.objects.filter(student=student,course=session.course,status__in=['enrolled','completed']).exists():return Response({'detail':'Not enrolled in this course.'},status=403)
        rec,_=AttendanceRecord.objects.get_or_create(session=session,student=student)
        return Response(AttendanceRecordSerializer(rec).data)
    @action(detail=True,methods=['post'])
    def close(self,request,pk=None):
        s=self.get_object();check_professor(request,s.course_id);s.is_open=False;s.save(update_fields=['is_open','updated_at']);return Response(AttendanceSessionSerializer(s).data)

class AttendanceRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=AttendanceRecord.objects.select_related('session','student');serializer_class=AttendanceRecordSerializer;permission_classes=[IsAuthenticated]
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:return qs
        try:return qs.filter(session__course__professor=self.request.user) if self.request.user.profile.role=='professor' else qs.filter(student__user=self.request.user)
        except Exception:return qs.none()

class QuizAttemptViewSet(viewsets.ModelViewSet):
    queryset=QuizAttempt.objects.select_related('quiz','student','quiz__course');serializer_class=QuizAttemptSerializer;permission_classes=[IsAuthenticated]
    http_method_names=['get','post','head','options','patch']
    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Use the quiz submit endpoint to create a test attempt.')
    def get_queryset(self):
        qs=super().get_queryset()
        if self.request.user.is_staff or self.request.user.is_superuser:return qs
        try:return qs.filter(quiz__course__professor=self.request.user) if self.request.user.profile.role=='professor' else qs.filter(student__user=self.request.user)
        except Exception:return qs.none()
    @action(detail=True, methods=['patch'])
    def grade(self, request, pk=None):
        attempt=self.get_object()
        check_professor(request, attempt.quiz.course_id)
        raw=request.data.get('graded_score')
        if raw is None:
            return Response({'detail':'graded_score is required.'},status=400)
        try: score=int(raw)
        except (TypeError,ValueError): return Response({'detail':'graded_score must be a number.'},status=400)
        if score<0 or score>attempt.total_marks:
            return Response({'detail':f'graded_score must be between 0 and {attempt.total_marks}.'},status=400)
        attempt.graded_score=score
        attempt.feedback=str(request.data.get('feedback','')).strip()
        attempt.save(update_fields=['graded_score','feedback','updated_at'])
        return Response(QuizAttemptSerializer(attempt).data)
