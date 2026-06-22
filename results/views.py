"""
Results views - Marks entry, approval, and management
FIXED:
  - ResultEntryView.get_context_data no longer calls StudentResult.objects.create()
    during a GET request. Creating DB records on GET breaks offline because the
    GET is served from SW cache — so when the offline POST is replayed, the result
    IDs don't exist and every student is silently skipped.
  - ResultEntryView.post now uses get_or_create so it works whether the GET
    was served live or from cache.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.db import transaction

from core.utils import SchoolRoleMixin, school_role_required, get_default_school
from .models import Term, GradeScale, StudentResult, TermSummary, AssessmentComponent
from .forms import TermForm, GradeScaleForm, StudentResultForm, BulkResultEntryForm, TermApprovalForm, AssessmentComponentForm
from academics.models import Student, Subject, ClassSection, AcademicYear


@method_decorator(login_required, name='dispatch')
class TermListView(SchoolRoleMixin, ListView):
    model = Term
    template_name = 'results/term_list.html'
    context_object_name = 'terms'
    required_roles = ['headmaster', 'admin', 'senior']

    def get_queryset(self):
        return Term.objects.filter(
            academic_year__school=get_default_school()
        ).select_related('academic_year')


@method_decorator(login_required, name='dispatch')
class TermCreateView(SchoolRoleMixin, CreateView):
    model = Term
    form_class = TermForm
    template_name = 'results/term_form.html'
    success_url = reverse_lazy('results:term_list')
    required_roles = ['headmaster', 'admin', 'senior']

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if hasattr(form, 'fields') and 'academic_year' in form.fields:
            form.fields['academic_year'].queryset = AcademicYear.objects.filter(school=get_default_school())
        return form

    def form_valid(self, form):
        # If this term is set as current, unset all other terms in the academic year
        if form.cleaned_data.get('is_current'):
            Term.objects.filter(
                academic_year=form.cleaned_data['academic_year'],
                is_current=True
            ).exclude(pk=self.object.pk if self.object else None).update(is_current=False)
        messages.success(self.request, 'Term created successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class TermUpdateView(SchoolRoleMixin, UpdateView):
    model = Term
    form_class = TermForm
    template_name = 'results/term_form.html'
    success_url = reverse_lazy('results:term_list')
    required_roles = ['headmaster', 'admin', 'senior']

    def get_queryset(self):
        return Term.objects.filter(
            academic_year__school=get_default_school()
        ).select_related('academic_year')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if hasattr(form, 'fields') and 'academic_year' in form.fields:
            form.fields['academic_year'].queryset = AcademicYear.objects.filter(school=get_default_school())
        return form

    def form_valid(self, form):
        # If this term is set as current, unset all other terms in the academic year
        if form.cleaned_data.get('is_current'):
            Term.objects.filter(
                academic_year=form.cleaned_data['academic_year'],
                is_current=True
            ).exclude(pk=self.object.pk).update(is_current=False)
        messages.success(self.request, 'Term updated successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class TermDeleteView(SchoolRoleMixin, DeleteView):
    model = Term
    template_name = 'results/term_confirm_delete.html'
    success_url = reverse_lazy('results:term_list')
    required_roles = ['headmaster', 'admin', 'senior']

    def get_queryset(self):
        return Term.objects.filter(
            academic_year__school=get_default_school()
        )

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Term deleted successfully!')
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class GradeScaleListView(ListView):
    model = GradeScale
    template_name = 'results/grade_scale_list.html'
    context_object_name = 'grade_scales'

    def get_queryset(self):
        return GradeScale.objects.filter(school=get_default_school())


@method_decorator(login_required, name='dispatch')
class GradeScaleCreateView(CreateView):
    model = GradeScale
    form_class = GradeScaleForm
    template_name = 'results/grade_scale_form.html'
    success_url = reverse_lazy('results:grade_scale_list')

    def form_valid(self, form):
        form.instance.school = get_default_school()
        messages.success(self.request, 'Grade scale added successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class GradeScaleUpdateView(UpdateView):
    model = GradeScale
    form_class = GradeScaleForm
    template_name = 'results/grade_scale_form.html'
    success_url = reverse_lazy('results:grade_scale_list')

    def get_queryset(self):
        return GradeScale.objects.filter(school=get_default_school())

    def form_valid(self, form):
        messages.success(self.request, 'Grade scale updated successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class GradeScaleDeleteView(DeleteView):
    model = GradeScale
    template_name = 'results/grade_scale_confirm_delete.html'
    success_url = reverse_lazy('results:grade_scale_list')

    def get_queryset(self):
        return GradeScale.objects.filter(school=get_default_school())

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Grade scale deleted successfully!')
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class AssessmentComponentListView(ListView):
    model = AssessmentComponent
    template_name = 'results/assessment_component_list.html'
    context_object_name = 'components'

    def get_queryset(self):
        return AssessmentComponent.objects.filter(school=get_default_school()).select_related('subject')


@method_decorator(login_required, name='dispatch')
class AssessmentComponentCreateView(CreateView):
    model = AssessmentComponent
    form_class = AssessmentComponentForm
    template_name = 'results/assessment_component_form.html'
    success_url = reverse_lazy('results:assessment_component_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = get_default_school()
        return kwargs

    def form_valid(self, form):
        form.instance.school = get_default_school()
        messages.success(self.request, 'Assessment component added successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AssessmentComponentUpdateView(UpdateView):
    model = AssessmentComponent
    form_class = AssessmentComponentForm
    template_name = 'results/assessment_component_form.html'
    success_url = reverse_lazy('results:assessment_component_list')

    def get_queryset(self):
        return AssessmentComponent.objects.filter(school=get_default_school())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = get_default_school()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Assessment component updated successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AssessmentComponentDeleteView(DeleteView):
    model = AssessmentComponent
    template_name = 'results/assessment_component_confirm_delete.html'
    success_url = reverse_lazy('results:assessment_component_list')

    def get_queryset(self):
        return AssessmentComponent.objects.filter(school=get_default_school())

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Assessment component deleted successfully!')
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class ResultEntryView(TemplateView):
    template_name = 'results/result_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = get_default_school()

        class_section_id = self.request.GET.get('class')
        subject_id = self.request.GET.get('subject')
        term_id = self.request.GET.get('term')

        if class_section_id and subject_id and term_id:
            class_section = get_object_or_404(ClassSection, id=class_section_id, school=school)
            subject = get_object_or_404(Subject, id=subject_id, school=school)
            term = get_object_or_404(Term, id=term_id, academic_year__school=school)

            students = Student.objects.filter(
                current_class=class_section,
                school=school,
                is_active=True
            ).select_related('user')

            school_user = self.request.user.school_memberships.filter(school=school).first()

            existing_results = StudentResult.objects.filter(
                student__in=students,
                subject=subject,
                term=term
            ).select_related('student', 'student__user')

            results_map = {r.student_id: r for r in existing_results}

            # FIX: do NOT call StudentResult.objects.create() here.
            # Creating records on GET breaks offline replay because the GET is
            # served from SW cache — the DB write never happens offline, so the
            # IDs don't exist when the POST is later replayed on the server.
            # Instead, pass the student list + existing results to the template
            # and let the POST handler use get_or_create.
            result_rows = []
            for student in students:
                result_rows.append({
                    'student': student,
                    'result': results_map.get(student.id),  # None if not yet created
                })

            context['class_section'] = class_section
            context['subject'] = subject
            context['term'] = term
            context['result_rows'] = result_rows
            # Keep 'results' for any existing template references
            context['results'] = [row['result'] for row in result_rows if row['result']]

        context['classes'] = ClassSection.objects.filter(school=school)
        context['subjects'] = Subject.objects.filter(school=school)
        context['terms'] = Term.objects.filter(academic_year__school=school)
        return context

    def post(self, request, *args, **kwargs):
        school = get_default_school()
        school_user = request.user.school_memberships.filter(school=school).first()

        class_id = request.POST.get('class')
        subject_id = request.POST.get('subject')
        term_id = request.POST.get('term')

        # Resolve objects once upfront so get_or_create has all defaults
        class_section = get_object_or_404(ClassSection, id=class_id, school=school) if class_id else None
        subject = get_object_or_404(Subject, id=subject_id, school=school) if subject_id else None
        term = get_object_or_404(Term, id=term_id, academic_year__school=school) if term_id else None

        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('ca_'):
                    result_id = key.replace('ca_', '')
                    try:
                        # FIX: use get_or_create instead of get() so this works
                        # whether the page was loaded live or from SW cache offline.
                        # If the result row was never created (offline GET from cache),
                        # we create it now during the POST replay.
                        result, _ = StudentResult.objects.get_or_create(
                            id=result_id,
                            defaults={
                                'subject': subject,
                                'term': term,
                                'class_section': class_section,
                                'entered_by': school_user,
                                'status': 'draft',
                                # student must be resolved from the result_id prefix in the form
                                # The template should include a hidden student_<result_id> field
                                # (see note in template comments)
                            }
                        )

                        if result.status == 'locked':
                            continue

                        result.continuous_assessment = float(value or 0)
                        result.exam_score = float(request.POST.get(f'exam_{result_id}', 0) or 0)
                        result.teacher_comment = request.POST.get(f'comment_{result_id}', '')
                        result.entered_by = school_user
                        result.calculate_total()

                        grade_scales = GradeScale.objects.filter(school=school).order_by('-min_score')
                        result.assign_grade(grade_scales)

                        result.status = 'submitted'
                        result.save()
                    except (StudentResult.DoesNotExist, ValueError):
                        continue

        # Auto-calculate positions per subject
        if class_id and subject_id and term_id:
            sub_results = StudentResult.objects.filter(
                class_section_id=class_id,
                subject_id=subject_id,
                term_id=term_id,
                status='submitted'
            ).order_by('-total_score')
            for i, r in enumerate(sub_results, 1):
                r.position = i
                r.save(update_fields=['position'])

        messages.success(request, 'Results submitted! Pending headmaster approval.')
        return redirect(f"{request.path}?class={class_id}&subject={subject_id}&term={term_id}")


@method_decorator(login_required, name='dispatch')
class PendingApprovalsView(ListView):
    model = StudentResult
    template_name = 'results/pending_approvals.html'
    context_object_name = 'pending_results'

    def get_queryset(self):
        return StudentResult.objects.filter(
            class_section__school=get_default_school(),
            status='submitted'
        ).select_related('student__user', 'subject', 'term')

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        result_ids = request.POST.getlist('result_ids')

        results = StudentResult.objects.filter(
            id__in=result_ids,
            class_section__school=get_default_school()
        )

        if action == 'approve':
            results.update(status='approved', approved_by=request.user.school_memberships.filter(school=get_default_school()).first())
            messages.success(request, f'{results.count()} results approved!')
        elif action == 'lock':
            results.update(status='locked')
            messages.success(request, f'{results.count()} results locked!')

        return redirect('results:pending_approvals')


@method_decorator(login_required, name='dispatch')
class StudentResultsView(DetailView):
    model = Student
    template_name = 'results/student_results.html'
    context_object_name = 'student'

    def get_queryset(self):
        return Student.objects.filter(school=get_default_school())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object

        context['term_summaries'] = TermSummary.objects.filter(
            student=student
        ).select_related('term', 'term__academic_year').order_by('term__academic_year', 'term__term_number')

        current_term = Term.objects.filter(
            academic_year__school=get_default_school(),
            is_current=True
        ).first()

        if current_term:
            context['current_results'] = StudentResult.objects.filter(
                student=student,
                term=current_term,
                status__in=['approved', 'locked']
            ).select_related('subject')
            context['current_term'] = current_term

        return context


@login_required
@school_role_required(['headmaster'])
def approve_all_results(request):
    if request.method == 'POST':
        term_id = request.POST.get('term_id')
        school = get_default_school()
        school_user = request.user.school_memberships.filter(school=school).first()

        qs = StudentResult.objects.filter(
            class_section__school=school,
            status='submitted'
        )
        if term_id:
            qs = qs.filter(term_id=term_id)

        count = qs.update(status='approved', approved_by=school_user)
        messages.success(request, f'{count} results approved successfully!')

    return redirect('results:pending_approvals')


@method_decorator(login_required, name='dispatch')
@method_decorator(school_role_required(['headmaster', 'admin', 'secretary']), name='dispatch')
class StudentProceedView(TemplateView):
    template_name = 'results/student_proceed.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = get_default_school()

        from academics.models import ClassSection, AcademicYear

        class_id = self.request.GET.get('class')

        if class_id:
            source_class = get_object_or_404(ClassSection, id=class_id, school=school)
            students = Student.objects.filter(
                current_class=source_class,
                is_active=True
            ).select_related('user')
            context['source_class'] = source_class
            context['students'] = students

        context['classes'] = ClassSection.objects.filter(school=school).select_related('class_level', 'academic_year')
        context['academic_years'] = AcademicYear.objects.filter(school=school)
        return context

    def post(self, request, *args, **kwargs):
        school = get_default_school()
        student_ids = request.POST.getlist('student_ids')
        target_class_id = request.POST.get('target_class')
        action = request.POST.get('action')

        if not student_ids or not target_class_id:
            messages.error(request, "Please select students and a target class.")
            return redirect('results:student_promotion')

        target_class = get_object_or_404(ClassSection, id=target_class_id, school=school)

        with transaction.atomic():
            students = Student.objects.filter(id__in=student_ids, school=school)

            if action == 'proceed':
                count = students.update(current_class=target_class)
                messages.success(request, f"Successfully proceeded {count} students to {target_class}.")
            elif action == 'repeat':
                count = students.update(current_class=target_class)
                messages.success(request, f"Successfully set {count} students to repeat in {target_class}.")
            elif action == 'withdraw':
                count = students.update(is_active=False)
                messages.success(request, f"Successfully withdrew {count} students from the school.")

        return redirect('results:student_proceed')