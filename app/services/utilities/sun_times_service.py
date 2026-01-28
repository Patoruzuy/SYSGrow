"""
Sun Times Service
=================

Provides sunrise, sunset, dawn, dusk calculations based on geographic location.
Uses the free sunrise-sunset.org API for calculations.

Features:
- Sunrise/sunset times for any date
- Civil, nautical, and astronomical twilight
- Caching to minimize API calls
- Fallback to schedule-based times if API fails

Author: Sebastian Gomez
Date: January 2026
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, Any, Tuple
from functools import lru_cache
from zoneinfo import ZoneInfo
import json

logger = logging.getLogger(__name__)


@dataclass
class SunTimes:
    """Sun times for a specific date and location."""
    date: date
    sunrise: time
    sunset: time
    solar_noon: time
    day_length_hours: float
    civil_twilight_begin: Optional[time] = None
    civil_twilight_end: Optional[time] = None
    nautical_twilight_begin: Optional[time] = None
    nautical_twilight_end: Optional[time] = None
    astronomical_twilight_begin: Optional[time] = None
    astronomical_twilight_end: Optional[time] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        def time_str(t: Optional[time]) -> Optional[str]:
            return t.strftime("%H:%M") if t else None
        
        return {
            "date": self.date.isoformat(),
            "sunrise": time_str(self.sunrise),
            "sunset": time_str(self.sunset),
            "solar_noon": time_str(self.solar_noon),
            "day_length_hours": self.day_length_hours,
            "civil_twilight_begin": time_str(self.civil_twilight_begin),
            "civil_twilight_end": time_str(self.civil_twilight_end),
            "nautical_twilight_begin": time_str(self.nautical_twilight_begin),
            "nautical_twilight_end": time_str(self.nautical_twilight_end),
            "astronomical_twilight_begin": time_str(self.astronomical_twilight_begin),
            "astronomical_twilight_end": time_str(self.astronomical_twilight_end),
        }


class SunTimesService:
    """
    Service for calculating sun times based on geographic location.
    
    Uses the free sunrise-sunset.org API:
    https://sunrise-sunset.org/api
    
    API is free, no authentication required, rate-limited.
    """
    
    API_URL = "https://api.sunrise-sunset.org/json"
    
    def __init__(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        timezone: Optional[str] = None,
        cache_hours: int = 24,
    ):
        """
        Initialize sun times service.
        
        Args:
            latitude: Default latitude for calculations
            longitude: Default longitude for calculations
            timezone: Timezone string (e.g., 'America/New_York')
            cache_hours: Hours to cache sun times (default 24)
        """
        self.default_latitude = latitude
        self.default_longitude = longitude
        self.timezone = timezone
        self.cache_hours = cache_hours
        
        # Simple in-memory cache: {(lat, lng, date_str): (SunTimes, cached_at)}
        self._cache: Dict[Tuple[float, float, str], Tuple[SunTimes, datetime]] = {}
        
        logger.info(f"SunTimesService initialized (lat={latitude}, lng={longitude})")
    
    def get_sun_times(
        self,
        target_date: Optional[date] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Optional[SunTimes]:
        """
        Get sun times for a specific date and location.
        
        Args:
            target_date: Date to get sun times for (default: today)
            latitude: Latitude (default: use configured default)
            longitude: Longitude (default: use configured default)
            
        Returns:
            SunTimes object or None if calculation fails
        """
        lat = latitude or self.default_latitude
        lng = longitude or self.default_longitude
        
        if lat is None or lng is None:
            logger.warning("No location configured for sun times calculation")
            return None
        
        target_date = target_date or date.today()
        
        # Check cache
        cache_key = (lat, lng, target_date.isoformat())
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Fetch from API
        sun_times = self._fetch_sun_times(lat, lng, target_date)
        
        if sun_times:
            self._cache[cache_key] = (sun_times, datetime.now())
        
        return sun_times
    
    def _get_cached(self, cache_key: Tuple[float, float, str]) -> Optional[SunTimes]:
        """Get cached sun times if still valid."""
        if cache_key not in self._cache:
            return None
        
        sun_times, cached_at = self._cache[cache_key]
        if datetime.now() - cached_at > timedelta(hours=self.cache_hours):
            del self._cache[cache_key]
            return None
        
        return sun_times
    
    def _fetch_sun_times(
        self,
        latitude: float,
        longitude: float,
        target_date: date,
    ) -> Optional[SunTimes]:
        """
        Fetch sun times from sunrise-sunset.org API.
        
        API returns UTC times by default.
        """
        try:
            import requests
            
            params = {
                "lat": latitude,
                "lng": longitude,
                "date": target_date.isoformat(),
                "formatted": 0,  # Get ISO 8601 format
            }
            
            response = requests.get(
                self.API_URL,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") != "OK":
                logger.error(f"Sun times API error: {data.get('status')}")
                return None
            
            results = data.get("results", {})
            
            return self._parse_api_response(results, target_date)
            
        except ImportError:
            logger.warning("requests library not available, using fallback sun times")
            return self._fallback_sun_times(target_date)
        except Exception as e:
            logger.error(f"Failed to fetch sun times: {e}")
            return self._fallback_sun_times(target_date)
    
    def _parse_api_response(
        self,
        results: Dict[str, Any],
        target_date: date,
    ) -> SunTimes:
        """Parse API response into SunTimes object."""
        def parse_time(iso_str: Optional[str]) -> Optional[time]:
            if not iso_str:
                return None
            try:
                # API returns UTC ISO 8601 format
                dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                if self.timezone:
                    try:
                        dt = dt.astimezone(ZoneInfo(self.timezone))
                    except Exception:
                        logger.debug("Invalid timezone '%s' for sun times; using UTC", self.timezone)
                return dt.time()
            except (ValueError, AttributeError):
                return None
        
        # Calculate day length from sunrise/sunset
        sunrise = parse_time(results.get("sunrise"))
        sunset = parse_time(results.get("sunset"))
        
        day_length = 0.0
        if sunrise and sunset:
            sunrise_minutes = sunrise.hour * 60 + sunrise.minute
            sunset_minutes = sunset.hour * 60 + sunset.minute
            if sunset_minutes > sunrise_minutes:
                day_length = (sunset_minutes - sunrise_minutes) / 60.0
        
        # Also try to parse the day_length from API if available
        api_day_length = results.get("day_length")
        if isinstance(api_day_length, (int, float)):
            day_length = api_day_length / 3600.0  # Convert seconds to hours
        
        return SunTimes(
            date=target_date,
            sunrise=sunrise or time(6, 0),
            sunset=sunset or time(18, 0),
            solar_noon=parse_time(results.get("solar_noon")) or time(12, 0),
            day_length_hours=day_length,
            civil_twilight_begin=parse_time(results.get("civil_twilight_begin")),
            civil_twilight_end=parse_time(results.get("civil_twilight_end")),
            nautical_twilight_begin=parse_time(results.get("nautical_twilight_begin")),
            nautical_twilight_end=parse_time(results.get("nautical_twilight_end")),
            astronomical_twilight_begin=parse_time(results.get("astronomical_twilight_begin")),
            astronomical_twilight_end=parse_time(results.get("astronomical_twilight_end")),
        )
    
    def _fallback_sun_times(self, target_date: date) -> SunTimes:
        """
        Provide fallback sun times when API is unavailable.
        
        Uses approximate values for temperate latitudes.
        Adjusts based on month for seasonal variation.
        """
        month = target_date.month
        
        # Approximate sunrise/sunset times by month (temperate latitude)
        # Values are approximate for ~40°N latitude
        seasonal_times = {
            1: (time(7, 20), time(17, 0)),   # January
            2: (time(6, 50), time(17, 40)),  # February
            3: (time(6, 10), time(18, 15)),  # March
            4: (time(6, 25), time(19, 50)),  # April (DST)
            5: (time(5, 50), time(20, 20)),  # May
            6: (time(5, 30), time(20, 45)),  # June
            7: (time(5, 45), time(20, 35)),  # July
            8: (time(6, 15), time(20, 0)),   # August
            9: (time(6, 45), time(19, 15)),  # September
            10: (time(7, 15), time(18, 30)), # October
            11: (time(6, 50), time(16, 55)), # November (DST ends)
            12: (time(7, 15), time(16, 40)), # December
        }
        
        sunrise, sunset = seasonal_times.get(month, (time(6, 0), time(18, 0)))
        
        sunrise_minutes = sunrise.hour * 60 + sunrise.minute
        sunset_minutes = sunset.hour * 60 + sunset.minute
        day_length = (sunset_minutes - sunrise_minutes) / 60.0
        
        return SunTimes(
            date=target_date,
            sunrise=sunrise,
            sunset=sunset,
            solar_noon=time(12, 0),
            day_length_hours=day_length,
        )
    
    def is_daytime(
        self,
        check_time: Optional[datetime] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        use_civil_twilight: bool = False,
    ) -> bool:
        """
        Check if it's currently daytime at the location.
        
        Args:
            check_time: Time to check (default: now)
            latitude: Location latitude
            longitude: Location longitude
            use_civil_twilight: If True, use civil twilight instead of sunrise/sunset
            
        Returns:
            True if it's daytime
        """
        check_time = check_time or datetime.now()
        sun_times = self.get_sun_times(
            target_date=check_time.date(),
            latitude=latitude,
            longitude=longitude,
        )
        
        if not sun_times:
            # Default to daytime if no data available
            return True
        
        current_time = check_time.time()
        
        if use_civil_twilight and sun_times.civil_twilight_begin and sun_times.civil_twilight_end:
            start = sun_times.civil_twilight_begin
            end = sun_times.civil_twilight_end
        else:
            start = sun_times.sunrise
            end = sun_times.sunset
        
        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        
        return start_minutes <= current_minutes < end_minutes
    
    def get_light_schedule_for_plant(
        self,
        target_hours: float,
        target_date: Optional[date] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Tuple[time, time]:
        """
        Calculate optimal light schedule to achieve target hours.
        
        For outdoor units, supplements natural light.
        For indoor units, calculates schedule centered on solar noon.
        
        Args:
            target_hours: Target light hours per day
            target_date: Date to calculate for
            latitude: Location latitude
            longitude: Location longitude
            
        Returns:
            Tuple of (start_time, end_time) for artificial lighting
        """
        sun_times = self.get_sun_times(
            target_date=target_date,
            latitude=latitude,
            longitude=longitude,
        )
        
        if sun_times:
            natural_hours = sun_times.day_length_hours
            solar_noon = sun_times.solar_noon
        else:
            natural_hours = 12.0
            solar_noon = time(12, 0)
        
        # Calculate how much artificial light needed
        supplemental_hours = max(0, target_hours - natural_hours)
        
        if supplemental_hours == 0:
            # No supplemental light needed, return sunrise/sunset
            if sun_times:
                return (sun_times.sunrise, sun_times.sunset)
            return (time(6, 0), time(18, 0))
        
        # Center artificial light period around solar noon
        half_hours = target_hours / 2
        noon_minutes = solar_noon.hour * 60 + solar_noon.minute
        
        start_minutes = max(0, int(noon_minutes - half_hours * 60))
        end_minutes = min(24 * 60 - 1, int(noon_minutes + half_hours * 60))
        
        start = time(start_minutes // 60, start_minutes % 60)
        end = time(end_minutes // 60, end_minutes % 60)
        
        return (start, end)
    
    def clear_cache(self):
        """Clear the sun times cache."""
        self._cache.clear()
        logger.info("Sun times cache cleared")
    
    def set_location(self, latitude: float, longitude: float, timezone: Optional[str] = None):
        """
        Update default location.
        
        Args:
            latitude: New latitude
            longitude: New longitude
            timezone: Optional timezone string
        """
        self.default_latitude = latitude
        self.default_longitude = longitude
        if timezone:
            self.timezone = timezone
        
        # Clear cache when location changes
        self.clear_cache()
        logger.info(f"Sun times location updated: lat={latitude}, lng={longitude}")


# Singleton instance
_sun_times_service: Optional[SunTimesService] = None


def get_sun_times_service() -> SunTimesService:
    """Get or create the singleton SunTimesService instance."""
    global _sun_times_service
    if _sun_times_service is None:
        _sun_times_service = SunTimesService()
    return _sun_times_service


def configure_sun_times_service(
    latitude: float,
    longitude: float,
    timezone: Optional[str] = None,
) -> SunTimesService:
    """
    Configure the sun times service with location.
    
    Args:
        latitude: Geographic latitude
        longitude: Geographic longitude
        timezone: Optional timezone string
        
    Returns:
        Configured SunTimesService instance
    """
    global _sun_times_service
    _sun_times_service = SunTimesService(
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )
    return _sun_times_service
