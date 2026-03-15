from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from infrastructure.database.ops.activity_log import ActivityOperations


@dataclass(frozen=True)
class ActivityRepository:
    _backend: ActivityOperations

    def insert(self, activity: Dict[str, Any]) -> Optional[int]:
        return self._backend.insert_activity(activity)

    def recent(self, limit: int = 50, activity_type: Optional[str] = None, severity: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._backend.get_recent_activities(limit=limit, activity_type=activity_type, severity=severity, user_id=user_id)

    def for_entity(self, entity_type: str, entity_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        return self._backend.get_activities_for_entity(entity_type, entity_id, limit)

    def statistics(self) -> Dict[str, Any]:
        return self._backend.get_activity_statistics()
