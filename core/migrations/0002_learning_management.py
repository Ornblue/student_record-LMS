from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='quizattempt', name='graded_score',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quizattempt', name='feedback',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('max_marks', models.PositiveIntegerField(default=100)),
                ('is_published', models.BooleanField(default=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.course')),
            ],
            options={'ordering': ['due_date', '-created_at']},
        ),
        migrations.CreateModel(
            name='AssignmentSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('answer', models.TextField(blank=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='assignment_submissions/')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('marks', models.PositiveIntegerField(blank=True, null=True)),
                ('feedback', models.TextField(blank=True)),
                ('assignment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='core.assignment')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_submissions', to='core.student')),
            ],
            options={'ordering': ['-submitted_at'], 'unique_together': {('assignment', 'student')}},
        ),
        migrations.CreateModel(
            name='CourseGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('letter_grade', models.CharField(blank=True, default='', max_length=2)),
                ('feedback', models.TextField(blank=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='final_grades', to='core.course')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_grades', to='core.student')),
            ],
            options={'ordering': ['student__last_name', 'student__first_name'], 'unique_together': {('course', 'student')}},
        ),
    ]
