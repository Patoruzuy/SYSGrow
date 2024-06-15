"""
Flask application for managing plant growth environment.

Author: Sebastian Gomez
Date: 26/05/24
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
from grow_manager import GrowthManager, DatabaseManager
from actuator_manager import RelayActuator
import matplotlib.pyplot as plt
import io
import base64
import atexit


app = Flask(__name__, static_folder='static')
app.config['DATABASE'] = 'database/grow_tent.db'
database_manager = DatabaseManager()
database_manager.init_app(app)

with app.app_context():
    global manager
    manager = GrowthManager(database_manager=database_manager)

# Register cleanup function to be called on exit
atexit.register(manager.actuator_manager.cleanup)

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
    Add a new plant to the system.

    Returns:
        str: Rendered HTML template.
        redirect: Redirect to the index page.
    """
    if request.method == 'POST':
        plant_type = request.form['plant_type']
        plant_stage = request.form['plant_stage']
        manager.add_plant(plant_type, plant_stage)
        return redirect(url_for('index'))
    return render_template('add_plant.html')

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

@app.route('/soil_moisture_history/<int:plant_id>')
def soil_moisture_history(plant_id):
    history = database_manager.get_soil_moisture_history(plant_id)
    plant = database_manager.get_plant(plant_id)
    return render_template('index.html', history=history, plant=plant)

@app.route('/link_sensor', methods=['GET', 'POST'])
def link_sensor():
    """
    Link a soil moisture sensor to a plant.

    Returns:
        redirect: Redirect to the index page.
    """
    if request.method == 'POST':
        plant_id = request.form['plant_id']
        sensor_id = request.form['sensor_id']
        manager.link_sensor_to_plant(plant_id, sensor_id)
        return redirect(url_for('index'))
    
    plants = manager.database_manager.get_all_plants()
    sensors = manager.database_manager.get_sensors_by_type('Soil-Moisture')
    print("Plants retrieved:", plants)
    print("Soil moisture sensors retrieved:", sensors)
    return render_template('link_sensor.html', plants=plants, sensors=sensors)

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

@app.route('/sensor_data')
def sensor_data():
    """
    Display sensor data in tabular format.

    Returns:
        str: Rendered HTML template.
    """
    sensor_data = manager.database_manager.get_sensor_data()
    plant_sensor_data = manager.database_manager.get_all_plants()
    return render_template('sensor_data.html', sensor_data=sensor_data, plant_sensor_data=plant_sensor_data)

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
        manager.set_stage_durations(plant_name, seed_days, grow_days)
        return redirect(url_for('index'))
    plants = manager.database_manager.get_all_plants()
    return render_template('set_stage_durations.html', plants=plants)

@app.route('/actuator')
def actuator():
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

    return render_template('actuator.html', available_actuators=available_actuators, active_actuators=active_actuators, active_sensors=active_sensors, actuator_states=actuator_states)

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
    sensor_type = request.form['sensor_type']
    sensor_pin = request.form.get('sensor_pin', type=int)
    sensor_ip = request.form.get('sensor_ip', None)
    if not sensor_type or (not sensor_pin and not sensor_ip):
        return jsonify({'status': 'error', 'message': 'Invalid sensor configuration'}), 400

    manager.sensor_manager.add_sensor(sensor_type, sensor_pin, sensor_ip)
    return jsonify({'status': 'success', 'sensor': sensor_type}), 200

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

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        name = request.form.get('device_name')
        type = request.form.get('device_type')
        gpio = request.form.get('device_gpio')
        ip_address = request.form.get('device_ip')
        sensor_functionality = request.form.get('sensor_functionality')
        actuator_functionality = request.form.get('actuator_functionality')
        print("Sensor: ", sensor_functionality, "actuator: ", actuator_functionality)

        # if name and (sensor_functionality or actuator_functionality):
        #     gpio = int(gpio) if gpio else None
        # print("Second debugging, Sensor: ", sensor_functionality, "actuator: ", actuator_functionality)
        # if type == 'sensor':
        #     functionality = sensor_functionality
        #     manager.sensor_manager.add_sensor(name, gpio, ip_address, type, functionality)
        #     print("Add to sensor manager", name, gpio, ip_address, )
        # elif type == 'actuator':
        #     functionality = actuator_functionality
        #     print("Add to device manager", name, gpio, ip_address, type, functionality)
        #     manager.device_manager.add_device(name, gpio, ip_address, type, functionality)

        return redirect(url_for('settings'))
    else:
        devices = database_manager.get_device_configs()
        print("devices:", devices)
        sensors = database_manager.get_sensor_configs()
        print("sensors:", sensors)
        return render_template('settings.html', devices=devices, sensors=sensors)
    
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': str(error)}), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({'status': 'error', 'message': 'Bad request'}), 400

    
if __name__ == '__main__':
    app.run(host="192.168.0.40", debug=True, use_reloader=False)
