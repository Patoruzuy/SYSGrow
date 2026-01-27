import time
import unittest
from app.utils.event_bus import EventBus

class TestEventBus(unittest.TestCase):
    """Unit tests for the EventBus module."""

    def setUp(self):
        """Setup before each test."""
        self.event_bus = EventBus()
        self.received_data = None

    def event_listener(self, data):
        """Helper method to capture published event data."""
        self.received_data = data

    def test_subscribe_and_publish(self):
        """Test event subscription and publishing."""
        self.event_bus.subscribe("test_event", self.event_listener)
        self.event_bus.publish("test_event", {"key": "value"})

        # Wait for event processing
        time.sleep(0.1)

        self.assertEqual(self.received_data, {"key": "value"})

    def test_multiple_subscribers(self):
        """Test multiple subscribers receiving events."""
        listener_1_data = []
        listener_2_data = []

        import time
        import unittest
        from app.utils.event_bus import EventBus


        class TestEventBus(unittest.TestCase):
            """Unit tests for the EventBus module."""

            def setUp(self):
                """Setup before each test."""
                self.event_bus = EventBus()
                self.received_data = None

            def event_listener(self, data):
                """Helper method to capture published event data."""
                self.received_data = data

            def test_subscribe_and_publish(self):
                """Test event subscription and publishing."""
                self.event_bus.subscribe("test_event", self.event_listener)
                self.event_bus.publish("test_event", {"key": "value"})

                # Wait for event processing
                time.sleep(0.1)

                self.assertEqual(self.received_data, {"key": "value"})

            def test_multiple_subscribers(self):
                """Test multiple subscribers receiving events."""
                listener_1_data = []
                listener_2_data = []

                def listener_1(data):
                    listener_1_data.append(data)

                def listener_2(data):
                    listener_2_data.append(data)

                self.event_bus.subscribe("multi_event", listener_1)
                self.event_bus.subscribe("multi_event", listener_2)
                self.event_bus.publish("multi_event", {"message": "Hello"})

                # Wait for event processing
                time.sleep(0.1)

                self.assertEqual(listener_1_data, [{"message": "Hello"}])
                self.assertEqual(listener_2_data, [{"message": "Hello"}])

            def test_no_subscribers(self):
                """Ensure no error occurs when publishing without subscribers."""
                try:
                    self.event_bus.publish("unsubscribed_event", {"data": "test"})
                except Exception as e:
                    self.fail(f"Event publishing failed unexpectedly: {e}")


        if __name__ == "__main__":
            unittest.main()
