"""Custom DRF exception handler.

Errors are returned as:  {"errors": {"field": "message"}}
For non-field / detail errors the key is "detail".
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def _flatten(errors):
    """Convert DRF error structures into {field: single message}."""
    result = {}
    if isinstance(errors, dict):
        for key, value in errors.items():
            result[key] = _pick(value)
    elif isinstance(errors, list):
        result["detail"] = _pick(errors)
    else:
        result["detail"] = str(errors)
    return result


def _pick(value):
    if isinstance(value, dict):
        # non-field errors nested etc — join first messages
        parts = []
        for k, v in value.items():
            parts.append(f"{k}: {_pick(v)}")
        return "; ".join(parts)
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        detail = getattr(response, "detail", None)
        data = response.data
        if isinstance(data, dict) and set(data.keys()) == {"detail"}:
            errors = {"detail": _pick(data["detail"])}
        elif isinstance(data, dict):
            errors = {}
            for key, value in data.items():
                errors[key] = _pick(value)
        else:
            errors = {"detail": _pick(data)}
        response.data = {"errors": errors}
    return response
