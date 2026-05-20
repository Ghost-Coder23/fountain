"""EduCore URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from schools import views as school_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Public site
    path('', school_views.HomeView.as_view(), name='home'),
    # path('features/', school_views.FeaturesView.as_view(), name='features'),
    # path('pricing/', school_views.PricingView.as_view(), name='pricing'),
    # path('contact/', school_views.ContactView.as_view(), name='contact'),
    path('privacy-policy/', school_views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms-and-conditions/', school_views.TermsAndConditionsView.as_view(), name='terms_and_conditions'),
    # path('gallery/', school_views.GalleryListView.as_view(), name='gallery'),
    # path('register-school/', school_views.SchoolRegistrationView.as_view(), name='register_school'),
    # path('registration-pending/', TemplateView.as_view(template_name='schools/registration_pending.html'), name='registration_pending'),
    # Auth
    path('accounts/', include('accounts.urls')),
    # School management
    path('school/', include('schools.urls')),
    # Academic modules
    path('academics/', include('academics.urls')),
    path('results/', include('results.urls')),
    path('reports/', include('reports.urls')),
    # New modules
    path('attendance/', include('attendance.urls')),
    path('fees/', include('fees.urls')),
    path('notifications/', include('notifications.urls')),
    path('analytics/', include('analytics.urls')),
    # Platform superadmin
    path('platform/', include('superadmin.urls')),
    # PWA Support
    path('sw.js', school_views.service_worker, name='service_worker'),
    path('manifest.json', school_views.manifest, name='manifest'),
    path('offline/', school_views.offline_view, name='offline'),
    path('inventory/', include('inventory.urls')),
    path('messages/', include('messaging.urls')),
    path('api/', include('api.urls')),
    # Timetable
    path('timetable/', include('timetable.urls')),
    path('offline-sync/', TemplateView.as_view(
    template_name='offline_sync.html'
), name='offline_sync'),
    path('api/csrf-refresh/', school_views.csrf_refresh, name='csrf_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
