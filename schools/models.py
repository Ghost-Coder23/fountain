"""
Schools models - Multi-tenant school management
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import TenantManager, SyncBaseModel


class School(models.Model):
    """School tenant model"""
    # Note: We keep integer ID for School to avoid breaking subdomain routing
    # but we add updated_at and is_deleted for sync.
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]

    name = models.CharField(max_length=200)
    subdomain = models.CharField(max_length=50, unique=True, db_index=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.CharField(max_length=200, blank=True, help_text='School public website or URL')
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    theme_color = models.CharField(max_length=7, default='#4F46E5', help_text='Hex color code')
    motto = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    # Parent Registration
    parent_registration_enabled = models.BooleanField(default=True)
    registration_token = models.CharField(max_length=100, unique=True, blank=True, null=True)

    # Subscription
    subscription_active = models.BooleanField(default=False)
    subscription_expires = models.DateTimeField(null=True, blank=True)

    # Grading Configuration
    GRADING_SYSTEM_CHOICES = [
        ('system', 'System Grading (Default: 30% CA, 70% Exam)'),
        ('custom_weights', 'Custom CA/Exam Weights'),
        ('multiple_components', 'Multiple Assessment Components'),
        ('subject_specific', 'Subject-Specific Grading'),
    ]
    
    grading_system = models.CharField(
        max_length=30,
        choices=GRADING_SYSTEM_CHOICES,
        default='system',
        help_text='Choose the grading system for your school'
    )
    
    # Custom Weights System
    ca_weight = models.FloatField(
        default=30.0,
        help_text='Weight percentage for Continuous Assessment (CA)',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    exam_weight = models.FloatField(
        default=70.0,
        help_text='Weight percentage for Exam',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.registration_token:
            self.registration_token = str(uuid.uuid4())
        super().save(*args, **kwargs)

    def regenerate_registration_token(self):
        self.registration_token = str(uuid.uuid4())
        self.save()

    def get_absolute_url(self):
        from django.conf import settings
        domain = getattr(settings, 'TENANT_DOMAIN', 'educore.com')
        return f"https://{self.subdomain}.{domain}"

    def get_full_domain(self):
        from django.conf import settings
        domain = getattr(settings, 'TENANT_DOMAIN', 'educore.com')
        return f"{self.subdomain}.{domain}"


class SchoolUser(SyncBaseModel):
    """Link between User and School with role"""
    ROLE_CHOICES = [
        ('headmaster', 'Headmaster'),
        ('admin', 'School Admin'),
        ('secretary', 'Secretary'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('senior', 'Senior'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='school_memberships')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='members', db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    signature = models.ImageField(upload_to='signatures/', blank=True, null=True)

    class Meta:
        unique_together = ['user', 'school']

    def __str__(self):
        return f"{self.user.username} - {self.school.name} ({self.role})"


class GalleryItem(SyncBaseModel):
    """Gallery item (image or video) for global showcase or specific school"""
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='gallery_items', null=True, blank=True, help_text="Leave blank for global showcase")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='image')
    image = models.ImageField(upload_to='gallery/images/', blank=True, null=True, help_text="Upload if media type is Image")
    video_url = models.URLField(blank=True, null=True, help_text="YouTube or Vimeo URL if media type is Video")
    video_file = models.FileField(upload_to='gallery/videos/', blank=True, null=True, help_text="Upload video file (MP4, WebM, etc.")
    is_featured = models.BooleanField(default=False, help_text="Show on the home page")

    objects = models.Manager() # Default to standard manager for global showcase
    tenant_objects = TenantManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        school_name = self.school.name if self.school else "Global Showcase"
        return f"{self.title} ({self.media_type}) - {school_name}"
