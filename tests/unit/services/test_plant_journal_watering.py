"""Tests for plant journal watering records wiring into manual irrigation."""

from unittest.mock import Mock

from app.services.application.plant_journal_service import PlantJournalService


def test_record_watering_event_forwards_to_manual_irrigation():
    repo = Mock()
    repo.create_watering_entry.return_value = 101

    manual_service = Mock()
    service = PlantJournalService(journal_repo=repo, manual_irrigation_service=manual_service)

    entry_id = service.record_watering_event(
        plant_id=10,
        unit_id=5,
        amount=2.0,
        unit="l",
        notes="manual",
        user_id=7,
        watered_at_utc="2026-01-28T10:00:00+00:00",
    )

    assert entry_id == 101
    manual_service.log_watering_event.assert_called_once()
    _, kwargs = manual_service.log_watering_event.call_args
    assert kwargs["amount_ml"] == 2000.0
    assert kwargs["unit_id"] == 5
    assert kwargs["user_id"] == 7


def test_record_watering_event_skips_forward_if_missing_unit_or_user():
    repo = Mock()
    repo.create_watering_entry.return_value = 202

    manual_service = Mock()
    service = PlantJournalService(journal_repo=repo, manual_irrigation_service=manual_service)

    entry_id = service.record_watering_event(
        plant_id=10,
        unit_id=None,
        amount=250,
        unit="ml",
        notes="manual",
        user_id=None,
        watered_at_utc=None,
    )

    assert entry_id == 202
    manual_service.log_watering_event.assert_not_called()
