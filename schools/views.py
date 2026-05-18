"""
Schools views - Public website and school management
"""
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, ListView, UpdateView
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django import forms
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
import os

@ensure_csrf_cookie
def csrf_refresh(request):
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok'})

@require_GET
def service_worker(request):
    """Serves the Service Worker file"""
    sw_path = os.path.join(settings.BASE_DIR, 'sw.js')
    with open(sw_path, 'rb') as f:
        return HttpResponse(f.read(), content_type='application/javascript')

@require_GET
def manifest(request):
    """Serves the PWA Manifest file"""
    manifest_path = os.path.join(settings.BASE_DIR, 'manifest.json')
    with open(manifest_path, 'rb') as f:
        return HttpResponse(f.read(), content_type='application/json')

@require_GET
def offline_view(request):
    """Offline fallback page"""
    return render(request, 'offline.html')

@login_required
def offline_sync_page(request):
    """Page for managing offline sync operations"""
    return render(request, 'schools/offline_sync.html')

from core.utils import SchoolRoleMixin, send_welcome_email
from .models import School, SchoolUser, GalleryItem
from .forms import SchoolRegistrationForm, SchoolBrandingForm, AddSchoolUserForm, ParentRegistrationForm, SchoolUserEditForm, SchoolUserSignatureForm

class HomeView(TemplateView):
    #Landing page for schools where theye register their schools and get the credential for their space
    template_name = 'schools/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_schools_count'] = School.objects.filter(status='active').count()
        context['features'] = [
            {
                'icon': 'bi-clipboard-check',
                'title': 'Academic Excellence',
                'description': 'Automated grading, custom report cards, and comprehensive student performance tracking.'
            },
            {
                'icon': 'bi-wallet2',
                'title': 'Financial Management',
                'description': 'Smart fee tracking, automated invoicing, and transparent financial reporting.'
            },
            {
                'icon': 'bi-person-badge',
                'title': 'Unified School Portal',
                'description': 'Single secure access point for staff, parents, and students with robust privacy.'
            },
            {
                'icon': 'bi-globe',
                'title': 'Private Workspace',
                'description': 'Your school operates on its own secure, professionally branded digital space.'
            },
            {
                'icon': 'bi-chat-left-text',
                'title': 'Seamless Communication',
                'description': 'Direct channels for announcements and real-time student progress updates.'
            },
            {
                'icon': 'bi-shield-lock',
                'title': 'Advanced Data Privacy',
                'description': 'State-of-the-art security protecting every aspect of your educational records.'
            },
            {
                'icon': 'bi-graph-up-arrow',
                'title': 'Intuitive Analytics',
                'description': 'Visualize enrollment trends and academic performance in one simple dashboard.'
            },
            {
                'icon': 'bi-hdd-stack',
                'title': 'Asset & Resource Control',
                'description': 'Efficiently manage school property, library resources, and inventory.'
            },
        ]
        return context


class FeaturesView(TemplateView):
    """Features page"""
    template_name = 'schools/features.html'


class PricingView(TemplateView):
    """Pricing page"""
    template_name = 'schools/pricing.html'


class ContactView(TemplateView):
    """Contact page"""
    template_name = 'schools/contact.html'

    def post(self, request, *args, **kwargs):
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        message_text = request.POST.get('message', '').strip()

        if not full_name or not email or not message_text:
            messages.error(request, 'Please fill in all contact form fields.')
            return self.get(request, *args, **kwargs)

        recipient_list = ['bsoftdgital@gmail.com']
        subject = f'Contact message from {full_name}'
        body = (
            f'You have received a new contact form submission.\n\n'
            f'Name: {full_name}\n'
            f'Email: {email}\n\n'
            f'Message:\n{message_text}\n'
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent. Thank you!')
        except Exception:
            messages.error(request, 'Your message could not be sent. Please try again later.')

        return self.get(request, *args, **kwargs)



class PrivacyPolicyView(TemplateView):
    """Privacy policy page"""
    template_name = 'schools/privacy_policy.html'


class TermsAndConditionsView(TemplateView):
    """Terms and conditions page"""
    template_name = 'schools/terms_and_conditions.html'


class SchoolRegistrationView(CreateView):
    """School self-registration view"""
    model = School
    form_class = SchoolRegistrationForm
    template_name = 'schools/register_school.html'
    success_url = reverse_lazy('registration_pending')

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Create school
                school = form.save(commit=False)
                school.status = 'pending'
                # Use headmaster email as the primary school contact during registration
                school.email = form.cleaned_data['headmaster_email']
                school.save()

                # Create headmaster user
                user = User.objects.create_user(
                    username=form.cleaned_data['headmaster_email'],
                    email=form.cleaned_data['headmaster_email'],
                    password=form.cleaned_data['headmaster_password'],
                    first_name=form.cleaned_data['headmaster_first_name'],
                    last_name=form.cleaned_data['headmaster_last_name']
                )

                # Create SchoolUser link
                SchoolUser.objects.create(
                    user=user,
                    school=school,
                    role='headmaster',
                    is_active=True
                )

                # Send notification to platform owner
                self.notify_platform_owner(school)

                messages.success(
                    self.request, 
                    f'Registration successful! Your school "{school.name}" is pending approval. '
                    f'You will be notified at {school.email} once approved.'
                )

                # Auto-login the new headmaster
                auth_user = authenticate(
                    self.request,
                    username=user.username,
                    password=form.cleaned_data['headmaster_password']
                )
                if auth_user:
                    login(self.request, auth_user)

                return redirect('registration_pending')

        except Exception as e:
            messages.error(self.request, f'Registration failed: {str(e)}')
            return self.form_invalid(form)

    def notify_platform_owner(self, school):
        """Send email notification to platform owner"""
        try:
            send_mail(
                subject=f'New School Registration: {school.name}',
                message=f'A new school "{school.name}" has registered and is pending approval.\n'
                        f'Subdomain: {school.subdomain}\n'
                        f'Email: {school.email}',
                from_email='noreply@educore.com',
                recipient_list=['admin@educore.com'],
                fail_silently=True
            )
        except:
            pass


# School Admin Views (require login and school membership)
@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    """Legacy dashboard endpoint; forwards to unified analytics dashboard"""
    template_name = 'schools/dashboard.html'

    def get(self, request, *_, **__):
        # Single source of truth for role-based dashboards lives in analytics.views.dashboard
        return redirect('analytics:dashboard')

    def render_headmaster_dashboard(self, request, school):
        from results.models import TermSummary, StudentResult
        from academics.models import Student, ClassSection

        context = {
            'school': school,
            'total_students': Student.objects.filter(school=school, is_active=True).count(),
            'total_teachers': SchoolUser.objects.filter(school=school, role='teacher').count(),
            'total_classes': ClassSection.objects.filter(school=school).count(),
            'pending_approvals': StudentResult.objects.filter(
                class_section__school=school,
                status='submitted'
            ).count(),
            'recent_results': TermSummary.objects.filter(
                class_section__school=school
            ).select_related('student', 'term')[:10]
        }
        return render(request, 'schools/dashboard_headmaster.html', context)

    def render_admin_dashboard(self, request, school):
        from academics.models import Student, ClassSection
        from attendance.models import AttendanceSession
        from fees.models import FeeInvoice

        today = date.today()
        total_students = Student.objects.filter(school=school, is_active=True).count()
        total_teachers = SchoolUser.objects.filter(
            school=school, role='teacher', is_active=True
        ).count()
        total_classes = ClassSection.objects.filter(school=school).count()
        total_parents = SchoolUser.objects.filter(
            school=school, role='parent', is_active=True
        ).count()
        total_users = SchoolUser.objects.filter(school=school, is_active=True).count()

        total_invoiced = FeeInvoice.objects.filter(school=school).aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_collected = FeeInvoice.objects.filter(school=school).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        outstanding_balance = total_invoiced - total_collected
        overdue_invoices = FeeInvoice.objects.filter(
            school=school,
            status__in=['unpaid', 'partial', 'overdue'],
            due_date__lt=today
        ).count()

        classes_marked_today = AttendanceSession.objects.filter(
            school=school, date=today, is_finalized=True
        ).count()
        attendance_completion_pct = round(
            (classes_marked_today / total_classes) * 100, 1
        ) if total_classes else 0
        student_teacher_ratio = round(
            total_students / total_teachers, 1
        ) if total_teachers else None

        context = {
            'school': school,
            'today': today,
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_classes': total_classes,
            'total_parents': total_parents,
            'total_users': total_users,
            'total_invoiced': total_invoiced,
            'total_collected': total_collected,
            'outstanding_balance': outstanding_balance,
            'overdue_invoices': overdue_invoices,
            'classes_marked_today': classes_marked_today,
            'attendance_completion_pct': attendance_completion_pct,
            'student_teacher_ratio': student_teacher_ratio,
        }
        return render(request, 'schools/dashboard_admin.html', context)

    def render_teacher_dashboard(self, request, school):
        from academics.models import TeacherSubjectAssignment

        assignments = TeacherSubjectAssignment.objects.filter(
            teacher__user=request.user,
            class_section__school=school
        ).select_related('subject', 'class_section')

        context = {
            'school': school,
            'assignments': assignments,
        }
        return render(request, 'schools/dashboard_teacher.html', context)

    def render_student_dashboard(self, request, school):
        from results.models import TermSummary
        from academics.models import Student

        try:
            student = Student.objects.get(user=request.user, school=school)
            summaries = TermSummary.objects.filter(student=student).select_related('term')

            context = {
                'school': school,
                'student': student,
                'summaries': summaries,
            }
            return render(request, 'schools/dashboard_student.html', context)
        except Student.DoesNotExist:
            messages.error(request, "Student profile not found.")
            return redirect('home')

    def render_parent_dashboard(self, request, school):
        from academics.models import Student

        # Find children linked to this parent's email
        children = Student.objects.filter(
            school=school,
            parent_email=request.user.email,
            is_active=True
        )

        context = {
            'school': school,
            'children': children,
        }
        return render(request, 'schools/dashboard_parent.html', context)


@method_decorator(login_required, name='dispatch')
class SchoolSettingsView(UpdateView):
    """School branding and settings (admin/headmaster only)"""
    model = School
    form_class = SchoolBrandingForm
    template_name = 'schools/school_settings.html'
    success_url = reverse_lazy('dashboard')

    def get_object(self):
        return self.request.school

    def dispatch(self, request, *args, **kwargs):
        school = getattr(request, 'school', None)
        if school:
            membership = SchoolUser.objects.filter(user=request.user, school=school, is_active=True).first()
            if membership and membership.role not in ['headmaster', 'admin']:
                messages.error(request, "You don't have permission to access this page.")
                return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'School settings updated successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class UserManagementView(ListView):
    """Manage school users"""
    model = SchoolUser
    template_name = 'schools/user_management.html'
    context_object_name = 'users'

    def get_queryset(self):
        return SchoolUser.objects.filter(
            school=self.request.school
        ).select_related('user').order_by('role', 'user__last_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = self.request.school
        context['add_user_form'] = AddSchoolUserForm()
        return context


@login_required
def add_school_user(request):
    """Add a new user to the school or link an existing one"""
    if request.method == 'POST':
        form = AddSchoolUserForm(request.POST)
        if form.is_valid():
            school = request.school
            email = form.cleaned_data['email']
            role = form.cleaned_data['role']

            # Check if user already exists
            user = User.objects.filter(email=email).first()
            is_new_user = False
            
            if user:
                # User exists, check if they are already in this school
                if SchoolUser.objects.filter(user=user, school=school).exists():
                    messages.warning(request, f"User {email} is already a member of this school.")
                    return redirect('user_management')
            else:
                # Create new user
                is_new_user = True
                import random
                import string
                temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=temp_password,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name']
                )

            # Create SchoolUser membership
            SchoolUser.objects.create(
                user=user,
                school=school,
                role=role,
                is_active=True
            )

            # Send welcome/notification email
            send_welcome_email(request, user, school, is_new_user=is_new_user)

            messages.success(request, f"User {user.get_full_name()} added to {school.name}!")
            return redirect('user_management')

    return redirect('user_management')


@login_required
def school_user_edit(request, pk):
    """Edit school user details"""
    school_user = get_object_or_404(SchoolUser, pk=pk, school=request.school)
    
    class UserForm(forms.Form):
        first_name = forms.CharField()
        last_name = forms.CharField()
        email = forms.EmailField()
    
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        school_user_form = SchoolUserEditForm(request.POST, instance=school_user)
        
        if user_form.is_valid() and school_user_form.is_valid():
            # Update user
            school_user.user.first_name = user_form.cleaned_data['first_name']
            school_user.user.last_name = user_form.cleaned_data['last_name']
            school_user.user.email = user_form.cleaned_data['email']
            school_user.user.save()
            
            school_user_form.save()
            messages.success(request, f'User {school_user.user.get_full_name()} updated successfully!')
            return redirect('user_management')
    else:
        user_form = UserForm(initial={
            'first_name': school_user.user.first_name,
            'last_name': school_user.user.last_name,
            'email': school_user.user.email,
        })
        school_user_form = SchoolUserEditForm(instance=school_user)
    
    context = {
        'school_user': school_user,
        'user_form': user_form,
        'school_user_form': school_user_form,
        'school': request.school,
    }
    return render(request, 'schools/user_edit.html', context)


@login_required
def school_user_deactivate(request, pk):
    """Toggle school user active status"""
    school_user = get_object_or_404(SchoolUser, pk=pk, school=request.school)

    school_user.is_active = not school_user.is_active
    action = 'deactivated' if not school_user.is_active else 'reactivated'
    school_user.save()
    messages.success(request, f"User {school_user.user.get_full_name()} {action} successfully!")
    return redirect('user_management')



class ParentRegistrationView(CreateView):
    """Parent self-registration view"""
    form_class = ParentRegistrationForm
    template_name = 'schools/parent_register.html'
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        school = getattr(request, 'school', None)
        if not school:
            messages.error(request, "School context not found.")
            return redirect('home')
        
        if not school.parent_registration_enabled:
            messages.error(request, "Parent self-registration is currently disabled for this school.")
            return redirect('home')

        # Check token if registration_token is set
        token = request.GET.get('token')
        if school.registration_token and token != school.registration_token:
            messages.error(request, "Invalid or expired registration link.")
            return redirect('home')

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if 'instance' in kwargs:
            kwargs.pop('instance')
        kwargs['school'] = getattr(self.request, 'school', None)
        return kwargs



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = self.request.school
        return context

    def form_valid(self, form):
        school = self.request.school
        email = form.cleaned_data['parent_email']
        from academics.models import Student, ParentStudentLink
        student = Student.objects.get(
            school=school,
            admission_number=form.cleaned_data['student_admission']
        )

        with transaction.atomic():
            # Check if user already exists or is logged in
            if self.request.user.is_authenticated:
                user = self.request.user
                is_new_user = False
            else:
                user = User.objects.filter(email=email).first()
                is_new_user = False
                
                if not user:
                    is_new_user = True
                    # Create user
                    user = User.objects.create_user(
                        username=email,
                        email=email,
                        password=form.cleaned_data['password1'],
                        first_name=form.cleaned_data['parent_first_name'],
                        last_name=form.cleaned_data['parent_last_name']
                    )

            # Create or get SchoolUser membership
            parent_membership, created = SchoolUser.objects.get_or_create(
                user=user,
                school=school,
                defaults={'role': 'parent', 'is_active': True}
            )

            # Explicitly link parent to selected child.
            ParentStudentLink.objects.get_or_create(
                school=school,
                parent=parent_membership,
                student=student,
                defaults={'relationship': 'parent'},
            )

            # Auto-link additional children sharing the same parent email in this school.
            sibling_students = Student.objects.filter(
                school=school,
                parent_email__iexact=user.email,
                is_active=True,
            ).exclude(pk=student.pk)
            linked_count = 1
            for sibling in sibling_students:
                _, created_link = ParentStudentLink.objects.get_or_create(
                    school=school,
                    parent=parent_membership,
                    student=sibling,
                    defaults={'relationship': 'parent'},
                )
                if created_link:
                    linked_count += 1

        if is_new_user:
            send_welcome_email(self.request, user, school, is_new_user=True)

        messages.success(
            self.request,
            f'Welcome {user.get_full_name()}! Your account is linked to {linked_count} child record(s).'
        )

        # Auto-login the new parent if not already logged in
        if not self.request.user.is_authenticated and is_new_user:
            user = authenticate(self.request, username=user.username, password=form.cleaned_data['password1'])
            if user:
                login(self.request, user)
        
        return redirect('dashboard')


@login_required
def upload_signature(request):
    school_user = get_object_or_404(SchoolUser, user=request.user, school=request.school)
    if request.method == 'POST':
        form = SchoolUserSignatureForm(request.POST, request.FILES, instance=school_user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Signature uploaded successfully!')
            return redirect('school_settings')
    else:
        form = SchoolUserSignatureForm(instance=school_user)
    return render(request, 'schools/upload_signature.html', {'form': form, 'school': request.school})


import qrcode
import io
from django.urls import reverse
from django.http import HttpResponse

@login_required
def registration_qr_code(request):
    """Generates a QR code for parent registration"""
    school = request.school
    if not school:
        return HttpResponse("School not found", status=404)
    
    # Construct the registration URL
    # Use the school's subdomain and token
    base_url = request.build_absolute_uri(reverse('parent_register'))
    registration_url = f"{base_url}?token={school.registration_token}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(registration_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save image to a bytes buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
def toggle_registration(request):
    """Toggles parent self-registration status"""
    # Only headmaster or admin can toggle
    membership = get_object_or_404(SchoolUser, user=request.user, school=request.school)
    if membership.role not in ['headmaster', 'admin']:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('school_settings')

    school = request.school
    school.parent_registration_enabled = not school.parent_registration_enabled
    school.save()
    
    status = "enabled" if school.parent_registration_enabled else "disabled"
    messages.success(request, f"Parent registration has been {status}.")
    return redirect('school_settings')


@login_required
def regenerate_registration_token(request):
    """Regenerates the parent registration token (invalidates old QR codes)"""
    membership = get_object_or_404(SchoolUser, user=request.user, school=request.school)
    if membership.role not in ['headmaster', 'admin']:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('school_settings')

    school = request.school
    school.regenerate_registration_token()
    messages.success(request, "Registration token has been regenerated. Old QR codes are now invalid.")
    return redirect('school_settings')


@require_GET
@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker_cleanup(_request):
    """
    Legacy SW cleanup endpoint.
    Keeps /sw.js available so browsers with older PWA registrations can fetch
    this script, clear old caches, and unregister themselves.
    """
    content = """
self.addEventListener('install', event => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(key => caches.delete(key))))
      .then(() => self.registration.unregister())
      .then(() => self.clients.matchAll({ type: 'window' }))
      .then(clients => {
        clients.forEach(client => client.navigate(client.url));
      })
  );
});
"""
    return HttpResponse(content, content_type='application/javascript')


class GalleryListView(ListView):
    """Gallery page showing global showcase items"""
    model = GalleryItem
    template_name = 'schools/gallery.html'
    context_object_name = 'gallery_items'

    def get_queryset(self):
        # Show only global items (those not tied to any school)
        return GalleryItem.objects.filter(school__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = getattr(self.request, 'school', None)
        return context
