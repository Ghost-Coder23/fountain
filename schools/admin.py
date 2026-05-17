"""Schools admin configuration"""
from django.contrib import admin
from .models import School, SchoolUser, GalleryItem


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'status', 'subscription_active', 'created_at']
    list_filter = ['status', 'subscription_active', 'created_at']
    search_fields = ['name', 'subdomain', 'email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'subdomain', 'email', 'phone', 'address')
        }),
        ('Branding', {
            'fields': ('logo', 'theme_color', 'motto')
        }),
        ('Status', {
            'fields': ('status', 'is_demo', 'subscription_active', 'subscription_expires')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SchoolUser)
class SchoolUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'school', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'school']
    search_fields = ['user__username', 'user__email', 'school__name']
    fieldsets = (
        (None, {'fields': ('user', 'school', 'role', 'is_active', 'signature')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ['created_at']


@admin.register(GalleryItem)
class GalleryItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'school', 'media_type', 'is_featured', 'created_at']
    list_filter = ['media_type', 'is_featured', 'school']
    search_fields = ['title', 'description', 'school__name']
    readonly_fields = ['created_at']
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'media_type', 'school', 'is_featured')
        }),
        ('Image', {
            'fields': ('image',),
            'classes': ('collapse',)
        }),
        ('Video', {
            'fields': ('video_url', 'video_file'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
