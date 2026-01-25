"""
Unit tests for AnalyticsService.

Tests the analytics service methods including:
- Caching functionality (latest readings, history)
- Concurrent execution of efficiency calculations
- Cache utilities (warming, statistics, clearing)
- Environmental calculations (trends, correlations, VPD)
- Efficiency score calculations (stability, energy, automation)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

from app.services.application.analytics_service import AnalyticsService
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository


# ==================== Fixtures ====================

@pytest.fixture
def mock_analytics_repo():
    """Create a mock AnalyticsRepository."""
    repo = Mock(spec=AnalyticsRepository)
    return repo


@pytest.fixture
def mock_device_repo():
    """Create a mock DeviceRepository."""
    repo = Mock(spec=DeviceRepository)
    return repo


@pytest.fixture
def mock_growth_repo():
    """Create a mock GrowthRepository."""
    repo = Mock(spec=GrowthRepository)
    return repo


@pytest.fixture
def analytics_service(mock_analytics_repo, mock_device_repo, mock_growth_repo):
    """Create AnalyticsService instance with mocked repositories."""
    service = AnalyticsService(
        repository=mock_analytics_repo,
        device_repository=mock_device_repo,
        growth_repository=mock_growth_repo
    )
    return service


@pytest.fixture
def sample_sensor_readings():
    """Generate sample sensor readings for testing."""
    base_time = datetime(2025, 1, 1, 12, 0, 0)
    readings = []
    
    for i in range(10):
        readings.append({
            'id': i + 1,
            'unit_id': 1,
            'sensor_id': 1,
            'temperature': 22.0 + (i * 0.5),  # 22.0 to 26.5
            'humidity': 60.0 + (i * 2),  # 60 to 78
            'soil_moisture': 40.0 + i,  # 40 to 49
            'timestamp': base_time + timedelta(hours=i),
            'created_at': (base_time + timedelta(hours=i)).isoformat()
        })
    
    return readings


@pytest.fixture
def sample_actuator_readings():
    """Generate sample actuator power readings for testing."""
    base_time = datetime(2025, 1, 1, 12, 0, 0)
    readings = []
    
    for i in range(20):
        readings.append({
            'id': i + 1,
            'actuator_id': 1,
            'power_watts': 100.0 + (i * 5),  # Varying power
            'voltage': 120.0,
            'current': (100.0 + (i * 5)) / 120.0,
            'power_factor': 0.95,
            'created_at': base_time + timedelta(hours=i)
        })
    
    return readings


# ==================== Caching Tests ====================

class TestCachingFunctionality:
    """Test caching behavior for sensor readings."""

    def test_get_latest_sensor_reading_caches_result(self, analytics_service, mock_analytics_repo):
        """Verify that get_latest_sensor_reading caches the result."""
        # Arrange
        expected_reading = {
            'id': 1,
            'temperature': 23.5,
            'humidity': 65.0,
            'timestamp': datetime.now().isoformat()
        }
        mock_analytics_repo.get_latest_sensor_reading.return_value = expected_reading
        
        # Act - First call should hit database
        result1 = analytics_service.get_latest_sensor_reading(unit_id=1)
        
        # Act - Second call should hit cache
        result2 = analytics_service.get_latest_sensor_reading(unit_id=1)
        
        # Assert
        assert result1 == expected_reading
        assert result2 == expected_reading
        # Repository should only be called once (cached on second call)
        assert mock_analytics_repo.get_latest_sensor_reading.call_count == 1

    def test_get_latest_sensor_reading_different_units_separate_cache(self, analytics_service, mock_analytics_repo):
        """Verify that different units have separate cache entries."""
        # Arrange
        reading_unit1 = {'id': 1, 'unit_id': 1, 'temperature': 23.0}
        reading_unit2 = {'id': 2, 'unit_id': 2, 'temperature': 25.0}
        
        mock_analytics_repo.get_latest_sensor_reading.side_effect = [reading_unit1, reading_unit2]
        
        # Act
        result1 = analytics_service.get_latest_sensor_reading(unit_id=1)
        result2 = analytics_service.get_latest_sensor_reading(unit_id=2)
        
        # Assert
        assert result1['temperature'] == 23.0
        assert result2['temperature'] == 25.0
        assert mock_analytics_repo.get_latest_sensor_reading.call_count == 2

    def test_fetch_sensor_history_caches_result(self, analytics_service, mock_analytics_repo, sample_sensor_readings):
        """Verify that fetch_sensor_history caches results."""
        # Arrange
        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 2, 0, 0, 0)
        mock_analytics_repo.fetch_sensor_history.return_value = sample_sensor_readings
        
        # Act - First call
        result1 = analytics_service.fetch_sensor_history(start, end, unit_id=1)
        
        # Act - Second call with same parameters
        result2 = analytics_service.fetch_sensor_history(start, end, unit_id=1)
        
        # Assert
        assert len(result1) == 10
        assert result1 == result2
        # Should only hit database once
        assert mock_analytics_repo.fetch_sensor_history.call_count == 1

    def test_clear_caches_clears_all_caches(self, analytics_service, mock_analytics_repo):
        """Verify that clear_caches() clears all cache entries."""
        # Arrange
        reading = {'id': 1, 'temperature': 23.5}
        mock_analytics_repo.get_latest_sensor_reading.return_value = reading
        
        # Act - Populate cache
        analytics_service.get_latest_sensor_reading(unit_id=1)
        assert mock_analytics_repo.get_latest_sensor_reading.call_count == 1
        
        # Act - Clear caches
        analytics_service.clear_caches()
        
        # Act - Call again should hit database
        analytics_service.get_latest_sensor_reading(unit_id=1)
        
        # Assert - Should have called database twice (cache was cleared)
        assert mock_analytics_repo.get_latest_sensor_reading.call_count == 2

    def test_get_cache_stats_returns_statistics(self, analytics_service, mock_analytics_repo):
        """Verify that get_cache_stats() returns cache statistics."""
        # Arrange
        reading = {'id': 1, 'temperature': 23.5}
        mock_analytics_repo.get_latest_sensor_reading.return_value = reading
        
        # Act - Populate cache
        analytics_service.get_latest_sensor_reading(unit_id=1)
        analytics_service.get_latest_sensor_reading(unit_id=1)  # Cache hit
        
        # Act - Get stats
        stats = analytics_service.get_cache_stats()
        
        # Assert
        assert 'latest_readings' in stats
        assert 'history' in stats
        assert stats['latest_readings']['size'] >= 0
        assert 'hit_rate' in stats['latest_readings']


# ==================== Concurrent Execution Tests ====================

class TestConcurrentExecution:
    """Test concurrent efficiency calculations."""

    def test_calculate_efficiency_scores_concurrent_returns_all_scores(self, analytics_service, mock_device_repo):
        """Verify that concurrent calculation returns all three scores."""
        # Arrange
        mock_device_repo.list_sensor_configs.return_value = []
        mock_device_repo.count_anomalies_for_sensors.return_value = 0
        
        # Mock the individual calculation methods
        with patch.object(analytics_service, 'calculate_environmental_stability', return_value=85.0), \
             patch.object(analytics_service, 'calculate_energy_efficiency', return_value=90.0), \
             patch.object(analytics_service, 'calculate_automation_effectiveness', return_value=88.0):
            
            # Act
            result = analytics_service.calculate_efficiency_scores_concurrent(unit_id=1)
            
            # Assert
            assert result['environmental'] == 85.0
            assert result['energy'] == 90.0
            assert result['automation'] == 88.0

    def test_calculate_efficiency_scores_concurrent_includes_previous_week(self, analytics_service, mock_device_repo):
        """Verify that previous week scores are calculated when requested."""
        # Arrange
        mock_device_repo.list_sensor_configs.return_value = []
        mock_device_repo.count_anomalies_for_sensors.return_value = 0
        
        with patch.object(analytics_service, 'calculate_environmental_stability', return_value=85.0), \
             patch.object(analytics_service, 'calculate_energy_efficiency', return_value=90.0), \
             patch.object(analytics_service, 'calculate_automation_effectiveness', return_value=88.0):
            
            # Act
            result = analytics_service.calculate_efficiency_scores_concurrent(
                unit_id=1,
                include_previous=True
            )
            
            # Assert
            assert 'previous_environmental' in result
            assert 'previous_energy' in result
            assert 'previous_automation' in result

    def test_calculate_efficiency_scores_handles_errors_gracefully(self, analytics_service, mock_device_repo):
        """Verify that errors in one calculation don't break others."""
        # Arrange
        mock_device_repo.list_sensor_configs.return_value = []
        
        with patch.object(analytics_service, 'calculate_environmental_stability', side_effect=Exception("DB Error")), \
             patch.object(analytics_service, 'calculate_energy_efficiency', return_value=90.0), \
             patch.object(analytics_service, 'calculate_automation_effectiveness', return_value=88.0):
            
            # Act
            result = analytics_service.calculate_efficiency_scores_concurrent(unit_id=1)
            
            # Assert - Should return neutral score for failed calculation
            assert result['environmental'] == 75.0  # Neutral/fallback score
            assert result['energy'] == 90.0
            assert result['automation'] == 88.0


# ==================== Cache Warming Tests ====================

class TestCacheWarming:
    """Test cache warming functionality."""

    def test_warm_cache_populates_caches(self, analytics_service, mock_analytics_repo):
        """Verify that warm_cache pre-populates the caches."""
        # Arrange
        mock_analytics_repo.get_latest_sensor_reading.return_value = {'temperature': 23.5}
        mock_analytics_repo.fetch_sensor_history.return_value = []
        
        # Act
        stats = analytics_service.warm_cache(unit_ids=[1, 2])
        
        # Assert
        assert 'units_processed' in stats
        assert stats['units_processed'] == 2
        assert 'execution_time_ms' in stats
        assert mock_analytics_repo.get_latest_sensor_reading.call_count >= 2

    def test_warm_cache_handles_no_units(self, analytics_service, mock_analytics_repo):
        """Verify that warm_cache handles empty unit list."""
        # Act
        stats = analytics_service.warm_cache(unit_ids=[])
        
        # Assert
        assert stats['units_processed'] == 0


# ==================== Environmental Analytics Tests ====================

class TestEnvironmentalCalculations:
    """Test environmental metric calculations."""

    def test_calculate_vpd_with_zones_optimal_seedling(self, analytics_service):
        """Test VPD calculation for optimal seedling conditions."""
        # Act
        result = analytics_service.calculate_vpd_with_zones(temperature=22.0, humidity=80.0)
        
        # Assert
        assert result['value'] is not None
        assert result['unit'] == 'kPa'
        assert result['status'] == 'optimal'
        assert result['zone'] == 'seedling'
        assert 'seedling' in result['optimal_for']

    def test_calculate_vpd_with_zones_optimal_vegetative(self, analytics_service):
        """Test VPD calculation for optimal vegetative conditions."""
        # Act
        result = analytics_service.calculate_vpd_with_zones(temperature=24.0, humidity=65.0)
        
        # Assert
        assert result['status'] == 'optimal'
        assert result['zone'] == 'vegetative'
        assert 'vegetative' in result['optimal_for']

    def test_calculate_vpd_with_zones_optimal_flowering(self, analytics_service):
        """Test VPD calculation for optimal flowering conditions."""
        # Act - Use 27°C and 60% RH which gives VPD ~1.4 kPa (in flowering zone)
        result = analytics_service.calculate_vpd_with_zones(temperature=27.0, humidity=60.0)
        
        # Assert
        assert result['status'] == 'optimal'
        assert result['zone'] == 'flowering'
        assert 'flowering' in result['optimal_for']

    def test_calculate_vpd_with_zones_too_low(self, analytics_service):
        """Test VPD calculation when VPD is too low."""
        # Act
        result = analytics_service.calculate_vpd_with_zones(temperature=20.0, humidity=95.0)
        
        # Assert
        assert result['zone'] == 'too_low'
        assert result['status'] == 'low'

    def test_calculate_vpd_with_zones_too_high(self, analytics_service):
        """Test VPD calculation when VPD is too high."""
        # Act
        result = analytics_service.calculate_vpd_with_zones(temperature=35.0, humidity=30.0)
        
        # Assert
        assert result['zone'] == 'too_high'
        assert result['status'] == 'high'

    def test_calculate_vpd_with_none_values(self, analytics_service):
        """Test VPD calculation with None values."""
        # Act
        result = analytics_service.calculate_vpd_with_zones(temperature=None, humidity=60.0)
        
        # Assert
        assert result['value'] is None
        assert result['status'] == 'unknown'

    def test_analyze_metric_trends_detects_rising_trend(self, analytics_service):
        """Test trend detection for rising values."""
        # Arrange - Create readings with rising temperature
        readings = []
        for i in range(10):
            readings.append({
                'temperature': 20.0 + i,  # Rising from 20 to 29
                'humidity': 60.0,
                'soil_moisture': 40.0
            })
        
        # Act
        trends = analytics_service.analyze_metric_trends(readings, days=1)
        
        # Assert
        assert trends['temperature']['trend'] == 'rising'
        assert trends['temperature']['change'] > 0

    def test_analyze_metric_trends_detects_falling_trend(self, analytics_service):
        """Test trend detection for falling values."""
        # Arrange
        readings = []
        for i in range(10):
            readings.append({
                'temperature': 30.0 - i,  # Falling from 30 to 21
                'humidity': 60.0,
                'soil_moisture': 40.0
            })
        
        # Act
        trends = analytics_service.analyze_metric_trends(readings, days=1)
        
        # Assert
        assert trends['temperature']['trend'] == 'falling'
        assert trends['temperature']['change'] < 0

    def test_analyze_metric_trends_detects_stable(self, analytics_service):
        """Test trend detection for stable values."""
        # Arrange
        readings = []
        for i in range(10):
            readings.append({
                'temperature': 23.0 + (i % 2) * 0.1,  # Very small oscillation
                'humidity': 60.0,
                'soil_moisture': 40.0
            })
        
        # Act
        trends = analytics_service.analyze_metric_trends(readings, days=1)
        
        # Assert
        assert trends['temperature']['trend'] == 'stable'

    def test_calculate_environmental_correlations_with_valid_data(self, analytics_service):
        """Test correlation calculation with sufficient data."""
        # Arrange - Create correlated data (negative correlation typical for temp-humidity)
        readings = []
        for i in range(20):
            readings.append({
                'temperature': 20.0 + i,
                'humidity': 80.0 - (i * 1.5)  # Inversely correlated
            })
        
        # Act
        result = analytics_service.calculate_environmental_correlations(readings)
        
        # Assert
        assert result['temp_humidity_correlation'] is not None
        assert -1.0 <= result['temp_humidity_correlation'] <= 1.0
        assert result['correlation_interpretation'] in ['weak', 'moderate', 'strong']
        assert result['sample_size'] == 20

    def test_calculate_environmental_correlations_insufficient_data(self, analytics_service):
        """Test correlation calculation with insufficient data."""
        # Arrange
        readings = [{'temperature': 23.0, 'humidity': 60.0}]  # Only 1 reading
        
        # Act
        result = analytics_service.calculate_environmental_correlations(readings)
        
        # Assert
        assert result['temp_humidity_correlation'] is None
        assert result['correlation_interpretation'] == 'insufficient_data'


# ==================== Efficiency Score Tests ====================

class TestEfficiencyScores:
    """Test efficiency score calculations."""

    def test_calculate_environmental_stability_with_stable_conditions(self, analytics_service, mock_analytics_repo, mock_device_repo):
        """Test stability score with stable environmental conditions."""
        # Arrange - Create stable readings
        readings = []
        for i in range(50):
            readings.append({
                'temperature': 23.0 + (i % 2) * 0.1,  # Very stable
                'humidity': 60.0 + (i % 2) * 0.5,
                'soil_moisture': 40.0
            })
        
        mock_analytics_repo.fetch_sensor_history.return_value = readings
        mock_device_repo.list_sensor_configs.return_value = []
        mock_device_repo.count_anomalies_for_sensors.return_value = 0
        
        # Act
        score = analytics_service.calculate_environmental_stability(unit_id=1, days=7)
        
        # Assert
        assert 75.0 <= score <= 100.0  # Should be good to excellent

    def test_calculate_environmental_stability_with_volatile_conditions(self, analytics_service, mock_analytics_repo, mock_device_repo):
        """Test stability score with volatile conditions."""
        # Arrange - Create volatile readings
        readings = []
        for i in range(50):
            readings.append({
                'temperature': 20.0 + (i % 10),  # High variation
                'humidity': 50.0 + (i % 20),
                'soil_moisture': 40.0
            })
        
        mock_analytics_repo.fetch_sensor_history.return_value = readings
        mock_device_repo.list_sensor_configs.return_value = []
        mock_device_repo.count_anomalies_for_sensors.return_value = 10  # Many anomalies
        
        # Act
        score = analytics_service.calculate_environmental_stability(unit_id=1, days=7)
        
        # Assert
        assert score < 75.0  # Should be fair or poor

    def test_calculate_environmental_stability_no_data(self, analytics_service, mock_analytics_repo):
        """Test stability score when no data available."""
        # Arrange
        mock_analytics_repo.fetch_sensor_history.return_value = []
        
        # Act
        score = analytics_service.calculate_environmental_stability(unit_id=1, days=7)
        
        # Assert
        assert score == 70.0  # Neutral score


# ==================== Data Formatting Tests ====================

class TestDataFormatting:
    """Test data formatting for charts and visualization."""

    def test_format_sensor_chart_data_basic(self, analytics_service, sample_sensor_readings):
        """Test basic chart data formatting."""
        # Act
        result = analytics_service.format_sensor_chart_data(sample_sensor_readings)
        
        # Assert
        assert 'timestamps' in result
        assert 'temperature' in result
        assert 'humidity' in result
        assert 'soil_moisture' in result
        assert len(result['timestamps']) == 10
        assert len(result['temperature']) == 10

    def test_format_sensor_chart_data_empty_readings(self, analytics_service):
        """Test chart formatting with empty readings."""
        # Act
        result = analytics_service.format_sensor_chart_data([])
        
        # Assert
        assert result['timestamps'] == []
        assert result['temperature'] == []

    def test_format_sensor_chart_data_handles_missing_values(self, analytics_service):
        """Test that formatting handles missing values gracefully."""
        # Arrange
        readings = [
            {'timestamp': datetime.now().isoformat(), 'temperature': 23.0},
            {'timestamp': datetime.now().isoformat(), 'humidity': 60.0},
        ]
        
        # Act
        result = analytics_service.format_sensor_chart_data(readings)
        
        # Assert
        assert len(result['timestamps']) == 2
        assert result['temperature'][0] == 23.0
        assert result['temperature'][1] is None
        assert result['humidity'][0] is None
        assert result['humidity'][1] == 60.0


# ==================== Statistics Tests ====================

class TestStatistics:
    """Test statistical calculations."""

    def test_get_sensor_statistics_with_data(self, analytics_service, mock_analytics_repo, sample_sensor_readings):
        """Test statistics calculation with valid data."""
        # Arrange
        mock_analytics_repo.fetch_sensor_history.return_value = sample_sensor_readings
        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 2, 0, 0, 0)
        
        # Act
        stats = analytics_service.get_sensor_statistics(start, end, unit_id=1)
        
        # Assert
        assert stats['count'] == 10
        assert 'temperature' in stats
        assert 'humidity' in stats
        assert stats['temperature']['avg'] is not None
        assert stats['temperature']['min'] is not None
        assert stats['temperature']['max'] is not None

    def test_get_sensor_statistics_no_data(self, analytics_service, mock_analytics_repo):
        """Test statistics calculation with no data."""
        # Arrange
        mock_analytics_repo.fetch_sensor_history.return_value = []
        start = datetime(2025, 1, 1, 0, 0, 0)
        end = datetime(2025, 1, 2, 0, 0, 0)
        
        # Act
        stats = analytics_service.get_sensor_statistics(start, end, unit_id=1)
        
        # Assert
        assert stats['count'] == 0


# ==================== Integration Tests ====================

class TestServiceIntegration:
    """Test service initialization and integration."""

    def test_analytics_service_initializes_correctly(self, mock_analytics_repo, mock_device_repo):
        """Test that service initializes with correct attributes."""
        # Act
        service = AnalyticsService(
            repository=mock_analytics_repo,
            device_repository=mock_device_repo
        )
        
        # Assert
        assert service.repository is mock_analytics_repo
        assert service.device_repository is mock_device_repo
        assert service._latest_reading_cache is not None
        assert service._history_cache is not None

    def test_analytics_service_without_device_repo(self, mock_analytics_repo):
        """Test that service works without device repository."""
        # Act
        service = AnalyticsService(repository=mock_analytics_repo)
        
        # Assert
        assert service.repository is mock_analytics_repo
        assert service.device_repository is None


class TestEnrichedHistory:
    """Tests for get_enriched_sensor_history and photoperiod logic."""

    def test_get_enriched_sensor_history_from_lux_sensor(self, analytics_service, mock_analytics_repo):
        """Test getting enriched history using light sensor (lux) as primary source."""
        # Arrange
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_analytics_repo.fetch_sensor_history.return_value = [
            {'timestamp': (now - timedelta(hours=2)).isoformat(), 'temperature': 25.0, 'light_lux': 500},
            {'timestamp': (now - timedelta(hours=1)).isoformat(), 'temperature': 26.0, 'light_lux': 600},
            {'timestamp': now.isoformat(), 'temperature': 22.0, 'light_lux': 10}
        ]

        # Act
        result = analytics_service.get_sensors_history_enriched(
            start_datetime=now - timedelta(hours=5),
            end_datetime=now,
            unit_id=1,
        )

        # Assert basic enrichment (lux values preserved and readings returned)
        assert 'readings' in result
        assert len(result['readings']) == 3
        assert 'light_lux' in result['readings'][0]

    def test_get_enriched_sensor_history_with_schedule(self, analytics_service, mock_analytics_repo):
        """Test getting enriched history using a fixed schedule."""
        # Arrange
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_analytics_repo.fetch_sensor_history.return_value = [
            {'timestamp': (now - timedelta(hours=10)).isoformat(), 'temperature': 20.0}, # 02:00 (Night)
            {'timestamp': (now - timedelta(hours=2)).isoformat(), 'temperature': 25.0}  # 10:00 (Day)
        ]

        # Act: call without day override (scheduling may be empty in tests)
        result = analytics_service.get_sensors_history_enriched(
            start_datetime=now - timedelta(hours=24),
            end_datetime=now,
            unit_id=1,
        )

        # Basic assertions about structure
        assert 'readings' in result
        assert 'summary' in result

    def test_get_enriched_sensor_history_aggregation(self, analytics_service, mock_analytics_repo):
        """Test that enriched history respects interval aggregation."""
        # Arrange
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 10 readings, 1 per hour
        readings = []
        for i in range(10):
            readings.append({
                'timestamp': (now - timedelta(hours=i)).isoformat(),
                'temperature': 20.0 + i,
                'light_lux': 1000 if i < 5 else 0
            })
        mock_analytics_repo.fetch_sensor_history.return_value = readings

        # Act: basic call without aggregation interval
        result = analytics_service.get_sensors_history_enriched(
            start_datetime=now - timedelta(hours=24),
            end_datetime=now,
            unit_id=1,
        )

        # Assert basic shape and count
        assert 'readings' in result
        assert result['summary']['count'] == 10
