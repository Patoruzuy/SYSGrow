
"""
System Schemas
==============

Pydantic models for system request/response validation.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

class SystemInfoSchema(BaseModel):
    """System information response schema."""
    
    version: str = Field(..., description="Application version")
    api_status: Literal["online", "offline"] = Field(..., alias="apiStatus", description="API status")
    db_status: Literal["connected", "disconnected"] = Field(..., alias="dbStatus", description="Database connection status")
    last_backup: str = Field(..., alias="lastBackup", description="Timestamp of last backup or 'Not configured'")
    uptime: int = Field(..., description="System uptime in seconds")
    storage_used: int = Field(..., alias="storageUsed", description="Storage used in bytes")
    storage_total: int = Field(..., alias="storageTotal", description="Total storage in bytes")
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "version": "v2.5.0",
                "apiStatus": "online",
                "dbStatus": "connected",
                "lastBackup": "Not configured",
                "uptime": 60,
                "storageUsed": 5368709120,
                "storageTotal": 107374182400
            }
        }
    )