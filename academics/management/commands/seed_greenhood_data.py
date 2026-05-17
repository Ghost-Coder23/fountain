import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from schools.models import School, SchoolUser
from academics.models import AcademicYear, ClassLevel, Subject, ClassSection, Student


class Command(BaseCommand):
    help = 'Seed sample data for Greenhood Academy'

    def handle(self, *args, **options):
        # Get Greenwood Academy
        try:
            school = School.objects.get(name__iexact='Greenwood Academy')
        except School.DoesNotExist:
            self.stdout.write(self.style.ERROR('Greenwood Academy not found!'))
            return

        self.stdout.write(f'Found school: {school.name}')

        # Get or create current academic year
        current_year, created = AcademicYear.objects.get_or_create(
            school=school,
            name='2025-2026',
            defaults={
                'start_date': date(2025, 1, 10),
                'end_date': date(2025, 12, 10),
                'is_current': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created academic year 2025-2026'))

        # Delete existing Grade 6 and 7 class levels
        ClassLevel.objects.filter(school=school, name__icontains='Grade 6').delete()
        ClassLevel.objects.filter(school=school, name__icontains='Grade 7').delete()
        self.stdout.write(self.style.SUCCESS('Deleted Grade 6 and 7'))

        # Create Form 1 to 4 class levels
        form_classes = []
        for i in range(1, 5):
            class_level, created = ClassLevel.objects.get_or_create(
                school=school,
                name=f'Form {i}',
                defaults={'order': i}
            )
            form_classes.append(class_level)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Form {i}'))

        # Create sections for each form (A and B)
        class_sections = []
        for class_level in form_classes:
            for section in ['A', 'B']:
                section_obj, created = ClassSection.objects.get_or_create(
                    school=school,
                    class_level=class_level,
                    section_name=section,
                    academic_year=current_year,
                    defaults={'class_teacher': None}
                )
                class_sections.append(section_obj)
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created {class_level.name} {section}'))

        # Create subjects
        subject_names = [
            'Mathematics',
            'English Language',
            'Shona',
            'Geography',
            'Computer Studies',
            'Combined Science',
            'Commerce'
        ]
        subjects = []
        for name in subject_names:
            subject, created = Subject.objects.get_or_create(
                school=school,
                name=name,
                defaults={'code': name[:3].upper(), 'description': ''}
            )
            subjects.append(subject)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created subject: {name}'))

        # Create 14 teachers (10 + 4 more)
        first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Robert', 'Jennifer', 'William', 'Elizabeth', 'James', 'Patricia', 'Richard', 'Linda']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Anderson', 'Taylor', 'Thomas', 'Moore']

        teachers = []
        for i in range(14):
            first_name = first_names[i]
            last_name = last_names[i]
            username = f'teacher{i+1}'
            email = f'{username}@greenhood.ac.zw'

            # Create user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'is_staff': False
                }
            )
            if created:
                user.set_password('password123')
                user.save()

            # Create school user
            school_user, created = SchoolUser.objects.get_or_create(
                school=school,
                user=user,
                defaults={'role': 'teacher'}
            )
            teachers.append(school_user)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created teacher: {first_name} {last_name}'))

        # Assign class teachers
        for i, section in enumerate(class_sections):
            section.class_teacher = teachers[i % len(teachers)]
            section.save()

        # Create 95 students
        student_first_names = [
            'Tinashe', 'Rutendo', 'Tendai', 'Kudakwashe', 'Nyasha', 'Tafadzwa', 'Rumbidzai', 'Takudzwa', 'Shamiso', 'Anesu',
            'Tawanda', 'Chenai', 'Munashe', 'Vimbai', 'Tadiwa', 'Farai', 'Kundai', 'Tapiwa', 'Rudo', 'Tinashe',
            'Nyasha', 'Tendai', 'Kudakwashe', 'Rutendo', 'Tafadzwa', 'Shamiso', 'Takudzwa', 'Rumbidzai', 'Anesu', 'Tadiwa',
            'Munashe', 'Vimbai', 'Farai', 'Kundai', 'Tapiwa', 'Rudo', 'Tawanda', 'Chenai', 'Tinashe', 'Nyasha',
            'Tendai', 'Kudakwashe', 'Rutendo', 'Tafadzwa', 'Shamiso', 'Takudzwa', 'Rumbidzai', 'Anesu', 'Tadiwa', 'Munashe',
            'Vimbai', 'Farai', 'Kundai', 'Tapiwa', 'Rudo', 'Tawanda', 'Chenai', 'Tinashe', 'Nyasha', 'Tendai', 'Kudakwashe',
            'Rutendo', 'Tafadzwa', 'Shamiso', 'Takudzwa', 'Rumbidzai', 'Anesu', 'Tadiwa', 'Munashe', 'Vimbai', 'Farai', 'Kundai',
            'Tapiwa', 'Rudo', 'Tawanda', 'Chenai', 'Tinashe', 'Nyasha', 'Tendai', 'Kudakwashe', 'Rutendo', 'Tafadzwa', 'Shamiso',
            'Takudzwa', 'Rumbidzai', 'Anesu'
        ]
        student_last_names = [
            'Moyo', 'Ncube', 'Sibanda', 'Dube', 'Chikwanda', 'Zulu', 'Banda', 'Ngwenya', 'Mpofu', 'Sithole',
            'Ndlovu', 'Muleya', 'Hove', 'Chinhoyi', 'Mutasa', 'Manyika', 'Mashiri', 'Mupfumburi', 'Gumbo', 'Zivengwa',
            'Moyo', 'Ncube', 'Sibanda', 'Dube', 'Chikwanda', 'Zulu', 'Banda', 'Ngwenya', 'Mpofu', 'Sithole',
            'Ndlovu', 'Muleya', 'Hove', 'Chinhoyi', 'Mutasa', 'Manyika', 'Mashiri', 'Mupfumburi', 'Gumbo', 'Zivengwa',
            'Moyo', 'Ncube', 'Sibanda', 'Dube', 'Chikwanda', 'Zulu', 'Banda', 'Ngwenya', 'Mpofu', 'Sithole',
            'Ndlovu', 'Muleya', 'Hove', 'Chinhoyi', 'Mutasa', 'Manyika', 'Mashiri', 'Mupfumburi', 'Gumbo', 'Zivengwa',
            'Moyo', 'Ncube', 'Sibanda', 'Dube', 'Chikwanda', 'Zulu', 'Banda', 'Ngwenya', 'Mpofu', 'Sithole',
            'Ndlovu', 'Muleya', 'Hove', 'Chinhoyi', 'Mutasa', 'Manyika', 'Mashiri', 'Mupfumburi', 'Gumbo', 'Zivengwa'
        ]

        for i in range(95):
            first_name = student_first_names[i % len(student_first_names)]
            last_name = student_last_names[i % len(student_last_names)]
            admission_number = f'GH{2025}{i+1:03d}'
            username = f'student{i+1}'
            email = f'{username}@greenhood.ac.zw'
            gender = random.choice(['M', 'F'])
            date_of_birth = date(2010, 1, 1) + timedelta(days=random.randint(0, 1460))
            parent_name = f'Mr/Mrs {last_name}'
            parent_phone = f'+26377{random.randint(1000000, 9999999)}'
            parent_email = f'parent{last_name.lower()}@gmail.com'
            current_class = class_sections[i % len(class_sections)]

            # Create user
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'is_staff': False
                }
            )
            if created:
                user.set_password('password123')
                user.save()

            # Create school user
            school_user, created = SchoolUser.objects.get_or_create(
                school=school,
                user=user,
                defaults={'role': 'student'}
            )

            # Create student
            student, created = Student.objects.get_or_create(
                school=school,
                admission_number=admission_number,
                defaults={
                    'user': user,
                    'school_user': school_user,
                    'date_of_birth': date_of_birth,
                    'gender': gender,
                    'address': 'Harare, Zimbabwe',
                    'phone': '',
                    'current_class': current_class,
                    'parent_name': parent_name,
                    'parent_phone': parent_phone,
                    'parent_email': parent_email,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created student: {first_name} {last_name} ({admission_number})'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded all data!'))
