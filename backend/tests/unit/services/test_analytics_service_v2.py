"""
Unit tests for new AnalyticsService methods.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace
from typing import List, Dict, Any

from app.services.application.analytics_service import AnalyticsService
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository


@pytest.fixture
def mock_analytics_repo():
    return Mock(spec=AnalyticsRepository)


@pytest.fixture
def mock_device_repo():
    return Mock(spec=DeviceRepository)


@pytest.fixture
def mock_growth_repo():
    return Mock(spec=GrowthRepository)


@pytest.fixture
def analytics_service(mock_analytics_repo, mock_device_repo, mock_growth_repo):
    return AnalyticsService(
        repository=mock_analytics_repo,
        device_repository=mock_device_repo,
        growth_repository=mock_growth_repo
    )


class TestAnalyticsServiceV2:
    
    def test_get_environmental_dashboard_summary(self, analytics_service, mock_analytics_repo):
        # Setup
        mock_analytics_repo.get_latest_sensor_reading.return_value = {'temperature': 25.0}
        
        # get_sensor_statistics calls fetch_sensor_history on repo
        mock_analytics_repo.fetch_sensor_history.return_value = [
            {'temperature': 24.0, 'humidity': 60.0, 'timestamp': datetime.now()},
            {'temperature': 25.0, 'humidity': 62.0, 'timestamp': datetime.now()}
        ]
        
        # Execute
        result = analytics_service.get_environmental_dashboard_summary(unit_id=1)
        
        # Verify
        assert result['unit_id'] == 1
        assert result['current']['temperature'] == 25.0
        assert 'daily_stats' in result
        assert 'timestamp' in result

    def test_get_energy_dashboard_summary(self, analytics_service, mock_device_repo):
        # Setup
        mock_device_repo.list_actuators.return_value = [
            {'actuator_id': 1, 'name': 'Light 1', 'actuator_type': 'light'}
        ]
        # mock get_actuator_energy_cost_trends (internal call)
        with patch.object(AnalyticsService, 'get_actuator_energy_cost_trends') as mock_trends:
            mock_trends.return_value = {'total_cost': 10.5, 'cost_unit': '$'}
            mock_device_repo.get_actuator_power_readings.return_value = [{'power_watts': 100.0}]
            
            # Execute
            result = analytics_service.get_energy_dashboard_summary(unit_id=1, days=7)
            
            # Verify
            assert result['total_cost'] == 10.5
            assert result['total_devices'] == 1
            assert result['current_power'] == 100.0

    def test_get_composite_efficiency_score(self, analytics_service):
        # Mock calculate_efficiency_scores_concurrent
        with patch.object(AnalyticsService, 'calculate_efficiency_scores_concurrent') as mock_calc:
            mock_calc.return_value = {
                'environmental': 90.0,
                'energy': 80.0,
                'automation': 70.0,
                'previous_environmental': 85.0,
                'previous_energy': 82.0,
                'previous_automation': 75.0
            }
            
            # Execute
            result = analytics_service.get_composite_efficiency_score(unit_id=1)
            
            # Verify
            # (90*0.4) + (80*0.3) + (70*0.3) = 36 + 24 + 21 = 81
            assert result['overall_score'] == 81.0
            assert result['grade'] == 'B'
            assert result['trend'] == 'stable' # 81.0 - (85*0.4 + 82*0.3 + 75*0.3) = 81.0 - (34 + 24.6 + 22.5) = 81.0 - 81.1 = -0.1

    def test_get_actuators_analytics_overview(self, analytics_service, mock_device_repo):
        # Setup
        mock_device_repo.list_actuators.return_value = [{'actuator_id': 1}]
        
        with patch.object(AnalyticsService, 'get_actuator_energy_dashboard') as mock_dash:
            mock_dash.return_value = {'status': 'ok'}
            
            # Execute
            result = analytics_service.get_actuators_analytics_overview(unit_id=1)
            
            # Verify
            assert result['count'] == 1
            assert result['actuators'][0]['status'] == 'ok'

    def test_get_multi_unit_analytics_overview(self, analytics_service, mock_growth_repo):
        # Setup
        mock_growth_repo.list_units.return_value = [{'unit_id': 1, 'name': 'Unit 1'}]
        
        with patch.object(AnalyticsService, 'get_latest_sensor_reading') as mock_latest, \
             patch.object(AnalyticsService, 'get_comparative_energy_analysis') as mock_comp:
            
            mock_latest.return_value = {'temp': 20}
            mock_comp.return_value = {'usage': 'high'}
            
            # Execute
            result = analytics_service.get_multi_unit_analytics_overview()
            
            # Verify
            assert result['total_units'] == 1
            assert result['units'][0]['unit_name'] == 'Unit 1'

    def test_get_sensors_history_enriched(self, analytics_service, mock_analytics_repo, mock_growth_repo):
        # Setup
        start = datetime.now(timezone.utc) - timedelta(days=1)
        end = datetime.now(timezone.utc)
        
        mock_analytics_repo.fetch_sensor_history.return_value = [
            {'temperature': 22.0, 'humidity': 60.0, 'timestamp': start + timedelta(hours=1)},
            {'temperature': 24.0, 'humidity': 65.0, 'timestamp': start + timedelta(hours=2)}
        ]
        
        mock_growth_repo.get_unit.return_value = {
            'unit_id': 1,
            'light_mode': 'schedule',
            'schedules': {'light': {'start_time': '06:00', 'end_time': '18:00', 'enabled': True}}
        }
        
        # Configure scheduling_service on the analytics_service to supply schedules
        mock_sched = Mock()
        mock_sched.get_schedules_for_unit.return_value = [SimpleNamespace(start_time='06:00', end_time='18:00')]
        analytics_service.scheduling_service = mock_sched

        # Execute
        result = analytics_service.get_sensors_history_enriched(
            start_datetime=start,
            end_datetime=end,
            unit_id=1
        )
        # Verify
        assert len(result['readings']) == 2
        assert 'vpd' in result['readings'][0]
        assert 'summary' in result
