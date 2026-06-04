"""
Custom domain exceptions for the nptmpl codebase.
"""

class NptmplError(Exception):
    """Base exception for all nptmpl-related errors."""
    pass

class ConfigurationError(NptmplError):
    """Raised when there is an issue with the global or local configuration."""
    pass

class RegistryError(NptmplError):
    """Base class for registry-related errors."""
    pass

class TemplateNotFoundError(RegistryError):
    """Raised when a requested template or version does not exist."""
    pass

class TemplateAlreadyExistsError(RegistryError):
    """Raised when trying to add a template that already exists without overwrite."""
    pass

class VersionConflictError(RegistryError):
    """Raised when a version update is not semantically greater than the current latest."""
    pass

class ValidationError(NptmplError):
    """Raised when metadata or template structure validation fails."""
    pass

class EngineError(NptmplError):
    """Base class for file system engine errors."""
    pass

class DestinationNotEmptyError(EngineError):
    """Raised when the destination directory is not empty and override is needed."""
    pass

class RenderingError(EngineError):
    """Raised when Jinja2 rendering fails."""
    pass

class ExtractionError(EngineError):
    """Raised when archive extraction fails or is deemed unsafe."""
    pass

class RemoteError(NptmplError):
    """Base class for remote registry operations (HTTP/SSH)."""
    pass

class AuthenticationError(RemoteError):
    """Raised when remote authentication fails."""
    pass

class NetworkError(RemoteError):
    """Raised when a network operation fails after retries."""
    pass
