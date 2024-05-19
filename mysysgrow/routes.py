from flask import render_template, request, redirect, url_for, jsonify
from run import app
from .growth_manager import GrowthManager

# Function to simulate fetching sensor data (replace with actual implementation)
def get_sensor_data():
    temperature_c = 25  # Example temperature value
    humidity = 60  # Example humidity value
    return temperature_c, humidity

@app.route('/')
def index():
    # Fetch real-time sensor data
    temperature_c, humidity = get_sensor_data()
    return render_template('index.html', temperature_c=temperature_c)

@app.route('/strain_form')
def strain_form():
    return render_template('strain_form.html')

@app.route('/submit_growth_data', methods=['POST'])
def submit_growth_data():
    if request.method == 'POST':
        # Extract form data
        strain = request.form['strain']
        stage = request.form['stage']
        stage_duration = request.form['stage_duration']
        light = request.form['light']
        day_temp = request.form['day_temp']
        night_temp = request.form['night_temp']
        ph = request.form['ph']
        ec = request.form['ec']
        humidity = request.form['humidity']
        light_power = request.form['light_power']
        watering = request.form['watering']

        # Perform any necessary processing (e.g., save data to a database)
        # Redirect to the index page after processing
        return redirect(url_for('strain_form'))
    else:
        # Handle invalid requests (e.g., GET requests to this route)
        return redirect(url_for('index'))  # Redirect to the index page
    
@app.route('/update_stage/<int:grow_id>', methods=['GET'])
def update_stage(grow_id):
    growth_manager = GrowthManager()
    growth_manager.check_stage_transition(grow_id)
    return jsonify({'message': 'Stage transition checked and updated if necessary.'})