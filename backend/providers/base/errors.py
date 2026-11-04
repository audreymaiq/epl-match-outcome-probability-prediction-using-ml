class ProviderUnavailableError(RuntimeError):
    """Authentication, quota or contract failure that must stop the current ingestion."""
