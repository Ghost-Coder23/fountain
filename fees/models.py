"""
Fees models - Fee structures, invoices, payments
"""
from django.db import models
from django.utils import timezone
from schools.models import School, SchoolUser
from academics.models import Student, AcademicYear, ClassLevel
from results.models import Term
from core.models import TenantManager


class FeeStructure(models.Model):
    """Define what fees are charged for a class level in a term"""
    CURRENCY_CHOICES = [('USD', 'USD'), ('ZWL', 'ZWL')]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_structures')
    name = models.CharField(max_length=100)  # e.g. "Tuition Fee", "Dev Levy"
    class_level = models.ForeignKey(ClassLevel, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='fee_structures')
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    is_mandatory = models.BooleanField(default=True)
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['academic_year', 'name']

    def __str__(self):
        return f"{self.name} - {self.school.name} ({self.currency} {self.amount})"


class FeeInvoice(models.Model):
    """Invoice issued to a student for fees"""
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('waived', 'Waived'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_invoices')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_invoices')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unpaid')
    due_date = models.DateField(null=True, blank=True)
    issued_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(SchoolUser, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-issued_date']

    def __str__(self):
        return f"INV-{self.invoice_number} - {self.student}"

    def update_balance(self):
        """Recalculate amount_paid and balance from payments"""
        total_paid = self.payments.filter(status='confirmed').aggregate(
            t=models.Sum('amount')
        )['t'] or 0
        self.amount_paid = total_paid
        self.balance = self.amount - self.amount_paid
        if self.amount_paid >= self.amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = 'overdue'
        else:
            self.status = 'unpaid'
        self.save(update_fields=['amount_paid', 'balance', 'status'])

    def save(self, *args, **kwargs):
        self.balance = self.amount - self.amount_paid
        if self.amount_paid >= self.amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = 'overdue'
        else:
            self.status = 'unpaid'
        super().save(*args, **kwargs)

    def generate_invoice_number(self):
        import random, string
        return ''.join(random.choices(string.digits, k=8))


class FeePayment(models.Model):
    """Record of a payment made against an invoice"""
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('paynow', 'Paynow'),
        ('ecocash', 'EcoCash'),
        ('onemoney', 'OneMoney'),
        ('bank_transfer', 'Bank Transfer'),
        ('zimswitch', 'Zimswitch'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    ]

    invoice = models.ForeignKey(FeeInvoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='confirmed')
    reference = models.CharField(max_length=100, blank=True)
    paynow_poll_url = models.URLField(blank=True)
    payment_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(SchoolUser, on_delete=models.SET_NULL, null=True, related_name='received_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update invoice balance
        self.invoice.update_balance()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.update_balance()


class ExpenseCategory(models.Model):
    """Categories for school expenses"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name_plural = "Expense Categories"

    def __str__(self):
        return f"{self.name} - {self.school.name}"


class Expense(models.Model):
    """Record of school spending"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, related_name='expenses')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    date = models.DateField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(SchoolUser, on_delete=models.SET_NULL, null=True, related_name='recorded_expenses')
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} ({self.currency} {self.amount})"


class PaymentConfig(models.Model):
    """School payment gateway configuration"""
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name='payment_config')
    # Paynow
    paynow_integration_id = models.CharField(max_length=100, blank=True)
    paynow_integration_key = models.CharField(max_length=200, blank=True)
    paynow_result_url = models.URLField(blank=True)
    paynow_return_url = models.URLField(blank=True)
    # EcoCash
    ecocash_merchant_code = models.CharField(max_length=100, blank=True)
    # General
    accept_cash = models.BooleanField(default=True)
    accept_paynow = models.BooleanField(default=False)
    accept_ecocash = models.BooleanField(default=False)
    accept_bank_transfer = models.BooleanField(default=False)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_branch = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"Payment config for {self.school.name}"
