from core.utils import get_default_school
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import AssetCategory, AssetItem
from .forms import AssetCategoryForm, AssetItemForm
from schools.models import School

@login_required
def inventory_dashboard(request):
    school = get_default_school()
    categories = AssetCategory.objects.filter(school=school)
    assets = AssetItem.objects.filter(school=school)
    return render(request, 'inventory/dashboard.html', {
        'categories': categories,
        'assets': assets,
        'school': school,
    })

@login_required
def add_asset_category(request):
    school = get_default_school()
    if request.method == 'POST':
        form = AssetCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.school = school
            category.save()
            messages.success(request, 'Asset category added!')
            return redirect('inventory:dashboard')
    else:
        form = AssetCategoryForm()
    return render(request, 'inventory/add_category.html', {'form': form, 'school': school})

@login_required
def add_asset_item(request):
    school = get_default_school()
    if request.method == 'POST':
        form = AssetItemForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.school = school
            asset.save()
            messages.success(request, 'Asset item added!')
            return redirect('inventory:dashboard')
    else:
        form = AssetItemForm()
        form.fields['category'].queryset = AssetCategory.objects.filter(school=school)
    return render(request, 'inventory/add_item.html', {'form': form, 'school': school})
