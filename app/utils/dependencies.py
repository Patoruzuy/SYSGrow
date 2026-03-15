"""Dependency injection utilities for managing circular dependencies.

This module provides helpers for validating and documenting bidirectional
dependencies in the service layer.
"""

from typing import Any, Optional


def validate_circular_dependency(
    service: Any,
    dependency_name: str,
    service_name: str
) -> None:
    """
    Validate that a circular dependency was properly initialized.

    This helper is used to ensure that bidirectional dependencies are
    correctly wired by the ContainerBuilder before services are used.

    Args:
        service: The service instance to check
        dependency_name: Name of the dependency attribute (e.g., '_plant_service')
        service_name: Human-readable name for error messages (e.g., 'GrowthService')

    Raises:
        RuntimeError: If the dependency attribute is None

    Example:
        >>> class MyService:
        ...     def __init__(self, other_service: Optional['OtherService'] = None):
        ...         self._other_service = other_service
        ...
        ...     def use_dependency(self):
        ...         validate_circular_dependency(self, '_other_service', 'MyService')
        ...         return self._other_service.some_method()
    """
    dep = getattr(service, dependency_name, None)
    if dep is None:
        raise RuntimeError(
            f"{service_name}.{dependency_name} not initialized. "
            f"Ensure ContainerBuilder.build() completed successfully."
        )


def get_circular_dependency(
    service: Any,
    dependency_name: str,
    service_name: str
) -> Any:
    """
    Get a circular dependency with validation.

    Convenience wrapper that validates and returns the dependency in one call.

    Args:
        service: The service instance to check
        dependency_name: Name of the dependency attribute
        service_name: Human-readable name for error messages

    Returns:
        The dependency instance

    Raises:
        RuntimeError: If the dependency is not initialized

    Example:
        >>> class MyService:
        ...     def __init__(self, other: Optional['OtherService'] = None):
        ...         self._other = other
        ...
        ...     @property
        ...     def other_service(self) -> 'OtherService':
        ...         return get_circular_dependency(self, '_other', 'MyService')
    """
    validate_circular_dependency(service, dependency_name, service_name)
    return getattr(service, dependency_name)


__all__ = [
    'validate_circular_dependency',
    'get_circular_dependency',
]
