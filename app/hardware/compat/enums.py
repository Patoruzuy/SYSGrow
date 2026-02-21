"""
Lightweight enum adapters to bridge app-level enums and infrastructure enums.

These helpers avoid invasive refactors by converting via the `.value` strings.
Usage is optional and can be adopted incrementally where cross-layer mapping is needed.

NOTE: ``ActuatorType`` is now a single canonical enum defined in
``app.enums.device`` and re-exported by ``app.domain.actuators``.
The ``app_to_infra_actuator_type`` / ``infra_to_app_actuator_type`` helpers
are retained as thin wrappers so existing call-sites keep working, but
they now simply coerce the incoming value through the enum's ``_missing_``
hook rather than iterating members manually.
"""

from __future__ import annotations

from app.domain.actuators import Protocol as InfraProtocol
from app.enums.device import ActuatorType, Protocol as AppProtocol

# ActuatorType is now the *same* enum in both layers.
InfraActuatorType = ActuatorType
AppActuatorType = ActuatorType


def app_to_infra_actuator_type(value: str | ActuatorType) -> ActuatorType:
    """Normalise an actuator-type string or enum to the canonical ActuatorType.

    Legacy lowercase values (``"pump"``, ``"light"``, …) are resolved via
    the ``_missing_`` hook on ``ActuatorType``.
    """
    if isinstance(value, ActuatorType):
        return value
    s = value.value if hasattr(value, "value") else str(value)
    try:
        return ActuatorType(s)
    except ValueError:
        return ActuatorType.UNKNOWN


def infra_to_app_actuator_type(value: str | ActuatorType) -> ActuatorType | None:
    """Alias of ``app_to_infra_actuator_type`` — both layers share the same enum now."""
    return app_to_infra_actuator_type(value)


def app_to_infra_protocol(value: str | AppProtocol) -> InfraProtocol:
    s = value.value if hasattr(value, "value") else str(value)
    for member in InfraProtocol:
        if member.value == s or member.name.lower() == s.lower():
            return member
    # Default to GPIO if unknown
    return InfraProtocol.GPIO


def infra_to_app_protocol(value: str | InfraProtocol) -> AppProtocol | None:
    s = value.value if hasattr(value, "value") else str(value)
    for member in AppProtocol:
        if member.value == s or member.name.lower() == s.lower():
            return member
    return None
