"""
Flask application for managing plant growth environment.

Author: Sebastian Gomez
Date: 26/05/24
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
from grow_manager import GrowthManager, DatabaseManager
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
atexit.register(manager.device_manager.cleanup)

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
    plants = manager.get_all_plants()
    return render_template('add_plant.html', plants=plants)

@app.route('/reading_update')
def reading_update():
    """
    Fetch the current environmental sensor data and return it as JSON.

    This endpoint is called by the client-side JavaScript to get the latest
    temperature and humidity readings without refreshing the entire page.

    Returns:
        Response: A Flask Response object containing the sensor data in JSON format.
    """
    # Call the method to read the current environmental data from the sensor
    data = manager.monitor_environment()

    # Return the sensor data as a JSON response
    return jsonify(data)

@app.route('/sensor_data')
def sensor_data():
    """
    Display sensor data in tabular format.

    Returns:
        str: Rendered HTML template.
    """
    sensor_data = manager.database_manager.get_sensor_data()
    return render_template('sensor_data.html', sensor_data=sensor_data)

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

@app.route('/test_device')
def test_device():
    functionality = request.args.get('functionality')
    print('Functionality to test: ', functionality)
    success = manager.device_manager.test_device(functionality)
    return jsonify({'success': success})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        devices = []
        device_count = int(request.form['device_count'])
        for i in range(1, device_count + 1):
            name = request.form.get(f'device_name_{i}')
            gpio = request.form.get(f'device_gpio_{i}')
            ip_address = request.form.get(f'device_ip_{i}')
            functionality = request.form.get(f'device_functionality_{i}')
            if name and functionality:
                gpio = int(gpio) if gpio else None
                devices.append({
                    'name': name,
                    'gpio': gpio,
                    'ip_address': ip_address,
                    'functionality': functionality
                })
        # Clear existing devices and add the new ones
        database_manager.clear_devices()
        for device in devices:
            manager.device_manager.add_device(**device)
        return redirect(url_for('settings'))
    else:
        devices = database_manager.get_device_configs()
        return render_template('settings.html', devices=devices)
    
if __name__ == '__main__':
    app.run(host="192.168.0.40", debug=True, use_reloader=False)
