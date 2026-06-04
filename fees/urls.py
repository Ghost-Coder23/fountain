"""Fees URL configuration"""
from django.urls import path
from . import views

app_name = 'fees'

urlpatterns = [
    path('', views.fees_home, name='home'),
    path('structures/', views.fee_structure_list, name='structure_list'),
    path('structures/<int:pk>/edit/', views.fee_structure_edit, name='structure_edit'),
    path('structures/<int:pk>/delete/', views.fee_structure_delete, name='structure_delete'),
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.create_invoice, name='create_invoice'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('invoices/<int:invoice_pk>/pay/', views.record_payment, name='record_payment'),
    path('payments/<int:payment_pk>/edit/', views.edit_payment, name='edit_payment'),
    path('invoices/bulk/', views.bulk_invoice, name='bulk_invoice'),
    path('quick-payment/', views.quick_payment, name='quick_payment'),
    path('statement/<uuid:student_id>/', views.student_fee_statement, name='student_statement'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('payment-config/', views.payment_config, name='payment_config'),
]
