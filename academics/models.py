"""
Academic models - Classes, Subjects, Students
"""
from django.db import models





from django.contrib.auth.models import User
from schools.models import School, SchoolUser
from core.models import TenantManager, SyncBaseModel


class AcademicYear(SyncBaseModel):
    """Academic year for a school"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='academic_years')
    name = models.CharField(max_length=50)  # e.g., "2024-2025"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} - {self.school.name}"


class ClassLevel(SyncBaseModel):
    """Class/Grade level (e.g., Grade 1, Grade 2)"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='class_levels')
    name = models.CharField(max_length=50)  # e.g., "Grade 1", "Class 5"
    order = models.IntegerField(default=0)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} - {self.school.name}"


class Subject(SyncBaseModel):
    """Subject offered by a school"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.school.name}"


class ClassSection(SyncBaseModel):
    """Specific class section (e.g., Grade 1A, Grade 1B)"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='class_sections')
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name='sections')
    section_name = models.CharField(max_length=20)  # e.g., "A", "B", "Science"
    class_teacher = models.ForeignKey(
        SchoolUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'role': 'teacher'},
        related_name='homeroom_classes'
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='sections')

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ['class_level', 'section_name', 'academic_year']
        ordering = ['class_level__order', 'section_name']

    def __str__(self):
        return f"{self.class_level.name} {self.section_name} - {self.academic_year.name}"


class Student(SyncBaseModel):
    """Student model linked to User and School"""
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students', db_index=True)
    school_user = models.OneToOneField(SchoolUser, on_delete=models.CASCADE, related_name='student_details')

    admission_number = models.CharField(max_length=50, unique=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)

    current_class = models.ForeignKey(
        ClassSection, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='students'
    )

    parent_name = models.CharField(max_length=200, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    parent_email = models.EmailField(blank=True)

    date_joined = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['admission_number']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.admission_number})"


class ParentStudentLink(SyncBaseModel):
    """Explicit link between a parent account and one or more students."""
    RELATIONSHIP_CHOICES = [
        ('parent', 'Parent'),
        ('guardian', 'Guardian'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='parent_student_links', null=True, blank=True)
    parent = models.ForeignKey(
        SchoolUser,
        on_delete=models.CASCADE,
        related_name='child_links',
        limit_choices_to={'role': 'parent'},
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parent_links')
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default='parent')

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ['parent', 'student']
        ordering = ['student__admission_number']

    def __str__(self):
        return f"{self.parent.user.get_full_name()} -> {self.student}"

    def save(self, *args, **kwargs):
        if self.student_id and not self.school_id:
            self.school = self.student.school
        super().save(*args, **kwargs)


class TeacherSubjectAssignment(SyncBaseModel):
    """Assign teachers to subjects in specific classes"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='teacher_subject_assignments', null=True, blank=True)
    teacher = models.ForeignKey(
        SchoolUser, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'teacher'},
        related_name='subject_assignments'
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_assignments')
    class_section = models.ForeignKey(ClassSection, on_delete=models.CASCADE, related_name='teacher_subjects')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='teacher_assignments')

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ['teacher', 'subject', 'class_section', 'academic_year']

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject.name} ({self.class_section})"

    def save(self, *args, **kwargs):
        if self.class_section_id and not self.school_id:
            self.school = self.class_section.school
        super().save(*args, **kwargs)
