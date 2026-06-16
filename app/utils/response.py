"""
Response utilities for AURA Restaurant POS.
Standardizes API JSON responses.
"""
from flask import jsonify

def success_response(data=None, message: str = "Success", status: int = 200):
    """
    Returns a standardized JSON success response.
    """
    payload = {"status": "success", "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status

def error_response(message: str, status: int = 400, errors: dict = None):
    """
    Returns a standardized JSON error response.
    """
    payload = {"status": "error", "message": message}
    if errors is not None:
        payload["errors"] = errors
    return jsonify(payload), status

def not_found_response(resource: str = "Record"):
    """
    Returns a standard 404 response.
    """
    return error_response(f"{resource} not found", 404)

def unauthorized_response():
    """
    Returns a standard 401 response.
    """
    return error_response("Unauthorized", 401)

def validation_error_response(errors: dict):
    """
    Returns a standard 422 validation error response.
    """
    return error_response("Validation failed", 422, errors)
