"""
Notifications models - In-app notifications with SMS/email stubs
"""
from django.db import models
from django.contrib.auth.models import User
from schools.models import School
from core.models import TenantManager


class Notification(models.Model):
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('alert', 'Alert'),
        ('fee', 'Fee Reminder'),
        ('attendance', 'Attendance Alert'),
        ('result', 'Result Published'),
        ('announcement', 'Announcement'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"


class SMSLog(models.Model):
    """Track SMS messages sent (stub - real SMS via Africa's Talking later)"""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('stub', 'Stub (not sent)'),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='sms_logs')
    recipient_phone = models.CharField(max_length=20)
    recipient_name = models.CharField(max_length=100, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='stub')
    provider_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SMS to {self.recipient_phone} [{self.status}]"


class Announcement(models.Model):
    """School-wide announcements visible to all users"""
    AUDIENCE_CHOICES = [
        ('all', 'Everyone'),
        ('teachers', 'Teachers Only'),
        ('parents', 'Parents Only'),
        ('students', 'Students Only'),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('schools.SchoolUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.school.name}"


class Activity(models.Model):
    """Lightweight activity stream for live updates in dashboard."""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='activities')
    actor = models.ForeignKey('schools.SchoolUser', on_delete=models.SET_NULL, null=True, blank=True)
    verb = models.CharField(max_length=100)  # e.g. 'voided invoice', 'created invoice'
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.actor} {self.verb} {self.target_type}#{self.target_id}"
