<<<<<<< HEAD
"""
Flask application for managing plant growth environment.

Author: Sebastian Gomez
Date: 26/05/24
"""

from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash, Response, g
from grow_manager import GrowthEnvironment
from database_handler import DatabaseHandler
import matplotlib.pyplot as plt
import logging
import signal
import time
import sys
import os
import io
import base64
import json
import atexit
from config_defaults import SystemConfigDefaults
from auth_manager import UserAuthManager
from functools import wraps
from cryptography.fernet import Fernet

app = Flask(__name__, static_folder='static')
app.config['DATABASE'] = 'database/grow_tent.db'
app.secret_key = 'aloha'
database_manager = DatabaseHandler()
database_manager.init_app(app)
authentication_manager = UserAuthManager(database_manager)
# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Generate or load encryption key
ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

with app.app_context():
    global manager
    manager = GrowthEnvironment(database_manager=database_manager)

# Register cleanup function to be called on exit
atexit.register(manager.actuator_controller.cleanup)

used_pins = {}

@app.context_processor
def inject_actuator_data():
    active_actuators = manager.actuator_controller.get_actuators()
    return dict(active_actuators=active_actuators)

@app.context_processor
def inject_active_page():
    return dict(active_page=request.endpoint)

def get_available_gpio_pins():
    return {pin: name for pin, name in SystemConfigDefaults.GPIO_PINS.items() if pin not in used_pins.values()}

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Register the user
        if authentication_manager.register_user(username, password):
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Registration failed. Username might already exist.', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        flash('You are already logged in.', 'info')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if authentication_manager.authenticate_user(username, password):
            # Set the user session
            session['user'] = username
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """
    Render the index page with a list of plants.

    Returns:
        str: Rendered HTML template.
    """
    plants = manager.tent.get_all_plants()
    # Combine light start and end times into a single string
    light_schedule_data = manager.get_light_schedule()
    if light_schedule_data:
        light_schedule = f"{light_schedule_data['light_start_time']} - {light_schedule_data['light_end_time']}"
    else:
        light_schedule = "N/A"
    
    fan_schedule_data = manager.get_fan_schedule()
    if fan_schedule_data:
        fan_schedule = f"{fan_schedule_data['fan_start_time']} - {fan_schedule_data['fan_end_time']}"
    else:
        fan_schedule = "N/A"
    thresholds = {
        'temperature_threshold': manager.temperature_threshold,
        'humidity_threshold': manager.humidity_threshold,
        'soil_moisture_threshold': manager.soil_moisture_threshold
        }
    return render_template('index.html', plants=plants, fan_schedule=fan_schedule, light_schedule=light_schedule, thresholds=thresholds)

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
        redirect: Redirect to the settings page.
    """
    temperature_threshold = float(request.form['temperature_threshold'])
    humidity_threshold = float(request.form['humidity_threshold'])
    soil_moisture_threshold = float(request.form['soil_moisture_threshold'])
    manager.set_thresholds(temperature_threshold, humidity_threshold, soil_moisture_threshold)
    return redirect(url_for('settings'))

@app.route('/add_plant', methods=['GET', 'POST'])
def add_plant():
    """
    Add a plant and link soil moisture sensors to plants.
    """
    if request.method == 'POST':
        try:
            plant_name = request.form.get('plant_name')
            plant_type = request.form.get('plant_type') # I need to create a field in the plant table
            days_in_stage = int(request.form.get('days_in_stage'))
            current_stage = request.form.get('plant_stage')

            if not current_stage:
                flash("Please select a valid plant stage.", "error")
                return redirect(url_for('add_plant'))
            
            # Extract durations from the form
            stage_durations = {
                'Germination': int(request.form.get('germination_days', 0)),
                'Seedling': int(request.form.get('seedling_days', 0)),
                'Vegetative': int(request.form.get('vegetative_days', 0)),
                'Flowering': int(request.form.get('flowering_days', 0)),
                'Fruit Development': int(request.form.get('fruit_development_days', 0)),
                'Harvest': int(request.form.get('harvest_days', 0))
            }
            
            # Validate if the days in the current stage exceed the stage duration
            current_stage_duration = stage_durations.get(current_stage.capitalize())
            if current_stage_duration is None:
                flash(f"Invalid stage: {current_stage}", "error")
                return redirect(url_for('add_plant'))
            if days_in_stage > current_stage_duration:
                flash(f"Days in current stage exceed the duration for the {current_stage} stage.", "error")
                return redirect(url_for('add_plant'))
        
            manager.add_plant(plant_name, stage_durations, current_stage, days_in_stage)
            flash(f"Plant '{plant_name}' of type '{plant_type}' added successfully.", "success")
            return redirect(url_for('index'))  # Redirect to index or plant list
        except Exception as e:
            logging.error(f"Error adding plant: {e}")
            flash("An error occurred while adding the plant. Please try again.", "error")
            return redirect(url_for('add_plant'))

    plants_info = SystemConfigDefaults.plants_info
    plants = manager.tent.get_all_plants()
    sensors = manager.database_manager.get_sensors_by_model('Soil-Moisture')
    return render_template('add_plant.html', plants=plants, sensors=sensors, plants_info=plants_info)

@app.route('/set_active_plant', methods=['POST'])
def set_active_plant():
    plant_id = request.form.get('active_plant_id')
    if not plant_id:
        flash("Please select a plant to set as active.", "error")
        return redirect(url_for('index'))

    try:
        plant_id = int(plant_id)
    except ValueError:
        flash("Invalid plant ID.", "error")
        return redirect(url_for('index'))

    active_plant = manager.tent.get_plant_by_id(plant_id)
    
    if not active_plant:
        flash("Plant not found.", "error")
        return redirect(url_for('index'))
    
    manager.set_active_plant(active_plant)
    manager.adjust_environment(active_plant)
    flash(f"Plant '{active_plant.name}' is now the active plant.", "success")
    return redirect(url_for('index'))

@app.route('/remove-plant', methods=['POST'])
def remove_plant():
    data = request.get_json()
    plant_id = data.get('plant_id')
    
    if plant_id:
        plant_id = int(plant_id)  # Ensure plant_id is an integer
        manager.tent.remove_plant(plant_id)  # Remove from Tent
        return jsonify({"status": f"Plant with ID {plant_id} removed successfully."})
    else:
        return jsonify({"status": "No plant ID provided."}), 400

@app.route('/harvest/<int:plant_id>')
def harvest_plant(plant_id):
    plant = manager.tent.get_plant_by_id(plant_id)
    return render_template('harvest.html', plant=plant)

@app.route('/submit_harvest/<int:plant_id>', methods=['POST'])
def submit_harvest(plant_id):
    harvest_weight = request.form['harvest_weight']
    photo = request.files['photo']

    # Save the photo to a directory
    photo_path = None
    if photo:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
        photo.save(photo_path)

    # Record the harvest details
    manager.record_harvest(plant_id, harvest_weight, photo_path)

    flash(f"Plant '{plant_id}' has been successfully harvested and recorded.")
    return redirect(url_for('index'))
    
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

@app.route('/<int:plant_id>/increase_days', methods=['POST'])
def increase_days(plant_id):
    plant = manager.tent.get_plant_by_id(plant_id)
    if plant:
        plant.increase_days_in_stage()
        return jsonify({"status": "success", "message": f"Increased days for {plant.name}."})
    return jsonify({"status": "error", "message": f"Plant {plant.name} not found."})

@app.route('/<int:plant_id>/decrease_days', methods=['POST'])
def decrease_days(plant_id):
    plant = manager.tent.get_plant_by_id(plant_id)
    if plant:
        plant.decrease_days_in_stage()
        return jsonify({"status": "success", "message": f"Decreased days for {plant.name}."})
    return jsonify({"status": "error", "message": f"Plant {plant.name} not found."})

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
    page = int(request.args.get('page', 1))
    limit = 20
    offset = (page - 1) * limit
    
    sensor_data = manager.database_manager.get_sensor_data(limit=limit, offset=offset)
    readings = manager.database_manager.get_all_plant_readings(limit=limit, offset=offset)
    print("readings sensor data: ", readings)
    next_page = page + 1
    prev_page = page - 1 if page > 1 else None
    
    return render_template('sensor_data.html', sensor_data=sensor_data, readings=readings, next_page=next_page, prev_page=prev_page)

@app.route('/sensor_data_graph')
def sensor_data_graph():
    """
    Display a graph of sensor data over time.

    Returns:
        str: Rendered HTML template with graph image.
    """
    sensor_data = manager.database_manager.get_sensor_data()
    
    if not sensor_data:
        flash('No sensor data available to plot.', 'error')
        return redirect(url_for('index'))

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

@app.route('/devices')
def devices():
    available_gpio_pins = get_available_gpio_pins()
    available_actuators = ['Heater', 'Cooler', 'Humidifier', 'CO2Injector']  # List all available actuator types
    active_actuators = manager.actuator_controller.get_actuators()
    try:
        active_sensors = manager.sensor_manager.get_sensors()
        print(f"Active sensors: {active_sensors}")
    except Exception as e:
        print(f"Error retrieving sensors: {e}")
        active_sensors = []
    db_sensors = manager.database_manager.get_all_sensors()
    db_actuators = manager.database_manager.get_all_actuators()
    
    return render_template('devices.html', available_gpio_pins=available_gpio_pins, available_actuators=available_actuators, active_actuators=active_actuators, active_sensors=active_sensors, db_sensors=db_sensors, db_actuators=db_actuators)

@app.route('/add_actuator', methods=['POST'])
def add_actuator():
    actuator_device = request.form['actuator_type']
    actuator_pin = int(request.form['actuator_pin'])
    actuator_ip = request.form.get('actuator_ip', None)
    print("actuator device: ", actuator_device, "actuator pin: ", actuator_pin)
    if actuator_pin in used_pins.values():
        return jsonify({"status": "error", "message": "GPIO pin already used"}), 400
    manager.actuator_controller.add_actuator(actuator_device, actuator_pin, actuator_ip=None)
    used_pins[actuator_device] = actuator_pin
    return jsonify({"status": "success", "actuator": actuator_device})

@app.route('/add_sensor', methods=['POST'])
def add_sensor():
    sensor_name = request.form['sensor_name']
    sensor_type = request.form['sensor_type']
    sensor_model = request.form['sensor_model']
    sensor_pin = request.form.get('sensor_pin', type=int)
    adc_channel = request.form.get('adc_channel', None)
    sensor_ip = request.form.get('sensor_ip', None)

    print("sensor pin 1 and sensor model: app.py:", sensor_pin, sensor_model)

    if sensor_pin in used_pins.values():
        return jsonify({"status": "error", "message": "GPIO pin already used"}), 400
    
    # Only override sensor_pin if the sensor_type is Soil-Moisture
    if sensor_model == 'Soil-Moisture' and adc_channel:
        print(f"Mapping ADC channel {adc_channel} for Soil-Moisture sensor")
        sensor_pin_mapped = SystemConfigDefaults.ADC_CHANNEL_MAP.get(adc_channel, None)
        if sensor_pin_mapped is not None:
            sensor_pin = sensor_pin_mapped
    
    print("sensor pin 2: app.py:", sensor_pin)

    manager.sensor_manager.add_sensor(sensor_name, sensor_type, sensor_model, sensor_pin, sensor_ip)
    used_pins[sensor_name] = sensor_pin

    return jsonify({'status': 'success', 'sensor': sensor_name}), 200

@app.route('/remove_actuator', methods=['POST'])
def remove_actuator():
    data = request.json
    actuator_type = data['actuator_type']
    if actuator_type in used_pins.keys():
        actuator_type = used_pins.pop(actuator_type)
        manager.actuator_controller.remove_actuator(actuator_type)
        return jsonify({"status": "success", "actuator": actuator_type})
    else:
        return jsonify({"status": "error", "message": "Actuator nof found"}), 400

@app.route('/remove_sensor', methods=['POST'])
def remove_sensor():
    data = request.json
    sensor_name = data.get('sensor_name')
    if sensor_name in used_pins.keys():
        sensor_id = data.get('sensor_id')
        sensor_name = data.get('sensor.name')
    
    if sensor_name in used_pins.key():
        used_pins.pop (sensor_name)

        sensor_id = int(sensor_id)
        manager.sensor_manager.remove_sensor(sensor_id)
        return jsonify({"status": f"Sensor {sensor_name} removed successfully."})
    else:
        return jsonify({"status": "Error removing the sensor."}), 400

@app.route('/control_actuator', methods=['POST'])
def control_actuator():
    data = request.json
    actuator_type = data['actuator_type']
    action = data['action']
    
    if action == 'activate':
        manager.actuator_controller.activate_actuator(actuator_type)
    elif action == 'deactivate':
        manager.actuator_controller.deactivate_actuator(actuator_type)
    
    return jsonify({"status": "success", "actuator": actuator_type, "action": action})

@app.route('/plants_guide')
def plants_guide():
    plants_info = SystemConfigDefaults.plants_info
    return render_template('plants_guide.html', plants=plants_info)

@app.route('/settings')
def settings():
    # Get the current settings from the manager or database
    light_schedule_data = manager.get_light_schedule()
    fan_schedule_data = manager.get_fan_schedule()
    thresholds = {
        'temperature_threshold': manager.temperature_threshold,
        'humidity_threshold': manager.humidity_threshold,
        'soil_moisture_threshold': manager.soil_moisture_threshold
    }

    # Assuming you have hotspot settings in the database
    hotspot_settings = manager.get_hotspot_settings()  # Example function to get hotspot settings

    # Pass the necessary data to the template
    return render_template(
        'settings.html', 
        light_schedule=light_schedule_data,
        fan_schedule=fan_schedule_data,
        thresholds=thresholds,
        ssid=hotspot_settings.get('ssid'),
        password=hotspot_settings.get('password')
    )

@app.route("/", methods=["GET", "POST"])
def wifi_config():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    available_modules = ['Relay Module', 'Enviroment Sensor Module', 'Mosture Sensor Module']
    if request.method == "POST":
        module = request.form.get("available_modules")
        ssid = request.form.get("ssid")
        password = request.form.get("password")

        if not module or not ssid or not password:
            flash("All fields are required!", "danger")
            return redirect(url_for("wifi_config"))

        # Encrypt Wi-Fi credentials
        wifi_payload = json.dumps({"ssid": ssid, "password": password})
        encrypted_payload = cipher.encrypt(wifi_payload.encode()).decode()

        # Publish encrypted credentials
        mqtt_topic = f"zigbee2mqtt/{module}/wifi_config"
        manager.update_wifi_config(mqtt_topic, encrypted_payload)

        flash(f"Wi-Fi credentials sent to {module}!", "success")

    return render_template("wifi_form.html", available_modules=available_modules)

# SIDE section
@app.route('/set_camera', methods=['POST'])
def set_camera():
    """
    Endpoint to set up the camera based on user input (type, IP, or USB index).
    """
    camera_type = request.form['camera_type']
    ip_address = request.form.get('ip_address')
    usb_cam_index = request.form.get('usb_cam_index')

    manager.camera_manager.save_camera_settings(camera_type, ip_address, usb_cam_index)
    return redirect(url_for('index'))

@app.route('/start_camera')
def start_camera():
    """
    Starts the camera via the CameraManager.
    """
    manager.start_camera()
    return redirect(url_for('index'))

@app.route('/stop_camera')
def stop_camera():
    """
    Stops the camera via the CameraManager.
    """
    manager.stop_camera()
    return redirect(url_for('index'))

def gen(camera):
    """
    Video streaming generator function. Streams frames from the camera or shows a placeholder on failure.
    """
    retry_count = 0
    max_retries = 5  # can be set a limit on retries on camera failure
    
    while True:
        frame = camera.get_frame()
        if frame is not None:
            retry_count = 0  # Reset retry count on success
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            # Retry before failing to the placeholder image
            retry_count += 1
            if retry_count < max_retries:
                print(f"Warning: Received a None frame from the camera. Retry {retry_count}/{max_retries}")
                time.sleep(1)  # Wait and retry
                continue
            
            # After max retries, switch to placeholder
            print("Error: Failed to retrieve camera frames after retries, displaying placeholder.")
            with open('static/images/placeholder.png', 'rb') as placeholder:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + placeholder.read() + b'\r\n')
            break

@app.route('/video_feed')
def video_feed():
    """
    Video streaming route. This function retrieves the camera instance and checks if the camera is running.
    """
    camera_instance = manager.camera_manager.camera_instance
    camera_running = manager.camera_manager.camera_running

    if camera_instance and camera_running:
        return Response(gen(camera_instance),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        # If no camera is running, return the placeholder image
        return Response(open('static/images/placeholder.png', 'rb').read(),
                        mimetype='image/jpeg')
    
@app.route('/fullscreen')
def fullscreen():
    """Fullscreen video stream."""
    return render_template('fullscreen.html')
    
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
=======
"""WSGI entry point for the SYSGrow backend application.

This module provides a minimal, robust CLI entrypoint used both in
development and production. It prefers environment configuration and
keeps startup behavior defensive (safe defaults, clear logging).
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from typing import Optional

from app import create_app, socketio


def build_app(secret: Optional[str] = None):
    """Create and return the Flask app.

    We call `create_app(bootstrap_runtime=True)` to ensure runtime
    initialization happens in development as in production. If a
    `secret` is provided via environment, set it on the app config.
    """
    # Keep call signature simple and defensive: use bootstrap flag, then
    # apply any runtime overrides to the app.config. This avoids depending
    # on the internal signature of `create_app`.
    app = create_app(bootstrap_runtime=True)
    if secret:
        try:
            app.config["SECRET_KEY"] = secret
        except Exception:
            # Be defensive: if app isn't fully configured, set environ
            os.environ["SYSGROW_SECRET_KEY"] = secret
    return app


app = build_app(os.getenv("SYSGROW_SECRET_KEY"))


def _env_flag_true(name: str) -> bool:
    v = os.getenv(name)
    return bool(v and v.lower() in ("1", "true", "yes", "on"))


def main() -> int:
    # Configure logging early so other modules pick it up
    level = logging.DEBUG if _env_flag_true("SYSGROW_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    host = os.getenv("SYSGROW_HOST", "0.0.0.0")
    port = int(os.getenv("SYSGROW_PORT", "8000"))
    debug = _env_flag_true("SYSGROW_DEBUG")

    logging.info("Starting server on %s:%s", host, port)
    logging.info("SocketIO async_mode: %s", socketio.async_mode)

    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
        logging.info("Server stopped.")
        return 0
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
        return 0
    except Exception as exc:  # pragma: no cover - top-level runtime errors
        logging.exception("ERROR: Failed to start server: %s", exc)
        return 1


if __name__ == "__main__":
    # Allow direct execution for development, mirror behavior used by
    # our console script `sysgrow-backend`.
    raise SystemExit(main())
>>>>>>> update
