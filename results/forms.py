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
