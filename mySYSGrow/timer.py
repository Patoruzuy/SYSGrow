"""
Timer and PlantTimerObserver classes for scheduling and observing plant growth in the grow tent.

Author: Sebastian Gomez
Date: May 2024
"""
import schedule
import time
from threading import Thread

class Timer:
    """
    Singleton class to manage scheduling and notifying observers.
    
    Attributes:
        observers (list): List of observer objects that get notified on schedule.
    """
    _instance = None

    def __new__(cls):
        """
        Ensures only one instance of Timer exists (Singleton pattern).
        """
        if cls._instance is None:
            cls._instance = super(Timer, cls).__new__(cls)
            cls._instance.observers = []
            cls._instance.schedule_thread = Thread(target=cls._run_schedule)
            cls._instance.schedule_thread.daemon = True
            cls._instance.schedule_thread.start()
        return cls._instance

    def attach(self, observer):
        """
        Attaches an observer to the timer.

        Args:
            observer (object): The observer to be attached.
        """
        self.observers.append(observer)

    def detach(self, observer):
        """
        Detaches an observer from the timer.

        Args:
            observer (object): The observer to be detached.
        """
        self.observers.remove(observer)

    def notify(self, message=None):
        """
        Notifies all attached observers with a specific message.

        Args:
            message (str): The message to send to observers.
        """
        for observer in self.observers:
            print(f"Notifying {observer} with message '{message}'")
            observer.update(message)

    def schedule_light(self, start_time, end_time):
        """
        Schedules light for plants and notifies observers.

        Args:
            start_time (str): The start time for the light schedule in 'HH:MM' format.
            end_time (str): The end time for the light schedule in 'HH:MM' format.
        """
        schedule.every().day.at(start_time).do(self.turn_on_lights)
        schedule.every().day.at(end_time).do(self.turn_off_lights)
        print(f"Light scheduled from {start_time} to {end_time}")

    def turn_on_lights(self):
        print("Turning on lights")
        self.notify("on")

    def turn_off_lights(self):
        print("Turning off lights")
        self.notify("off")

    @staticmethod
    def _run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

class LightObserver:
    """
    Observer class that responds to timer notifications by turning lights on and off.
    
    Attributes:
        device_manager (DeviceManager): The device manager to control devices.
        functionality (str): The functionality of the light device.
    """
    def __init__(self, device_manager, functionality):
        """
        Initializes the LightObserver with a device manager and functionality.

        Args:
            device_manager (DeviceManager): The device manager to control devices.
            functionality (str): The functionality of the light device.
        """
        self.device_manager = device_manager
        self.functionality = functionality

    def update(self, message):
        """
        Updates the light state based on the timer notification.

        Args:
            message (str): The desired state of the light ('on' or 'off').
        """
        if message == "on":
            self.device_manager.turn_on_device(self.functionality)
        elif message == "off":
            self.device_manager.turn_off_device(self.functionality)

class PlantTimerObserver:
    """
    Observer class that responds to timer notifications by growing a plant.
    
    Attributes:
        plant (Plant): The plant associated with this observer.
    """
    def __init__(self, plant):
        """
        Initializes the PlantTimerObserver with a plant.

        Args:
            plant (Plant): The plant associated with this observer.
        """
        self.plant = plant

    def update(self, message=None):
        """
        Triggers the plant to grow when the timer notifies.
        """
        self.plant.grow()
