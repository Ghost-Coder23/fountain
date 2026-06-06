from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from schools.models import School, SchoolUser


class CreateSeniorAccountTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name='Test School',
            subdomain='test',
            email='school@example.com',
            status='active',
        )
        self.url = reverse('analytics:create_senior_account')

    def test_headmaster_can_create_senior_account(self):
        director = User.objects.create_user(username='director', password='pass12345')
        SchoolUser.objects.create(
            user=director,
            school=self.school,
            role='headmaster',
            is_active=True,
        )
        self.client.force_login(director)

        response = self.client.post(self.url, {'email': 'senior@example.com'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        senior_user = User.objects.get(email='senior@example.com')
        self.assertTrue(
            SchoolUser.objects.filter(
                user=senior_user,
                school=self.school,
                role='senior',
                is_active=True,
            ).exists()
        )

    def test_non_director_cannot_create_senior_account(self):
        teacher = User.objects.create_user(username='teacher', password='pass12345')
        SchoolUser.objects.create(
            user=teacher,
            school=self.school,
            role='teacher',
            is_active=True,
        )
        self.client.force_login(teacher)

        response = self.client.post(self.url, {'email': 'senior@example.com'})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'Permission denied')
