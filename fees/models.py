"""
Fees models - Fee structures, invoices, payments
"""
from django.db import models
from django.utils import timezone
from schools.models import School, SchoolUser
from academics.models import Student, AcademicYear, ClassLevel
from results.models import Term
from core.models import TenantManager
from decimal import Decimal
from django.db import transaction
import uuid


class FeeStructure(models.Model):
    """Define what fees are charged for a class level in a term or month"""
    CURRENCY_CHOICES = [('USD', 'USD'), ('ZWL', 'ZWL')]
    BILLING_CYCLE_CHOICES = [
        ('termly', 'Termly'),
        ('monthly', 'Monthly'),
    ]
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'), (5, 'May'), (6, 'June'),
        (7, 'July'), (8, 'August'), (9, 'September'),
        (10, 'October'), (11, 'November'), (12, 'December'),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_structures')
    name = models.CharField(max_length=100)  # e.g. "Tuition Fee", "Dev Levy"
    class_level = models.ForeignKey(ClassLevel, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='fee_structures')
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='termly')
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True)
    month = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True)
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
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name='fee_invoices')
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True, related_name='fee_invoices', db_index=True)
    billing_month = models.IntegerField(choices=FeeStructure.MONTH_CHOICES, null=True, blank=True, db_index=True)
    billing_year = models.IntegerField(null=True, blank=True, db_index=True)
    billing_period_start = models.DateField(null=True, blank=True, db_index=True)
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
    replaced_invoice = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replacements')
    is_void = models.BooleanField(default=False, db_index=True)
    void_reason = models.TextField(blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(SchoolUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='voided_invoices')

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-issued_date']

    def __str__(self):
        return f"INV-{self.invoice_number} - {self.student}"

    @property
    def billing_period_label(self):
        if self.billing_month and self.billing_year:
            from datetime import date
            return date(self.billing_year, self.billing_month, 1).strftime('%B %Y')
        if self.term:
            return self.term.name
        return self.issued_date.strftime('%B %Y') if self.issued_date else 'Unassigned'

    def set_default_billing_period(self):
        from calendar import monthrange
        from datetime import date

        if not self.billing_month:
            self.billing_month = self.issued_date.month if self.issued_date else timezone.now().date().month
        if not self.billing_year:
            self.billing_year = self.issued_date.year if self.issued_date else timezone.now().date().year

        if self.billing_month and self.billing_year:
            self.billing_period_start = date(self.billing_year, self.billing_month, 1)
            last_day = monthrange(self.billing_year, self.billing_month)[1]
            self.billing_period_end = date(self.billing_year, self.billing_month, last_day)

        if self.fee_structure_id:
            if not self.academic_year_id:
                self.academic_year = self.fee_structure.academic_year
            if not self.term_id and self.fee_structure.term_id:
                self.term = self.fee_structure.term

        if not self.academic_year_id and self.school_id and self.billing_period_start:
            self.academic_year = AcademicYear.objects.filter(
                school=self.school,
                start_date__lte=self.billing_period_start,
                end_date__gte=self.billing_period_start,
            ).first()

        if not self.term_id and self.academic_year_id and self.billing_period_start:
            self.term = Term.objects.filter(
                academic_year=self.academic_year,
                start_date__lte=self.billing_period_start,
                end_date__gte=self.billing_period_start,
            ).first()

    def update_balance(self):
        """Recalculate amount_paid and balance from payments (use applied_amount)."""
        total_paid = self.payments.filter(status='confirmed').aggregate(
            t=models.Sum('applied_amount')
        )['t'] or Decimal('0')
        self.amount_paid = total_paid
        self.balance = max(self.amount - self.amount_paid, Decimal('0'))
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
        self.set_default_billing_period()
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
        # If this is a newly created invoice, attempt to auto-apply any available student credit
        if getattr(self, '_auto_apply_credit', True) and getattr(self, '_state', None) and self._state.adding is False:
            # already saved previously
            return
        # Note: when creating new invoices, Django will call save with _state.adding True before saving; we want to apply credit after creation
        # To avoid recursive saves, caller should set _auto_apply_credit attribute if needed. Auto-apply is handled in create paths explicitly.

    def apply_student_credit(self):
        """Apply available student credit to this invoice (creates fee payment entries if needed)."""
        try:
            sc = StudentCredit.objects.filter(student=self.student, school=self.school).first()
            if not sc or sc.balance <= Decimal('0'):
                return
            to_apply = min(sc.balance, self.balance)
            if to_apply <= Decimal('0'):
                return
            # Create a payment using credit
            with transaction.atomic():
                pay = FeePayment.objects.create(
                    invoice=self,
                    amount=to_apply,
                    currency=self.currency,
                    method='other',
                    status='confirmed',
                    reference='Applied student credit',
                    received_by=None,
                )
                # reduce credit balance
                sc.balance = sc.balance - to_apply
                sc.save(update_fields=['balance'])
                # invoice.update_balance() will be triggered by FeePayment.save()
        except Exception:
            return

    def generate_invoice_number(self):
        import random, string
        return ''.join(random.choices(string.digits, k=8))

    def void_and_replace(self, user, reason=''):
        """Mark this invoice as void and create a replacement invoice linked to it.
        Returns the new invoice instance.
        """
        from django.utils import timezone as dj_tz
        # create activity record after operation
        from notifications.models import Activity
        with transaction.atomic():
            # mark original as void
            self.is_void = True
            self.void_reason = reason or ''
            self.voided_at = dj_tz.now()
            self.voided_by = user
            # preserve status but mark as waived for clarity
            self.status = 'waived'
            self.save(update_fields=['is_void', 'void_reason', 'voided_at', 'voided_by', 'status'])

            # create replacement invoice with same details but new number and unpaid state
            new_invoice = FeeInvoice.objects.create(
                school=self.school,
                student=self.student,
                fee_structure=self.fee_structure,
                academic_year=self.academic_year,
                term=self.term,
                billing_month=self.billing_month,
                billing_year=self.billing_year,
                billing_period_start=self.billing_period_start,
                invoice_number=str(uuid.uuid4().int)[:8],
                amount=self.amount,
                currency=self.currency,
                amount_paid=Decimal('0'),
                balance=self.amount,
                status='unpaid',
                due_date=self.due_date,
                issued_date=timezone.now().date(),
                notes=f"Replacement for voided invoice {self.invoice_number}. Reason: {reason}\nOriginal notes: {self.notes}",
                created_by=user,
            )
            new_invoice.replaced_invoice = self
            new_invoice.save()
            # create activity feed entry
            try:
                Activity.objects.create(
                    school=self.school,
                    actor=user,
                    verb='voided invoice',
                    target_type='invoice',
                    target_id=str(self.pk),
                    description=f"Voided invoice {self.invoice_number} by {user.user.get_full_name() if user and getattr(user,'user',None) else user}. Reason: {reason}",
                )
                Activity.objects.create(
                    school=self.school,
                    actor=user,
                    verb='created replacement invoice',
                    target_type='invoice',
                    target_id=str(new_invoice.pk),
                    description=f"Replacement invoice {new_invoice.invoice_number} created for voided {self.invoice_number}",
                )
            except Exception:
                pass
            return new_invoice


class StudentCredit(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='student_credits')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='credits')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        unique_together = ('school', 'student')

    def __str__(self):
        return f"Credit {self.balance} for {self.student}"


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
    # amount that was applied to the invoice (remaining portion is treated as student credit)
    applied_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
        """When saving, compute applied_amount (portion used for invoice) and move any overpayment to StudentCredit."""
        previous_applied = Decimal('0')
        previous_amount = Decimal('0')
        previous_status = None
        if self.pk:
            try:
                old = FeePayment.objects.get(pk=self.pk)
                previous_applied = old.applied_amount or Decimal('0')
                previous_amount = old.amount or Decimal('0')
                previous_status = old.status
            except FeePayment.DoesNotExist:
                previous_applied = Decimal('0')

        # Determine how much should be applied to the invoice
        applied = Decimal('0')
        over = Decimal('0')
        if self.status == 'confirmed':
            # Sum applied amounts of other confirmed payments for this invoice
            others_sum = self.invoice.payments.filter(status='confirmed').exclude(pk=self.pk).aggregate(t=models.Sum('applied_amount'))['t'] or Decimal('0')
            available = max(self.invoice.amount - others_sum, Decimal('0'))
            applied = min(Decimal(self.amount), available)
            over = Decimal(self.amount) - applied
        else:
            applied = Decimal('0')
            over = Decimal('0')

        self.applied_amount = applied

        super().save(*args, **kwargs)

        # Adjust student credit by the change in overpayment
        prev_over = max(previous_amount - previous_applied, Decimal('0'))
        new_over = max(Decimal(self.amount) - self.applied_amount, Decimal('0'))
        delta_over = new_over - prev_over
        if delta_over != Decimal('0'):
            sc, _ = StudentCredit.objects.get_or_create(school=self.invoice.school, student=self.invoice.student, defaults={'balance': Decimal('0')})
            sc.balance = sc.balance + delta_over
            sc.save(update_fields=['balance'])

        # Update invoice balance now
        self.invoice.update_balance()

    def delete(self, *args, **kwargs):
        # When deleting, reverse any overpayment that was converted to student credit
        over = max(self.amount - (self.applied_amount or Decimal('0')), Decimal('0'))
        if over > Decimal('0'):
            sc = StudentCredit.objects.filter(school=self.invoice.school, student=self.invoice.student).first()
            if sc:
                sc.balance = max(sc.balance - over, Decimal('0'))
                sc.save(update_fields=['balance'])
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

    # Automatic invoice generation settings
    auto_generate_invoices = models.BooleanField(default=False, help_text='If enabled, the system will auto-generate monthly invoices on the configured day')
    invoice_generation_day = models.IntegerField(default=1, help_text='Day of month to generate invoices (1-28 recommended)')

    objects = TenantManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"Payment config for {self.school.name}"
