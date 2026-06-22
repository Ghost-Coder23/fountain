"""Results forms"""
from django import forms
from .models import Term, GradeScale, StudentResult, TermSummary, AssessmentComponent


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ['academic_year', 'term_number', 'name', 'start_date', 'end_date', 'is_current']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        academic_year = cleaned_data.get('academic_year')
        term_number = cleaned_data.get('term_number')

        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError("Start date must be before end date.")

        # Check for term_number uniqueness within the same academic year
        if academic_year and term_number:
            # Exclude the current instance if we're updating
            queryset = Term.objects.filter(
                academic_year=academic_year,
                term_number=term_number
            )
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise forms.ValidationError(
                    f"Term {term_number} already exists for this academic year."
                )

        # If setting is_current=True, make sure we handle other current terms in the academic year
        if cleaned_data.get('is_current'):
            other_terms = Term.objects.filter(
                academic_year=academic_year,
                is_current=True
            )
            if self.instance.pk:
                other_terms = other_terms.exclude(pk=self.instance.pk)
            if other_terms.exists():
                # We'll automatically unset is_current on other terms instead of raising an error
                pass

        return cleaned_data


class GradeScaleForm(forms.ModelForm):
    class Meta:
        model = GradeScale
        fields = ['grade', 'min_score', 'max_score', 'description']


class AssessmentComponentForm(forms.ModelForm):
    class Meta:
        model = AssessmentComponent
        fields = ['name', 'subject', 'weight', 'order']
        
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            from academics.models import Subject
            self.fields['subject'].queryset = Subject.objects.filter(school=school)
            self.fields['subject'].required = False


class StudentResultForm(forms.ModelForm):
    class Meta:
        model = StudentResult
        fields = ['continuous_assessment', 'exam_score', 'teacher_comment']
        widgets = {
            'continuous_assessment': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.5}),
            'exam_score': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.5}),
            'teacher_comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional comment about student performance'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        ca = cleaned_data.get('continuous_assessment', 0)
        exam = cleaned_data.get('exam_score', 0)

        if ca < 0 or ca > 100:
            raise forms.ValidationError("Continuous Assessment must be between 0 and 100.")
        if exam < 0 or exam > 100:
            raise forms.ValidationError("Exam score must be between 0 and 100.")

        return cleaned_data


class BulkResultEntryForm(forms.Form):
    """Form for entering results for multiple students at once"""
    subject = forms.ModelChoiceField(queryset=None)
    class_section = forms.ModelChoiceField(queryset=None)
    term = forms.ModelChoiceField(queryset=None)

    def __init__(self, school=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from academics.models import Subject, ClassSection
            from .models import Term
            self.fields['subject'].queryset = Subject.objects.filter(school=school)
            self.fields['class_section'].queryset = ClassSection.objects.filter(school=school)
            self.fields['term'].queryset = Term.objects.filter(academic_year__school=school)


class TermApprovalForm(forms.Form):
    """Form for headmaster to approve/lock term results"""
    action = forms.ChoiceField(choices=[
        ('approve', 'Approve Results'),
        ('lock', 'Lock Results (Final)'),
    ])
    headmaster_comment = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False,
        help_text="Optional comment to appear on all report cards"
    )
