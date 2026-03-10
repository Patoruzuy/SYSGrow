"""
Unit tests for app.utils.psychrometrics module.

Tests the air-science derived metric calculations:
- VPD (Vapor Pressure Deficit)
- Dew Point
- Heat Index
"""

import pytest

from app.utils.psychrometrics import (
    calculate_dew_point_c,
    calculate_heat_index_c,
    calculate_svp_kpa,
    calculate_vpd_kpa,
    compute_derived_metrics,
)


class TestSaturationVaporPressure:
    """Test saturation vapor pressure calculation (Magnus formula)."""

    def test_svp_at_0c(self):
        """SVP at 0°C should be approximately 0.611 kPa."""
        svp = calculate_svp_kpa(0)
        assert 0.60 < svp < 0.62

    def test_svp_at_20c(self):
        """SVP at 20°C should be approximately 2.34 kPa."""
        svp = calculate_svp_kpa(20)
        assert 2.3 < svp < 2.4

    def test_svp_at_25c(self):
        """SVP at 25°C should be approximately 3.17 kPa."""
        svp = calculate_svp_kpa(25)
        assert 3.1 < svp < 3.2


class TestVPD:
    """Test Vapor Pressure Deficit calculation."""

    def test_vpd_100_percent_humidity_is_zero(self):
        """At 100% RH, VPD should be 0."""
        vpd = calculate_vpd_kpa(25, 100)
        assert vpd == pytest.approx(0, abs=0.01)

    def test_vpd_0_percent_humidity_equals_svp(self):
        """At 0% RH, VPD should equal SVP."""
        temp = 25
        vpd = calculate_vpd_kpa(temp, 0)
        svp = calculate_svp_kpa(temp)
        assert vpd == pytest.approx(svp, rel=0.01)

    def test_vpd_typical_grow_room_conditions(self):
        """25°C at 60% RH should give VPD around 1.27 kPa."""
        vpd = calculate_vpd_kpa(25, 60)
        assert 1.2 < vpd < 1.4

    def test_vpd_negative_temperature(self):
        """VPD should work with sub-zero temperatures."""
        vpd = calculate_vpd_kpa(-5, 80)
        assert vpd > 0


class TestDewPoint:
    """Test dew point calculation."""

    def test_dew_point_100_percent_humidity_equals_temp(self):
        """At 100% RH, dew point should equal air temperature."""
        temp = 25
        dew_point = calculate_dew_point_c(temp, 100)
        assert dew_point == pytest.approx(temp, abs=0.5)

    def test_dew_point_lower_than_temp(self):
        """Dew point should always be <= air temperature."""
        dew_point = calculate_dew_point_c(25, 60)
        assert dew_point < 25

    def test_dew_point_typical_conditions(self):
        """25°C at 60% RH should give dew point around 16.7°C."""
        dew_point = calculate_dew_point_c(25, 60)
        assert 15 < dew_point < 18


class TestHeatIndex:
    """Test heat index calculation."""

    def test_heat_index_below_threshold_equals_temp(self):
        """Below 27°C and 40% RH, heat index should equal temperature."""
        hi = calculate_heat_index_c(25, 50)
        assert hi == pytest.approx(25, abs=0.1)

    def test_heat_index_hot_humid_conditions(self):
        """30°C at 80% RH should have heat index higher than temp."""
        hi = calculate_heat_index_c(30, 80)
        assert hi > 30

    def test_heat_index_very_hot(self):
        """35°C at 70% RH should feel significantly hotter."""
        hi = calculate_heat_index_c(35, 70)
        assert hi > 40


class TestComputeDerivedMetrics:
    """Test the combined compute_derived_metrics function."""

    def test_returns_all_keys(self):
        """Should return vpd_kpa, dew_point_c, and heat_index_c."""
        result = compute_derived_metrics(25, 60)
        assert "vpd_kpa" in result
        assert "dew_point_c" in result
        assert "heat_index_c" in result

    def test_returns_none_values_for_none_temp(self):
        """Should return dict with None values if temperature is None."""
        result = compute_derived_metrics(None, 60)
        assert result["vpd_kpa"] is None
        assert result["dew_point_c"] is None
        assert result["heat_index_c"] is None

    def test_returns_none_values_for_none_humidity(self):
        """Should return dict with None values if humidity is None."""
        result = compute_derived_metrics(25, None)
        assert result["vpd_kpa"] is None
        assert result["dew_point_c"] is None
        assert result["heat_index_c"] is None

    def test_values_are_numeric(self):
        """All returned values should be numeric."""
        result = compute_derived_metrics(25, 60)
        assert isinstance(result["vpd_kpa"], (int, float))
        assert isinstance(result["dew_point_c"], (int, float))
        assert isinstance(result["heat_index_c"], (int, float))


class TestDIF:
    """Test DIF (Difference between Day and Night Temperature) calculation.

    Note: calculate_dif_c takes a sequence of temperature readings with timestamps
    and calculates the average difference between day and night periods.
    For now, we skip these tests as they require pandas and more complex setup.
    """

    @pytest.mark.skip(reason="calculate_dif_c requires time-series data with pandas")
    def test_positive_dif(self):
        """Positive DIF when day temp > night temp."""
        pass

    @pytest.mark.skip(reason="calculate_dif_c requires time-series data with pandas")
    def test_zero_dif(self):
        """Zero DIF when day temp == night temp."""
        pass

    @pytest.mark.skip(reason="calculate_dif_c requires time-series data with pandas")
    def test_negative_dif(self):
        """Negative DIF when day temp < night temp."""
        pass
