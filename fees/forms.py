"""Fees forms"""
from django import forms
from django.utils import timezone
from datetime import time, datetime
import pytz
from .models import FeeStructure, FeeInvoice, FeePayment, PaymentConfig, Expense, ExpenseCategory
from academics.models import ClassLevel, AcademicYear
from results.models import Term


class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['name', 'class_level', 'academic_year', 'billing_cycle', 'term', 'month', 'amount', 'currency', 'is_mandatory', 'due_date', 'description']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, school=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['class_level'].queryset = ClassLevel.objects.filter(school=school)
            self.fields['class_level'].empty_label = "All Classes"
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['term'].queryset = Term.objects.filter(academic_year__school=school)
            self.fields['term'].empty_label = "All Terms"
            self.fields['month'].empty_label = "All Months"
            self.fields['class_level'].required = False
            self.fields['term'].required = False
            self.fields['month'].required = False


class FeeInvoiceForm(forms.ModelForm):
    class Meta:
        model = FeeInvoice
        fields = ['student', 'fee_structure', 'academic_year', 'term', 'billing_month', 'billing_year', 'amount', 'currency', 'due_date', 'notes']
        labels = {
            'billing_month': 'Billing Month',
            'billing_year': 'Billing Year',
        }
        widgets = {
            'student': forms.Select(attrs={'class': 'searchable-select'}),
            'fee_structure': forms.Select(attrs={'class': 'searchable-select'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'billing_year': forms.NumberInput(attrs={'min': 2000, 'max': 2100}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, school=None, selected_period=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from academics.models import Student
            self.fields['student'].queryset = Student.objects.filter(school=school, is_active=True).select_related('user')
            self.fields['fee_structure'].queryset = FeeStructure.objects.filter(school=school)
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['term'].queryset = Term.objects.filter(academic_year__school=school)
            self.fields['fee_structure'].required = False
            self.fields['academic_year'].required = False
            self.fields['term'].required = False
            self.fields['billing_month'].required = False
            self.fields['billing_year'].required = False

        if selected_period and not self.is_bound:
            if selected_period.get('academic_year'):
                self.fields['academic_year'].initial = selected_period['academic_year']
            if selected_period.get('term'):
                self.fields['term'].initial = selected_period['term']
            if selected_period['scope'] == 'month':
                self.fields['billing_month'].initial = selected_period['month']
                self.fields['billing_year'].initial = selected_period['year']

    def clean(self):
        cleaned = super().clean()
        month = cleaned.get('billing_month')
        year = cleaned.get('billing_year')
        term = cleaned.get('term')

        if month and not year:
            self.add_error('billing_year', 'Enter a billing year for this month.')
        if year and not month:
            self.add_error('billing_month', 'Select a billing month for this year.')
        if not month and not term:
            raise forms.ValidationError('Select either a billing month/year or a term for this invoice.')
        return cleaned


class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['amount', 'currency', 'method', 'reference', 'payment_date', 'notes']
        labels = {
            'reference': 'Receipt Number'
        }
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def clean_payment_date(self):
        date_obj = self.cleaned_data.get('payment_date')
        if date_obj:
            tz = pytz.timezone('Africa/Harare')
            dt = tz.localize(datetime.combine(date_obj, time(12, 0)))
            self.instance.payment_date = dt
        else:
            self.instance.payment_date = timezone.now()
        return self.cleaned_data.get('payment_date')


class PaymentConfigForm(forms.ModelForm):
    class Meta:
        model = PaymentConfig
        fields = [
            'paynow_integration_id', 'paynow_integration_key', 'paynow_result_url', 'paynow_return_url',
            'accept_cash', 'accept_paynow', 'accept_ecocash', 'accept_bank_transfer', 'bank_name', 'bank_account_number', 'bank_branch',
            'auto_generate_invoices', 'invoice_generation_day'
        ]


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['category', 'title', 'amount', 'currency', 'date', 'reference', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, school=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['category'].queryset = ExpenseCategory.objects.filter(school=school)


class QuickPaymentForm(forms.Form):
    """Combines invoice creation and payment in one step"""
    student = forms.ModelChoiceField(queryset=None, widget=forms.Select(attrs={'class': 'searchable-select'}))
    fee_structure = forms.ModelChoiceField(queryset=None, required=False, help_text="Select a fee structure to auto-fill details", widget=forms.Select(attrs={'class': 'searchable-select'}))
    academic_year = forms.ModelChoiceField(queryset=None, required=False)
    term = forms.ModelChoiceField(queryset=None, required=False)
    billing_month = forms.ChoiceField(choices=[('', 'Whole Term')] + FeeStructure.MONTH_CHOICES, required=False, label='Billing Month')
    billing_year = forms.IntegerField(required=False, min_value=2000, max_value=2100, label='Billing Year')
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    currency = forms.ChoiceField(choices=FeeStructure.CURRENCY_CHOICES)
    method = forms.ChoiceField(choices=FeePayment.METHOD_CHOICES)
    reference = forms.CharField(max_length=100, required=False, label="Receipt Number")
    payment_date = forms.DateField(initial=timezone.now, widget=forms.DateInput(attrs={'type': 'date'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, school=None, selected_period=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from academics.models import Student
            self.fields['student'].queryset = Student.objects.filter(school=school, is_active=True).select_related('user')
            self.fields['fee_structure'].queryset = FeeStructure.objects.filter(school=school)
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school)
            self.fields['term'].queryset = Term.objects.filter(academic_year__school=school)

        if selected_period and not self.is_bound:
            if selected_period.get('academic_year'):
                self.fields['academic_year'].initial = selected_period['academic_year']
            if selected_period.get('term'):
                self.fields['term'].initial = selected_period['term']
            if selected_period['scope'] == 'month':
                self.fields['billing_month'].initial = selected_period['month']
                self.fields['billing_year'].initial = selected_period['year']

    def clean(self):
        cleaned = super().clean()
        month = cleaned.get('billing_month')
        year = cleaned.get('billing_year')
        term = cleaned.get('term')
        if month:
            cleaned['billing_month'] = int(month)
            if not year:
                self.add_error('billing_year', 'Enter a billing year for this month.')
        elif year:
            self.add_error('billing_month', 'Select a billing month for this year.')
        elif not term:
            raise forms.ValidationError('Select either a billing month/year or a term for this payment invoice.')
        return cleaned
