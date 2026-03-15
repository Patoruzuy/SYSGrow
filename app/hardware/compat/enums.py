"""
Lightweight enum adapters to bridge app-level enums and infrastructure enums.

These helpers avoid invasive refactors by converting via the `.value` strings.
Usage is optional and can be adopted incrementally where cross-layer mapping is needed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.enums.device import ActuatorType as AppActuatorType
    from app.enums.device import Protocol as AppProtocol
else:
    try:
        from app.enums.device import ActuatorType as AppActuatorType
        from app.enums.device import Protocol as AppProtocol
    except Exception:  # pragma: no cover
        AppActuatorType = None  # type: ignore
        AppProtocol = None  # type: ignore

from app.domain.actuators import (
    ActuatorType as InfraActuatorType,
    Protocol as InfraProtocol,
)


def app_to_infra_actuator_type(value: str | "AppActuatorType") -> InfraActuatorType:
    """Map app enums/strings to infrastructure ActuatorType by value."""
    s = value.value if hasattr(value, "value") else str(value)
    for member in InfraActuatorType:
        if member.value == s or member.name.lower() == s.lower():
            return member
    # Fallback
    return InfraActuatorType.UNKNOWN


def infra_to_app_actuator_type(value: str | InfraActuatorType) -> Optional["AppActuatorType"]:
    """Map infrastructure ActuatorType to app ActuatorType by value (if available)."""
    if AppActuatorType is None:
        return None
    s = value.value if hasattr(value, "value") else str(value)
    for member in AppActuatorType:
        if member.value == s or member.name.lower() == s.lower():
            return member
    return None


def app_to_infra_protocol(value: str | "AppProtocol") -> InfraProtocol:
    s = value.value if hasattr(value, "value") else str(value)
    for member in InfraProtocol:
        if member.value == s or member.name.lower() == s.lower():
            return member
    # Default to GPIO if unknown
    return InfraProtocol.GPIO


def infra_to_app_protocol(value: str | InfraProtocol) -> Optional["AppProtocol"]:
    if AppProtocol is None:
        return None
    s = value.value if hasattr(value, "value") else str(value)
    for member in AppProtocol:
        if member.value == s or member.name.lower() == s.lower():
            return member
    return None

