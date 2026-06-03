from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('initial-sync/', views.InitialSyncView.as_view(), name='initial_sync'),
    path('sync/', views.BatchSyncView.as_view(), name='batch_sync'),
    path('csrf-refresh/', views.CsrfRefreshView.as_view(), name='csrf_refresh'),
]
