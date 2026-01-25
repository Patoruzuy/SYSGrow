"""
TaskScheduler: Manages scheduling for plant growth and device automation with AI & MQTT integration.

Author: Sebastian Gomez
Date: May 2024
"""
import schedule
import time
import logging
from datetime import datetime
from threading import Thread
from utils.event_bus import EventBus
from mqtt.mqtt_notifier import MQTTNotifier

logging.basicConfig(level=logging.INFO, filename="task_scheduler.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class TaskScheduler:
    """
    Singleton class managing scheduled tasks for plants & devices, integrating AI & MQTT.

    Attributes:
        observers (list): List of objects notified on schedule.
        event_bus (EventBus): Publishes scheduling events.
        mqtt_notifier (MQTTNotifier): Publishes schedule updates via MQTT.
    """
    _instance = None

    def __new__(cls):
        """Ensures only one instance of TaskScheduler (Singleton)."""
        if cls._instance is None:
            cls._instance = super(TaskScheduler, cls).__new__(cls)
            cls._instance.observers = []
            cls._instance.event_bus = EventBus()
            cls._instance.mqtt_notifier = MQTTNotifier()
            cls._instance.schedule_thread = Thread(target=cls._run_schedule)
            cls._instance.schedule_thread.daemon = True
            cls._instance.schedule_thread.start()
        return cls._instance

    def attach(self, observer):
        """Attaches an observer to the scheduler."""
        self.observers.append(observer)
        logging.info(f"Attached observer: {observer}")

    def detach(self, observer):
        """Detaches an observer from the scheduler."""
        self.observers.remove(observer)
        logging.info(f"Detached observer: {observer}")

    def notify(self, message=None):
        """Notifies all observers with a specific message."""
        for observer in self.observers:
            try:
                observer.update(message)
                logging.info(f"Notified {observer} with '{message}'")
            except Exception as e:
                logging.error(f"Error notifying {observer}: {e}")

    def schedule_plant_growth(self, time_of_day="00:00"):
        """
        Schedules plant growth daily at a specific time.
        
        Args:
            time_of_day (str): Time when plants should grow ('HH:MM' format).
        """
        schedule.every().day.at(time_of_day).do(self.notify, 'grow')
        logging.info(f"Plant growth scheduled daily at {time_of_day}")
        self.mqtt_notifier.publish_event("plant_growth_schedule", {"time": time_of_day})

    def schedule_device(self, device_name, start_time, end_time):
        """
        Schedules ON/OFF times for a device.

        Args:
            device_name (str): The name of the device.
            start_time (str): Time to turn **ON** ('HH:MM' format).
            end_time   (str): Time to turn **OFF** ('HH:MM' format).
        """
        schedule.every().day.at(start_time).do(self.notify, {'device': device_name, 'state': 'on'})
        schedule.every().day.at(end_time).do(self.notify, {'device': device_name, 'state': 'off'})

        logging.info(f"Scheduled {device_name}: ON at {start_time}, OFF at {end_time}")
        self.mqtt_notifier.publish_event("device_schedule_update", {
            "device": device_name,
            "start_time": start_time,
            "end_time": end_time
        })

        self._evaluate_device_status(device_name, start_time, end_time)

    def _evaluate_device_status(self, device_name, start_time, end_time):
        """
        Immediately evaluates if a device should be ON or OFF.
        """
        now = datetime.now().time()
        device_on = datetime.strptime(start_time, "%H:%M").time()
        device_off = datetime.strptime(end_time, "%H:%M").time()

        if device_on < device_off:
            if device_on <= now < device_off:
                self.notify({'device': device_name, 'state': 'on'})
            else:
                self.notify({'device': device_name, 'state': 'off'})
        else:
            if now >= device_on or now < device_off:
                self.notify({'device': device_name, 'state': 'on'})
            else:
                self.notify({'device': device_name, 'state': 'off'})

    @staticmethod
    def _run_schedule():
        """Continuously runs the scheduler."""
        while True:
            schedule.run_pending()
            time.sleep(1)


class DeviceStateObserver:
    """
    Observes scheduled device changes and controls actuators accordingly.
    """
    def __init__(self, device_name, actuator_controller):
        self.device_name = device_name
        self.actuator_controller = actuator_controller

    def update(self, message):
        """
        Updates device state based on schedule.
        
        Args:
            message (dict): {'device': <device_name>, 'state': 'on'/'off'}
        """
        device = message.get('device')
        state = message.get('state')

        if state == "on":
            self.actuator_controller.activate_actuator(device)
        elif state == "off":
            self.actuator_controller.deactivate_actuator(device)

        logging.info(f"Device '{device}' turned {state}")


class PlantTimerObserver:
    """
    Observes plant growth schedules.
    """
    def __init__(self, plant):
        self.plant = plant

    def update(self, message=None):
        """
        Triggers the plant to grow on schedule.
        """
        self.plant.grow()
        logging.info(f"Plant {self.plant.get_name()} advanced growth stage")
