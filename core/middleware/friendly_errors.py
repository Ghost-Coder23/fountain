import logging
import traceback
from django.shortcuts import render
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class FriendlyErrorMiddleware:
    """Middleware to return friendly error pages and consistent JSON error responses.

    - For HTML requests: render templates/500.html on exceptions.
    - For AJAX/JSON requests: return JSON {ok: false, error: 'Friendly message'}.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            # If status indicates server error, render friendly page
            if response.status_code >= 500 and not request.path.startswith('/static/'):
                return render(request, '500.html', status=500)
            return response
        except Exception as e:
            # Log full stack for ops
            tb = traceback.format_exc()
            logger.error('Unhandled exception: %s\n%s', str(e), tb)
            # Return JSON for XHR/fetch requests
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json' or request.headers.get('accept', '').lower().startswith('application/json'):
                return JsonResponse({'ok': False, 'error': 'An unexpected error occurred. Please try again or contact your administrator.'}, status=500)
            # Render friendly 500 page
            return render(request, '500.html', status=500)
