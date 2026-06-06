"""Analytics URL configuration"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dev/demo-headmaster/', views.dev_create_demo_headmaster, name='dev_demo_headmaster'),
    path('docs/usage/', views.docs_usage, name='docs_usage'),
    path('create-senior/', views.create_senior_account, name='create_senior_account'),
    path('api/attendance/', views.api_chart_attendance, name='api_attendance'),
    path('api/fees/', views.api_chart_fees, name='api_fees'),
]
