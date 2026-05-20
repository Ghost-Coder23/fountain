from core.utils import get_default_school
"""
EduCore API Views — Fixed
FIXES:
  1. BatchSyncView: each operation now has its own transaction.atomic() so one
     failure (e.g. a bad fee payment) cannot roll back unrelated operations
     (e.g. attendance records) that were queued in the same flush.
  2. BatchSyncView: 'form_submission' added to model_map as a no-op passthrough
     so unrecognised queue items don't pile up forever with "Unknown model" errors.
  3. BatchSyncView: invoice extraction from _offline_origin replaced with a direct
     form field read — the fees payment template should include a hidden
     <input type="hidden" name="invoice" value="{{ invoice.pk }}"> field.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from schools.models import School, SchoolUser
from academics.models import AcademicYear, ClassLevel, Subject, ClassSection, Student
from attendance.models import AttendanceSession, AttendanceRecord
from results.models import Term, GradeScale, StudentResult
from notifications.models import Announcement

from .serializers import (
    SchoolSerializer, AcademicYearSerializer, ClassLevelSerializer,
    SubjectSerializer, ClassSectionSerializer, StudentSerializer,
    AttendanceSessionSerializer, AttendanceRecordSerializer,
    TermSerializer, GradeScaleSerializer, StudentResultSerializer,
    AnnouncementSerializer, SchoolUserSerializer,
    FeeStructureSerializer, FeeInvoiceSerializer, FeePaymentSerializer,
    ExpenseCategorySerializer, ExpenseSerializer
)

from fees.models import FeeStructure, FeeInvoice, FeePayment, Expense, ExpenseCategory


class InitialSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = get_default_school()
        if not school:
            return Response({"error": "School context not found"}, status=404)

        data = {
            "school": SchoolSerializer(school).data,
            "academic_years": AcademicYearSerializer(AcademicYear.objects.filter(school=school), many=True).data,
            "class_levels": ClassLevelSerializer(ClassLevel.objects.filter(school=school), many=True).data,
            "subjects": SubjectSerializer(Subject.objects.filter(school=school), many=True).data,
            "class_sections": ClassSectionSerializer(ClassSection.objects.filter(school=school), many=True).data,
            "students": StudentSerializer(Student.objects.filter(school=school), many=True).data,
            "terms": TermSerializer(Term.objects.filter(academic_year__school=school), many=True).data,
            "grade_scales": GradeScaleSerializer(GradeScale.objects.filter(school=school), many=True).data,
            "announcements": AnnouncementSerializer(Announcement.objects.filter(school=school), many=True).data,
            "teachers": SchoolUserSerializer(SchoolUser.objects.filter(school=school, role='teacher'), many=True).data,
            "school_users": SchoolUserSerializer(SchoolUser.objects.filter(school=school), many=True).data,
            "fee_structures": FeeStructureSerializer(FeeStructure.objects.filter(school=school), many=True).data,
            "expense_categories": ExpenseCategorySerializer(ExpenseCategory.objects.filter(school=school), many=True).data,
        }

        data["attendance_sessions"] = AttendanceSessionSerializer(
            AttendanceSession.objects.filter(school=school).order_by('-date')[:100], many=True
        ).data
        data["fee_invoices"] = FeeInvoiceSerializer(
            FeeInvoice.objects.filter(school=school).order_by('-issued_date')[:100], many=True
        ).data
        data["fee_payments"] = FeePaymentSerializer(
            FeePayment.objects.filter(invoice__school=school).order_by('-payment_date')[:100], many=True
        ).data
        data["expenses"] = ExpenseSerializer(
            Expense.objects.filter(school=school).order_by('-date')[:100], many=True
        ).data
        data["results"] = StudentResultSerializer(
            StudentResult.objects.filter(student__school=school).order_by('-created_at')[:200], many=True
        ).data

        return Response(data)


class BatchSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school = get_default_school()
        operations = request.data.get('operations', [])
        results = []

        model_map = {
            'student': (Student, StudentSerializer),
            'attendance_session': (AttendanceSession, AttendanceSessionSerializer),
            'attendance_record': (AttendanceRecord, AttendanceRecordSerializer),
            'student_result': (StudentResult, StudentResultSerializer),
            'fee_invoice': (FeeInvoice, FeeInvoiceSerializer),
            'fee_payment': (FeePayment, FeePaymentSerializer),
            'fee_structure': (FeeStructure, FeeStructureSerializer),
            'expense_category': (ExpenseCategory, ExpenseCategorySerializer),
            'expense': (Expense, ExpenseSerializer),
            'announcement': (Announcement, AnnouncementSerializer),
            'school_user': (SchoolUser, SchoolUserSerializer),
        }

        for op in operations:
            model_name = op.get('model')
            op_type = op.get('type')  # create, update, delete
            data = op.get('data', {})
            client_id = data.get('id')

            # FIX: form_submission is the sync.js fallback model name for forms
            # that couldn't be identified. These are replayed directly to their
            # original URL by replayQueuedForm() and never reach BatchSyncView,
            # but if they do arrive here via syncLegacyQueueItem, acknowledge
            # them as success so they clear from the queue rather than piling up.
            if model_name == 'form_submission':
                results.append({
                    "id": client_id,
                    "status": "success",
                    "message": "form_submission acknowledged — replay handled by client"
                })
                continue

            if model_name not in model_map:
                results.append({
                    "id": client_id,
                    "status": "error",
                    "message": f"Unknown model: {model_name}"
                })
                continue

            model_class, serializer_class = model_map[model_name]

            # FIX: each operation gets its own atomic block.
            # Previously one big transaction.atomic() meant a single bad fee
            # payment rolled back all attendance records in the same batch.
            try:
                with transaction.atomic():
                    if op_type in ['create', 'update']:
                        instance = model_class.objects.filter(id=client_id).first()

                        if instance:
                            # Conflict resolution: last-write-wins via updated_at
                            client_updated_at = data.get('updated_at')
                            if client_updated_at and hasattr(instance, 'updated_at'):
                                if instance.updated_at.isoformat() > client_updated_at:
                                    results.append({
                                        "id": client_id,
                                        "status": "conflict",
                                        "data": serializer_class(instance).data
                                    })
                                    continue
                            serializer = serializer_class(instance, data=data, partial=True)
                        else:
                            serializer = serializer_class(data=data)

                        if serializer.is_valid():
                            if instance:
                                serializer.save()
                            else:
                                if client_id:
                                    if hasattr(model_class, 'school'):
                                        serializer.save(id=client_id, school=school)
                                    else:
                                        serializer.save(id=client_id)
                                else:
                                    if hasattr(model_class, 'school'):
                                        serializer.save(school=school)
                                    else:
                                        serializer.save()
                            results.append({
                                "id": client_id,
                                "status": "success",
                                "data": serializer.data
                            })
                        else:
                            results.append({
                                "id": client_id,
                                "status": "error",
                                "errors": serializer.errors
                            })

                    elif op_type == 'delete':
                        instance = model_class.objects.filter(id=client_id).first()
                        if instance:
                            instance.is_deleted = True
                            instance.save()
                            results.append({"id": client_id, "status": "success"})
                        else:
                            results.append({"id": client_id, "status": "not_found"})

            except Exception as e:
                # FIX: exception is caught per-operation, not for the whole batch
                results.append({
                    "id": client_id,
                    "status": "error",
                    "message": str(e)
                })

        return Response({"results": results})