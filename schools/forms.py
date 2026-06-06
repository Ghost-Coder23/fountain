"""Schools forms"""
from django import forms
from django.contrib.auth.models import User
from .models import School, SchoolUser


class SchoolRegistrationForm(forms.ModelForm):
    """Form for school self-registration"""
    headmaster_first_name = forms.CharField(max_length=100, label="Headmaster First Name")
    headmaster_last_name = forms.CharField(max_length=100, label="Headmaster Last Name")
    headmaster_email = forms.EmailField(label="Headmaster Email")
    headmaster_password = forms.CharField(widget=forms.PasswordInput, label="Password")
    headmaster_password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    class Meta:
        model = School
        fields = ['name', 'subdomain']
        widgets = {
            'subdomain': forms.TextInput(attrs={
                'placeholder': 'e.g., greenwood',
                'help_text': 'This will create greenwood.educore.com'
            }),
        }

    def clean_subdomain(self):
        subdomain = self.cleaned_data['subdomain'].lower()
        if School.objects.filter(subdomain=subdomain).exists():
            raise forms.ValidationError("This subdomain is already taken.")
        if not subdomain.replace('-', '').isalnum():
            raise forms.ValidationError("Subdomain can only contain letters, numbers, and hyphens.")
        return subdomain

    def clean_headmaster_email(self):
        email = self.cleaned_data['headmaster_email']
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('headmaster_password')
        password_confirm = cleaned_data.get('headmaster_password_confirm')

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class SchoolLoginForm(forms.Form):
    """Form for school login"""
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class SchoolBrandingForm(forms.ModelForm):
    """Form for customizing school branding and settings"""
    class Meta:
        model = School
        fields = ['theme_color', 'motto', 'address', 'phone', 'email', 'website', 'grading_system', 'ca_weight', 'exam_weight']
        widgets = {
            'theme_color': forms.TextInput(attrs={'type': 'color'}),
            'ca_weight': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.5}),
            'exam_weight': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.5}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        grading_system = cleaned_data.get('grading_system')
        ca_weight = cleaned_data.get('ca_weight')
        exam_weight = cleaned_data.get('exam_weight')
        
        if grading_system == 'custom_weights' and ca_weight is not None and exam_weight is not None:
            total = ca_weight + exam_weight
            if total != 100.0:
                raise forms.ValidationError(f"Total weight must be 100%. Current total: {total}%")
        
        return cleaned_data


class AddSchoolUserForm(forms.Form):
    """Form to add a new user to a school"""
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=SchoolUser.ROLE_CHOICES)

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class SchoolUserEditForm(forms.ModelForm):
    """Form to edit school user details"""
    first_name = forms.CharField(max_length=100, label="First Name")
    last_name = forms.CharField(max_length=100, label="Last Name")
    email = forms.EmailField(label="Email")

    class Meta:
        model = SchoolUser
        fields = ['role', 'is_active']
        widgets = {
            'role': forms.Select(choices=SchoolUser.ROLE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        self.user_form = None
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        school_user = super().save(commit=False)
        if self.user_form:
            user = self.user_form.save(commit=False)
            user.first_name = self.user_form.cleaned_data['first_name']
            user.last_name = self.user_form.cleaned_data['last_name']
            user.email = self.user_form.cleaned_data['email']
            if commit:
                user.save()
        if commit:
            school_user.save()
        return school_user


class ParentRegistrationForm(forms.Form):
    """Form for parent self-registration"""
    student_admission = forms.CharField(max_length=20, label="Student Admission Number")
    parent_first_name = forms.CharField(max_length=100)
    parent_last_name = forms.CharField(max_length=100)
    parent_email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

    def clean_student_admission(self):
        admission = self.cleaned_data['student_admission']
        from academics.models import Student
        if not Student.objects.filter(school=self.school, admission_number=admission).exists():
            raise forms.ValidationError("Student admission number not found in this school.")
        return admission

    def clean_parent_email(self):
        email = self.cleaned_data['parent_email']
        # Check if user already has a membership in THIS school
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            if SchoolUser.objects.filter(user=user, school=self.school).exists():
                # If they are already in this school, check if they are already linked to this student
                # But we can just say they are already registered here.
                raise forms.ValidationError("You are already registered with this school. Please login to your dashboard.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class SchoolUserSignatureForm(forms.ModelForm):
    """Form to upload a signature image for SchoolUser"""
    class Meta:
        model = SchoolUser
        fields = ['signature']
