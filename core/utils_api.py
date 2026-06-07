from django.http import JsonResponse


def api_error(message='An error occurred', status=400):
    return JsonResponse({'ok': False, 'error': str(message)}, status=status)


def api_ok(data=None):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    return JsonResponse(payload)
