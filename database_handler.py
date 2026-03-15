"""
Description: This script defines the DatabaseManager class for managing the database operations related 
to sensor data, plant information and settings in a grow tent system.

Author: Sebastian Gomez
Date: 26/05/2024
"""

import sqlite3
from flask import g, current_app
import logging

class DatabaseHandler:
    """
    Handles the database operations for storing sensor data and plant information.

    Methods:
        get_db: Connects to the database.
        close_db: Closes the database connection.
        init_app: Initializes the app with database configurations.
        create_tables: Creates necessary tables in the database.
        get_device_configs: Retrieves device configurations from the database.
        clear_devices: Clears all device configurations from the database.
        insert_sensor_data: Inserts sensor data into the SensorReading table.
        insert_device: Inserts a new device into the Devices table.
        insert_plant: Inserts a new plant into the Plants table.
        update_plant_current_stage: Updates the growth stage of a plant in the Plants table.
        get_sensor_data: Retrieves all sensor data from the SensorReading table.
        get_plant: Retrieves a specific plant's information from the Plants table.
        get_light_schedule: Retrieves the light schedule from the Settings table.
        get_plants: Retrieves all plants from the Plants table.
        save_settings: Saves the settings to the database.
        load_settings: Loads the settings from the database.
    """

    def get_db(self):
        """Connects to the database."""
        if 'db' not in g:
            g.db = sqlite3.connect(current_app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
        return g.db
    
    def close_db(self, e=None):
        """Closes the database connection."""
        db = g.pop('db', None)
        if db is not None:
            db.close()

    def init_app(self, app):
        """Initializes the app with database configurations."""
        app.teardown_appcontext(self.close_db)
        with app.app_context():
            self.create_tables()

    def create_tables(self):
        """Creates the necessary tables in the database if they do not already exist."""
        try:
            db = self.get_db()
            db.execute('''CREATE TABLE IF NOT EXISTS Users (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                username TEXT UNIQUE NOT NULL,
                                password_hash TEXT NOT NULL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS HotspotSettings (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                ssid TEXT NOT NULL,
                                encrypted_password TEXT NOT NULL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Actuator (
                                actuator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                actuator_type TEXT NOT NULL,
                                device TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT,
                                zigbee_channel TEXT,
                                zigbee_topic TEXT,
                                mqtt_broker TEXT,
                                mqtt_port INTEGER
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Sensor (
                                sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                sensor_type,
                                sensor_model TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS SensorReading (
                                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                temperature REAL,
                                humidity REAL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Plants (
                                plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                current_stage TEXT,
                                days_in_current_stage INTEGER,
                                moisture_level REAL,
                                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS PlantReadings (
                                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_id INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                soil_moisture REAL,
                                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Settings (
                                id INTEGER PRIMARY KEY,
                                light_start_time TEXT,
                                light_end_time TEXT,
                                fan_start_time TEXT,
                                fan_end_time TEXT,
                                temperature_threshold REAL,
                                humidity_threshold REAL,
                                soil_moisture_threshold REAL,
                                active_plant_id INTEGER
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS CameraSettings (
                                id INTEGER PRIMARY KEY,
                                camera_type TEXT,
                                ip_address TEXT,
                                usb_cam_index INTEGER,
                                last_used TEXT,
                                resolution INTEGER,
                                quality INTEGER,
                                brightness INTEGER,
                                contrast INTEGER,
                                saturation INTEGER,
                                flip INTEGER
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS PlantSensors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_id INTEGER,
                                sensor_id INTEGER,
                                FOREIGN KEY (plant_id) REFERENCES Plants(id),
                                FOREIGN KEY (sensor_id) REFERENCES Sensor(id)
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS plant_history (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_name TEXT,
                                days_germination INTEGER,
                                days_seed INTEGER,
                                days_veg INTEGER,
                                days_flower INTEGER,
                                days_fruit_dev INTEGER,
                                avg_temp REAL,
                                avg_humidity REAL,
                                light_hours REAL,
                                harvest_weight REAL,
                                photo_path TEXT,
                                date_harvested DATETIME DEFAULT CURRENT_TIMESTAMP
                                )''')
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")
    
    def insert_user(self, username, password_hash):
        """Inserts a new user into the Users table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting user: {e}")
            raise e  # Re-raise exception for the caller to handle

    def get_user_by_username(self, username):
        """Fetches a user by username."""
        try:
            db = self.get_db()
            user = db.execute("SELECT * FROM Users WHERE username = ?", (username,)).fetchone()
            return user
        except sqlite3.Error as e:
            logging.error(f"Error fetching user: {e}")
            return None

    def save_hotspot_settings(self, ssid, encrypted_password):
        """Saves or updates the hotspot settings in the database."""
        try:
            db = self.get_db()
            db.execute('''
                INSERT OR REPLACE INTO HotspotSettings (id, ssid, encrypted_password)
                VALUES (1, ?, ?)
            ''', (ssid, encrypted_password))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error saving hotspot settings: {e}")

    def load_hotspot_settings(self):
        """Loads the hotspot settings from the database."""
        try:
            db = self.get_db()
            settings = db.execute('SELECT ssid, encrypted_password FROM HotspotSettings WHERE id = 1').fetchone()
            if settings:
                return {'ssid': settings['ssid'], 'encrypted_password': settings['encrypted_password']}
            return None
        except sqlite3.Error as e:
            logging.error(f"Error loading hotspot settings: {e}")
            return None
    
    def insert_actuator(self, name, gpio, ip_address):
        """Inserts a new actuator into the Actuator table."""
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO Actuator (name, gpio, ip_address) VALUES (?, ?, ?)",
                            (name, gpio, ip_address))
            db.commit()
            # Retrieve the last inserted actuator_id
            actuator_id = cursor.lastrowid
            return actuator_id
        except sqlite3.Error as e:
            logging.error(f"Error inserting actuator: {e}")

    def remove_actuator(self, name):
        """Removes an actuator from the Actuator table."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Actuator WHERE name = ?", (name,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error removing actuator: {e}")

    def insert_sensor(self, name, sensor_type, sensor_model, gpio, ip_address):
        """
        Inserts a new sensor into the database and returns the assigned sensor_id.

        Args:
            sensor_name (str): The name of the sensor.
            sensor_type (str): The type of the sensor.
            sensor_model (str): The model or name of the sensor.
            gpio (int, optional): The GPIO pin number for control.
            ip_address (str, optional): The IP address for wireless control.

        Returns:
            int: The ID of the newly inserted sensor.
        """
        try:
            db = self.get_db()
            cursor = db.cursor()
            
            cursor.execute(
                "INSERT INTO Sensor (name, sensor_type, sensor_model, gpio, ip_address) VALUES (?, ?, ?, ?, ?)",
                (name, sensor_type, sensor_model, gpio, ip_address))
            
            db.commit()
            # Retrieve the last inserted sensor_id
            sensor_id = cursor.lastrowid
            return sensor_id
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor: {e}")
            return None

    def remove_sensor(self, sensor_id):
        """Removes a sensor from the Sensor table based on its id."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Sensor WHERE sensor_id = ?", (sensor_id,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error removing sensor: {e}")

    def insert_plant(self, name, current_stage, days_in_current_stage, moisture_level):
        """
        Inserts a new plant into the Plants table.

        Args:
            name (str): The name of the plant.
            current_stage (str): The current growth stage of the plant.
            days_in_current_stage (int): The number of days the plant has been in its current stage.
            moisture_level (float, optional): The soil moisture level.

        Returns:
            int: The ID of the newly inserted plant, or None if the insertion failed.
        """
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute('''INSERT INTO Plants (name, current_stage, days_in_current_stage, moisture_level)
                            VALUES (?, ?, ?, ?)''', 
                            (name, current_stage, days_in_current_stage, moisture_level))
            db.commit()
            
            # Retrieve and return the last inserted plant_id
            plant_id = cursor.lastrowid
            return plant_id
    
        except sqlite3.Error as e:
            logging.error(f"Error inserting plant: {e}")
            return None  # Optionally, you could also raise an exception instead

    def remove_plant(self, plant_id):
        """
        Removes a plant from the database by its ID.

        Args:
            plant_id (int): The ID of the plant to remove.
        """
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM Plants WHERE plant_id = ?", (plant_id,))
            db.commit()
            print(f"Plant with ID {plant_id} removed from the database.")
        except sqlite3.Error as e:
            logging.error(f"Error removing plant with ID {plant_id}: {e}")

    def insert_soil_moisture_history(self, plant_id, soil_moisture):
        """Inserts a new soil moisture reading into the PlantReadings table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO PlantReadings (plant_id, soil_moisture) VALUES (?, ?)",
                       (plant_id, soil_moisture))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting soil moisture history: {e}")

    def insert_sensor_data(self, temperature=None, humidity=None):
        """
        Inserts sensor data into the SensorReading table.

        Args:
            temperature (float, optional): The temperature value.
            humidity (float, optional): The humidity value.
            moisture_level (float optional): The plant moisture level
        """
        try:
            db = self.get_db()
            db.execute('''INSERT INTO SensorReading (temperature, humidity)
                                VALUES (?, ?)
                                ''', 
                                (temperature, humidity))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor data: {e}")
        
    def get_actuator_configs(self):
        """Retrieves actuator configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute("SELECT id, actuator_type, device, gpio, ip_address, zigbee_topic, mqtt_broker, mqtt_port FROM Actuator")
            rows = cursor.fetchall()
            actuator_configs = []
            for row in rows:
                config = {
                    'id': row['id'],
                    'actuator_type': row['actuator_type'],
                    'device': row['device'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address'],
                    'zigbee_topic': row['zigbee_topic'],
                    'mqtt_broker': row['mqtt_broker'],
                    'mqtt_port': row['mqtt_port']
                }
                actuator_configs.append(config)
            return actuator_configs
        except sqlite3.Error as e:
            logging.error(f"Error getting actuator configs: {e}")
            return []

    def get_sensor_configs(self):
        """Retrieves sensor configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute("SELECT sensor_id, name, sensor_type, sensor_model, gpio, ip_address FROM Sensor")
            rows = cursor.fetchall()
            sensor_configs = []
            for row in rows:
                config = {
                    'sensor_id': row ['sensor_id'],
                    'name': row ['name'],
                    'sensor_type': row['sensor_type'],
                    'sensor_model': row['sensor_model'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address']
                }
                sensor_configs.append(config)
            return sensor_configs
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor configs: {e}")
            return []
        
    def get_sensor_data(self, limit=20, offset=0):
        """
        Retrieves sensor data from the database, sorted in descending order by timestamp.

        Args:
            limit (int): The maximum number of records to return.
            offset (int): The number of records to skip before starting to return records.

        Returns:
            list: A list of tuples containing the sensor data.
        """
        db = self.get_db()
        cursor = db.execute('''
            SELECT * FROM SensorReading
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()
        
    def get_sensor_by_id(self, sensor_id):
        """
        Retrieves a sensor from the database by its ID.

        Args:
            sensor_id (int): The ID of the sensor.

        Returns:
            dict: Sensor information.
        """
        try:
            db = self.get_db()
            cursor = db.execute('SELECT * FROM Sensor WHERE sensor_id = ?', (sensor_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor by ID: {e}")
            return None
        
    def get_all_actuators(self):
        """
        Retrieves all actuators from the database.

        Returns:
            list: A list of dictionaries containing actuator data.
        """
        db = self.get_db()
        cursor = db.execute('SELECT * FROM Actuator')
        actuators = cursor.fetchall()
        return [dict(row) for row in actuators]
    
    def get_all_sensors(self):
        """
        Retrieves all sensors from the database.

        Returns:
            list: A list of dictionaries containing sensor data.
        """
        db = self.get_db()
        cursor = db.execute('SELECT * FROM Sensor')
        sensors = cursor.fetchall()
        return [dict(row) for row in sensors]
    
    def get_sensors_by_model(self, sensor_model):
        """Retrieves sensors by type from the database."""
        try:
            db = self.get_db()
            sensors = db.execute('SELECT * FROM Sensor WHERE sensor_model = ?', (sensor_model,)).fetchall()
            return sensors
        except sqlite3.Error as e:
            logging.error(f"Error retrieving sensors by model: {e}")
            return []

    def get_sensors_for_plant(self, plant_id):
        """
        Get sensors linked to a specific plant.

        Args:
            plant_id (int): The ID of the plant.

        Returns:
            list: List of sensor IDs linked to the plant.
        """
        try:
            db = self.get_db()
            cursor = db.execute("SELECT sensor_id FROM PlantSensors WHERE plant_id = ?", (plant_id,))
            return [row['sensor_id'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error getting sensors for plant: {e}")
            return []
        
    def get_soil_moisture_history(self, plant_id):
        """Fetches the historical soil moisture data for a plant."""
        db = self.get_db()
        return db.execute("SELECT * FROM SoilMoistureHistory WHERE plant_id = ? ORDER BY timestamp", (plant_id,)).fetchall()

    def set_active_plant(self, plant_id):
        """
        Sets the specified plant as the active plant.

        Args:
            plant_id (int): The ID of the plant to set as active.
        """
        db = self.get_db()
        db.execute('UPDATE Settings SET active_plant_id = ?', (plant_id,))
        db.commit()

    def get_active_plant(self):
        """
        Retrieves the active plant from the database.

        Returns:
            int: The ID of the active plant.
        """
        db = self.get_db()
        active_plant = db.execute('SELECT active_plant_id FROM Settings LIMIT 1').fetchone()
        return active_plant['active_plant_id'] if active_plant else None

    def get_plant_by_id(self, plant_id):
        """
        Get plant details by ID.

        Args:
            plant_id (int): The ID of the plant.

        Returns:
            row: Details of the plant.
        """
        try:
            db = self.get_db()
            cursor = db.execute("SELECT * FROM Plants WHERE plant_id = ?", (plant_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting plant by ID: {e}")
            return None
        
    def get_all_plants(self) -> list:
        """
        Retrieves all plants from the Plants table.

        Returns:
            list: A list of tuples containing plant records.
        """
        try:
            db = self.get_db()
            return db.execute('SELECT * FROM Plants').fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting plants: {e}")
            return []
        
    def get_all_plant_readings(self, limit=None, offset=None):
        """
        Retrieves plant readings from the database, with optional limit and offset for pagination.

        Args:
            limit (int, optional): The maximum number of readings to return.
            offset (int, optional): The number of readings to skip before starting to return results.

        Returns:
            list: A list of plant readings.
        """
        db = self.get_db()
        query = "SELECT * FROM PlantReadings ORDER BY timestamp DESC"
        params = []

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)

        cursor = db.execute(query, params)
        return cursor.fetchall()
        
    def get_plant_sensors(self):
        """
        Retrieves all plant-sensor mappings from the database.

        Returns:
            list: A list of dictionaries containing plant-sensor mappings.
        """
        db = self.get_db()
        cursor = db.execute('SELECT * FROM PlantSensors')
        plant_sensors = cursor.fetchall()
        return [dict(row) for row in plant_sensors]
    
    def get_plant_by_sensor_name(self, sensor_name):
        """
        Retrieves plant by the sensor name from the database.

        Returns:
            dict: Details of the plant.
        """
        try:
            db = self.get_db()
            cursor = db.execute("SELECT * FROM Sensor WHERE name = ?", (sensor_name,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting plant by ID: {e}")
            return None

    def link_sensor_to_plant(self, plant_id, sensor_id):
        """
        Link a soil moisture sensor to a plant in the database.

        Args:
            plant_id (int): The ID of the plant.
            sensor_id (int): The ID of the sensor.
        """
        try:
            db = self.get_db()
            db.execute("INSERT INTO PlantSensors (plant_id, sensor_id) VALUES (?, ?)",
                       (plant_id, sensor_id))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error linking sensor to plant: {e}") 

    def update_plant_current_stage(self, name, current_stage):
        """
        Updates the growth stage of a plant in the Plants table.

        Args:
            name (str): The name of the plant.
            current_stage (str): The new growth stage of the plant.
        """
        try:
            db = self.get_db()
            db.execute('''UPDATE Plants
                                SET current_stage = ?
                                WHERE name = ?
                                ''', 
                                (current_stage, name))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error updating plant growth stage: {e}")

    def insert_plant_history(self, plant_name, days_germination, days_seed, days_veg, days_flower, days_fruit_dev, avg_temp, avg_humidity, light_hours, harvest_weight, photo_path, date_harvested):
        """
        Inserts a plant's lifecycle data into the plant_history table.

        Args:
            All the lifecycle details collected from the plant.
        """
        db = self.get_db()
        db.execute('''
            INSERT INTO plant_history 
            (plant_name, days_germination, days_seed, days_veg, days_flower, days_fruit_dev, avg_temp, avg_humidity, light_hours, harvest_weight, photo_path, date_harvested) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (plant_name, days_germination, days_seed, days_veg, days_flower, days_fruit_dev, avg_temp, avg_humidity, light_hours, harvest_weight, photo_path, date_harvested)
        )
        db.commit()

    def get_average_temperature(self, plant_name):
        # Implement logic to calculate average temperature for the plant.
        pass

    def get_average_humidity(self, plant_name):
        # Implement logic to calculate average humidity for the plant.
        pass

    def get_total_light_hours(self, plant_name):
        # Implement logic to calculate total light hours for the plant.
        pass

    def update_plant_days(self, plant_name, days_in_current_stage):
        """Updates the days in the current stage for a specific plant."""
        try:
            db = self.get_db()
            db.execute('''UPDATE Plants SET days_in_current_stage = ? WHERE name = ?''',
                       (days_in_current_stage, plant_name))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error updating plant days: {e}")

    def update_plant_soil_moisture(self, plant_name, moisture_level):
        """Updates the soil moisture reading for a specific plant."""
        try:
            db = self.get_db()
            db.execute('''UPDATE Plants SET moisture_level = ? WHERE name = ?''',
                       (moisture_level, plant_name))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error updating plant moisture: {e}")
        
    def get_light_schedule(self):
        """
        Retrieves the light_start_time and light_end_time from the Settings table.

        Returns:
            dict: A dictionary containing start_time and end_time schedules.
        """
        try:
            db = self.get_db()
            schedule = db.execute('SELECT light_start_time, light_end_time FROM Settings ORDER BY id DESC LIMIT 1').fetchone()
            if schedule:
                return {'light_start_time': schedule['light_start_time'], 'light_end_time': schedule['light_end_time']}
            return None
        except sqlite3.Error as e:
            logging.error(f"Error getting light schedule: {e}")
            return None
        
    def get_fan_schedule(self):
        """
        Retrieves the fan_start_time and fan_end_time from the Settings table.

        Returns:
            dict: A dictionary containing start_time and end_time schedules.
        """
        try:
            db = self.get_db()
            schedule = db.execute('SELECT fan_start_time, fan_end_time FROM Settings ORDER BY id DESC LIMIT 1').fetchone()
            if schedule:
                return {'fan_start_time': schedule['fan_start_time'], 'fan_end_time': schedule['fan_end_time']}
            return None
        except sqlite3.Error as e:
            logging.error(f"Error getting fan schedule: {e}")
            return None
    
    def save_settings(self, light_start_time, light_end_time, fan_start_time, fan_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, active_plant_id):
        """
        Saves the settings to the database, replacing existing settings if they exist.

        Args:
            light_start_time (str): The start time for the lights.
            light_end_time (str): The end time for the lights.
            fan_start_time (str): The start time for the fan.
            fan_end_time (str): The end time for the fan.
            temperature_threshold (float): The temperature threshold.
            humidity_threshold (float): The humidity threshold.
            soil_moisture_threshold (float): The soil moisture threshold.
            active_plant_id (int): The ID of the currently active plant.
        """
        try:
            db = self.get_db()
            db.execute('''
            INSERT OR REPLACE INTO Settings (id, light_start_time, light_end_time, fan_start_time, fan_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, active_plant_id)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', 
            (light_start_time, light_end_time, fan_start_time, fan_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, active_plant_id))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error saving settings: {e}")

    def load_settings(self) -> dict:
        """
        Loads the settings from the database.

        Returns:
            dict: A dictionary containing light_start_time, light_end_time, fan_start_time, fan_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, and active_plant_id.
        """
        try:
            db = self.get_db()
            settings = db.execute('SELECT * FROM Settings WHERE id = 1').fetchone()
            if settings:
                return dict(settings)
            return None
        except sqlite3.Error as e:
            logging.error(f"Error loading settings: {e}")
            return None
        
    def save_camera_settings(self, camera_type, ip_address, usb_cam_index, last_used, resolution, quality, brightness, contrast, saturation, flip):
        """
        Saves the camera settings to the database, replacing existing settings if they exist.

        Args:
            camera_type (str): Either 'usb' or 'esp32' camera type.
            ip_address (str): The IP address of the ESP32 camera (only relevant for 'esp32' type).
            usb_cam_index (int): The USB index of the USB camera (only relevant for 'usb' type).
            last_used (str): The last time the camera was used.
            resolution (int): Resolution value of the camera.
            quality (int): Quality setting of the camera.
            brightness (int): Brightness level.
            contrast (int): Contrast level.
            saturation (int): Saturation level.
            flip (int): Flip setting (0 for normal, 1 for flipped).
        """
        try:
            db = self.get_db()
            db.execute('''
            INSERT OR REPLACE INTO CameraSettings (id, camera_type, ip_address, usb_cam_index, last_used, resolution, quality, brightness, contrast, saturation, flip)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', 
            (camera_type, ip_address, usb_cam_index, last_used, resolution, quality, brightness, contrast, saturation, flip))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error saving camera settings: {e}")

    def load_camera_settings(self) -> dict:
        """
        Loads the camera settings from the database.

        Returns:
            dict: A dictionary containing camera_type, ip_address, usb_cam_index, last_used, resolution, quality, brightness, contrast, saturation, and flip.
        """
        try:
            db = self.get_db()
            camera_settings = db.execute('''
                SELECT camera_type, ip_address, usb_cam_index, last_used, resolution, quality, brightness, contrast, saturation, flip 
                FROM CameraSettings 
                WHERE id = 1
            ''').fetchone()
            
            if camera_settings:
                return {
                    'camera_type': camera_settings['camera_type'],
                    'ip_address': camera_settings['ip_address'],
                    'usb_cam_index': camera_settings['usb_cam_index'],
                    'last_used': camera_settings['last_used'],
                    'resolution': camera_settings['resolution'],
                    'quality': camera_settings['quality'],
                    'brightness': camera_settings['brightness'],
                    'contrast': camera_settings['contrast'],
                    'saturation': camera_settings['saturation'],
                    'flip': camera_settings['flip']
                }
            return None
        except sqlite3.Error as e:
            logging.error(f"Error loading camera settings: {e}")
            return None
