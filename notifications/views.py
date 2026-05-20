from core.utils import get_default_school
"""Notifications views"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification, Announcement
from schools.models import SchoolUser


@login_required
def notification_list(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    if school_user.role in ('student', 'parent'):
        notifications = Notification.objects.filter(
            recipient=request.user, school=school, notification_type__in=['announcement']
        ).order_by('-created_at')[:50]
    else:
        notifications = Notification.objects.filter(
            recipient=request.user, school=school
        ).order_by('-created_at')[:50]
    # Mark all as read
    Notification.objects.filter(recipient=request.user, school=school, is_read=False).update(is_read=True)
    return render(request, 'notifications/notification_list.html', {'notifications': notifications})


@login_required
@require_POST
def mark_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save()
    return JsonResponse({'status': 'ok'})


@login_required
def unread_count(request):
    school = get_default_school()
    count = Notification.objects.filter(recipient=request.user, school=school, is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def announcements(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    active = Announcement.objects.filter(school=school, is_active=True)
    return render(request, 'notifications/announcements.html', {
        'announcements': active,
        'school_user': school_user,
    })


@login_required
def create_announcement(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    if school_user and school_user.role not in ('headmaster', 'admin'):
        from django.contrib import messages
        messages.error(request, "No permission.")
        return redirect('notifications:announcements')

    if request.method == 'POST':
        from .models import Announcement
        from notifications.utils import create_announcement_notifications
        ann = Announcement.objects.create(
            school=school,
            title=request.POST.get('title'),
            content=request.POST.get('content'),
            audience=request.POST.get('audience', 'all'),
            created_by=school_user,
            is_active=True,
        )
        create_announcement_notifications(ann)
        from django.contrib import messages
        messages.success(request, 'Announcement created and sent to all relevant users.')
        return redirect('notifications:announcements')
    return render(request, 'notifications/create_announcement.html', {'school_user': school_user})
