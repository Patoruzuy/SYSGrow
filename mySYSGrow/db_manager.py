"""
Description: This script defines the DatabaseManager class for managing the database operations related 
to sensor data, plant information and settings in a grow tent system.

Author: Sebastian Gomez
Date: 26/05/2024
"""

import sqlite3
from flask import g, current_app
import logging

class DatabaseManager:
    """
    Manages the database operations for storing sensor data and plant information.

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
            db.execute('''CREATE TABLE IF NOT EXISTS Actuator (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Sensor (
                                sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                sensor_type TEXT NOT NULL,
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
                                days_in_current_stage,
                                moisture_level REAL,
                                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                                )''')
            db.execute('''CREATE TABLE PlantReadings (
                                reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_id INTEGER,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                soil_moisture REAL,
                                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                            ''')
            db.execute('''CREATE TABLE IF NOT EXISTS Settings (
                                id INTEGER PRIMARY KEY,
                                light_start_time TEXT,
                                light_end_time TEXT,
                                temperature_threshold REAL,
                                humidity_threshold REAL,
                                soil_moisture_threshold REAL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS PlantSensors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_id INTEGER,
                                sensor_id INTEGER,
                                FOREIGN KEY (plant_id) REFERENCES Plants(id),
                                FOREIGN KEY (sensor_id) REFERENCES Sensor(id)
                                )''')
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")

    def insert_actuator(self, name, gpio, ip_address):
        """Inserts a new actuator into the Actuator table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO Actuator (name, gpio, ip_address) VALUES (?, ?, ?)",
                            (name, gpio, ip_address))
            db.commit()
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

    def insert_device(self, name, gpio, ip_address, type, functionality):
        """Inserts a new device into the Devices table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO Device (name, gpio, ip_address, type, functionality) VALUES (?, ?, ?, ?, ?)",
                            (name, gpio, ip_address, type, functionality))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting device: {e}")

    def insert_sensor(self, sensor_type, gpio, ip_address):
        """Inserts a new sensor into the Sensor table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO Sensor (sensor_type, gpio, ip_address) VALUES (?, ?, ?)",
                            (sensor_type, gpio, ip_address))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor: {e}")

    def insert_plant(self, name, current_stage, days_in_current_stage, moisture_level):
        """
        Inserts a new plant into the Plants table.

        Args:
            name (str): The name of the plant.
            current_stage (str): The current growth stage of the plant.
            moisture_level (float, optional): The soil moisture level.
        """
        try:
            db = self.get_db()
            db.execute('''INSERT INTO Plants (name, current_stage, days_in_current_stage, moisture_level)
                                VALUES (?, ?, ?, ?)
                                ''', 
                                (name, current_stage, days_in_current_stage, moisture_level))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting plant: {e}")

    def insert_soil_moisture_history(self, plant_id, moisture_level):
        """Inserts a new soil moisture reading into the PlantReadings table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO PlantReadings (plant_id, moisture_level) VALUES (?, ?)",
                       (plant_id, moisture_level))
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
            cursor = db.execute("SELECT name, gpio, ip_address FROM Actuator")
            rows = cursor.fetchall()
            actuator_configs = []
            for row in rows:
                config = {
                    'name': row['name'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address']
                }
                actuator_configs.append(config)
            return actuator_configs
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor configs: {e}")
            return []

    def get_sensor_configs(self):
        """Retrieves sensor configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute("SELECT sensor_type, gpio, ip_address FROM Sensor")
            rows = cursor.fetchall()
            sensor_configs = []
            for row in rows:
                config = {
                    'sensor_type': row['sensor_type'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address']
                }
                sensor_configs.append(config)
            return sensor_configs
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor configs: {e}")
            return []
        
    def get_sensor_data(self) -> list:
        """
        Retrieves all sensor data from the SensorReading table.

        Returns:
            list: A list of tuples containing sensor data records.
        """
        try:
            db = self.get_db()
            return db.execute('SELECT * FROM SensorReading').fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor data: {e}")
            return []
    
    def get_plant(self, id) -> tuple:
        """
        Retrieves a specific plant's information from the Plants table.

        Args:
            id (int): The ID of the plant.

        Returns:
            tuple: A tuple containing the plant's name and current stage.
        """
        try:
            db = self.get_db()
            return db.execute('SELECT name, current_stage FROM Plants WHERE id = ?', (id,)).fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting plant: {e}")
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
        
    def get_sensor(self, sensor_id):
        """
        Retrieves a sensor from the database by its ID.

        Args:
            sensor_id (int): The ID of the sensor.

        Returns:
            dict: Sensor information.
        """
        db = self.get_db()
        sensor = db.execute('SELECT * FROM Sensor WHERE sensor_id = ?', (sensor_id,)).fetchone()
        if sensor:
            return dict(sensor)
        return None
    
    def get_sensors_by_type(self, sensor_type):
        """Retrieves sensors by type from the database."""
        try:
            db = self.get_db()
            sensors = db.execute('SELECT * FROM Sensor WHERE sensor_type = ?', (sensor_type,)).fetchall()
            return sensors
        except sqlite3.Error as e:
            logging.error(f"Error retrieving sensors by type: {e}")
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

    def get_plant_by_id(self, plant_id):
        """
        Get plant details by ID.

        Args:
            plant_id (int): The ID of the plant.

        Returns:
            dict: Details of the plant.
        """
        try:
            db = self.get_db()
            cursor = db.execute("SELECT * FROM Plants WHERE id = ?", (plant_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting plant by ID: {e}")
            return None

    def remove_sensor(self, functionality):
        """Removes a sensor from the Sensor table based on its functionality."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Sensor WHERE functionality = ?", (functionality,))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error removing sensor: {e}")

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

    def update_plant_days(self, plant_name, days_in_current_stage):
        """Updates the days in the current stage for a specific plant."""
        try:
            db = self.get_db()
            db.execute('''UPDATE Plants SET days_in_current_stage = ? WHERE name = ?''',
                       (days_in_current_stage, plant_name))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error updating plant days: {e}")
        
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
                return {'start_time': schedule['light_start_time'], 'end_time': schedule['light_end_time']}
            return None
        except sqlite3.Error as e:
            logging.error(f"Error getting light schedule: {e}")
            return None
    
    def save_settings(self, light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold):
        """
        Saves the settings to the database, replacing existing settings if they exist.

        Args:
            light_start_time (str): The start time for the lights.
            light_end_time (str): The end time for the lights.
            temperature_threshold (float): The temperature threshold.
            humidity_threshold (float): The humidity threshold.
            soil_moisture_threshold (float): The soil moisture threshold.
        """
        try:
            db = self.get_db()
            db.execute('''
            INSERT OR REPLACE INTO Settings (id, light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold)
            VALUES (1, ?, ?, ?, ?, ?)
            ''', 
            (light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error saving settings: {e}")

    def load_settings(self) -> dict:
        """
        Loads the settings from the database.

        Returns:
            dict: A dictionary containing light_start_time, light_end_time, temperature_threshold, humidity_threshold, and soil_moisture_threshold.
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
