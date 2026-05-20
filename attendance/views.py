"""
Attendance views - Mark and view attendance
FIXED:
  - notify_absences moved outside transaction.atomic() so a notification
    failure can no longer roll back saved attendance records.
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from .models import AttendanceSession, AttendanceRecord
from .forms import AttendanceSessionForm
from academics.models import ClassSection, Student
from schools.models import SchoolUser
from core.utils import export_to_excel, export_to_csv, get_default_school


@login_required
def attendance_home(request):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    today = date.today()

    if school_user and school_user.role == 'teacher':
        classes = ClassSection.objects.filter(
            school=school,
            teacher_subjects__teacher=school_user
        ).distinct()
    else:
        classes = ClassSection.objects.filter(school=school)

    today_sessions = AttendanceSession.objects.filter(
        school=school, date=today
    ).select_related('class_section', 'marked_by__user')

    recent_sessions = AttendanceSession.objects.filter(
        school=school,
        date__gte=today - timedelta(days=7)
    ).select_related('class_section').order_by('-date')[:20]

    context = {
        'classes': classes,
        'today_sessions': today_sessions,
        'recent_sessions': recent_sessions,
        'today': today,
    }
    return render(request, 'attendance/attendance_home.html', context)


@login_required
def mark_attendance(request, class_id):
    school = get_default_school()
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    class_section = get_object_or_404(ClassSection, id=class_id, school=school)

    selected_date = request.GET.get('date', str(date.today()))
    try:
        selected_date = date.fromisoformat(selected_date)
    except ValueError:
        selected_date = date.today()

    session, created = AttendanceSession.objects.get_or_create(
        class_section=class_section,
        date=selected_date,
        defaults={'school': school, 'marked_by': school_user}
    )

    students = Student.objects.filter(
        current_class=class_section, school=school, is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    existing = {r.student_id: r for r in session.records.all()}

    if request.method == 'POST':
        # FIX: keep the atomic block only for DB writes.
        # notify_absences is outside so a notification error never
        # rolls back attendance that was already saved.
        absent_students = []
        with transaction.atomic():
            for student in students:
                status = request.POST.get(f'status_{student.id}', 'present')
                notes = request.POST.get(f'notes_{student.id}', '')
                AttendanceRecord.objects.update_or_create(
                    session=session,
                    student=student,
                    defaults={'status': status, 'notes': notes}
                )
                if status == 'absent':
                    absent_students.append(student)

            session.is_finalized = True
            session.marked_by = school_user
            session.save()

        # FIX: notifications run after commit, failure is non-fatal
        try:
            from notifications.utils import notify_absences
            notify_absences(school, session, absent_students)
        except Exception as e:
            # Log but don't surface to user — attendance is already saved
            import logging
            logging.getLogger(__name__).warning(
                f'notify_absences failed for session {session.id}: {e}'
            )

        messages.success(request, f'Attendance saved for {class_section} on {selected_date}.')
        return redirect('attendance:home')

    student_records = []
    for s in students:
        student_records.append({
            'student': s,
            'record': existing.get(s.id),
        })

    context = {
        'class_section': class_section,
        'session': session,
        'student_records': student_records,
        'selected_date': selected_date,
        'is_finalized': session.is_finalized,
    }
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
def attendance_report(request):
    school = get_default_school()
    class_id = request.GET.get('class')
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)

    classes = ClassSection.objects.filter(school=school)
    sessions = []
    students = []
    matrix = {}

    if class_id:
        class_section = get_object_or_404(ClassSection, id=class_id, school=school)
        sessions = AttendanceSession.objects.filter(
            class_section=class_section,
            date__month=month,
            date__year=year
        ).order_by('date')
        students = Student.objects.filter(
            current_class=class_section, school=school, is_active=True
        ).select_related('user').order_by('user__last_name')

        for student in students:
            matrix[student.id] = {}
            for session in sessions:
                rec = session.records.filter(student=student).first()
                matrix[student.id][session.id] = rec.status if rec else '-'

    context = {
        'classes': classes,
        'sessions': sessions,
        'students': students,
        'matrix': matrix,
        'selected_class': int(class_id) if class_id else None,
        'month': int(month),
        'year': int(year),
    }
    return render(request, 'attendance/attendance_report.html', context)


@login_required
def session_detail(request, session_id):
    school = get_default_school()
    session = get_object_or_404(AttendanceSession, id=session_id, school=school)
    records = session.records.select_related('student__user').order_by('student__user__last_name')
    context = {'session': session, 'records': records, 'summary': session.get_summary()}
    return render(request, 'attendance/session_detail.html', context)


@login_required
def export_attendance(request, format='excel'):
    """Export attendance report to Excel or CSV"""
    school = get_default_school()
    class_id = request.GET.get('class')
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    if not class_id:
        messages.warning(request, 'Please select a class first.')
        return redirect('attendance:report')
    
    class_section = get_object_or_404(ClassSection, id=class_id, school=school)
    sessions = AttendanceSession.objects.filter(
        class_section=class_section,
        date__month=month,
        date__year=year
    ).order_by('date')
    students = Student.objects.filter(
        current_class=class_section, school=school, is_active=True
    ).select_related('user').order_by('user__last_name')
    
    # Prepare headers
    headers = ['Student', 'Admission No.']
    for session in sessions:
        headers.append(session.date.strftime('%Y-%m-%d'))
    
    # Prepare data
    data = []
    for student in students:
        row = [
            student.user.get_full_name(),
            student.admission_number
        ]
        for session in sessions:
            rec = session.records.filter(student=student).first()
            row.append(rec.status.upper() if rec else '-')
        data.append(row)
    
    filename = f"attendance_{class_section.class_name}_{year}_{month}.xlsx" if format == 'excel' else f"attendance_{class_section.class_name}_{year}_{month}.csv"
    
    if format == 'excel':
        return export_to_excel(data, headers, filename)
    else:
        return export_to_csv(data, headers, filename)