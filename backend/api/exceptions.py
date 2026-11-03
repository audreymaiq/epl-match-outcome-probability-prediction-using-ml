# api/exceptions.py
"""Custom HTTP exceptions with structured error bodies."""

from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    def __init__(self, resource: str, resource_id: int | str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"{resource} with id '{resource_id}' not found."},
        )


class ModelNotLoadedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "MODEL_NOT_LOADED", "message": "Install a trained model artifact and restart the API."},
        )


class PredictionFailedException(HTTPException):
    def __init__(self, reason: str = "Unknown error"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "PREDICTION_FAILED", "message": f"Could not compute prediction: {reason}"},
        )


class DatabaseException(HTTPException):
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "DB_ERROR", "message": detail},
        )

