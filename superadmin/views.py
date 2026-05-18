"""
Superadmin views - Platform-level management for EduCore owner
Only accessible to Django superusers
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count, Sum

from schools.models import School, SchoolUser
from academics.models import Student
from fees.models import FeeInvoice


def superadmin_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Superadmin access required.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return _wrapped


@superadmin_required
def platform_dashboard(request):
    total_schools = School.objects.count()
    active_schools = School.objects.filter(status='active').count()
    pending_schools = School.objects.filter(status='pending').count()
    total_students = Student.objects.count()
    total_users = SchoolUser.objects.count()

    # Schools by status
    schools = School.objects.annotate(
        student_count=Count('students'),
        user_count=Count('members')
    ).order_by('-created_at')

    # Recent registrations
    recent = School.objects.filter(status='pending').order_by('-created_at')[:10]

    context = {
        'total_schools': total_schools,
        'active_schools': active_schools,
        'pending_schools': pending_schools,
        'total_students': total_students,
        'total_users': total_users,
        'schools': schools,
        'recent_pending': recent,
    }
    return render(request, 'superadmin/dashboard.html', context)


@superadmin_required
def school_list(request):
    status = request.GET.get('status', '')
    qs = School.objects.annotate(student_count=Count('students')).order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'superadmin/school_list.html', {'schools': qs, 'status_filter': status})


@superadmin_required
def approve_school(request, school_id):
    from django.core.mail import send_mail
    from django.conf import settings
    
    school = get_object_or_404(School, id=school_id)
    school.status = 'active'
    school.subscription_active = True
    school.save()
    
    # Send approval email to school
    try:
        headmaster = SchoolUser.objects.filter(school=school, role='headmaster').first()
        if headmaster:
            send_mail(
                subject=f'Your school "{school.name}" has been approved!',
                message=f'''
Congratulations! Your school "{school.name}" has been approved and is now active!

You can now login at: {request.build_absolute_uri('/accounts/login/')}
Your school subdomain: {school.subdomain}

Best regards,
AcademiaLink Team
''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[school.email, headmaster.user.email],
                fail_silently=False,
            )
    except Exception as e:
        print(f"Error sending approval email: {e}")
    
    messages.success(request, f'{school.name} has been approved and activated.')
    return redirect('superadmin:dashboard')


@superadmin_required
def suspend_school(request, school_id):
    school = get_object_or_404(School, id=school_id)
    school.status = 'suspended'
    school.save()
    messages.warning(request, f'{school.name} has been suspended.')
    return redirect('superadmin:school_list')


@superadmin_required
def school_detail(request, school_id):
    school = get_object_or_404(School, id=school_id)
    members = SchoolUser.objects.filter(school=school).select_related('user').order_by('role')
    students = Student.objects.filter(school=school, is_active=True).count()
    context = {
        'school': school,
        'members': members,
        'student_count': students,
    }
    return render(request, 'superadmin/school_detail.html', context)
