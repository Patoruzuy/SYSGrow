import logging
import threading
import time

logger = logging.getLogger(__name__)


class CameraBase:
    """
    Base class for camera implementations with instance-level state.

    This allows multiple camera instances to run independently without
    interfering with each other.
    """

    def __init__(self):
        """Initialize instance-level camera state."""
        self._thread = None  # Background thread that reads frames from the camera
        self._frame = None  # Current frame stored here by background thread
        self._last_access = 0  # Time of last client access to the camera
        self._lock = threading.Lock()  # Ensure thread safety
        self._running = False  # Control flag for thread

    def initialize(self):
        """Initialize the camera, start the background thread if necessary."""
        with self._lock:
            if self._thread is None:
                # Start the background frame thread
                self._running = True
                self._thread = threading.Thread(target=self._thread_func)
                self._thread.start()

                # Wait until the first frame is available
                timeout = time.time() + 5  # 5 second timeout
                while self._frame is None and time.time() < timeout:
                    time.sleep(0.1)

    def get_frame(self):
        """Return the current camera frame."""
        self._last_access = time.time()
        self.initialize()
        return self._frame

    def frames(self):
        """Generator that returns frames from the camera."""
        raise RuntimeError("Must be implemented by subclasses.")

    def _thread_func(self):
        """Camera background thread."""
        logger.info("Starting camera thread")
        frames_iterator = self.frames()
        try:
            for frame in frames_iterator:
                if not self._running:
                    break

                with self._lock:
                    self._frame = frame

                # If there hasn't been any clients asking for frames in
                # the last 10 seconds then stop the thread
                if time.time() - self._last_access > 10:
                    logger.info("Stopping camera thread due to inactivity")
                    break
        except Exception as e:
            logger.error(f"Error in camera thread: {e}", exc_info=True)
        finally:
            try:
                frames_iterator.close()
            except Exception as e:
                logger.warning(f"Error closing frames iterator: {e}")
            with self._lock:
                self._thread = None
                self._running = False

    def stop(self):
        """Stop the camera and clean up resources."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
