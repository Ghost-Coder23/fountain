from core.utils import get_default_school
"""Notifications views"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification, Announcement, Activity
from schools.models import SchoolUser
from django.utils import timezone
from django.utils.dateparse import parse_datetime


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


@login_required
def activity_feed(request):
    school = get_default_school()
    since = request.GET.get('since')
    limit = int(request.GET.get('limit', 50))
    qs = Activity.objects.filter(school=school)
    if since:
        try:
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(created_at__gt=dt)
        except Exception:
            pass
    items = qs.order_by('created_at')[:limit]
    data = []
    for a in items:
        data.append({
            'id': a.id,
            'actor': a.actor.user.get_full_name() if a.actor and a.actor.user else str(a.actor),
            'verb': a.verb,
            'target_type': a.target_type,
            'target_id': a.target_id,
            'description': a.description,
            'created_at': a.created_at.isoformat(),
        })
    return JsonResponse(data, safe=False)


@login_required
def undo_void_invoice(request, pk):
    """Allow undoing a void within a short grace period (e.g., 10 minutes)."""
    school = get_default_school()
    inv = get_object_or_404(FeeInvoice, pk=pk, school=school)
    # only allow undo if invoice was just voided and has a replacement
    if not getattr(inv, 'is_void', False) or not inv.replacements.exists():
        return JsonResponse({'ok': False, 'error': 'No recent void found'}, status=400)
    # check grace period (10 minutes)
    now = timezone.now()
    if not inv.voided_at or (now - inv.voided_at).total_seconds() > 600:
        return JsonResponse({'ok': False, 'error': 'Grace period expired'}, status=400)
    # perform undo: delete replacement and clear void on original
    try:
        # assume only one replacement created immediately
        rep = inv.replacements.first()
        # delete replacement (and any zero payments created) only if it has no confirmed payments
        if rep.payments.filter(status='confirmed').exists():
            return JsonResponse({'ok': False, 'error': 'Replacement already has payments'}, status=400)
        rep.delete()
        inv.is_void = False
        inv.void_reason = ''
        inv.voided_at = None
        inv.voided_by = None
        inv.status = 'unpaid'
        inv.save()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
