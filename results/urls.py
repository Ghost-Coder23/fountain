"""Results URL configuration"""
from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    # Terms
    path('terms/', views.TermListView.as_view(), name='term_list'),
    path('terms/add/', views.TermCreateView.as_view(), name='term_add'),
    path('terms/<uuid:pk>/edit/', views.TermUpdateView.as_view(), name='term_edit'),
    path('terms/<uuid:pk>/delete/', views.TermDeleteView.as_view(), name='term_delete'),


    # Grade Scales
    path('grade-scales/', views.GradeScaleListView.as_view(), name='grade_scale_list'),
    path('grade-scales/add/', views.GradeScaleCreateView.as_view(), name='grade_scale_add'),
    path('grade-scales/<uuid:pk>/edit/', views.GradeScaleUpdateView.as_view(), name='grade_scale_edit'),
    path('grade-scales/<uuid:pk>/delete/', views.GradeScaleDeleteView.as_view(), name='grade_scale_delete'),

    # Assessment Components
    path('assessment-components/', views.AssessmentComponentListView.as_view(), name='assessment_component_list'),
    path('assessment-components/add/', views.AssessmentComponentCreateView.as_view(), name='assessment_component_add'),
    path('assessment-components/<uuid:pk>/edit/', views.AssessmentComponentUpdateView.as_view(), name='assessment_component_edit'),
    path('assessment-components/<uuid:pk>/delete/', views.AssessmentComponentDeleteView.as_view(), name='assessment_component_delete'),

    # Result Entry
    path('entry/', views.ResultEntryView.as_view(), name='result_entry'),

    path('entry/bulk/', views.ResultEntryView.as_view(), name='bulk_entry'),

    # Approvals
    path('pending-approvals/', views.PendingApprovalsView.as_view(), name='pending_approvals'),
    path('approve-all/', views.approve_all_results, name='approve_all'),

    # Student Results
    path('student/<uuid:pk>/', views.StudentResultsView.as_view(), name='student_results'),

    # Promotions (Proceed)
    path('proceed/', views.StudentProceedView.as_view(), name='student_proceed'),
]
