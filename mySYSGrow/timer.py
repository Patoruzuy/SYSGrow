"""
Timer and PlantTimerObserver classes for scheduling and observing plant growth in the grow tent.

Author: Sebastian Gomez
Date: May 2024
"""

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

    def notify(self):
        """
        Notifies all attached observers.
        """
        for observer in self.observers:
            observer.update()

    def schedule_light(self, start_time, end_time):
        """
        Schedules light for plants and notifies observers.

        Args:
            start_time (str): The start time for the light schedule.
            end_time (str): The end time for the light schedule.
        """
        print(f"Light scheduled from {start_time} to {end_time}")
        self.notify()


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

    def update(self):
        """
        Triggers the plant to grow when the timer notifies.
        """
        self.plant.grow()
