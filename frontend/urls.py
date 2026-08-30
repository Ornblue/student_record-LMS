from django.urls import path
from . import views
urlpatterns=[
 path('',views.login_page,name='login-page'),path('dashboard/',views.dashboard,name='dashboard-page'),
 path('students/',views.students,name='students-page'),path('students/<int:student_id>/',views.student_detail,name='student-detail-page'),
 path('courses/',views.courses,name='courses-page'),path('enrollments/',views.enrollments,name='enrollments-page'),
 path('activity/',views.activity_log,name='activity-page'),path('portal/',views.portal,name='portal-page')]
