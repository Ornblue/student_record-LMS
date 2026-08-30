from rest_framework_simplejwt.views import TokenRefreshView
from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import *
router=DefaultRouter()
router.register(r'students',StudentViewSet,basename='student')
router.register(r'courses',CourseViewSet,basename='course')
router.register(r'enrollments',EnrollmentViewSet,basename='enrollment')
router.register(r'activity-log',ActivityLogViewSet,basename='activitylog')
router.register(r'materials',CourseMaterialViewSet,basename='material')
router.register(r'quizzes',QuizViewSet,basename='quiz')
router.register(r'questions',QuizQuestionViewSet,basename='question')
router.register(r'quiz-attempts',QuizAttemptViewSet,basename='quiz-attempt')
router.register(r'attendance-sessions',AttendanceSessionViewSet,basename='attendance-session')
router.register(r'attendance-records',AttendanceRecordViewSet,basename='attendance-record')
router.register(r'assignments',AssignmentViewSet,basename='assignment')
router.register(r'assignment-submissions',AssignmentSubmissionViewSet,basename='assignment-submission')
router.register(r'course-grades',CourseGradeViewSet,basename='course-grade')
urlpatterns=[path('auth/register/',RegisterView.as_view()),path('auth/login/',LoginView.as_view()),path('auth/token/refresh/',TokenRefreshView.as_view()),path('auth/me/',MeView.as_view()),path('my-courses/',MyCoursesView.as_view()),path('courses/<int:course_id>/performance/',CoursePerformanceView.as_view()),path('dashboard/',DashboardView.as_view()),path('',include(router.urls))]
