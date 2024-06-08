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
        insert_sensor_data: Inserts sensor data into the SensorData table.
        insert_device: Inserts a new device into the Devices table.
        insert_plant: Inserts a new plant into the Plants table.
        update_plant_growth_stage: Updates the growth stage of a plant in the Plants table.
        get_sensor_data: Retrieves all sensor data from the SensorData table.
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
            db.execute('''CREATE TABLE IF NOT EXISTS Device (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT,
                                type TEXT NOT NULL,
                                functionality TEXT NOT NULL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Sensor (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT NOT NULL,
                                gpio INTEGER,
                                ip_address TEXT,
                                type TEXT NOT NULL,
                                functionality TEXT NOT NULL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS SensorData (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                plant_name TEXT,
                                temperature REAL,
                                humidity REAL,
                                moisture_level REAL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Plants (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                growth_stage TEXT,
                                moisture_level REAL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS Settings (
                                id INTEGER PRIMARY KEY,
                                light_start_time TEXT,
                                light_end_time TEXT,
                                temperature_threshold REAL,
                                humidity_threshold REAL,
                                soil_moisture_threshold REAL,
                                light_gpio REAL,
                                fan_gpio REAL,
                                water_spray_gpio REAL
                                )''')
            db.execute('''CREATE TABLE IF NOT EXISTS plant_sensors (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                plant_id INTEGER,
                                sensor_id INTEGER,
                                FOREIGN KEY (plant_id) REFERENCES Plants(id),
                                FOREIGN KEY (sensor_id) REFERENCES Sensor(id)
                                )''')
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error creating tables: {e}")

    def insert_device(self, name, gpio, ip_address, type, functionality):
        """Inserts a new device into the Devices table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO Device (name, gpio, ip_address, functionality) VALUES (?, ?, ?, ?, ?)",
                            (name, gpio, ip_address, type, functionality))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting device: {e}")

    def insert_sensor(self, name, gpio, ip_address, type, functionality):
        """Inserts a new sensor into the Sensor table."""
        try:
            db = self.get_db()
            db.execute("INSERT INTO Sensor (name, gpio, ip_address, type, functionality) VALUES (?, ?, ?, ?, ?)",
                            (name, gpio, ip_address, type, functionality))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor: {e}")

    def insert_plant(self, name, growth_stage, moisture_level):
        """
        Inserts a new plant into the Plants table.

        Args:
            name (str): The name of the plant.
            growth_stage (str): The current growth stage of the plant.
            moisture_level (float, optional): The soil moisture level.
        """
        try:
            db = self.get_db()
            db.execute('''INSERT INTO Plants (name, growth_stage, moisture_level)
                                VALUES (?, ?, ?)
                                ''', 
                                (name, growth_stage, moisture_level))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting plant: {e}")

    def insert_sensor_data(self, plant_name=None, temperature=None, humidity=None, moisture_level=None):
        """
        Inserts sensor data into the SensorData table.

        Args:
            temperature (float, optional): The temperature value.
            humidity (float, optional): The humidity value.
            moisture_level (float optional): The plant moisture level
        """
        try:
            db = self.get_db()
            db.execute('''INSERT INTO SensorData (plant_name, temperature, humidity, moisture_level)
                                VALUES (?, ?, ?, ?)
                                ''', 
                                (plant_name, temperature, humidity, moisture_level))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error inserting sensor data: {e}")

    def get_device_configs(self):
        """Retrieves device configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute("SELECT name, gpio, ip_address, functionality FROM Device")
            rows = cursor.fetchall()
            device_configs = []
            for row in rows:
                config = {
                    'name': row['name'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address'],
                    'type': row['type'],
                    'functionality': row['functionality']
                }
                device_configs.append(config)
            return device_configs
        except sqlite3.Error as e:
            logging.error(f"Error getting device configs: {e}")
            return []

    def get_sensor_configs(self):
        """Retrieves sensor configurations from the database."""
        try:
            db = self.get_db()
            cursor = db.execute("SELECT name, gpio, ip_address, type, functionality FROM Sensor")
            rows = cursor.fetchall()
            sensor_configs = []
            for row in rows:
                config = {
                    'name': row['name'],
                    'gpio': row['gpio'],
                    'ip_address': row['ip_address'],
                    'type': row['type'],
                    'functionality': row['functionality']
                }
                sensor_configs.append(config)
            return sensor_configs
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor configs: {e}")
            return []
        
    def get_sensor_data(self) -> list:
        """
        Retrieves all sensor data from the SensorData table.

        Returns:
            list: A list of tuples containing sensor data records.
        """
        try:
            db = self.get_db()
            return db.execute('SELECT * FROM SensorData').fetchall()
        except sqlite3.Error as e:
            logging.error(f"Error getting sensor data: {e}")
            return []
    
    def get_plant(self, id) -> tuple:
        """
        Retrieves a specific plant's information from the Plants table.

        Args:
            id (int): The ID of the plant.

        Returns:
            tuple: A tuple containing the plant's name and growth stage.
        """
        try:
            db = self.get_db()
            return db.execute('SELECT name, growth_stage FROM Plants WHERE id = ?', (id,)).fetchone()
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
            cursor = db.execute("SELECT sensor_id FROM plant_sensors WHERE plant_id = ?", (plant_id,))
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

    def get_device_by_id(self, device_id):
        """
        Get device details by ID.

        Args:
            device_id (int): The ID of the device.

        Returns:
            dict: Details of the device.
        """
        try:
            db = self.get_db()
            cursor = db.execute("SELECT * FROM Device WHERE id = ?", (device_id,))
            return cursor.fetchone()
        except sqlite3.Error as e:
            logging.error(f"Error getting device by ID: {e}")
            return None

    def clear_devices(self):
        """Clears all device configurations from the database."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM Device")
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error clearing devices: {e}")

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
            db.execute("INSERT INTO plant_sensors (plant_id, sensor_id) VALUES (?, ?)",
                       (plant_id, sensor_id))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error linking sensor to plant: {e}") 

    def update_plant_growth_stage(self, name, growth_stage):
        """
        Updates the growth stage of a plant in the Plants table.

        Args:
            name (str): The name of the plant.
            growth_stage (str): The new growth stage of the plant.
        """
        try:
            db = self.get_db()
            db.execute('''UPDATE Plants
                                SET growth_stage = ?
                                WHERE name = ?
                                ''', 
                                (growth_stage, name))
            db.commit()
        except sqlite3.Error as e:
            logging.error(f"Error updating plant growth stage: {e}")
        
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
    
    def save_settings(self, light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, light_gpio, fan_gpio, water_spray_gpio):
        """
        Saves the settings to the database, replacing existing settings if they exist.

        Args:
            light_start_time (str): The start time for the lights.
            light_end_time (str): The end time for the lights.
            temperature_threshold (float): The temperature threshold.
            humidity_threshold (float): The humidity threshold.
            soil_moisture_threshold (float): The soil moisture threshold.
            light_gpio (float): The GPIO pin for the light.
            fan_gpio (float): The GPIO pin for the fan.
            water_spray_gpio (float): The GPIO pin for the water spray.
        """
        try:
            db = self.get_db()
            db.execute('''
            INSERT OR REPLACE INTO Settings (id, light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, light_gpio, fan_gpio, water_spray_gpio)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', 
            (light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, light_gpio, fan_gpio, water_spray_gpio))
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
