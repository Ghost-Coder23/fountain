"""Accounts forms"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import UserProfile


class CustomAuthenticationForm(AuthenticationForm):
    """Custom login form with Bootstrap styling"""
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )

    def clean(self):
        email = self.cleaned_data.get('username')
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                self.cleaned_data['username'] = user.get_username()
        return super().clean()


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()

    class Meta:
        model = UserProfile
        fields = ['phone', 'address', 'bio', 'date_of_birth']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }


class PasswordChangeForm(forms.Form):
    """Custom password change form"""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Current Password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="New Password",
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm New Password"
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data.get('current_password')
        if not self.user.check_password(current):
            raise forms.ValidationError("Current password is incorrect.")
        return current

    def clean(self):
        cleaned_data = super().clean()
        new = cleaned_data.get('new_password')
        confirm = cleaned_data.get('confirm_password')

        if new and confirm and new != confirm:
            raise forms.ValidationError("New passwords do not match.")

        return cleaned_data
