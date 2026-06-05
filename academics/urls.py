"""Academics URL configuration"""
from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    path('years/', views.AcademicYearListView.as_view(), name='academic_year_list'),
    path('years/add/', views.AcademicYearCreateView.as_view(), name='academic_year_add'),
    path('years/<uuid:pk>/edit/', views.AcademicYearUpdateView.as_view(), name='academic_year_edit'),
    path('years/<uuid:pk>/delete/', views.AcademicYearDeleteView.as_view(), name='academic_year_delete'),
    path('class-levels/', views.ClassLevelListView.as_view(), name='class_level_list'),
    path('class-levels/add/', views.ClassLevelCreateView.as_view(), name='class_level_add'),
    path('class-levels/<uuid:pk>/edit/', views.ClassLevelUpdateView.as_view(), name='class_level_edit'),
    path('class-levels/<uuid:pk>/delete/', views.ClassLevelDeleteView.as_view(), name='class_level_delete'),
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', views.SubjectCreateView.as_view(), name='subject_add'),
    path('subjects/<uuid:pk>/edit/', views.SubjectUpdateView.as_view(), name='subject_edit'),
    path('subjects/<uuid:pk>/delete/', views.SubjectDeleteView.as_view(), name='subject_delete'),
    path('sections/', views.ClassSectionListView.as_view(), name='class_section_list'),
    path('sections/add/', views.ClassSectionCreateView.as_view(), name='class_section_add'),
    path('sections/<uuid:pk>/edit/', views.ClassSectionUpdateView.as_view(), name='class_section_edit'),
    path('sections/<uuid:pk>/delete/', views.ClassSectionDeleteView.as_view(), name='class_section_delete'),
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/add/', views.StudentCreateView.as_view(), name='student_add'),
    path('students/<uuid:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/<uuid:pk>/edit/', views.StudentUpdateView.as_view(), name='student_edit'),
    path('students/<uuid:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/add/', views.TeacherCreateView.as_view(), name='teacher_add'),
    path('teachers/<uuid:pk>/edit/', views.TeacherUpdateView.as_view(), name='teacher_edit'),
    path('teachers/<uuid:pk>/delete/', views.TeacherDeleteView.as_view(), name='teacher_delete'),
    path('parents/', views.ParentListView.as_view(), name='parent_list'),
    path('assignments/', views.TeacherAssignmentListView.as_view(), name='teacher_assignment_list'),
    path('assignments/add/', views.TeacherAssignmentCreateView.as_view(), name='teacher_assignment_add'),
    path('assignments/<uuid:pk>/edit/', views.TeacherAssignmentUpdateView.as_view(), name='teacher_assignment_edit'),
    path('assignments/<uuid:pk>/delete/', views.TeacherAssignmentDeleteView.as_view(), name='teacher_assignment_delete'),
    path('students/export/<str:format>/', views.export_students, name='export_students'),
    path('students/autocomplete/', views.student_autocomplete, name='student_autocomplete'),
]
