from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from django.db import transaction
from fees.models import FeeStructure, FeeInvoice, PaymentConfig
from academics.models import Student
from core.utils import get_default_school
from results.models import Term

class Command(BaseCommand):
    help = 'Generate monthly invoices for schools with auto generation enabled'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Year for invoices (defaults to current year)')
        parser.add_argument('--month', type=int, help='Month for invoices (1-12). Defaults to current month')
        parser.add_argument('--school', type=int, help='Specific school id to generate for')

    def handle(self, *args, **options):
        today = timezone.now().date()
        year = options.get('year') or today.year
        month = options.get('month') or today.month
        school_id = options.get('school')

        # Get fee structures for target month (monthly billing) and schools with auto enabled
        structs = FeeStructure.objects.filter(billing_cycle='monthly')
        if school_id:
            structs = structs.filter(school_id=school_id)

        processed = 0
        for s in structs.select_related('school'):
            try:
                config = s.school.payment_config
            except PaymentConfig.DoesNotExist:
                continue
            if not config.auto_generate_invoices:
                continue
            if config.invoice_generation_day != today.day and (not options.get('month')):
                # If called without --month, only run on the configured day
                continue

            # Determine which students should receive this structure
            students_qs = Student.objects.filter(school=s.school, is_active=True)
            if s.class_level:
                students_qs = students_qs.filter(current_class__class_level=s.class_level)

            for student in students_qs:
                # Avoid creating duplicate invoice for same student/structure/month
                invoice_number = f"{year}{month:02d}{s.school.id}{student.admission_number}"
                if FeeInvoice.objects.filter(
                    school=s.school,
                    student=student,
                    fee_structure=s,
                    billing_month=month,
                    billing_year=year,
                ).exists() or FeeInvoice.objects.filter(invoice_number=invoice_number).exists():
                    continue
                billing_start = date(year, month, 1)
                term = s.term or Term.objects.filter(
                    academic_year=s.academic_year,
                    start_date__lte=billing_start,
                    end_date__gte=billing_start,
                ).first()
                with transaction.atomic():
                    inv = FeeInvoice.objects.create(
                        school=s.school,
                        student=student,
                        fee_structure=s,
                        academic_year=s.academic_year,
                        term=term,
                        billing_month=month,
                        billing_year=year,
                        invoice_number=invoice_number,
                        amount=s.amount,
                        currency=s.currency,
                        due_date=s.due_date or date(year, month, min(config.invoice_generation_day,28)),
                        issued_date=date(year, month, 1),
                        created_by=None,
                    )
                    processed += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {processed} invoices'))
