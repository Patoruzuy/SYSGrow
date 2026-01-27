from types import SimpleNamespace
from app.hardware.sensors.processors.priority_processor import PriorityProcessor
from app.enums import SensorType

pr = PriorityProcessor(stale_seconds=999)
soil_sensor = SimpleNamespace(id=1, unit_id=1, name='Soil Probe', sensor_type=SensorType.PLANT, model='Soil-Moisture', protocol='mqtt')
env_sensor = SimpleNamespace(id=2, unit_id=1, name='Env Sensor', sensor_type=SensorType.ENVIRONMENTAL, model='BME280', protocol='zigbee2mqtt')

sensors = {1: soil_sensor, 2: env_sensor}

def resolve_sensor(sid):
    return sensors.get(sid)

soil_reading = SimpleNamespace(sensor_id=1, unit_id=1, data={'temperature':18.0,'humidity':55.0,'soil_moisture':42.0}, quality_score=0.5)
env_reading = SimpleNamespace(sensor_id=2, unit_id=1, data={'temperature':22.0,'humidity':60.0}, quality_score=0.9)

pr.ingest(sensor=soil_sensor, reading=soil_reading, resolve_sensor=resolve_sensor)
print('primary after soil:', pr.primary_sensors)
pr.ingest(sensor=env_sensor, reading=env_reading, resolve_sensor=resolve_sensor)
print('primary after env:', pr.primary_sensors)
print('soil primary_metrics:', pr._primary_metrics_for_sensor(soil_sensor))
print('soil is_primary_temp:', pr._is_primary_metric(soil_sensor, 'temperature'))
print('soil auto_priority temp:', pr._auto_priority(soil_sensor, 'temperature'))
print('env primary_metrics:', pr._primary_metrics_for_sensor(env_sensor))
print('env is_primary_temp:', pr._is_primary_metric(env_sensor, 'temperature'))
print('env auto_priority temp:', pr._auto_priority(env_sensor, 'temperature'))
print('get_primary temp:', pr.get_primary_sensor(1,'temperature'))
