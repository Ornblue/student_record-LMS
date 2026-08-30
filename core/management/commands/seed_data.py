"""Seed a complete demo LMS dataset.

Demo credentials:
    Admin is created separately with createsuperuser.
    Professor: professor1 / Professor@123
    Student:  student1 / Student@123
    Student:  student2 / Student@123
"""
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import (Student, Course, Enrollment, ActivityLog, UserProfile,
                         CourseMaterial, Quiz, QuizQuestion, AttendanceSession,
                         AttendanceRecord, Assignment, AssignmentSubmission)

COURSES=[
 ('CS101','Introduction to Programming',4,'Computer Science',35),
 ('CS201','Data Structures & Algorithms',4,'Computer Science',30),
 ('CS301','Database Systems',3,'Computer Science',25),
 ('CS350','Web Application Development',3,'Computer Science',20),
 ('MA110','Calculus I',4,'Mathematics',40),
 ('MA210','Linear Algebra',3,'Mathematics',30),
 ('PH101','General Physics',4,'Physics',30),
 ('BUS150','Principles of Management',3,'Business Administration',35),
]
FIRST=['Aarav','Vivaan','Ishaan','Aditi','Diya','Ananya','Kabir','Meera','Rohan','Sara','Priya','Arjun']
LAST=['Sharma','Patel','Gupta','Iyer','Reddy','Nair','Khan','Singh','Das','Verma','Mehta']

class Command(BaseCommand):
    help='Create a complete demo LMS dataset with users, courses, content, tests, assignments and attendance.'
    def add_arguments(self,parser):
        parser.add_argument('--flush',action='store_true',help='Delete core data and demo users first.')
        parser.add_argument('--students',type=int,default=12)

    @transaction.atomic
    def handle(self,*args,**opts):
        if opts['flush']:
            AssignmentSubmission.objects.all().delete(); AttendanceRecord.objects.all().delete(); AttendanceSession.objects.all().delete()
            QuizQuestion.objects.all().delete(); Quiz.objects.all().delete(); Assignment.objects.all().delete(); CourseMaterial.objects.all().delete()
            Enrollment.objects.all().delete(); Student.objects.all().delete(); Course.objects.all().delete(); ActivityLog.objects.all().delete()
            for username in ['professor1','student1','student2']:
                User.objects.filter(username=username).delete()
            self.stdout.write(self.style.WARNING('Core demo data cleared.'))

        professor,_=User.objects.get_or_create(username='professor1',defaults={'first_name':'Demo','last_name':'Professor','email':'professor1@example.edu'})
        professor.set_password('Professor@123'); professor.save()
        UserProfile.objects.update_or_create(user=professor,defaults={'role':'professor'})

        students=[]
        # guaranteed login students first
        for username,first,last,email in [('student1','Demo','Student','student1@example.edu'),('student2','Demo','Student Two','student2@example.edu')]:
            u,_=User.objects.get_or_create(username=username,defaults={'first_name':first,'last_name':last,'email':email})
            u.set_password('Student@123'); u.save()
            UserProfile.objects.update_or_create(user=u,defaults={'role':'student'})
            s,_=Student.objects.get_or_create(user=u,defaults={'first_name':first,'last_name':last,'email':email,'department':'Computer Science'})
            students.append(s)
        for i in range(max(0,opts['students']-2)):
            first=random.choice(FIRST); last=random.choice(LAST); username=f'demo_student{i+1}'
            if User.objects.filter(username=username).exists(): continue
            email=f'{username}@example.edu'; u=User.objects.create_user(username=username,password='Student@123',first_name=first,last_name=last,email=email)
            UserProfile.objects.create(user=u,role='student')
            students.append(Student.objects.create(user=u,first_name=first,last_name=last,email=email,department=random.choice(['Computer Science','Mathematics','Physics'])))

        courses=[]
        for code,title,credits,dept,capacity in COURSES:
            c,_=Course.objects.get_or_create(course_code=code,defaults={'title':title,'credits':credits,'department':dept,'capacity':capacity,'description':f'{title} demo course','professor':professor,'instructor':professor.get_full_name()})
            if c.professor_id is None: c.professor=professor; c.instructor=professor.get_full_name(); c.save(update_fields=['professor','instructor','updated_at'])
            courses.append(c)

        # Enroll demo students into the first four courses.
        for s in students:
            for c in courses[:4]:
                Enrollment.objects.get_or_create(student=s,course=c,semester='2026-Fall',defaults={'status':'enrolled'})

        # Learning content for first course.
        c=courses[0]
        CourseMaterial.objects.get_or_create(course=c,title='Python Introduction',defaults={'material_type':'video','url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ','description':'Introductory Python video','is_published':True})
        CourseMaterial.objects.get_or_create(course=c,title='Week 1 Notes',defaults={'material_type':'note','content':'Variables, data types, conditions, loops and functions.','is_published':True})
        assignment,_=Assignment.objects.get_or_create(course=c,title='Python Basics Assignment',defaults={'description':'Write a short program using functions and explain your approach.','max_marks':100,'is_published':True})
        quiz,_=Quiz.objects.get_or_create(course=c,title='Python Fundamentals Test',defaults={'description':'Demo multiple-choice test','duration_minutes':20,'is_published':True})
        if not quiz.questions.exists():
            QuizQuestion.objects.create(quiz=quiz,question='Which keyword defines a function in Python?',option_a='func',option_b='def',option_c='function',option_d='define',correct_option='B',marks=2)
            QuizQuestion.objects.create(quiz=quiz,question='Which type is used for whole numbers?',option_a='int',option_b='str',option_c='list',option_d='bool',correct_option='A',marks=2)
        for s in students[:2]:
            AssignmentSubmission.objects.get_or_create(assignment=assignment,student=s,defaults={'answer':'Demo assignment submission.'})
        session,_=AttendanceSession.objects.get_or_create(course=c,title='Demo Live Class',date=timezone.localdate(),defaults={'is_open':True,'join_code':'DEMO12345'})
        for s in students[:1]: AttendanceRecord.objects.get_or_create(session=session,student=s)
        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
        self.stdout.write(self.style.SUCCESS('Professor: professor1 / Professor@123'))
        self.stdout.write(self.style.SUCCESS('Student: student1 / Student@123'))
        self.stdout.write(self.style.SUCCESS('Student: student2 / Student@123'))
