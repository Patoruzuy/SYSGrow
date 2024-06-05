"""
Description: This script defines the DatabaseManager class for managing the database operations related 
to sensor data, plant information and settings in a grow tent system.

Author: Sebastian Gomez
Date: 26/05/2024
"""

import sqlite3
from flask import g, current_app

class DatabaseManager:
    """
    Manages the database operations for storing sensor data and plant information.

    """
    def get_db(self):
        if 'db' not in g:
            g.db = sqlite3.connect(current_app.config['DATABASE'])
            g.db.row_factory = sqlite3.Row
        return g.db
    
    def close_db(self, e=None):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    def init_app(self, app):
        app.teardown_appcontext(self.close_db)
        with app.app_context():
            self.create_tables()

    def create_tables(self):
        """
        Creates the necessary tables in the database if they do not already exist.
        """
        db = self.get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS Device (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            gpio INTEGER,
                            ip_address TEXT,
                            functionality TEXT NOT NULL
                            )''')
        db.execute('''CREATE TABLE IF NOT EXISTS SensorData (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
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
        db.execute('''
                            CREATE TABLE IF NOT EXISTS Settings (
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
        db.commit()

    def get_device_configs(self):
        self.cursor.execute("SELECT name, gpio, ip_address, functionality FROM Devices")
        rows = self.cursor.fetchall()
        device_configs = []
        for row in rows:
            config = {
                'name': row[0],
                'gpio': row[1],
                'ip_address': row[2],
                'functionality': row[3]
            }
            device_configs.append(config)
        return device_configs
    
    def insert_sensor_data(self, temperature=None, humidity=None, moisture_level=None):
        """
        Inserts sensor data into the SensorData table.

        Args:
            temperature (float, optional): The temperature value.
            humidity (float, optional): The humidity value.
            moisture_level (float optional): The plant moisture level
        """
        db = self.get_db()
        db.execute('''INSERT INTO SensorData (temperature, humidity, moisture_level)
                            VALUES (?, ?, ?)
                            ''', 
                            (temperature, humidity, moisture_level))
        db.commit()

    def insert_device(self, name, gpio, ip_address, functionality):

        db = self.get_db()
        db.execute("INSERT INTO Devices (name, gpio, ip_address, functionality) VALUES (?, ?, ?, ?)",
                           (name, gpio, ip_address, functionality))

    def insert_plant(self, name, growth_stage, moisture_level):
        """
        Inserts a new plant into the Plants table.

        Args:
            name (str): The name of the plant.
            growth_stage (str): The current growth stage of the plant.
            moisture_level (float, optional): The soil moisture level.
        """
        db = self.get_db()
        db.execute('''INSERT INTO Plants (name, growth_stage, moisture_level)
                            VALUES (?, ?, ?)
                            ''', 
                            (name, growth_stage, moisture_level))
        db.commit()

    def update_plant_growth_stage(self, name, growth_stage):
        """
        Updates the growth stage of a plant in the Plants table.

        Args:
            name (str): The name of the plant.
            growth_stage (str): The new growth stage of the plant.
            moisture_level (float, optional): The soil moisture level.
        """
        db = self.get_db()
        db.execute('''UPDATE Plants
                            SET growth_stage = ?
                            WHERE name = ?
                            ''', 
                            (growth_stage, name))
        db.commit()

    def get_sensor_data(self) -> list:
        """
        Retrieves all sensor data from the SensorData table.

        Returns:
            list: A list of tuples containing sensor data records.
        """
        db = self.get_db()
        return db.execute('SELECT * FROM SensorData').fetchall()
        
    
    def get_plant(self, id) -> tuple:
        """
        Retrieves a specific plant's information from the SensorData table.

        Args:
            id (int): The ID of the plant.

        Returns:
            tuple: A tuple containing the plant's name and growth stage.
        """
        db = self.get_db()
        return db.execute('SELECT name, growth_stage FROM SensorData WHERE id = ?', (id,)).fetchone()
        
    def get_light_schedule(self):
        """
        Retrieves the light_start_time and light_end_time from the setting table.

        Returns:
            tuple: A list of tuples containing start_time and end_time schedules.
        """
        db = self.get_db()
        schedule = db.execute('SELECT light_start_time, light_end_time FROM Settings ORDER BY id DESC LIMIT 1').fetchone()
        if schedule:
            return {'start_time':schedule[0], 'end_time': schedule[1]}
        return None

    
    def get_plants(self) -> list:
        """
        Retrieves all plants from the Plants table.

        Returns:
            list: A list of tuples containing plant records.
        """
        db = self.get_db()
        return db.execute('SELECT * FROM Plants').fetchall()
    
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
        db = self.get_db()
        # Insert or replace the settings in the database
        db.execute('''
        INSERT OR REPLACE INTO Settings (id, light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, light_gpio, fan_gpio, water_spray_gpio)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', 
        (light_start_time, light_end_time, temperature_threshold, humidity_threshold, soil_moisture_threshold, light_gpio, fan_gpio, water_spray_gpio))
        db.commit()

    def load_settings(self) -> tuple:
        """
        Loads the settings from the database.

        Returns:
            tuple: A tuple containing light_start_time, light_end_time, temperature_threshold, humidity_threshold, and soil_moisture_threshold.
        """
        db = self.get_db()
        # Select the settings from the database
        return db.execute('SELECT * FROM Settings WHERE id = 1').fetchone()
        

