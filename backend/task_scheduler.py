"""
Timer and PlantTimerObserver classes for scheduling and observing plant growth in the grow tent.

Author: Sebastian Gomez
Date: May 2024
"""
import schedule
import time
from datetime import datetime
from threading import Thread

class TaskScheduler:
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
            cls._instance = super(TaskScheduler, cls).__new__(cls)
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
        print("Timer attach", observer)

    def detach(self, observer):
        """
        Detaches an observer from the timer.

        Args:
            observer (object): The observer to be detached.
        """
        self.observers.remove(observer)
        print("TImer detach", observer)

    def notify(self, message=None):
        """
        Notifies all attached observers with a specific message.

        Args:
            message (str): The message to send to observers.
        """
        for observer in self.observers:
            try:
                print(f"Notifying {observer} with message '{message}'")
                observer.update(message)
            except Exception as e:
                print(f"Error notifying observer {observer}: {e}")

    def schedule_plant_growth(self, time_of_day="00:00"):
        """
        Schedules the plant growth to occur daily at a specific time.
        
        Args:
            time_of_day (str): The time of day when the plant should grow in 'HH:MM' format.
        """
        schedule.every().day.at(time_of_day).do(self.notify, 'grow')
        print(f"Plant growth scheduled daily at {time_of_day}")

    def schedule_device(self, start_time, end_time):
        """
        Generic method to schedule a device on/off once per day.

        Args:
            start_time (str): "HH:MM" for when to send the `on` message.
            end_time   (str): "HH:MM" for when to send the `off` message.
        """
        # Schedule the on/off messages
        schedule.every().day.at(start_time).do(self.notify, 'on')
        schedule.every().day.at(end_time).do(self.notify, 'off')
        
        print(f"Scheduled device from {start_time} to {end_time}")
        
        # Immediately evaluate whether it should be on or off right now
        self._evaluate_device_status(start_time, end_time)

    def _evaluate_device_status(self, start_time, end_time):
        """
        Immediately decides if we should notify "on" or "off" based on the current time.
        (so the device goes on/off right away).
        """
        now = datetime.now().time()
        device_on  = datetime.strptime(start_time, "%H:%M").time()
        device_off = datetime.strptime(end_time,   "%H:%M").time()

        # Decide if we're currently in the 'on' window or not
        if device_on < device_off:
            # Normal case: e.g. 08:00 -> 20:00 same day
            if device_on <= now < device_off:
                self.notify('on')
            else:
                self.notify('off')
        else:
            # "overnight" case: start time is e.g. 20:00, end time is 06:00 next day
            if now >= device_on or now < device_off:
                self.notify('on')
            else:
                self.notify('off')

    @staticmethod
    def _run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

class DeviceStateObserver:
    """
    A single observer class that can handle different update behaviors.
    """
    def __init__(self, device_name, actuator_controller):
        """
        Args:
            device_name: The actual name of the device being controlled.
            actuator_controller: Reference to the actuator_controller.
        """
        self.actuator_controller = actuator_controller
        self.device_name = device_name

    def update(self, message):
        """
        Updates the state of the device based on the timer notification.

        Args:
            message (str): "on" or "off" (or other custom commands).
        """
        if message == "on":
            self.actuator_controller.activate_actuator(self.device_name)
        elif message == "off":
            self.actuator_controller.deactivate_actuator(self.device_name)


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
