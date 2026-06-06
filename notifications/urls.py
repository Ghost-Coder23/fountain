"""Notifications URL configuration"""
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('unread/', views.unread_count, name='unread_count'),
    path('<uuid:pk>/read/', views.mark_read, name='mark_read'),
    path('announcements/', views.announcements, name='announcements'),
    path('announcements/create/', views.create_announcement, name='create_announcement'),
    path('activity/', views.activity_feed, name='activity_feed'),
    path('invoice/<int:pk>/undo-void/', views.undo_void_invoice, name='undo_void_invoice'),
]
