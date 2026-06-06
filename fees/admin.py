from django.contrib import admin
from .models import FeeStructure, FeeInvoice, FeePayment, PaymentConfig

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['name', 'school', 'amount', 'currency', 'academic_year']
    list_filter = ['school', 'currency']

@admin.register(FeeInvoice)
class FeeInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'student', 'billing_period_label', 'amount', 'amount_paid', 'status']
    list_filter = ['school', 'status', 'currency', 'billing_year', 'billing_month', 'term']

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'method', 'status', 'payment_date']
    list_filter = ['method', 'status']

@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ['school', 'accept_cash', 'accept_paynow', 'accept_ecocash']
