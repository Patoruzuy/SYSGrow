from infrastructure.database.repositories.devices import DeviceRepository


def test_get_by_friendly_name_falls_back_to_sensor_name_for_legacy_zigbee2mqtt_configs():
    class FakeBackend:
        def get_sensor_configs(self, unit_id=None):
            return [
                {
                    "sensor_id": 12,
                    "unit_id": 1,
                    "name": "Environment_sensor",
                    "protocol": "zigbee2mqtt",
                    "config": {
                        # Legacy schema: only base topic stored, no friendly_name key.
                        "mqtt_topic": "zigbee2mqtt",
                        "zigbee_address": "0xa4c13833229dd565",
                    },
                }
            ]

    repo = DeviceRepository(FakeBackend())
    result = repo.get_by_friendly_name("Environment_sensor")

    assert result is not None
    assert result.sensor_id == 12
    assert result.unit_id == 1
