"""
Single Tenancy Middleware - Sets the default school for all requests
"""
from schools.models import School


class SchoolMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        school = School.objects.first()
        request.school = school
        return self.get_response(request)
