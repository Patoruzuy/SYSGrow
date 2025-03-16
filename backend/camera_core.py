import time
import threading

class CameraBase(object):
    thread = None  # Background thread that reads frames from the camera
    frame = None  # Current frame stored here by background thread
    last_access = 0  # Time of last client access to the camera
    lock = threading.Lock()  # Ensure thread safety

    @classmethod
    def initialize(cls):
        """Initialize the camera, start the background thread if necessary."""
        with cls.lock:
            if cls.thread is None:
                # Start the background frame thread
                cls.thread = threading.Thread(target=cls._thread)
                cls.thread.start()

                # Wait until the first frame is available
                while cls.frame is None:
                    time.sleep(0.1)

    @classmethod
    def get_frame(cls):
        """Return the current camera frame."""
        cls.last_access = time.time()
        cls.initialize()
        return cls.frame

    @staticmethod
    def frames():
        """Generator that returns frames from the camera."""
        raise RuntimeError('Must be implemented by subclasses.')

    @classmethod
    def _thread(cls):
        """Camera background thread."""
        print('Starting camera thread.')
        frames_iterator = cls.frames()
        try:
            for frame in frames_iterator:
                with cls.lock:
                    cls.frame = frame

                # If there hasn't been any clients asking for frames in
                # the last 10 seconds then stop the thread
                if time.time() - cls.last_access > 10:
                    print('Stopping camera thread due to inactivity.')
                    break
        finally:
            frames_iterator.close()
            with cls.lock:
                cls.thread = None

