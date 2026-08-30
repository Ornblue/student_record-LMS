"""
Custom DRF exception handler so every error response (validation error,
404, permission denied, etc.) comes back in a single consistent shape:

    {"success": false, "errors": {...} }

instead of DRF's default bare list/dict, making the frontend's error
handling code much simpler.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            'success': False,
            'errors': response.data,
        }
        return response

    # Unhandled exception -> generic 500 instead of an HTML crash page.
    return Response(
        {'success': False, 'errors': {'detail': 'An unexpected server error occurred.'}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
