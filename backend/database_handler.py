"""
Description: This script defines the DatabaseManager class for managing the database operations related 
to sensor data, plant information and settings in a grow tent system.

Author: Sebastian Gomez
Date: 26/05/2024
"""

import sqlite3
from flask import g, current_app
import logging
import json

class DatabaseHandler:
    """
    Handles database operations for storing sensor data, plant information, actuator logs,
    AI decisions, and environmental settings in the grow units system.

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

            # Users Table
            db.execute('''CREATE TABLE IF NOT EXISTS Users (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                username TEXT UNIQUE NOT NULL,
                                password_hash TEXT NOT NULL
                                    )''')
            # Hotspot WiFi Settings
            db.execute('''CREATE TABLE IF NOT EXISTS HotspotSettings (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                ssid TEXT NOT NULL,
                                encrypted_password TEXT NOT NULL
                                )''')            
            # Growth Units Table
            db.execute('''CREATE TABLE IF NOT EXISTS GrowthUnits (
                                unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                location TEXT DEFAULT "Indoor",
                                active_plant_id INTEGER,
                                temperature_threshold REAL DEFAULT 24.0,
                                humidity_threshold REAL DEFAULT 50.0,
                                soil_moisture_threshold REAL DEFAULT 40.0,
                                co2_threshold REAL DEFAULT 800.0,
                                voc_threshold REAL DEFAULT 0.0,
                                light_intensity_threshold INTEGER DEFAULT 500,
                                aqi_threshold INTEGER DEFAULT 50,
                                light_start_time TEXT DEFAULT "08:00",
                                light_end_time TEXT DEFAULT "20:00",
                                FOREIGN KEY (active_plant_id) REFERENCES Plants(plant_id)
                                )''')
            
            # Actuator Table
            db.execute('''CREATE TABLE IF NOT EXISTS Actuator (
                                actuator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                actuator_type TEXT NOT NULL,
                                device TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT,
                                zigbee_channel TEXT,
                                zigbee_topic TEXT,
                                mqtt_broker TEXT,
                                mqtt_port INTEGER,
                                growth_unit_id INTEGER,
                                FOREIGN KEY (growth_unit_id) REFERENCES GrowthUnits(unit_id)
                                )''')
            
            # Sensor Table
            db.execute('''CREATE TABLE IF NOT EXISTS Sensor (
                                sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                sensor_type TEXT NOT NULL,
                                sensor_model TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT,
                                communication TEXT DEFAULT 'GPIO',
                                redis_keys TEXT,
                                update_interval INTEGER DEFAULT 60,
                                battery_key TEXT,
                                growth_unit_id INTEGER,
                                FOREIGN KEY (growth_unit_id) REFERENCES GrowthUnits(unit_id)
                                )''')
            
            # Sensor Readings Table
            db.execute('''CREATE TABLE IF NOT EXISTS SensorReading (
                                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                sensor_id INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                temperature REAL,
                                humidity REAL,
                                soil_moisture REAL,
                                co2_ppm REAL,
                                voc_ppb REAL,
                                aqi INTEGER,
                                pressure REAL,
                                FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id)
                                )''')
            
            # Plants Table
            db.execute('''CREATE TABLE IF NOT EXISTS Plants (
                                plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                plant_type TEXT NOT NULL,
                                current_stage TEXT,
                                days_in_stage INTEGER,
                                moisture_level REAL,
                                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                                )''')
            
            # Plant Health Tracking
            db.execute('''CREATE TABLE IF NOT EXISTS PlantHealth (
                                health_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_id INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                leaf_color TEXT,
                                growth_rate REAL,
                                nutrient_deficiency TEXT,
                                disease_detected TEXT,
                                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                                )''')
            
            # Actuator History Table
            db.execute('''CREATE TABLE IF NOT EXISTS ActuatorHistory (
                                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                actuator_id INTEGER,
                                unit_id INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                action TEXT CHECK (action IN ('ON', 'OFF')),
                                duration INTEGER,
                                reason TEXT,
                                FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id),
                                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                                )''')
            
            # AI Decision Logs
            db.execute('''CREATE TABLE IF NOT EXISTS AI_DecisionLogs (
                                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                unit_id INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                ai_temperature REAL,
                                ai_humidity REAL,
                                ai_soil_moisture REAL,
                                actual_temperature REAL,
                                actual_humidity REAL,
                                actual_soil_moisture REAL,
                                actuator_triggered BOOLEAN DEFAULT 0,
                                override BOOLEAN DEFAULT 0,
                                reason TEXT,
                                confidence_level REAL,
                                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Feedback (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                decision_log_id INTEGER,
                                score INTEGER CHECK(score BETWEEN 1 AND 5),
                                comments TEXT,
                                FOREIGN KEY (decision_log_id) REFERENCES AI_DecisionLogs(log_id)
                            ))''')
            # Threshold Overrides Table
            db.execute('''CREATE TABLE IF NOT EXISTS ThresholdOverrides (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                unit_id INTEGER NOT NULL,
                                temperature_threshold REAL,
                                humidity_threshold REAL,
                                soil_moisture_threshold REAL,
                                manual_override BOOLEAN DEFAULT 0,
                                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
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
                                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                                FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id)
                                )''')

            # Plant History Table
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

    def insert_actuator(self, actuator_type, device, gpio=None, ip_address=None, zigbee_channel=None, zigbee_topic=None, mqtt_broker=None, mqtt_port=None, growth_unit_id=None):
        """Inserts a new actuator into the Actuator table."""
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO Actuator (actuator_type, device, gpio, ip_address, zigbee_channel, zigbee_topic, mqtt_broker, mqtt_port, growth_unit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (actuator_type, device, gpio, ip_address, zigbee_channel, zigbee_topic, mqtt_broker, mqtt_port, growth_unit_id))
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error inserting actuator: {e}")
            return None

    def remove_actuator(self, actuator_id):
        """Removes an actuator from the Actuator table."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Actuator WHERE actuator_id = ?", (actuator_id,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error removing actuator: {e}")

    def insert_sensor(self, name, sensor_type, sensor_model, gpio=None, ip_address=None,
                    communication="GPIO", redis_keys=None, update_interval=60,
                    battery_key=None, growth_unit_id=None):
        """Inserts a new sensor into the Sensor table."""
        try:
            db = self.get_db()
            db.execute('''
                INSERT INTO Sensor (name, sensor_type, sensor_model, gpio, ip_address,
                                    communication, redis_keys, update_interval, battery_key, growth_unit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                sensor_type,
                sensor_model,
                gpio,
                ip_address,
                communication,
                json.dumps(redis_keys) if redis_keys else None,
                update_interval,
                battery_key,
                growth_unit_id
            ))
            db.commit()
            logging.info(f"✅ Sensor '{name}' inserted successfully.")
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor '{name}': {e}")

    def remove_sensor(self, sensor_id):
        """Removes a sensor from the Sensor table based on its id."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Sensor WHERE sensor_id = ?", (sensor_id,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error removing sensor: {e}")

    def insert_plant(self, name, plant_type, current_stage, days_in_stage=0, moisture_level=0.0):
        """Inserts a new plant into the Plants table."""
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO Plants (name, plant_type, current_stage, days_in_stage, moisture_level)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, plant_type, current_stage, days_in_stage, moisture_level))
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error inserting plant: {e}")
            return None

    def remove_plant(self, plant_id):
        """Removes a plant from the Plants table by its ID."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Plants WHERE plant_id = ?", (plant_id,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error removing plant: {e}")

    def get_actuator_configs(self):
        """Retrieves actuator configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute('''
                SELECT actuator_id, actuator_type, device, gpio, ip_address, zigbee_channel, zigbee_topic, mqtt_broker, mqtt_port, growth_unit_id
                FROM Actuator
            ''')
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting actuator configs: {e}")
            return []

    def get_sensor_configs(self):
        """Retrieves sensor configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute('''
                SELECT sensor_id, name, sensor_type, sensor_model, gpio, ip_address, growth_unit_id
                FROM Sensor
            ''')
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor configs: {e}")
            return []

    def insert_sensor_data(self, sensor_id, temperature=None, humidity=None, soil_moisture=None,
                        co2_ppm=None, voc_ppb=None, aqi=None, pressure=None):
        """Inserts sensor data into the SensorReading table."""
        try:
            db = self.get_db()
            db.execute('''
                INSERT INTO SensorReading (sensor_id, temperature, humidity, soil_moisture,
                                        co2_ppm, voc_ppb, aqi, pressure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (sensor_id, temperature, humidity, soil_moisture, co2_ppm, voc_ppb, aqi, pressure))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor data: {e}")

    def get_sensor_data(self, limit=20, offset=0):
        """Retrieves sensor data from the database, sorted in descending order by timestamp."""
        try:
            db = self.get_db()
            cursor = db.execute('''
                SELECT * FROM SensorReading
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor data: {e}")
            return []

    def get_sensor_by_id(self, sensor_id):
        """Retrieves a sensor from the database by its ID."""
        try:
            db = self.get_db()
            cursor = db.execute('SELECT * FROM Sensor WHERE sensor_id = ?', (sensor_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor by ID: {e}")
            return None

    def get_all_actuators(self):
        """Retrieves all actuators from the database."""
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
            cursor = db.execute('''
                SELECT sensor_id, name, sensor_type, sensor_model, gpio, ip_address,
                    communication, redis_keys, update_interval, battery_key, growth_unit_id
                FROM Sensor
            ''')
            rows = cursor.fetchall()
            sensor_configs = []
            for row in rows:
                config = {
                    'sensor_id': row['sensor_id'],
                    'name': row['name'],
                    'sensor_type': row['sensor_type'],
                    'sensor_model': row['sensor_model'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address'],
                    'communication': row['communication'],
                    'redis_keys': json.loads(row['redis_keys']) if row['redis_keys'] else {},
                    'update_interval': row['update_interval'],
                    'battery_key': row['battery_key'],
                    'growth_unit_id': row['growth_unit_id']
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
    
    def get_all_plants_for_unit(self, unit_id):
        """Retrieves all plants associated with a given growth unit."""
        try:
            db = self.get_db()
            query = '''SELECT * FROM Plants WHERE plant_id IN (
                        SELECT plant_id FROM GrowthUnits WHERE unit_id = ?
                      )'''
            return db.execute(query, (unit_id,)).fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error retrieving plants for unit {unit_id}: {e}")
            return []

    def get_plant_sensors(self):
        """Retrieves all plant-sensor mappings from the database."""
        try:
            db = self.get_db()
            return db.execute('SELECT * FROM PlantSensors').fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error retrieving plant sensors: {e}")
            return []

    def link_sensor_to_plant(self, plant_id, sensor_id):
        """Links a sensor to a specific plant."""
        try:
            db = self.get_db()
            db.execute('''INSERT INTO PlantSensors (plant_id, sensor_id) VALUES (?, ?)''',
                       (plant_id, sensor_id))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error linking sensor {sensor_id} to plant {plant_id}: {e}")

    def get_sensors_for_plant(self, plant_id):
        """Retrieves sensor IDs linked to a specific plant."""
        try:
            db = self.get_db()
            query = 'SELECT sensor_id FROM PlantSensors WHERE plant_id = ?'
            return [row['sensor_id'] for row in db.execute(query, (plant_id,)).fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error retrieving sensors for plant {plant_id}: {e}")
            return []


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

    def get_average_temperature(self, plant_id):
        """Calculates the average temperature for a given plant."""
        try:
            db = self.get_db()
            query = '''SELECT AVG(temperature) as avg_temp FROM SensorReading 
                       WHERE sensor_id IN (SELECT sensor_id FROM PlantSensors WHERE plant_id = ?)'''
            result = db.execute(query, (plant_id,)).fetchone()
            return result['avg_temp'] if result and result['avg_temp'] is not None else 0.0
        except sqlite3.Error as e:
            logging.error(f"Error calculating average temperature for plant {plant_id}: {e}")
            return 0.0

    def get_average_humidity(self, plant_id):
        """Calculates the average humidity for a given plant."""
        try:
            db = self.get_db()
            query = '''SELECT AVG(humidity) as avg_humidity FROM SensorReading 
                       WHERE sensor_id IN (SELECT sensor_id FROM PlantSensors WHERE plant_id = ?)'''
            result = db.execute(query, (plant_id,)).fetchone()
            return result['avg_humidity'] if result and result['avg_humidity'] is not None else 0.0
        except sqlite3.Error as e:
            logging.error(f"Error calculating average humidity for plant {plant_id}: {e}")
            return 0.0

    def get_total_light_hours(self, plant_id):
        """Calculates the total light hours for a given plant based on growth unit settings."""
        try:
            db = self.get_db()
            query = '''SELECT light_start_time, light_end_time FROM GrowthUnits 
                       WHERE unit_id = (SELECT unit_id FROM GrowthUnits WHERE active_plant_id = ?)'''
            result = db.execute(query, (plant_id,)).fetchone()
            if result and result['light_start_time'] and result['light_end_time']:
                from datetime import datetime
                start_time = datetime.strptime(result['light_start_time'], "%H:%M")
                end_time = datetime.strptime(result['light_end_time'], "%H:%M")
                light_hours = (end_time - start_time).seconds / 3600  # Convert seconds to hours
                return light_hours
            return 0.0
        except sqlite3.Error as e:
            logging.error(f"Error calculating total light hours for plant {plant_id}: {e}")
            return 0.0

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
    def get_latest_sensor_readings(self, unit_id):
        """
        Retrieves the most recent sensor readings for a specific growth unit.

        Args:
            unit_id (int): The growth unit ID.

        Returns:
            dict: Latest sensor readings.
        """
        db = self.get_db()
        query = """
            SELECT temperature, humidity, soil_moisture, co2_ppm, voc_ppb, aqi, pressure
            FROM SensorReading
            WHERE sensor_id IN (
                SELECT sensor_id FROM Sensor WHERE growth_unit_id = ?
            )
            ORDER BY timestamp DESC
            LIMIT 1
        """
        latest_reading = db.execute(query, (unit_id,)).fetchone()

        if latest_reading:
            return {
                "temperature": latest_reading["temperature"],
                "humidity": latest_reading["humidity"],
                "soil_moisture": latest_reading["soil_moisture"],
                "co2_ppm": latest_reading["co2_ppm"],
                "voc_ppb": latest_reading["voc_ppb"],
                "aqi": latest_reading["aqi"],
                "pressure": latest_reading["pressure"],
            }
        return {
            "temperature": None,
            "humidity": None,
            "soil_moisture": None,
            "co2_ppm": None,
            "voc_ppb": None,
            "aqi": None,
            "pressure": None,
        }

    def check_actuator_triggered(self, unit_id, actuator_name):
        """
        Checks if a specific actuator has been turned ON recently.

        Args:
            unit_id (int): The growth unit ID.
            actuator_name (str): The name of the actuator to check (e.g., "Water-Pump").

        Returns:
            bool: True if the actuator was activated in the last hour, False otherwise.
        """
        db = self.get_db()
        query = """
            SELECT timestamp
            FROM ActuatorHistory
            WHERE unit_id = ? 
            AND actuator_id = (
                SELECT actuator_id FROM Actuator WHERE actuator_type = ?
            )
            AND action = 'ON'
            ORDER BY timestamp DESC
            LIMIT 1
        """
        last_activation = db.execute(query, (unit_id, actuator_name)).fetchone()

        if last_activation:
            from datetime import datetime, timedelta
            last_time = datetime.strptime(last_activation["timestamp"], "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - last_time) < timedelta(hours=1)  # ✅ Check if activated in last 1 hour
        return False

    def insert_growth_unit(self, name, location="Indoor", active_plant_id=None, 
                           temperature_threshold=24.0, humidity_threshold=50.0, 
                           soil_moisture_threshold=40.0, light_start_time="08:00", 
                           light_end_time="20:00"):
        """Inserts a new growth unit into the GrowthUnits table."""
        try:
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO GrowthUnits (name, location, active_plant_id, 
                                         temperature_threshold, humidity_threshold, 
                                         soil_moisture_threshold, light_start_time, light_end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                           (name, location, active_plant_id, temperature_threshold, 
                            humidity_threshold, soil_moisture_threshold, light_start_time, light_end_time))
            db.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error inserting growth unit: {e}")
            return None

    def get_growth_unit(self, unit_id):
        """Fetches a specific growth unit by ID."""
        try:
            db = self.get_db()
            cursor = db.execute('SELECT * FROM GrowthUnits WHERE unit_id = ?', (unit_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error fetching growth unit: {e}")
            return None

    def get_all_growth_units(self):
        """Fetches all growth units."""
        try:
            db = self.get_db()
            cursor = db.execute('SELECT * FROM GrowthUnits')
            return cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error fetching all growth units: {e}")
            return []

    def update_growth_unit(self, unit_id, **kwargs):
        """Updates specific fields of a growth unit."""
        try:
            db = self.get_db()
            fields = [f"{key} = ?" for key in kwargs.keys()]
            values = list(kwargs.values()) + [unit_id]
            query = f"UPDATE GrowthUnits SET {', '.join(fields)} WHERE unit_id = ?"
            db.execute(query, values)
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error updating growth unit: {e}")

    def delete_growth_unit(self, unit_id):
        """Deletes a growth unit from the database."""
        try:
            db = self.get_db()
            db.execute('DELETE FROM GrowthUnits WHERE unit_id = ?', (unit_id,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error deleting growth unit: {e}")
        
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
