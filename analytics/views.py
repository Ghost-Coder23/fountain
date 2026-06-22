from core.utils import get_default_school
"""
Analytics views - Role-specific dashboards with real data
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Sum, Q, Case, When
from django.db import models
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model, login as auth_login
from django.shortcuts import HttpResponse
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from schools.models import SchoolUser, School
from academics.models import Student, ClassSection, AcademicYear, ParentStudentLink
from results.models import StudentResult, TermSummary, Term
from attendance.models import AttendanceSession, AttendanceRecord
from fees.models import FeeInvoice, FeePayment, Expense
from fees.periods import filter_invoices_for_period, get_selected_billing_period, period_query_string
from notifications.models import Notification, Announcement
from academics.models import Subject


def get_recent_announcements(school, audiences, limit=5):
    """Fetch active announcements for the supplied role audiences."""
    return Announcement.objects.filter(
        school=school,
        is_active=True
    ).filter(
        Q(audience='all') | Q(audience__in=audiences)
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
    ).order_by('-created_at')[:limit]


@login_required
def dashboard(request):
    school = get_default_school()
    if not school:
        return redirect('home')
    try:
        membership = SchoolUser.objects.get(user=request.user, school=school, is_active=True)
    except SchoolUser.DoesNotExist:
        return redirect('home')

    role = membership.role
    # Directors and headmasters see the Director dashboard
    if role in ['admin', 'headmaster']:
        return headmaster_admin_dashboard(request, school, membership)
    # 'senior' role maps to the Senior operational dashboard
    if role == 'senior':
        return headmaster_only_dashboard(request, school, membership)
    elif role == 'secretary':
        return secretary_dashboard(request, school, membership)
    elif role == 'teacher':
        return teacher_dashboard(request, school, membership)
    elif role == 'parent':
        return parent_dashboard(request, school, membership)
    elif role == 'student':
        return student_dashboard(request, school, membership)
    return redirect('home')


def headmaster_only_dashboard(request, school, membership):
    """Operational dashboard for headmasters — no revenue totals, focused on students, invoices and payments."""
    today = date.today()
    billing_period = get_selected_billing_period(request, school, today=today)

    # Searches
    student_q = request.GET.get('student_search', '').strip()
    invoice_q = request.GET.get('invoice_search', '').strip()

    students = Student.objects.filter(school=school, is_active=True).select_related('user', 'current_class')
    if student_q:
        students = students.filter(
            Q(user__first_name__icontains=student_q) |
            Q(user__last_name__icontains=student_q) |
            Q(admission_number__icontains=student_q) |
            Q(parent_email__icontains=student_q)
        )
    students = students.order_by('user__last_name')[:200]

    # Compute invoice balances per student for display (avoid template filters)
    student_ids = [s.id for s in students]
    invoice_sums = {}
    if student_ids:
        sums = FeeInvoice.objects.filter(school=school, student_id__in=student_ids).values('student_id').annotate(total_balance=Sum('balance'))
        for row in sums:
            invoice_sums[row['student_id']] = row['total_balance'] or 0

    students_with_balance = []
    for s in students:
        students_with_balance.append({'student': s, 'balance': invoice_sums.get(s.id, 0)})

    invoices = FeeInvoice.objects.filter(school=school).select_related('student__user', 'fee_structure')
    invoices = filter_invoices_for_period(invoices, billing_period)
    
    if invoice_q:
        invoices = invoices.filter(
            Q(student__user__first_name__icontains=invoice_q) |
            Q(student__user__last_name__icontains=invoice_q) |
            Q(invoice_number__icontains=invoice_q) |
            Q(student__admission_number__icontains=invoice_q)
        )
    invoices = invoices.order_by('-issued_date')[:200]

    recent_payments = FeePayment.objects.filter(
        invoice__school=school, 
        status='confirmed',
        invoice__in=filter_invoices_for_period(FeeInvoice.objects.filter(school=school), billing_period)
    ).select_related('invoice__student__user').order_by('-payment_date')[:20]

    # Operational counts for selected period
    period_invoices = filter_invoices_for_period(FeeInvoice.objects.filter(school=school), billing_period)
    unpaid_students = period_invoices.filter(status='unpaid').values('student').distinct().count()
    partial_students = period_invoices.filter(status='partial').values('student').distinct().count()
    overdue_invoices = period_invoices.filter(status__in=['unpaid', 'partial', 'overdue'], due_date__lt=today).count()

    context = {
        'role': 'senior',
        'billing_period': billing_period,
        'students_with_balance': students_with_balance,
        'students': students,
        'invoices': invoices,
        'recent_payments': recent_payments,
        'unpaid_students': unpaid_students,
        'partial_students': partial_students,
        'overdue_invoices': overdue_invoices,
        'student_q': student_q,
        'invoice_q': invoice_q,
    }
    return render(request, 'analytics/dashboard_headmaster_ops.html', context)


def headmaster_admin_dashboard(request, school, membership):
    today = date.today()
    current_term = Term.objects.filter(academic_year__school=school, is_current=True).first()
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    billing_period = get_selected_billing_period(request, school, today=today)

    total_students = Student.objects.filter(school=school, is_active=True).count()
    total_teachers = SchoolUser.objects.filter(school=school, role='teacher', is_active=True).count()
    total_parents = SchoolUser.objects.filter(school=school, role='parent', is_active=True).count()
    total_classes = ClassSection.objects.filter(school=school).count()
    pending_approvals = StudentResult.objects.filter(class_section__school=school, status='submitted').count()

    # Attendance today
    today_sessions = AttendanceSession.objects.filter(school=school, date=today)
    today_present = AttendanceRecord.objects.filter(session__in=today_sessions, status='present').count()
    today_absent = AttendanceRecord.objects.filter(session__in=today_sessions, status='absent').count()
    today_total = today_present + today_absent
    today_attendance_pct = round((today_present / today_total) * 100, 1) if today_total > 0 else 0
    classes_marked_today = today_sessions.filter(is_finalized=True).count()
    classes_unmarked_today = max(total_classes - classes_marked_today, 0)
    attendance_entry_pct = round(
        (classes_marked_today / total_classes) * 100, 1
    ) if total_classes else 0

    # Attendance this week
    week_start = today - timedelta(days=today.weekday())
    week_sessions = AttendanceSession.objects.filter(school=school, date__gte=week_start, date__lte=today)
    week_present = AttendanceRecord.objects.filter(session__in=week_sessions, status='present').count()
    week_total = AttendanceRecord.objects.filter(session__in=week_sessions).count()
    week_attendance_pct = round((week_present / week_total) * 100, 1) if week_total > 0 else 0

    # Fee summary
    invoices_for_period = filter_invoices_for_period(FeeInvoice.objects.filter(school=school), billing_period)
    total_invoiced = invoices_for_period.aggregate(t=Sum('amount'))['t'] or 0
    total_collected = FeePayment.objects.filter(
        invoice__in=invoices_for_period, status='confirmed'
    ).aggregate(t=Sum('amount'))['t'] or 0
    total_paid = total_collected
    collection_pct = round((total_collected / total_invoiced) * 100, 1) if total_invoiced > 0 else 0
    outstanding = total_invoiced - total_collected
    overdue_count = invoices_for_period.filter(status__in=['unpaid','partial', 'overdue'], due_date__lt=today).count()
    unpaid_invoices = invoices_for_period.filter(status='unpaid').count()
    partial_invoices = invoices_for_period.filter(status='partial').count()
    overdue_invoices = invoices_for_period.filter(status__in=['unpaid','partial', 'overdue'], due_date__lt=today).count()
    recent_invoices = invoices_for_period.select_related(
        'student__user'
    ).order_by('-created_at')[:8]

    # Recent payments
    recent_payments = FeePayment.objects.filter(
        invoice__in=invoices_for_period
    ).select_related('invoice__student__user').order_by('-payment_date')[:8]

    # Pending payments
    pending_payments_count = FeePayment.objects.filter(
        invoice__in=invoices_for_period, status='pending'
    ).count()

    # At-risk students (attendance < 80% this month)
    # Performance: batch aggregate attendance totals per student instead of per-student queries.
    month_start = today.replace(day=1)
    at_risk_rows = (
        AttendanceRecord.objects.filter(
            student__school=school,
            student__is_active=True,
            session__date__gte=month_start,
            session__date__lte=today,
        )
        .values('student')
        .annotate(
            total=Count('id'),
            present=Sum(
                Case(
                    When(status='present', then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            ),
        )
        .filter(total__gte=5)
    )

    at_risk = []
    rows_list = list(at_risk_rows)
    if rows_list:
        student_ids = [row['student'] for row in rows_list]
        students = Student.objects.filter(id__in=student_ids).select_related('user', 'current_class')
        student_map = {s.id: s for s in students}

        for row in rows_list:
            total = row.get('total') or 0
            present = row.get('present') or 0
            pct = (present / total) * 100 if total else 0
            if pct < 80:
                student = student_map.get(row['student'])
                if student is not None:
                    at_risk.append((student, round(pct, 1)))
    at_risk = sorted(at_risk, key=lambda x: x[1])[:10]

    # Class performance (term summaries)
    class_performance = []
    if current_term:
        for cs in ClassSection.objects.filter(school=school):
            avg = TermSummary.objects.filter(class_section=cs, term=current_term).aggregate(a=Avg('average'))['a']
            if avg:
                class_performance.append({'class': cs, 'average': round(avg, 1)})
        class_performance.sort(key=lambda x: x['average'], reverse=True)

    # Recent results pending
    recent_pending = StudentResult.objects.filter(
        class_section__school=school, status='submitted'
    ).select_related('student__user', 'subject', 'term').order_by('-updated_at')[:8]

    # Top performers (current term)
    top_performers = []
    if current_term:
        top_performers = TermSummary.objects.filter(
            class_section__school=school, term=current_term
        ).select_related('student__user', 'class_section').order_by('-average')[:8]

    # Financial Trends (Last 6 months)
    finance_labels = []
    revenue_data = []
    expense_data = []
    for i in range(5, -1, -1):
        target_month = (today.month - i - 1) % 12 + 1
        target_year = today.year + (today.month - i - 1) // 12
        m_start = date(target_year, target_month, 1)
        if target_month == 12:
            m_end = date(target_year + 1, 1, 1)
        else:
            m_end = date(target_year, target_month + 1, 1)
            
        rev = FeePayment.objects.filter(
            invoice__school=school, 
            payment_date__gte=m_start, 
            payment_date__lt=m_end,
            status='confirmed'
        ).aggregate(s=Sum('amount'))['s'] or 0
        
        exp = Expense.objects.filter(
            school=school,
            date__gte=m_start,
            date__lt=m_end
        ).aggregate(s=Sum('amount'))['s'] or 0
        
        revenue_data.append(float(rev))
        expense_data.append(float(exp))
        finance_labels.append(m_start.strftime('%b'))

    # --- Previous month summary for dashboard ---
    # compute start and end for previous calendar month
    if today.month == 1:
        prev_month = 12
        prev_year = today.year - 1
    else:
        prev_month = today.month - 1
        prev_year = today.year
    prev_start = date(prev_year, prev_month, 1)
    if prev_month == 12:
        prev_end = date(prev_year + 1, 1, 1)
    else:
        prev_end = date(prev_year, prev_month + 1, 1)

    prev_total_invoiced = FeeInvoice.objects.filter(
        school=school,
        issued_date__gte=prev_start,
        issued_date__lt=prev_end
    ).aggregate(t=Sum('amount'))['t'] or 0

    prev_total_collected = FeePayment.objects.filter(
        invoice__school=school,
        payment_date__gte=prev_start,
        payment_date__lt=prev_end,
        status='confirmed'
    ).aggregate(t=Sum('amount'))['t'] or 0

    prev_outstanding = prev_total_invoiced - prev_total_collected

    prev_overdue_count = FeeInvoice.objects.filter(
        school=school,
        status__in=['unpaid', 'partial'],
        due_date__lt=prev_end
    ).count()

    prev_month_label = prev_start.strftime('%B %Y')

    # Recent Activity Stream
    activity_feed = []
    
    # Helper to ensure everything is a datetime for sorting and template display
    from datetime import datetime, time
    import pytz
    tz = pytz.timezone('Africa/Harare')

    def ensure_datetime(val):
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return tz.localize(datetime.combine(val, time.min))
        return val
    
    # New Student Admissions
    new_students = Student.objects.filter(school=school).order_by('-date_joined')[:5]
    for s in new_students:
        activity_feed.append({
            'type': 'admission',
            'title': 'New Student Admission',
            'desc': f'{s.user.get_full_name()} joined {s.current_class or "school"}',
            'time': ensure_datetime(s.date_joined),
            'icon': 'bi-person-plus',
            'color': 'primary'
        })
        
    # Recent Payments
    for p in recent_payments:
        activity_feed.append({
            'type': 'payment',
            'title': 'Fee Payment Received',
            'desc': f'{p.currency} {p.amount} from {p.invoice.student.user.get_full_name()}',
            'time': ensure_datetime(p.payment_date),
            'icon': 'bi-cash-coin',
            'color': 'success'
        })
        
    # Recent Results
    recent_results = StudentResult.objects.filter(
        class_section__school=school
    ).select_related('student__user', 'subject', 'class_section').order_by('-updated_at')[:5]
    for r in recent_results:
        activity_feed.append({
            'type': 'result',
            'title': 'Result Recorded',
            'desc': f'{r.subject.name} score for {r.student.user.get_full_name()}',
            'time': ensure_datetime(r.updated_at),
            'icon': 'bi-pencil-square',
            'color': 'info'
        })
        
    # Sort activity feed by time
    activity_feed.sort(key=lambda x: x['time'], reverse=True)
    activity_feed = activity_feed[:10]

    # Students per class
    classes_data = []
    for cs in ClassSection.objects.filter(school=school).select_related('class_level'):
        count = Student.objects.filter(current_class=cs, school=school, is_active=True).count()
        classes_data.append({'class': cs, 'count': count})

    # Enrollment Trends (Last 6 months)
    enrollment_data = []
    enrollment_labels = []
    for i in range(5, -1, -1):
        target_month = (today.month - i - 1) % 12 + 1
        target_year = today.year + (today.month - i - 1) // 12
        m_start = date(target_year, target_month, 1)
        if target_month == 12:
            m_end = date(target_year + 1, 1, 1)
        else:
            m_end = date(target_year, target_month + 1, 1)
            
        count = Student.objects.filter(school=school, date_joined__gte=m_start, date_joined__lt=m_end).count()
        enrollment_data.append(count)
        enrollment_labels.append(m_start.strftime('%b'))

    # Notifications
    unread_notifications = Notification.objects.filter(
        recipient=request.user, school=school, is_read=False
    ).order_by('-created_at')[:5]
    announcements = get_recent_announcements(
        school, ['teachers', 'parents', 'students'], limit=5
    )

    context = {
        'role': membership.role,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_parents': total_parents,
        'total_classes': total_classes,
        'pending_approvals': pending_approvals,
        'today_attendance_pct': today_attendance_pct,
        'today_present': today_present,
        'today_absent': today_absent,
        'classes_marked_today': classes_marked_today,
        'classes_unmarked_today': classes_unmarked_today,
        'attendance_entry_pct': attendance_entry_pct,
        'week_attendance_pct': week_attendance_pct,
        'at_risk': at_risk,
        'class_performance': class_performance,
        'recent_pending': recent_pending,
        'top_performers': top_performers,
        'announcements': announcements,
        'current_term': current_term,
        'current_year': current_year,
        'unread_notifications': unread_notifications,
        'today': today,
        # Admin dashboard additions
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'fee_collected_pct': round((total_paid / total_invoiced) * 100, 1) if total_invoiced > 0 else 0,
        'fee_pending_pct': round((outstanding / total_invoiced) * 100, 1) if total_invoiced > 0 else 0,
        'unpaid_invoices': unpaid_invoices,
        'partial_invoices': partial_invoices,
        'overdue_invoices': overdue_invoices,
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
        'pending_payments_count': pending_payments_count,
        'classes_marked_today_admin': classes_marked_today,
        'classes_not_marked': classes_unmarked_today,
        'classes_data': classes_data,
        'enrollment_data': enrollment_data,
        'enrollment_labels': enrollment_labels,
        'finance_labels': finance_labels,
        'revenue_data': revenue_data,
        'expense_data': expense_data,
        'activity_feed': activity_feed,
        'billing_period': billing_period,
        'period_query': period_query_string(billing_period),
        # previous month summary
        'prev_month_label': prev_month_label,
        'prev_total_invoiced': prev_total_invoiced,
        'prev_total_collected': prev_total_collected,
        'prev_outstanding': prev_outstanding,
        'prev_overdue_count': prev_overdue_count,
    }
    return render(request, 'analytics/dashboard_admin.html', context)


def secretary_dashboard(request, school, membership):
    today = date.today()
    current_term = Term.objects.filter(academic_year__school=school, is_current=True).first()
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    billing_period = get_selected_billing_period(request, school, today=today)

    total_students = Student.objects.filter(school=school, is_active=True).count()
    total_teachers = SchoolUser.objects.filter(school=school, role='teacher', is_active=True).count()
    total_parents = SchoolUser.objects.filter(school=school, role='parent', is_active=True).count()
    total_classes = ClassSection.objects.filter(school=school).count()
    pending_approvals = StudentResult.objects.filter(class_section__school=school, status='submitted').count()

    # Attendance today
    today_sessions = AttendanceSession.objects.filter(school=school, date=today)
    today_present = AttendanceRecord.objects.filter(session__in=today_sessions, status='present').count()
    today_absent = AttendanceRecord.objects.filter(session__in=today_sessions, status='absent').count()
    today_total = today_present + today_absent
    today_attendance_pct = round((today_present / today_total) * 100, 1) if today_total > 0 else 0
    classes_marked_today = today_sessions.filter(is_finalized=True).count()
    classes_unmarked_today = max(total_classes - classes_marked_today, 0)
    attendance_entry_pct = round(
        (classes_marked_today / total_classes) * 100, 1
    ) if total_classes else 0

    # Attendance this week
    week_start = today - timedelta(days=today.weekday())
    week_sessions = AttendanceSession.objects.filter(school=school, date__gte=week_start, date__lte=today)
    week_present = AttendanceRecord.objects.filter(session__in=week_sessions, status='present').count()
    week_total = AttendanceRecord.objects.filter(session__in=week_sessions).count()
    week_attendance_pct = round((week_present / week_total) * 100, 1) if week_total > 0 else 0

    # Recent invoices and payments (without showing amounts)
    invoices_for_period = filter_invoices_for_period(FeeInvoice.objects.filter(school=school), billing_period)
    recent_invoices = invoices_for_period.select_related(
        'student__user'
    ).order_by('-created_at')[:8]

    recent_payments = FeePayment.objects.filter(
        invoice__in=invoices_for_period
    ).select_related('invoice__student__user').order_by('-payment_date')[:8]

    pending_payments_count = FeePayment.objects.filter(
        invoice__in=invoices_for_period, status='pending'
    ).count()

    # Invoice stats
    unpaid_invoices = invoices_for_period.filter(status='unpaid').count()
    partial_invoices = invoices_for_period.filter(status='partial').count()
    overdue_invoices = invoices_for_period.filter(status__in=['unpaid','partial', 'overdue'], due_date__lt=today).count()

    # At-risk students (attendance < 80% this month)
    month_start = today.replace(day=1)
    at_risk_ids = []
    for student in Student.objects.filter(school=school, is_active=True):
        records = AttendanceRecord.objects.filter(
            student=student, session__date__gte=month_start, session__date__lte=today
        )
        total = records.count()
        if total >= 5:
            present = records.filter(status='present').count()
            pct = (present / total) * 100
            if pct < 80:
                at_risk_ids.append((student, round(pct, 1)))
    at_risk = sorted(at_risk_ids, key=lambda x: x[1])[:10]

    # Class performance (term summaries)
    class_performance = []
    if current_term:
        for cs in ClassSection.objects.filter(school=school):
            avg = TermSummary.objects.filter(class_section=cs, term=current_term).aggregate(a=Avg('average'))['a']
            if avg:
                class_performance.append({'class': cs, 'average': round(avg, 1)})
        class_performance.sort(key=lambda x: x['average'], reverse=True)

    # Recent results pending
    recent_pending = StudentResult.objects.filter(
        class_section__school=school, status='submitted'
    ).select_related('student__user', 'subject', 'term').order_by('-updated_at')[:8]

    # Top performers (current term)
    top_performers = []
    if current_term:
        top_performers = TermSummary.objects.filter(
            class_section__school=school, term=current_term
        ).select_related('student__user', 'class_section').order_by('-average')[:8]

    # Recent Activity Stream
    activity_feed = []
    
    # Helper to ensure everything is a datetime for sorting and template display
    from datetime import datetime, time
    import pytz
    tz = pytz.timezone('Africa/Harare')

    def ensure_datetime(val):
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            return tz.localize(datetime.combine(val, time.min))
        return val
    
    # New Student Admissions
    new_students = Student.objects.filter(school=school).order_by('-date_joined')[:5]
    for s in new_students:
        activity_feed.append({
            'type': 'admission',
            'title': 'New Student Admission',
            'desc': f'{s.user.get_full_name()} joined {s.current_class or "school"}',
            'time': ensure_datetime(s.date_joined),
            'icon': 'bi-person-plus',
            'color': 'primary'
        })
        
    # Recent Payments (without amount)
    for p in recent_payments:
        activity_feed.append({
            'type': 'payment',
            'title': 'Fee Payment Received',
            'desc': f'Payment from {p.invoice.student.user.get_full_name()}',
            'time': ensure_datetime(p.payment_date),
            'icon': 'bi-cash-coin',
            'color': 'success'
        })
        
    # Recent Results
    recent_results = StudentResult.objects.filter(
        class_section__school=school
    ).select_related('student__user', 'subject', 'class_section').order_by('-updated_at')[:5]
    for r in recent_results:
        activity_feed.append({
            'type': 'result',
            'title': 'Result Recorded',
            'desc': f'{r.subject.name} score for {r.student.user.get_full_name()}',
            'time': ensure_datetime(r.updated_at),
            'icon': 'bi-pencil-square',
            'color': 'info'
        })
        
    # Sort activity feed by time
    activity_feed.sort(key=lambda x: x['time'], reverse=True)
    activity_feed = activity_feed[:10]

    # Students per class
    classes_data = []
    for cs in ClassSection.objects.filter(school=school).select_related('class_level'):
        count = Student.objects.filter(current_class=cs, school=school, is_active=True).count()
        classes_data.append({'class': cs, 'count': count})

    # Enrollment Trends (Last 6 months)
    enrollment_data = []
    enrollment_labels = []
    for i in range(5, -1, -1):
        target_month = (today.month - i - 1) % 12 + 1
        target_year = today.year + (today.month - i - 1) // 12
        m_start = date(target_year, target_month, 1)
        if target_month == 12:
            m_end = date(target_year + 1, 1, 1)
        else:
            m_end = date(target_year, target_month + 1, 1)
            
        count = Student.objects.filter(school=school, date_joined__gte=m_start, date_joined__lt=m_end).count()
        enrollment_data.append(count)
        enrollment_labels.append(m_start.strftime('%b'))

    # Notifications
    unread_notifications = Notification.objects.filter(
        recipient=request.user, school=school, is_read=False
    ).order_by('-created_at')[:5]
    announcements = get_recent_announcements(
        school, ['teachers', 'parents', 'students'], limit=5
    )

    context = {
        'role': 'secretary',
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_parents': total_parents,
        'total_classes': total_classes,
        'pending_approvals': pending_approvals,
        'today_attendance_pct': today_attendance_pct,
        'today_present': today_present,
        'today_absent': today_absent,
        'classes_marked_today': classes_marked_today,
        'classes_unmarked_today': classes_unmarked_today,
        'attendance_entry_pct': attendance_entry_pct,
        'week_attendance_pct': week_attendance_pct,
        'at_risk': at_risk,
        'class_performance': class_performance,
        'recent_pending': recent_pending,
        'top_performers': top_performers,
        'announcements': announcements,
        'current_term': current_term,
        'current_year': current_year,
        'unread_notifications': unread_notifications,
        'today': today,
        # Secretary dashboard additions (without financial amounts)
        'recent_invoices': recent_invoices,
        'recent_payments': recent_payments,
        'pending_payments_count': pending_payments_count,
        'unpaid_invoices': unpaid_invoices,
        'partial_invoices': partial_invoices,
        'overdue_invoices': overdue_invoices,
        'classes_marked_today_admin': classes_marked_today,
        'classes_not_marked': classes_unmarked_today,
        'classes_data': classes_data,
        'enrollment_data': enrollment_data,
        'enrollment_labels': enrollment_labels,
        'activity_feed': activity_feed,
        'billing_period': billing_period,
        'period_query': period_query_string(billing_period),
    }
    return render(request, 'analytics/dashboard_admin.html', context)


def teacher_dashboard(request, school, membership):
    today = date.today()
    from academics.models import TeacherSubjectAssignment

    assignments = TeacherSubjectAssignment.objects.filter(
        teacher=membership, class_section__school=school
    ).select_related('subject', 'class_section__class_level')

    my_classes = list({a.class_section for a in assignments})

    # Today's attendance status per class
    class_attendance = []
    for cs in my_classes:
        session = AttendanceSession.objects.filter(class_section=cs, date=today).first()
        student_count = Student.objects.filter(current_class=cs, school=school, is_active=True).count()
        class_attendance.append({
            'class': cs,
            'session': session,
            'marked': session is not None and session.is_finalized,
            'student_count': student_count,
        })

    # Pending result entry
    current_term = Term.objects.filter(academic_year__school=school, is_current=True).first()
    pending_entry = []
    if current_term:
        for a in assignments:
            entered = StudentResult.objects.filter(
                class_section=a.class_section,
                subject=a.subject,
                term=current_term
            ).count()
            total_students = Student.objects.filter(
                current_class=a.class_section, school=school, is_active=True
            ).count()
            pending_entry.append({
                'assignment': a,
                'entered': entered,
                'total': total_students,
                'remaining': max(total_students - entered, 0),
                'complete': entered >= total_students and total_students > 0,
            })

    # Class averages for my subjects
    class_averages = []
    if current_term:
        for a in assignments:
            avg = StudentResult.objects.filter(
                class_section=a.class_section,
                subject=a.subject,
                term=current_term,
                status__in=['approved', 'locked']
            ).aggregate(a=Avg('total_score'))['a']
            if avg:
                class_averages.append({
                    'class': a.class_section,
                    'subject': a.subject,
                    'average': round(avg, 1),
                })

    unread_notifications = Notification.objects.filter(
        recipient=request.user, school=school, is_read=False
    ).order_by('-created_at')[:5]

    classes_assigned = len(my_classes)
    classes_marked_today = sum(1 for c in class_attendance if c['marked'])
    classes_pending_today = max(classes_assigned - classes_marked_today, 0)
    attendance_completion_pct = round(
        (classes_marked_today / classes_assigned) * 100, 1
    ) if classes_assigned else 0

    total_result_slots = sum(pe['total'] for pe in pending_entry)
    total_result_entered = sum(pe['entered'] for pe in pending_entry)
    results_entry_pct = round(
        (total_result_entered / total_result_slots) * 100, 1
    ) if total_result_slots else 0
    pending_results_total = sum(pe['remaining'] for pe in pending_entry)

    best_class = None
    weakest_class = None
    if class_averages:
        best_class = max(class_averages, key=lambda x: x['average'])
        weakest_class = min(class_averages, key=lambda x: x['average'])

    announcements = get_recent_announcements(school, ['teachers'], limit=4)

    context = {
        'role': 'teacher',
        'assignments': assignments,
        'class_attendance': class_attendance,
        'classes_assigned': classes_assigned,
        'classes_marked_today': classes_marked_today,
        'classes_pending_today': classes_pending_today,
        'attendance_completion_pct': attendance_completion_pct,
        'pending_entry': pending_entry,
        'pending_results_total': pending_results_total,
        'results_entry_pct': results_entry_pct,
        'class_averages': class_averages,
        'best_class': best_class,
        'weakest_class': weakest_class,
        'announcements': announcements,
        'current_term': current_term,
        'unread_notifications': unread_notifications,
        'today': today,
    }
    return render(request, 'analytics/dashboard_teacher.html', context)


def parent_dashboard(request, school, membership):
    today = date.today()
    current_term = Term.objects.filter(academic_year__school=school, is_current=True).first()
    # Backward compatibility and auto-sync for records where only parent_email was set.
    legacy_children = Student.objects.filter(
        school=school,
        parent_email__iexact=request.user.email,
        is_active=True,
    ).select_related('user', 'current_class')
    for child in legacy_children:
        ParentStudentLink.objects.get_or_create(
            school=school,
            parent=membership,
            student=child,
            defaults={'relationship': 'parent'},
        )

    # Find children via explicit links OR matching parent email
    link_student_ids = ParentStudentLink.objects.filter(
        school=school,
        parent=membership,
    ).values_list('student_id', flat=True)

    children = Student.objects.filter(
        Q(id__in=link_student_ids) | Q(parent_email=request.user.email),
        school=school,
        is_active=True
    ).select_related('user', 'current_class').distinct()

    children_data = []
    total_balances = {} # Dict of currency: balance
    low_attendance_count = 0
    outstanding_fee_children = 0
    for child in children:
        # Attendance this month
        month_start = today.replace(day=1)
        records = AttendanceRecord.objects.filter(
            student=child, session__date__gte=month_start, session__date__lte=today
        )
        att_total = records.count()
        att_present = records.filter(status='present').count()
        att_pct = round((att_present / att_total) * 100, 1) if att_total > 0 else None
        if att_pct is not None and att_pct < 80:
            low_attendance_count += 1

        # Latest term results
        latest_summary = TermSummary.objects.filter(student=child).select_related('term').order_by('-term__term_number').first()
        latest_results = []
        if current_term:
            latest_results = StudentResult.objects.filter(
                student=child, term=current_term, status__in=['approved', 'locked']
            ).select_related('subject').order_by('subject__name')

        # Fee balance
        invoices = FeeInvoice.objects.filter(student=child, school=school)
        
        # Calculate balance per currency
        currencies = invoices.values_list('currency', flat=True).distinct()
        child_balances = []
        for curr in currencies:
            curr_invoices = invoices.filter(currency=curr)
            owed = curr_invoices.aggregate(t=Sum('amount'))['t'] or 0
            # Calculate paid amount by summing confirmed payments directly
            # This avoids issues if FeeInvoice.amount_paid is out of sync
            from fees.models import FeePayment
            paid = FeePayment.objects.filter(
                invoice__in=curr_invoices, 
                status='confirmed',
                currency=curr
            ).aggregate(t=Sum('amount'))['t'] or 0
            bal = owed - paid
            if bal != 0 or owed != 0:
                child_balances.append({
                    'currency': curr,
                    'owed': owed,
                    'paid': paid,
                    'balance': bal
                })
        
        # High-level summary for the child
        total_owed = invoices.aggregate(t=Sum('amount'))['t'] or 0
        # Sum of all confirmed payments across all currencies (might be mixed, but used for 'outstanding' check)
        total_paid_amt = FeePayment.objects.filter(
            invoice__in=invoices, status='confirmed'
        ).aggregate(t=Sum('amount'))['t'] or 0
        balance = total_owed - total_paid_amt
        
        overdue_invoices = invoices.filter(
            status__in=['unpaid', 'partial', 'overdue'], due_date__lt=today
        ).count()
        if balance > 0:
            outstanding_fee_children += 1
        
        # Aggregate totals per currency
        for b in child_balances:
            curr = b['currency']
            if curr not in total_balances:
                total_balances[curr] = 0
            total_balances[curr] += b['balance']

        best_result = None
        weak_result = None
        if latest_results:
            best_result = max(latest_results, key=lambda r: r.total_score)
            weak_result = min(latest_results, key=lambda r: r.total_score)

        children_data.append({
            'student': child,
            'att_pct': att_pct,
            'att_present': att_present,
            'att_total': att_total,
            'latest_summary': latest_summary,
            'latest_results': latest_results,
            'best_result': best_result,
            'weak_result': weak_result,
            'results_count': len(latest_results),
            'fee_balance': balance,
            'balances': child_balances,
            'overdue_invoices': overdue_invoices,
            'current_term': current_term,
        })

    unread_notifications = Notification.objects.filter(
        recipient=request.user, school=school, is_read=False
    ).order_by('-created_at')[:5]
    announcements = get_recent_announcements(school, ['parents'], limit=4)

    # Get payment configuration
    from fees.models import PaymentConfig
    payment_config = PaymentConfig.objects.filter(school=school).first()

    children_count = len(children_data)

    context = {
        'role': 'parent',
        'children_data': children_data,
        'children_count': children_count,
        'low_attendance_count': low_attendance_count,
        'outstanding_fee_children': outstanding_fee_children,
        'total_balances': total_balances,
        'announcements': announcements,
        'current_term': current_term,
        'unread_notifications': unread_notifications,
        'payment_config': payment_config,
        'today': today,
    }
    return render(request, 'analytics/dashboard_parent.html', context)


def student_dashboard(request, school, membership):
    today = date.today()
    try:
        student = Student.objects.get(user=request.user, school=school)
    except Student.DoesNotExist:
        return redirect('home')

    current_term = Term.objects.filter(academic_year__school=school, is_current=True).first()

    # Attendance this term
    term_records = []
    att_pct = None
    att_total = 0
    att_present = 0
    att_absent = 0
    att_late = 0
    if current_term:
        term_records = AttendanceRecord.objects.filter(
            student=student,
            session__date__gte=current_term.start_date,
            session__date__lte=today
        )
        att_total = term_records.count()
        att_present = term_records.filter(status='present').count()
        att_absent = term_records.filter(status='absent').count()
        att_late = term_records.filter(status='late').count()
        att_pct = round((att_present / att_total) * 100, 1) if att_total > 0 else None

    # Results
    current_results = []
    term_summaries = TermSummary.objects.filter(student=student).select_related('term').order_by('-term__term_number')
    if current_term:
        current_results = StudentResult.objects.filter(
            student=student, term=current_term, status__in=['approved', 'locked']
        ).select_related('subject').order_by('subject__name')

    subject_count = len(current_results)
    pass_count = sum(1 for r in current_results if r.total_score >= 50)
    fail_count = max(subject_count - pass_count, 0)
    best_subject = max(current_results, key=lambda r: r.total_score) if current_results else None
    weak_subject = min(current_results, key=lambda r: r.total_score) if current_results else None
    current_average = round(
        sum(r.total_score for r in current_results) / subject_count, 1
    ) if subject_count else None

    trend_delta = None
    latest_summary = term_summaries[0] if term_summaries else None
    previous_summary = term_summaries[1] if term_summaries and len(term_summaries) > 1 else None
    if latest_summary and previous_summary:
        trend_delta = round(latest_summary.average - previous_summary.average, 1)

    # Fee balance
    invoices = FeeInvoice.objects.filter(student=student)
    total_owed = invoices.aggregate(t=Sum('amount'))['t'] or 0
    from fees.models import FeePayment
    total_paid_amt = FeePayment.objects.filter(
        invoice__in=invoices, status='confirmed'
    ).aggregate(t=Sum('amount'))['t'] or 0
    fee_balance = total_owed - total_paid_amt
    overdue_invoices = invoices.filter(
        status__in=['unpaid', 'partial', 'overdue'], due_date__lt=today
    ).count()

    unread_notifications = Notification.objects.filter(
        recipient=request.user, school=school, is_read=False
    ).order_by('-created_at')[:5]
    announcements = get_recent_announcements(school, ['students'], limit=4)

    context = {
        'role': 'student',
        'student': student,
        'current_term': current_term,
        'current_results': current_results,
        'subject_count': subject_count,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'best_subject': best_subject,
        'weak_subject': weak_subject,
        'current_average': current_average,
        'latest_summary': latest_summary,
        'previous_summary': previous_summary,
        'trend_delta': trend_delta,
        'term_summaries': term_summaries,
        'att_pct': att_pct,
        'att_total': att_total,
        'att_present': att_present,
        'att_absent': att_absent,
        'att_late': att_late,
        'fee_balance': fee_balance,
        'overdue_invoices': overdue_invoices,
        'announcements': announcements,
        'unread_notifications': unread_notifications,
        'today': today,
    }
    return render(request, 'analytics/dashboard_student.html', context)


@login_required
def api_chart_attendance(request):
    """JSON: last 7 days school attendance %"""
    school = get_default_school()
    today = date.today()
    data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        sessions = AttendanceSession.objects.filter(school=school, date=d)
        present = AttendanceRecord.objects.filter(session__in=sessions, status='present').count()
        total = AttendanceRecord.objects.filter(session__in=sessions).count()
        pct = round((present / total) * 100, 1) if total > 0 else 0
        data.append({'date': str(d), 'pct': pct, 'present': present, 'total': total})
    return JsonResponse({'data': data})


@login_required
def api_chart_fees(request):
    """JSON: fee collection summary by month (last 6 months)"""
    school = get_default_school()
    today = date.today()
    data = []
    for i in range(5, -1, -1):
        month = (today.month - i - 1) % 12 + 1
        year = today.year if today.month - i > 0 else today.year - 1
        collected = FeePayment.objects.filter(
            invoice__school=school,
            status='confirmed',
            payment_date__month=month,
            payment_date__year=year
        ).aggregate(t=Sum('amount'))['t'] or 0
        data.append({'month': f'{year}-{month:02d}', 'collected': float(collected)})
    return JsonResponse({'data': data})


@login_required
def docs_usage(request):
    """Standalone usage docs page that renders the in-app docs partial."""
    school = get_default_school()
    return render(request, 'analytics/docs_usage.html', {'school': school})


def dev_create_demo_headmaster(request):
    """Development helper: create a demo headmaster account and log in.
    Only works when settings.DEBUG is True.
    """
    if not settings.DEBUG:
        return HttpResponse('Not available', status=404)
    User = get_user_model()
    username = 'demo_headmaster'
    password = 'Headmaster123!'

    user, created = User.objects.get_or_create(username=username, defaults={'email': 'demo_headmaster@example.com'})
    if created:
        user.set_password(password)
        user.is_active = True
        user.save()
    else:
        # Ensure password is known for demo (overwrite)
        user.set_password(password)
        user.save()

    # Attach to default school
    school = get_default_school()
    from schools.models import SchoolUser
    su, _ = SchoolUser.objects.get_or_create(user=user, school=school, defaults={'role': 'headmaster', 'is_active': True})
    if su.role != 'headmaster':
        su.role = 'headmaster'
        su.is_active = True
        su.save()

    # Log the user in
    auth_login(request, user)

    # Provide a short HTML response with credentials and a link to dashboard
    html = f"""
    <div style='font-family:system-ui,Arial;margin:30px'>
      <h3>Demo Headmaster Created</h3>
      <p>Username: <strong>{username}</strong></p>
      <p>Password: <strong>{password}</strong></p>
      <p><a href='""" + (settings.LOGIN_REDIRECT_URL or '/analytics/') + """'>Open Headmaster Dashboard</a></p>
    </div>
    """
    return HttpResponse(html)


@login_required
@require_POST
def create_senior_account(request):
    """Create a senior account and attach to the default school. POST-only, director users only.
    Expects JSON or form data: username (optional), email (required), first_name (optional), last_name (optional)
    Returns JSON: {'ok': True, 'username': ..., 'password': ...} on success
    """
    school = get_default_school()
    if not school:
        return JsonResponse({'ok': False, 'error': 'No school configured'}, status=400)

    # Directors can be stored as either admin or headmaster memberships.
    from schools.models import SchoolUser
    can_create_senior = SchoolUser.objects.filter(
        user=request.user,
        school=school,
        role__in=['admin', 'headmaster'],
        is_active=True,
    ).exists()
    if not can_create_senior and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    data = request.POST or request.body
    # prefer POST form fields
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()

    if not email:
        return JsonResponse({'ok': False, 'error': 'Email is required'}, status=400)

    User = get_user_model()
    if not username:
        username = email

    # ensure uniqueness
    base = username
    i = 1
    while User.objects.filter(username=username).exclude(email__iexact=email).exists():
        username = f"{base}{i}"
        i += 1

    # generate a secure random password
    password = get_random_string(12)

    # create or update user
    user = User.objects.filter(email__iexact=email).first()
    if user:
        created = False
    else:
        user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'first_name': first_name, 'last_name': last_name})
    if created:
        user.set_password(password)
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.save()
    else:
        # if user exists, set a new password and update fields
        user.set_password(password)
        user.email = email or user.email
        if first_name: user.first_name = first_name
        if last_name: user.last_name = last_name
        user.is_active = True
        user.save()

    # attach SchoolUser
    su, _ = SchoolUser.objects.get_or_create(user=user, school=school, defaults={'role': 'senior', 'is_active': True})
    if su.role != 'senior' or not su.is_active:
        su.role = 'senior'
        su.is_active = True
        su.save()

    return JsonResponse({'ok': True, 'username': user.username, 'password': password})
