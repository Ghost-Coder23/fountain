"""Attendance URL configuration"""
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_home, name='home'),
    path('mark/<uuid:class_id>/', views.mark_attendance, name='mark'),
    path('report/', views.attendance_report, name='report'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('report/export/<str:format>/', views.export_attendance, name='export_attendance'),
]
