from core.utils import get_default_school
from core.utils_api import api_error, api_ok
"""
Fees views - Fee structures, invoices, payments
"""
import uuid
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
import io
from django.template.loader import render_to_string
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import FeeStructure, FeeInvoice, FeePayment, PaymentConfig, Expense, ExpenseCategory
from .models import StudentCredit
from .forms import FeeStructureForm, FeeInvoiceForm, FeePaymentForm, PaymentConfigForm, ExpenseForm, ExpenseCategoryForm, QuickPaymentForm
from .periods import filter_invoices_for_period, get_selected_billing_period, period_query_string
from academics.models import Student, ClassLevel, AcademicYear
from schools.models import SchoolUser
from django.contrib import messages


def require_role(roles):
    from functools import wraps
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            school = get_default_school()
            su = SchoolUser.objects.filter(user=request.user, school=school).first()
            if not su or su.role not in roles:
                messages.error(request, "You do not have permission to access this page.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


@login_required
def fees_home(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    billing_period = get_selected_billing_period(request, school)
    invoices_for_period = filter_invoices_for_period(FeeInvoice.objects.filter(school=school), billing_period)

    # Income Stats
    total_invoiced = invoices_for_period.aggregate(t=Sum('amount'))['t'] or 0
    total_paid = FeePayment.objects.filter(
        invoice__in=invoices_for_period, status='confirmed'
    ).aggregate(t=Sum('amount'))['t'] or 0
    total_outstanding = total_invoiced - total_paid

    # Expense Stats
    expenses_for_period = Expense.objects.filter(school=school)
    if billing_period.get('start') and billing_period.get('end'):
        expenses_for_period = expenses_for_period.filter(date__gte=billing_period['start'], date__lte=billing_period['end'])
    total_expenses = expenses_for_period.aggregate(t=Sum('amount'))['t'] or 0
    net_position = total_paid - total_expenses

    recent_invoices = invoices_for_period.select_related(
        'student__user', 'fee_structure'
    ).order_by('-created_at')[:5]

    recent_payments = FeePayment.objects.filter(
        invoice__in=invoices_for_period, status='confirmed'
    ).select_related('invoice__student__user').order_by('-payment_date')[:5]

    recent_expenses = expenses_for_period.select_related('category').order_by('-date')[:5]

    overdue = invoices_for_period.filter(
        status__in=['unpaid', 'partial', 'overdue'],
        due_date__lt=date.today()
    ).count()

    # Total available student credit across the school
    total_credit = StudentCredit.objects.filter(school=school).aggregate(t=Sum('balance'))['t'] or 0

    context = {
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
        'total_expenses': total_expenses,
        'net_position': net_position,
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
        'recent_expenses': recent_expenses,
        'overdue_count': overdue,
        'school_user': school_user,
        'is_secretary': school_user and school_user.role == 'secretary',
        'billing_period': billing_period,
        'period_query': period_query_string(billing_period),
        'total_credit': total_credit,
    }
    return render(request, 'fees/fees_home.html', context)


@login_required
@require_role(['admin', 'headmaster', 'secretary'])
def expense_list(request):
    school = get_default_school()
    expenses = Expense.objects.filter(school=school).select_related('category')
    categories = ExpenseCategory.objects.filter(school=school)
    
    cat_form = ExpenseCategoryForm()
    exp_form = ExpenseForm(school=school)
    
    if request.method == 'POST':
        if 'add_category' in request.POST:
            cat_form = ExpenseCategoryForm(data=request.POST)
            if cat_form.is_valid():
                cat = cat_form.save(commit=False)
                cat.school = school
                cat.save()
                messages.success(request, 'Expense category added.')
                return redirect('fees:expense_list')
        elif 'add_expense' in request.POST:
            exp_form = ExpenseForm(school=school, data=request.POST)
            if exp_form.is_valid():
                exp = exp_form.save(commit=False)
                exp.school = school
                exp.recorded_by = SchoolUser.objects.filter(user=request.user, school=school).first()
                exp.save()
                messages.success(request, 'Expense recorded.')
                return redirect('fees:expense_list')
                
    context = {
        'expenses': expenses,
        'categories': categories,
        'cat_form': cat_form,
        'exp_form': exp_form,
    }
    return render(request, 'fees/expense_list.html', context)


@login_required
@require_role(['admin', 'headmaster', 'secretary'])
def quick_payment(request):
    """View to record a payment and auto-create an invoice if it doesn't exist"""
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    billing_period = get_selected_billing_period(request, school)
    form = QuickPaymentForm(school=school, selected_period=billing_period)

    if request.method == 'POST':
        form = QuickPaymentForm(school=school, selected_period=billing_period, data=request.POST)
        if form.is_valid():
            student = form.cleaned_data['student']
            structure = form.cleaned_data['fee_structure']
            academic_year = form.cleaned_data['academic_year']
            term = form.cleaned_data['term']
            billing_month = form.cleaned_data['billing_month']
            billing_year = form.cleaned_data['billing_year']
            amount = form.cleaned_data['amount']
            currency = form.cleaned_data['currency']
            method = form.cleaned_data['method']
            reference = form.cleaned_data['reference']
            payment_date = form.cleaned_data['payment_date']
            notes = form.cleaned_data['notes']

            try:
                from django.db import transaction
                with transaction.atomic():
                    # 1. Find or Create Invoice
                    invoice = None
                    if structure:
                        # Try to find an existing unpaid/partial invoice for this structure
                        invoice_lookup = FeeInvoice.objects.filter(
                            student=student, 
                            fee_structure=structure,
                            status__in=['unpaid', 'partial', 'overdue']
                        )
                        if billing_month and billing_year:
                            invoice_lookup = invoice_lookup.filter(billing_month=billing_month, billing_year=billing_year)
                        else:
                            invoice_lookup = invoice_lookup.filter(term=term, billing_month__isnull=True)
                        invoice = invoice_lookup.first()

                    if not invoice:
                        # Create a one-off invoice
                        invoice_name = structure.name if structure else "General Payment"
                        invoice = FeeInvoice.objects.create(
                            school=school,
                            student=student,
                            fee_structure=structure,
                            academic_year=academic_year,
                            term=term,
                            billing_month=billing_month or None,
                            billing_year=billing_year,
                            invoice_number=str(uuid.uuid4().int)[:8],
                            amount=amount if not structure else structure.amount,
                            currency=currency,
                            due_date=timezone.now().date(),
                            notes=f"Auto-generated for quick payment: {notes}",
                            created_by=school_user,
                        )
                        # Apply any available student credit to the newly created invoice
                        try:
                            invoice.apply_student_credit()
                        except Exception:
                            pass

                    # 2. Record Payment
                    # Convert date to datetime
                    import pytz
                    from datetime import time, datetime
                    tz = pytz.timezone('Africa/Harare')
                    dt = tz.localize(datetime.combine(payment_date, time(12, 0)))

                    payment = FeePayment.objects.create(
                        invoice=invoice,
                        amount=amount,
                        currency=currency,
                        method=method,
                        status='confirmed',
                        reference=reference,
                        payment_date=dt,
                        notes=notes,
                        received_by=school_user
                    )

                messages.success(request, f'Payment of {currency} {amount} recorded for {student.user.get_full_name()}.')
                return redirect('fees:invoice_detail', pk=invoice.pk)
            except Exception as e:
                messages.error(request, f'Error recording payment: {str(e)}')

    return render(request, 'fees/quick_payment.html', {'form': form, 'billing_period': billing_period})


@login_required
def fee_structure_list(request):
    school = get_default_school()
    structures = FeeStructure.objects.filter(school=school).select_related('class_level', 'academic_year', 'term')
    form = FeeStructureForm(school=school)
    if request.method == 'POST':
        form = FeeStructureForm(school=school, data=request.POST)
        if form.is_valid():
            fs = form.save(commit=False)
            fs.school = school
            fs.save()
            messages.success(request, 'Fee structure created.')
            return redirect('fees:structure_list')
    return render(request, 'fees/fee_structure_list.html', {'structures': structures, 'form': form})


@login_required
@require_role(['admin', 'headmaster', 'secretary'])
def fee_structure_edit(request, pk):
    school = get_default_school()
    structure = get_object_or_404(FeeStructure, pk=pk, school=school)
    if request.method == 'POST':
        form = FeeStructureForm(school=school, data=request.POST, instance=structure)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee structure updated.')
            return redirect('fees:structure_list')
    else:
        form = FeeStructureForm(school=school, instance=structure)
    return render(request, 'fees/fee_structure_form.html', {'form': form, 'title': 'Edit Fee Structure', 'structure': structure})


@login_required
@require_role(['admin', 'headmaster'])
def fee_structure_delete(request, pk):
    school = get_default_school()
    structure = get_object_or_404(FeeStructure, pk=pk, school=school)
    if request.method == 'POST':
        structure.delete()
        messages.success(request, 'Fee structure deleted.')
    return redirect('fees:structure_list')


@login_required
def invoice_list(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    billing_period = get_selected_billing_period(request, school)
    qs = FeeInvoice.objects.filter(school=school).select_related('student__user', 'fee_structure')
    qs = filter_invoices_for_period(qs, billing_period)
    if school_user and school_user.role == 'parent':
        qs = qs.filter(student__parent_email=request.user.email)

    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    if status_filter:
        if status_filter == 'overdue':
            qs = qs.filter(status__in=['unpaid', 'partial', 'overdue'], due_date__lt=date.today())
        else:
            qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(
            Q(student__user__first_name__icontains=search) |
            Q(student__user__last_name__icontains=search) |
            Q(invoice_number__icontains=search) |
            Q(student__admission_number__icontains=search)
        )

    # Build student credit map for invoices to avoid N+1 queries in template
    student_ids = list(qs.values_list('student_id', flat=True))
    credits_qs = StudentCredit.objects.filter(student_id__in=student_ids)
    credit_map = {c['student_id']: c['balance'] for c in credits_qs.values('student_id', 'balance')}

    context = {
        'invoices': qs.order_by('-created_at'),
        'status_filter': status_filter,
        'search': search,
        'billing_period': billing_period,
        'period_query': period_query_string(billing_period),
        'student_credit_map': credit_map,
    }
    return render(request, 'fees/invoice_list.html', context)


@login_required
def create_invoice(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    billing_period = get_selected_billing_period(request, school)
    form = FeeInvoiceForm(school=school, selected_period=billing_period)
    if request.method == 'POST':
        form = FeeInvoiceForm(school=school, selected_period=billing_period, data=request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.school = school
            invoice.created_by = school_user
            invoice.invoice_number = str(uuid.uuid4().int)[:8]
            invoice.balance = invoice.amount
            invoice.save()
            # Apply any available student credit to the newly created invoice
            try:
                invoice.apply_student_credit()
            except Exception:
                pass
            messages.success(request, f'Invoice #{invoice.invoice_number} created.')
            return redirect('fees:invoice_detail', pk=invoice.pk)
    return render(request, 'fees/invoice_form.html', {'form': form, 'title': 'Create Invoice', 'billing_period': billing_period})


@login_required
def invoice_detail(request, pk):
    school = get_default_school()
    invoice = get_object_or_404(FeeInvoice, pk=pk, school=school)
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    if school_user and school_user.role == 'parent' and invoice.student.parent_email != request.user.email:
        messages.error(request, "You can only view invoices for your own children.")
        return redirect('dashboard')
    payments = invoice.payments.order_by('-payment_date')
    payment_form = FeePaymentForm()
    sc = StudentCredit.objects.filter(school=school, student=invoice.student).first()
    available_credit = sc.balance if sc else 0
    return render(request, 'fees/invoice_detail.html', {
        'invoice': invoice,
        'payments': payments,
        'payment_form': payment_form,
        'available_credit': available_credit,
    })


@login_required
def record_payment(request, invoice_pk):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    invoice = get_object_or_404(FeeInvoice, pk=invoice_pk, school=school)
    if request.method == 'POST':
        payment_date_str = request.POST.get('payment_date')
        if payment_date_str:
            payment_date_str += ':00'  # Ensure seconds for datetime-local
        form = FeePaymentForm(data=request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.received_by = school_user
            payment.status = 'confirmed'
            payment.save()
            messages.success(request, f'Payment of {payment.currency} {payment.amount} recorded.')
        else:
            messages.error(request, f'Form errors: {form.errors}')
    return redirect('fees:invoice_detail', pk=invoice_pk)


@login_required
def edit_payment(request, payment_pk):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    payment = get_object_or_404(FeePayment, pk=payment_pk, invoice__school=school)
    if request.method == 'POST':
        form = FeePaymentForm(data=request.POST, instance=payment)
        if form.is_valid():
            payment = form.save()
            payment.received_by = school_user
            payment.save()
            payment.invoice.update_balance()
            messages.success(request, 'Payment updated successfully!')
            return redirect('fees:invoice_detail', pk=payment.invoice.pk)
    else:
        # Pre-fill form with existing payment data
        initial_data = {
            'amount': payment.amount,
            'currency': payment.currency,
            'method': payment.method,
            'reference': payment.reference,
            'payment_date': payment.payment_date.date() if payment.payment_date else None,
            'notes': payment.notes,
        }
        form = FeePaymentForm(initial=initial_data, instance=payment)
    return render(request, 'fees/payment_form.html', {
        'form': form,
        'payment': payment,
        'title': 'Edit Payment',
    })


@login_required
def student_fee_statement(request, student_id):
    school = get_default_school()
    student = get_object_or_404(Student, id=student_id, school=school)
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    if school_user and school_user.role == 'parent' and student.parent_email != request.user.email:
        messages.error(request, "You can only view statements for your own children.")
        return redirect('dashboard')
    invoices = FeeInvoice.objects.filter(student=student).prefetch_related('payments')
    total_owed = invoices.aggregate(t=Sum('amount'))['t'] or 0
    # Calculate paid amount by summing confirmed payments directly
    total_paid = FeePayment.objects.filter(
        invoice__in=invoices, status='confirmed'
    ).aggregate(t=Sum('amount'))['t'] or 0
    return render(request, 'fees/student_statement.html', {
        'student': student,
        'invoices': invoices,
        'total_owed': total_owed,
        'total_paid': total_paid,
        'balance': total_owed - total_paid,
    })


@login_required
def bulk_invoice(request):
    """Create invoices for all students in a class for a fee structure"""
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    billing_period = get_selected_billing_period(request, school)
    structures = FeeStructure.objects.filter(school=school)
    from academics.models import ClassSection
    classes = ClassSection.objects.filter(school=school)

    if request.method == 'POST':
        structure_id = request.POST.get('fee_structure')
        class_id = request.POST.get('class_section')
        structure = get_object_or_404(FeeStructure, id=structure_id, school=school)

        if class_id:
            students = Student.objects.filter(current_class_id=class_id, school=school, is_active=True)
        else:
            students = Student.objects.filter(school=school, is_active=True)

        created = 0
        for student in students:
            # For monthly structures, check if invoice exists for this month
            # For termly structures, check term
            # For general, check if any invoice exists for structure
            invoice_exists = False
            if structure.billing_cycle == 'monthly' and structure.month:
                # Check if there's an invoice for this structure and month in the current academic year
                invoice_exists = FeeInvoice.objects.filter(
                    student=student,
                    fee_structure=structure,
                    billing_month=billing_period['month'] if billing_period['scope'] == 'month' else structure.month,
                    billing_year=billing_period['year'] if billing_period['scope'] == 'month' else structure.academic_year.start_date.year,
                ).exists()
            elif structure.billing_cycle == 'termly' and structure.term:
                # Check if there's an invoice for this structure and term
                invoice_exists = FeeInvoice.objects.filter(
                    student=student,
                    fee_structure=structure,
                    term=billing_period.get('term') or structure.term,
                ).exists()
            else:
                # For general structures, check if any invoice exists
                invoice_exists = FeeInvoice.objects.filter(student=student, fee_structure=structure).exists()

            if not invoice_exists:
                FeeInvoice.objects.create(
                    school=school,
                    student=student,
                    fee_structure=structure,
                    academic_year=billing_period.get('academic_year') or structure.academic_year,
                    term=billing_period.get('term') or structure.term,
                    billing_month=billing_period['month'] if billing_period['scope'] == 'month' else None,
                    billing_year=billing_period['year'] if billing_period['scope'] == 'month' else None,
                    invoice_number=str(uuid.uuid4().int)[:8],
                    amount=structure.amount,
                    currency=structure.currency,
                    due_date=structure.due_date,
                    balance=structure.amount,
                    created_by=school_user,
                )
                # Apply credit if any
                try:
                    inv = FeeInvoice.objects.filter(student=student, fee_structure=structure).order_by('-created_at').first()
                    if inv:
                        inv.apply_student_credit()
                except Exception:
                    pass
                created += 1
        messages.success(request, f'{created} invoices created.')
        return redirect(f"{reverse('fees:invoice_list')}?{period_query_string(billing_period)}")

    return render(request, 'fees/bulk_invoice.html', {'structures': structures, 'classes': classes, 'billing_period': billing_period})


@login_required
@require_role(['admin', 'headmaster'])
def payment_config(request):
    school = get_default_school()
    config, _ = PaymentConfig.objects.get_or_create(school=school)
    form = PaymentConfigForm(instance=config)
    if request.method == 'POST':
        form = PaymentConfigForm(instance=config, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payment settings saved.')
            return redirect('fees:payment_config')
    return render(request, 'fees/payment_config.html', {'form': form, 'config': config})


@login_required
def invoice_pdf(request, pk):
    """Generate PDF receipt for a paid invoice"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    school = get_default_school()
    invoice = get_object_or_404(FeeInvoice, pk=pk, school=school)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    theme = colors.HexColor(school.theme_color or '#4F46E5')

    title_s = ParagraphStyle('T', parent=styles['Title'], fontSize=16, textColor=theme, alignment=1, spaceAfter=4)
    sub_s = ParagraphStyle('S', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.HexColor('#6b7280'), spaceAfter=2)
    norm_s = ParagraphStyle('N', parent=styles['Normal'], fontSize=9)

    story.append(Paragraph(school.name.upper(), title_s))
    story.append(Paragraph('FEE INVOICE / RECEIPT', title_s))
    story.append(HRFlowable(width='100%', thickness=1.5, color=theme))
    story.append(Spacer(1, 0.3*cm))

    sc = StudentCredit.objects.filter(school=school, student=invoice.student).first()
    available_credit = sc.balance if sc else 0

    data = [
        ['Invoice No:', invoice.invoice_number, 'Date:', str(invoice.issued_date)],
        ['Billing Period:', invoice.billing_period_label, 'Term:', invoice.term.name if invoice.term else '-'],
        ['Student:', invoice.student.user.get_full_name(), 'Admission:', invoice.student.admission_number],
        ['Amount:', f'{invoice.currency} {invoice.amount}', 'Paid:', f'{invoice.currency} {invoice.amount_paid}'],
        ['Balance:', f'{invoice.currency} {invoice.balance}', 'Status:', invoice.get_status_display()],
        ['Available Credit:', f'{invoice.currency} {available_credit}', '', ''],
    ]
    t = Table(data, colWidths=[3*cm, 6*cm, 3*cm, 6*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))

    payments = invoice.payments.filter(status='confirmed').order_by('-payment_date')
    if payments.exists():
        story.append(Paragraph('<b>Payment History</b>', norm_s))
        ph = [['Date', 'Method', 'Reference', 'Amount']]
        for p in payments:
            ph.append([str(p.payment_date.date()), p.get_method_display(), p.reference or '-', f'{p.currency} {p.amount}'])
        pt = Table(ph, colWidths=[3*cm, 4*cm, 5*cm, 6*cm])
        pt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), theme),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(pt)

    story.append(Spacer(1, 0.5*cm))
    footer_s = ParagraphStyle('F', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#9ca3af'), alignment=1)
    story.append(Paragraph(f'Generated by AcademiaLink | {school.name}', footer_s))
    # Add contact details to footer
    contact_lines = []
    if getattr(school, 'address', None):
        contact_lines.append(school.address)
    if getattr(school, 'phone', None):
        contact_lines.append(f"Tel: {school.phone}")
    if getattr(school, 'email', None):
        contact_lines.append(f"Email: {school.email}")
    if getattr(school, 'website', None):
        contact_lines.append(f"Website: {school.website}")
    if contact_lines:
        story.append(Paragraph(' | '.join(contact_lines), footer_s))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    # Friendly filename including student name and invoice number
    student_name = invoice.student.user.get_full_name().replace(' ', '_') if invoice.student and invoice.student.user else 'student'
    filename = f"{student_name}_Invoice_{invoice.invoice_number}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_role(['headmaster'])
def invoice_list_fragment(request):
    """Return rendered HTML fragment of invoices filtered by status for AJAX/modal."""
    if not request.is_ajax() and request.headers.get('accept','').find('application/json') == -1:
        return api_error('AJAX request expected', status=400)
    status = request.GET.get('status')
    school = get_default_school()
    qs = FeeInvoice.objects.filter(school=school)
    if status:
        qs = qs.filter(status=status)
    html = render_to_string('fees/_invoice_list_fragment.html', {'invoices': qs[:50]})
    return api_ok({'html': html})


@login_required
@require_role(['headmaster'])
def invoice_detail_fragment(request, pk):
    """Return rendered HTML fragment for a single invoice (AJAX/modal).
    """
    school = get_default_school()
    invoice = get_object_or_404(FeeInvoice, pk=pk, school=school)

    # Render detail fragment
    html = render_to_string('fees/partials/invoice_detail_fragment.html', {'inv': invoice}, request=request)
    return JsonResponse({'html': html})


@login_required
@require_role(['admin', 'headmaster'])
def run_generate_invoices(request):
    """Trigger the generate_monthly_invoices management command and return output.
    This endpoint is intended to be called via AJAX (POST) from the payment config page.
    """
    from django.views.decorators.http import require_POST
    from django.core.management import call_command
    import io

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    school = get_default_school()
    # Only allow users from the school with appropriate role (decorator handles role)
    out = io.StringIO()
    try:
        # call_command will run the management command for all schools; our command accepts --school-id optionally
        # If the command supports a school argument, pass it. Otherwise it will run for all.
        try:
            # Prefer passing school id if supported
            call_command('generate_monthly_invoices', f'--school={school.id}', stdout=out, stderr=out)
        except TypeError:
            # Fallback: call without school arg
            call_command('generate_monthly_invoices', stdout=out, stderr=out)
        return JsonResponse({'ok': True, 'output': out.getvalue()})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e), 'output': out.getvalue()}, status=500)


@login_required
@require_role(['admin', 'headmaster', 'secretary'])
def void_and_replace_invoice(request, pk):
    """Void an invoice and create a replacement. Expects POST with 'reason'."""
    school = get_default_school()
    inv = get_object_or_404(FeeInvoice, pk=pk, school=school)
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    reason = request.POST.get('reason', '').strip()
    try:
        new_inv = inv.void_and_replace(school_user, reason=reason)
        return JsonResponse({'ok': True, 'new_invoice_id': new_inv.pk, 'new_invoice_number': new_inv.invoice_number})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
