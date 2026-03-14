"""
Session Schemas
===============

Pydantic models for session) request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Literal


class SessionBroadcastSchema(BaseModel):
    """Schema for broadcasting session-related events via Socket.IO."""
    event: Literal['login', 'logout', 'revoke', 'session_expired']
    userId: int
    sessionId: str = Field(..., alias='session_id')
    timestamp: str  # ISO 8601 formatted timestamp