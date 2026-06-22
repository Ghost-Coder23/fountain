from django.shortcuts import render

def bad_request(request, exception=None):
    """View for 400 Bad Request errors."""
    # Check if user is logged in to decide which base template to use
    if request.user.is_authenticated:
        return render(request, '400.html', status=400)
    return render(request, '400_public.html', status=400)

def permission_denied(request, exception=None):
    """View for 403 Forbidden errors."""
    if request.user.is_authenticated:
        return render(request, '403.html', status=403)
    return render(request, '403_public.html', status=403)

def page_not_found(request, exception=None):
    """View for 404 Not Found errors."""
    if request.user.is_authenticated:
        return render(request, '404.html', status=404)
    return render(request, '404_public.html', status=404)

def server_error(request):
    """View for 500 Server Error errors."""
    if request.user.is_authenticated:
        return render(request, '500.html', status=500)
    return render(request, '500_public.html', status=500)
