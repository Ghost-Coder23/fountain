from core.utils import get_default_school
"""
Reports views - PDF report card generation
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse
from django.contrib import messages
import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from academics.models import Student, ClassSection
from results.models import Term, StudentResult, TermSummary
from .models import ReportCardTemplate, GeneratedReport
from schools.models import SchoolUser, School


def get_grade_color(grade):
    colors_map = {
        'A': colors.HexColor('#16a34a'),
        'B': colors.HexColor('#2563eb'),
        'C': colors.HexColor('#d97706'),
        'D': colors.HexColor('#dc2626'),
        'F': colors.HexColor('#7f1d1d'),
    }
    return colors_map.get(grade[0] if grade else 'F', colors.gray)


@login_required
def generate_report_card(request, student_id, term_id):
    school = get_default_school()
    student = get_object_or_404(Student, id=student_id, school=school)
    term = get_object_or_404(Term, id=term_id, academic_year__school=school)

    results = StudentResult.objects.filter(
        student=student,
        term=term,
        status__in=['approved', 'locked']
    ).select_related('subject').order_by('subject__name')

    try:
        summary = TermSummary.objects.get(student=student, term=term)
    except TermSummary.DoesNotExist:
        summary = None

    template = ReportCardTemplate.objects.filter(school=school, is_default=True).first()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    story = []
    styles = getSampleStyleSheet()

    # School theme color
    theme_hex = school.theme_color or '#4F46E5'
    theme_color = colors.HexColor(theme_hex)

    title_style = ParagraphStyle('SchoolTitle', parent=styles['Title'],
        fontSize=18, textColor=theme_color, alignment=TA_CENTER, spaceAfter=2)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#6b7280'))
    heading_style = ParagraphStyle('Heading', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold', textColor=theme_color, spaceAfter=4)
    normal_style = ParagraphStyle('Normal2', parent=styles['Normal'], fontSize=9)
    center_style = ParagraphStyle('Center', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)

    # Header
    story.append(Paragraph(school.name.upper(), title_style))
    if school.motto:
        story.append(Paragraph(f'"{school.motto}"', subtitle_style))
    if school.address:
        story.append(Paragraph(school.address, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=theme_color))
    story.append(Spacer(1, 0.3*cm))

    report_title = ParagraphStyle('ReportTitle', parent=styles['Normal'],
        fontSize=13, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=6)
    story.append(Paragraph('STUDENT ACADEMIC REPORT CARD', report_title))
    story.append(Paragraph(f'{term.name} — {term.academic_year.name}', center_style))
    story.append(Spacer(1, 0.4*cm))

    # Student info table
    full_name = student.user.get_full_name()
    class_name = str(student.current_class) if student.current_class else 'N/A'
    position_str = f"{summary.class_position}" if summary and summary.class_position else 'N/A'
    average_str = f"{summary.average:.1f}%" if summary else 'N/A'

    info_data = [
        [Paragraph('<b>Student Name:</b>', normal_style), Paragraph(full_name, normal_style),
         Paragraph('<b>Admission No:</b>', normal_style), Paragraph(student.admission_number, normal_style)],
        [Paragraph('<b>Class:</b>', normal_style), Paragraph(class_name, normal_style),
         Paragraph('<b>Gender:</b>', normal_style), Paragraph(student.get_gender_display(), normal_style)],
        [Paragraph('<b>Class Position:</b>', normal_style), Paragraph(position_str, normal_style),
         Paragraph('<b>Average Score:</b>', normal_style), Paragraph(average_str, normal_style)],
    ]

    info_table = Table(info_data, colWidths=[3.5*cm, 6*cm, 3.5*cm, 5*cm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fafb')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))

    # Results table
    story.append(Paragraph('ACADEMIC PERFORMANCE', heading_style))

    result_header = [
        Paragraph('<b>Subject</b>', normal_style),
        Paragraph('<b>CA (30%)</b>', center_style),
        Paragraph('<b>Exam (70%)</b>', center_style),
        Paragraph('<b>Total</b>', center_style),
        Paragraph('<b>Grade</b>', center_style),
        Paragraph('<b>Position</b>', center_style),
        Paragraph('<b>Remark</b>', center_style),
    ]

    result_rows = [result_header]
    for r in results:
        grade_para = Paragraph(f'<font color="{get_grade_color(r.grade).hexval() if r.grade else "#000"}"><b>{r.grade or "-"}</b></font>', center_style)
        result_rows.append([
            Paragraph(r.subject.name, normal_style),
            Paragraph(f'{r.continuous_assessment:.1f}', center_style),
            Paragraph(f'{r.exam_score:.1f}', center_style),
            Paragraph(f'{r.total_score:.1f}', center_style),
            Paragraph(r.grade or '-', center_style),
            Paragraph(str(r.position) if r.position else '-', center_style),
            Paragraph(r.teacher_comment[:40] if r.teacher_comment else '-', normal_style),
        ])

    results_table = Table(result_rows, colWidths=[5*cm, 2*cm, 2.5*cm, 2*cm, 1.5*cm, 2*cm, 3*cm])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), theme_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(results_table)
    story.append(Spacer(1, 0.4*cm))

    # Summary section
    if summary:
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
        story.append(Spacer(1, 0.2*cm))

        summary_data = [
            [Paragraph('<b>Total Marks:</b>', normal_style), Paragraph(f'{summary.total_marks:.1f}', normal_style),
             Paragraph('<b>Average:</b>', normal_style), Paragraph(f'{summary.average:.1f}%', normal_style),
             Paragraph('<b>Overall Grade:</b>', normal_style), Paragraph(summary.overall_grade or '-', normal_style)],
        ]
        if summary.attendance_days:
            summary_data.append([
                Paragraph('<b>Attendance:</b>', normal_style), Paragraph(f'{summary.attendance_days} days', normal_style),
                Paragraph('', normal_style), Paragraph('', normal_style),
                Paragraph('', normal_style), Paragraph('', normal_style),
            ])

        sum_table = Table(summary_data, colWidths=[3*cm, 3*cm, 2.5*cm, 3*cm, 3.5*cm, 3*cm])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
            ('BOX', (0, 0), (-1, -1), 0.5, theme_color),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 0.3*cm))

        if summary.headmaster_comment:
            story.append(Paragraph('<b>Headmaster\'s Comment:</b>', heading_style))
            story.append(Paragraph(summary.headmaster_comment, normal_style))
            story.append(Spacer(1, 0.3*cm))

    # Signature section
    story.append(Spacer(1, 0.5*cm))

    # Try to find class teacher and headmaster signatures
    class_teacher_sig = None
    headmaster_sig = None

    if student.current_class and student.current_class.class_teacher:
        if student.current_class.class_teacher.signature:
            try:
                sig_path = student.current_class.class_teacher.signature.path
                if os.path.exists(sig_path):
                    class_teacher_sig = Image(sig_path, width=2.5*cm, height=1.2*cm)
            except Exception:
                pass

    headmaster = SchoolUser.objects.filter(school=school, role='headmaster', is_active=True).first()
    if headmaster and headmaster.signature:
        try:
            sig_path = headmaster.signature.path
            if os.path.exists(sig_path):
                headmaster_sig = Image(sig_path, width=2.5*cm, height=1.2*cm)
        except Exception:
            pass

    sig_row_1 = [
        class_teacher_sig if class_teacher_sig else Paragraph('_____________________', center_style),
        headmaster_sig if headmaster_sig else Paragraph('_____________________', center_style)
    ]

    sig_data = [
        sig_row_1,
        [Paragraph("Class Teacher's Signature", center_style), Paragraph("Headmaster's Signature", center_style)],
    ]

    if template and template.headmaster_name:
        sig_data.append(['', Paragraph(f'<b>{template.headmaster_name}</b>', center_style)])
    elif headmaster:
        sig_data.append(['', Paragraph(f'<b>{headmaster.user.get_full_name()}</b>', center_style)])

    sig_table = Table(sig_data, colWidths=[9*cm, 9*cm])
    sig_table.setStyle(TableStyle([
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(sig_table)

    # Footer
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e5e7eb')))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7,
        textColor=colors.HexColor('#9ca3af'), alignment=TA_CENTER)
    story.append(Paragraph(f'Generated on {datetime.now().strftime("%d %B %Y")} | {school.name} | Powered by AcademiaLink', footer_style))

    doc.build(story)
    buffer.seek(0)

    # Save to disk
    filename = f"report_{student.admission_number}_{term.id}.pdf"
    reports_dir = os.path.join('media', 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(buffer.getvalue())

    # Track in DB
    school_user = SchoolUser.objects.filter(user=request.user, school=school).first()
    GeneratedReport.objects.update_or_create(
        term_summary=summary,
        report_type='term',
        defaults={
            'pdf_file': f'reports/{filename}',
            'generated_by': school_user,
        }
    ) if summary else None

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student.user.get_full_name()}_{term.name}_Report.pdf"'
    return response


@login_required
def download_report(request, pk):
    report = get_object_or_404(GeneratedReport, pk=pk)
    report.download_count += 1
    report.save()
    return FileResponse(open(report.pdf_file.path, 'rb'), content_type='application/pdf')


@login_required
def generate_class_reports(request, class_id, term_id):
    """Generate reports for all students in a class as a zip"""
    import zipfile
    school = get_default_school()
    class_section = get_object_or_404(ClassSection, id=class_id, school=school)
    term = get_object_or_404(Term, id=term_id, academic_year__school=school)
    students = Student.objects.filter(current_class=class_section, school=school, is_active=True)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        for student in students:
            # Re-use the single-student generation logic
            fake_request = request
            pdf_response = generate_report_card(fake_request, student.id, term_id)
            if hasattr(pdf_response, 'content'):
                zf.writestr(f"{student.user.get_full_name()}_{term.name}.pdf", pdf_response.content)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{class_section}_{term.name}_Reports.zip"'
    return response
