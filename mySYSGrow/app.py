"""
Flask application for managing plant growth environment.

Author: Sebastian Gomez
Date: 26/05/24
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
from grow_manager import GrowthManager, DatabaseManager
from actuator_manager import RelayActuator
import matplotlib.pyplot as plt
import threading
import signal
import sys
import io
import base64
import atexit
from default_values import DefaultValues

app = Flask(__name__, static_folder='static')
app.config['DATABASE'] = 'database/grow_tent.db'
database_manager = DatabaseManager()
database_manager.init_app(app)

with app.app_context():
    global manager
    manager = GrowthManager(database_manager=database_manager)

# Register cleanup function to be called on exit
atexit.register(manager.actuator_manager.cleanup)

used_pins = set()

def get_available_gpio_pins():
    return {pin: name for pin, name in DefaultValues.GPIO_PINS.items() if pin not in used_pins}

@app.route('/')
def index():
    """
    Render the index page with a list of plants.

    Returns:
        str: Rendered HTML template.
    """
    plants = manager.database_manager.get_all_plants()
    current_light_schedule = manager.get_light_schedule()
    thresholds = {
        'temperature_threshold': manager.temperature_threshold,
        'humidity_threshold': manager.humidity_threshold,
        'soil_moisture_threshold': manager.soil_moisture_threshold
        }
    return render_template('index.html', plants=plants, light_schedule=current_light_schedule or {}, thresholds=thresholds)

@app.route('/schedule_lights', methods=['GET', 'POST'])
def schedule_lights():
    """
    Schedule lights based on user input.

    Returns:
        redirect: Redirect to the index page.
    """
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    manager.set_light_schedule(start_time, end_time)
    return redirect(url_for('index'))

@app.route('/schedule_fan', methods=['GET', 'POST'])
def schedule_fan():
    """
    Schedule fan based on user input.

    Returns:
        redirect: Redirect to the settings page.
    """
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    manager.set_fan_schedule(start_time, end_time)
    return redirect(url_for('settings'))

@app.route('/set_thresholds', methods=['POST'])
def set_thresholds():
    """
    Set temperature, humedity and soil moisture threshold.

    Returns:
        redirect: Redirect to the index page.
    """
    temperature_threshold = float(request.form['temperature_threshold'])
    humidity_threshold = float(request.form['humidity_threshold'])
    soil_moisture_threshold = float(request.form['soil_moisture_threshold'])
    manager.set_thresholds(temperature_threshold, humidity_threshold, soil_moisture_threshold)
    return redirect(url_for('index'))

@app.route('/add_plant', methods=['GET', 'POST'])
def add_plant():
    """
    Add a plant and link soil moisture sensors to plants.

    Returns:
        redirect: Redirect to the index page or re-renders the add_plant page.
    """
    if request.method == 'POST':
        plant_type = request.form.get('plant_type')
        plant_stage = request.form.get('plant_stage')
        days_current_stage = request.form.get('days_in_stage')
        manager.add_plant(plant_type, plant_stage, days_current_stage)
        return redirect(url_for('index'))

    plants = manager.database_manager.get_all_plants()
    sensors = manager.database_manager.get_sensors_by_type('Soil-Moisture')
    print("Plants retrieved:", plants)
    print("Soil moisture sensors retrieved:", sensors)
    return render_template('add_plant.html', plants=plants, sensors=sensors)

@app.route('/link_sensor', methods=['POST'])
def link_sensor():
    """
    Link a soil moisture sensor to a plant.

    Returns:
        redirect: Redirect to the index page.
    """
    if request.method == 'POST':
        plant_id = request.form['plant_id']
        sensor_id = request.form['sensor_id']
        print("plant_id: ", plant_id, "SENSOR_ID: ", sensor_id)
        manager.link_sensor_to_plant(plant_id, sensor_id)
        return redirect(url_for('index'))

@app.route('/increase_days/<plant_name>', methods=['POST'])
def increase_days(plant_name):
    plant = manager.get_plant_by_name(plant_name)
    if plant:
        plant.increase_days_in_stage()
        manager.database_manager.update_plant_days(plant_name, plant.get_days_current_stage())
        return jsonify({"status": "success", "message": f"Increased days for {plant_name}."})
    return jsonify({"status": "error", "message": f"Plant {plant_name} not found."})

@app.route('/decrease_days/<plant_name>', methods=['POST'])
def decrease_days(plant_name):
    plant = manager.get_plant_by_name(plant_name)
    if plant:
        plant.decrease_days_in_stage()
        manager.database_manager.update_plant_days(plant_name, plant.get_days_current_stage())
        return jsonify({"status": "success", "message": f"Decreased days for {plant_name}."})
    return jsonify({"status": "error", "message": f"Plant {plant_name} not found."})

# @app.route('/sensor_data/<int:plant_id>')
# def soil_moisture_history(plant_id):
#     history = database_manager.get_soil_moisture_history(plant_id)
#     plant = database_manager.get_plant_by_id(plant_id)
#     return render_template('sensor_data.html', history=history, plant=plant)

@app.route('/reading_update')
def reading_update():
    """
    Fetch the current environmental sensor data and return it as JSON.

    This endpoint is called by the client-side JavaScript to get the latest
    temperature and humidity readings without refreshing the entire page.

    Returns:
        Response: A Flask Response object containing the sensor data in JSON format.
    """
    data = manager.monitor_environment()
    print(f"Reading update in app.py: {data}")
    return jsonify(data)

@app.route('/sensor_data/<int:plant_id>')
def sensor_data():
    """
    Display sensor data in tabular format.

    Returns:
        str: Rendered HTML template.
    """
    sensor_data = manager.database_manager.get_sensor_data()
    readings = manager.database_manager.get_all_plant_readings()
    return render_template('sensor_data.html', sensor_data=sensor_data, readings=readings)

@app.route('/sensor_data_graph')
def sensor_data_graph():
    """
    Display a graph of sensor data over time.

    Returns:
        str: Rendered HTML template with graph image.
    """
    sensor_data = manager.database_manager.get_sensor_data()
    timestamps = [data['timestamp'] for data in sensor_data]
    temperatures = [data['temperature'] for data in sensor_data]
    humidities = [data['humidity'] for data in sensor_data]
    moisture_levels = [data['moisture_level'] for data in sensor_data]

    fig, ax = plt.subplots(3, 1, figsize=(10, 15))

    ax[0].plot(timestamps, temperatures, label='Temperature')
    ax[0].set_title('Temperature over Time')
    ax[0].set_xlabel('Time')
    ax[0].set_ylabel('Temperature (C)')
    
    ax[1].plot(timestamps, humidities, label='Humidity')
    ax[1].set_title('Humidity over Time')
    ax[1].set_xlabel('Time')
    ax[1].set_ylabel('Humidity (%)')
    
    ax[2].plot(timestamps, moisture_levels, label='Soil Moisture')
    ax[2].set_title('Soil Moisture over Time')
    ax[2].set_xlabel('Time')
    ax[2].set_ylabel('Moisture Level')

    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    graph_url = base64.b64encode(img.getvalue()).decode()

    plt.close(fig)

    return render_template('sensor_data_graph.html', graph_url=graph_url)

@app.route('/set_stage_durations', methods=['GET', 'POST'])
def set_stage_durations():
    """
    Set stage durations for plant growth.

    Returns:
        str: Rendered HTML template.
        redirect: Redirect to the index page.
    """
    if request.method == 'POST':
        plant_name = request.form['plant_name']
        seed_days = int(request.form['seed_days'])
        grow_days = int(request.form['grow_days'])
        flowering_days = int(request.form['flowering_days'])
        manager.set_stage_durations(plant_name, seed_days, grow_days, flowering_days)
        return redirect(url_for('index'))
    plants = manager.database_manager.get_all_plants()
    return render_template('set_stage_durations.html', plants=plants)

@app.route('/settings')
def settings():
    available_gpio_pins = get_available_gpio_pins()
    available_actuators = ['Heater', 'Cooler', 'Humidifier', 'CO2Injector']  # List all available actuator types
    active_actuators = manager.actuator_manager.get_actuators()
    try:
        active_sensors = manager.sensor_manager.get_sensors()
        print(f"Active sensors: {active_sensors}")
    except Exception as e:
        print(f"Error retrieving sensors: {e}")
        active_sensors = []

    try:
        actuator_states = manager.actuator_manager.get_actuator_states()
    except Exception as e:
        print(f"Error retrieving actuator states: {e}")
        actuator_states = {actuator: 'off' for actuator in active_actuators}
    
    return render_template('settings.html', available_gpio_pins=available_gpio_pins, available_actuators=available_actuators, active_actuators=active_actuators, active_sensors=active_sensors, actuator_states=actuator_states)

# @app.route('/sensors')
# def sensors():
#     active_sensors = manager.sensor_manager.get_sensors()

@app.route('/add_actuator', methods=['POST'])
def add_actuator():
    actuator_type = request.form['actuator_type']
    actuator_pin = int(request.form['actuator_pin'])
    actuator_ip = request.form.get('actuator_ip', None)
    actuator = RelayActuator(actuator_type, actuator_pin, actuator_ip)
    manager.actuator_manager.add_actuator(actuator_type, actuator)
    return jsonify({"status": "success", "actuator": actuator_type})

@app.route('/add_sensor', methods=['POST'])
def add_sensor():
    sensor_name = request.form['sensor_name']
    sensor_type = request.form['sensor_type']
    sensor_pin = request.form.get('sensor_pin', type=int)
    adc_channel = request.form.get('adc_channel', None)
    sensor_ip = request.form.get('sensor_ip', None)

    print("sensor pin 1: app.py:", sensor_pin)

    if sensor_pin in used_pins:
        return jsonify({"status": "error", "message": "GPIO pin already used"}), 400
    
    # Only override sensor_pin if the sensor_type is Soil-Moisture
    if sensor_type == 'Soil-Moisture' and adc_channel:
        print(f"Mapping ADC channel {adc_channel} for Soil-Moisture sensor")
        sensor_pin_mapped = DefaultValues.ADC_CHANNEL_MAP.get(adc_channel, None)
        if sensor_pin_mapped is not None:
            sensor_pin = sensor_pin_mapped
    
    print("sensor pin 2: app.py:", sensor_pin)

    manager.sensor_manager.add_sensor(sensor_type, sensor_pin, sensor_ip)
    used_pins.add(sensor_pin)

    return jsonify({'status': 'success', 'sensor': sensor_name}), 200

@app.route('/remove_actuator', methods=['POST'])
def remove_actuator():
    data = request.json
    actuator_type = data['actuator_type']
    manager.actuator_manager.remove_actuator(actuator_type)
    return jsonify({"status": "success", "actuator": actuator_type})

@app.route('/remove_sensor', methods=['POST'])
def remove_sensor():
    data = request.json
    sensor_type = data['sensor_type']
    manager.sensor_manager.remove_sensor(sensor_type)
    return jsonify({"status": "success", "actuator": sensor_type})

@app.route('/control_actuator', methods=['POST'])
def control_actuator():
    data = request.json
    actuator_type = data['actuator_type']
    action = data['action']
    
    if action == 'activate':
        manager.actuator_manager.activate_actuator(actuator_type)
    elif action == 'deactivate':
        manager.actuator_manager.deactivate_actuator(actuator_type)
    
    return jsonify({"status": "success", "actuator": actuator_type, "action": action})
    
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': str(error)}), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({'status': 'error', 'message': 'Bad request'}), 400

def cleanup_resources(signal, frame):
    print("Cleaning up resources...")
    for sensor in manager.sensor_manager.sensors.values():
        if hasattr(sensor, 'cleanup'):
            sensor.cleanup()
    sys.exit(0)

# Register the signal handlers for cleanup
signal.signal(signal.SIGINT, cleanup_resources)
signal.signal(signal.SIGTERM, cleanup_resources)

    
if __name__ == '__main__':
    app.run(host="192.168.0.40", debug=True, use_reloader=False)
