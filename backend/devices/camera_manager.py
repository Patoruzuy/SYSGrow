import time
import requests
import threading
import cv2
import numpy as np
from backend.devices.camera_core import CameraBase

class CameraHandler(CameraBase):
    """
    A class to handle video streaming from either an ESP32-CAM over HTTP or a USB camera connected to a Raspberry Pi.
    
    Attributes:
    -----------
    url : str
        The URL for the ESP32-CAM's MJPEG stream.
    thread : threading.Thread
        Background thread for capturing frames from the camera.
    frame : bytes
        Current frame stored as a byte stream.
    last_access : float
        Timestamp of the last client access to the camera.
    running : bool
        Flag to control the running state of the thread.
    camera_type : str
        Type of camera being used ('esp32' or 'usb').
    cap : cv2.VideoCapture
        OpenCV VideoCapture object for the USB camera.

    Methods:
    --------
    __init__(camera_type='esp32', ip_address='192.168.0.xx', usb_cam_index=0):
        Initializes the MultiCamera object with the specified camera type and settings.
    
    initialize():
        Starts the background thread for capturing frames if it is not already running.
    
    get_frame():
        Returns the current frame from the camera.
    
    stop():
        Stops the camera streaming and releases resources.
    
    _thread(self):
        Background thread method to capture frames from the camera.
    """

    url = None
    thread = None
    frame = None
    last_access = 0
    running = False
    camera_type = None
    cap = None

    def __init__(self, camera_type, ip_address, usb_cam_index=0):
        """
        Initializes the MultiCamera object with the specified camera type and settings.
        
        Parameters:
        -----------
        camera_type : str
            The type of camera to use ('esp32' for ESP32-CAM, 'usb' for a USB camera).
        ip_address : str, optional
            The IP address of the ESP32-CAM (default is '192.168.0.xx').
        usb_cam_index : int, optional
            The index of the USB camera to use (default is 0).
        """
        self.camera_type = camera_type
        if camera_type == 'esp32':
            CameraHandler.url = f'http://{ip_address}:81/stream'
        elif camera_type == 'usb':
            CameraHandler.cap = cv2.VideoCapture(usb_cam_index)
            CameraHandler.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Set desired resolution
            CameraHandler.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        CameraHandler.running = True

    def initialize(self):
        """
        Starts the background thread for capturing frames if it is not already running.
        """
        if CameraHandler.thread is None:
            CameraHandler.thread = threading.Thread(target=self._thread, args=(self,))
            CameraHandler.thread.start()

            while self.frame is None:
                time.sleep(0.1)

    def get_frame(self):
        """
        Returns the current frame from the camera.
        
        Returns:
        --------
        bytes
            The current frame as a byte stream in JPEG format.
        """
        CameraHandler.last_access = time.time()
        self.initialize()
        return self.frame

    def stop(self):
        """
        Stops the camera streaming and releases resources.
        """
        self.running = False
        if CameraHandler.thread is not None:
            CameraHandler.thread.join()
        CameraHandler.thread = None
        if self.camera_type == 'usb' and CameraHandler.cap is not None:
            CameraHandler.cap.release()

    @classmethod
    def _thread(cls, self):
        """
        Background thread method to capture frames from the camera.
        
        This method handles capturing frames from either the ESP32-CAM's MJPEG stream or from a USB camera,
        depending on the camera type specified during initialization.
        """
        try:
            if self.camera_type == 'esp32':
                stream = requests.get(cls.url, stream=True)
                bytes_data = b''

                for chunk in stream.iter_content(chunk_size=1024):
                    if not self.running:
                        break

                    bytes_data += chunk
                    a = bytes_data.find(b'\xff\xd8')  # JPEG start
                    b = bytes_data.find(b'\xff\xd9')  # JPEG end

                    if a != -1 and b != -1:
                        jpg = bytes_data[a:b+2]
                        bytes_data = bytes_data[b+2:]

                        # Convert to numpy array
                        img_np = np.frombuffer(jpg, dtype=np.uint8)
                        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

                        with cls.lock:
                            cls.frame = cv2.imencode('.jpg', img)[1].tobytes()

                    if time.time() - cls.last_access > 10:
                        print('No client access for 10 seconds, stopping thread.')
                        break

            elif self.camera_type == 'usb':
                while self.running:
                    ret, frame = cls.cap.read()
                    if not ret:
                        print('Failed to grab frame from USB camera.')
                        break

                    with cls.lock:
                        cls.frame = cv2.imencode('.jpg', frame)[1].tobytes()

                    if time.time() - cls.last_access > 10:
                        print('No client access for 10 seconds, stopping thread.')
                        break

        except Exception as e:
            print(f"Unexpected error in camera thread: {e}")
        finally:
            cls.thread = None
            self.running = False

class ESP32CameraController:
    """
    A class to control and configure an ESP32-CAM by sending HTTP requests to its control endpoint.

    Methods:
    --------
    apply_settings(settings):
        Applies a batch of camera settings (resolution, quality, brightness, etc.) to the ESP32-CAM.

    set_resolution(value):
        Sets the resolution of the ESP32-CAM.

    set_quality(value):
        Sets the image quality of the ESP32-CAM.

    set_brightness(value):
        Sets the brightness level of the ESP32-CAM.

    set_contrast(value):
        Sets the contrast level of the ESP32-CAM.

    set_saturation(value):
        Sets the saturation level of the ESP32-CAM.

    set_flip(value):
        Sets whether the image should be flipped horizontally.

    apply_settings(settings):
        Applies a batch of camera settings (resolution, quality, brightness, etc.) to the ESP32-CAM.

    _send_request(var, val):
        Sends an HTTP request to modify a specific camera setting.
    """

    def __init__(self, ip_address):
        """
        Initializes the ESP32CamController with the specified IP address.

        Parameters:
        -----------
        ip_address : str
            The IP address of the ESP32-CAM.
        """
        self.base_url = f'http://{ip_address}/control'
        self.ip_address = ip_address

    def apply_settings(self, settings):
        """
        Applies multiple settings (resolution, quality, brightness, contrast, saturation, and flip) to the ESP32-CAM.

        Parameters:
        -----------
        settings : dict
            A dictionary containing all camera settings to be applied.
        """
        self.set_resolution(settings.get('resolution'))
        self.set_quality(settings.get('quality'))
        self.set_brightness(settings.get('brightness'))
        self.set_contrast(settings.get('contrast'))
        self.set_saturation(settings.get('saturation'))
        self.set_flip(settings.get('flip'))

    def set_resolution(self, value):
        """
        Sets the resolution of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The resolution value to be set (0 to 13).
        """
        return self._send_request('framesize', value)

    def set_quality(self, value):
        """
        Sets the image quality of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The quality value to be set (0 to 63, where lower is higher quality).
        """
        return self._send_request('quality', value)

    def set_brightness(self, value):
        """
        Sets the brightness level of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The brightness value (-2 to 2).
        """
        return self._send_request('brightness', value)

    def set_contrast(self, value):
        """
        Sets the contrast level of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The contrast value (-2 to 2).
        """
        return self._send_request('contrast', value)

    def set_saturation(self, value):
        """
        Sets the saturation level of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The saturation value (-2 to 2).
        """
        return self._send_request('saturation', value)

    def set_flip(self, value):
        """
        Sets whether the image should be flipped horizontally.

        Parameters:
        -----------
        value : int
            0 for normal, 1 for flipped.
        """
        return self._send_request('flip', value)

    def _send_request(self, var, val):
        """
        Sends an HTTP request to change a specific setting on the ESP32-CAM.

        Parameters:
        -----------
        var : str
            The camera setting to modify (e.g., 'framesize', 'quality').
        val : int
            The value to set for the specified variable.

        Returns:
        --------
        bool
            True if the request was successful, False otherwise.
        """
        url = f'{self.base_url}?var={var}&val={val}'
        response = requests.get(url)
        return response.status_code == 200

class CameraManager:
    """
    A class to manage camera instances, settings, and operations such as starting and stopping the camera.

    Attributes:
    -----------
    camera_instance : MultiCamera or None
        The currently active camera instance.
    camera_running : bool
        Flag indicating whether the camera is running.
    camera_lock : threading.Lock
        A lock to ensure thread-safe camera operations.
    user_id : int
        The ID of the user whose camera settings are being managed.

    Methods:
    --------
    load_camera_settings():
        Loads the user's camera settings from the database.

    get_camera_settings_from_db():
        Retrieves the camera settings from the database for the current user.

    set_camera(camera_type, ip_address=None, usb_cam_index=None):
        Sets and saves the camera configuration to the database.

    save_camera_settings_to_db(camera_type, ip_address, usb_cam_index):
        Saves the camera settings to the database.

    start_camera():
        Starts the camera using the settings stored in the database.

    stop_camera():
        Stops the currently running camera and releases resources.
    """

    def __init__(self, database_manager):
        """
        Initializes the CameraManager with the specified database instance.

        Parameters:
        -----------
        database_manager : DatabaseManager
            An instance of the database manager.
        """
        self.db_manager = database_manager
        self.camera_instance = None
        self.camera_running = False
        self.camera_lock = threading.Lock()

    def load_camera_settings(self):
        """
        Loads the user's camera settings from the database.

        Returns:
        --------
        dict
            A dictionary containing the camera settings for the user.
        """
        return self.db_manager.load_camera_settings()

    def start_camera(self):
        """
        Starts the camera using the settings stored in the database.
        """
        camera_settings = self.load_camera_settings()

        with self.camera_lock:
            if not self.camera_running:
                if self.camera_instance:
                    self.camera_instance.stop()

                if camera_settings['camera_type'] == 'esp32':
                    # Initialize ESP32 with the correct settings
                    self.camera_instance = CameraHandler(
                        camera_type='esp32', 
                        ip_address=camera_settings['ip_address']
                    )
                    settings_instance = ESP32CameraController(
                        ip_address=camera_settings['ip_address']
                    )
                    # Apply settings to the ESP32CamController
                    settings_instance.apply_settings(camera_settings)

                elif camera_settings['camera_type'] == 'usb':
                    # USB camera initialization
                    self.camera_instance = CameraHandler(
                        camera_type='usb', 
                        usb_cam_index=camera_settings.get('usb_cam_index')
                    )
                self.camera_running = True

    def stop_camera(self):
        """
        Stops the currently running camera and releases resources.
        """
        with self.camera_lock:
            if self.camera_running and self.camera_instance:
                self.camera_instance.stop()
                self.camera_running = False

    def save_camera_settings(self, camera_type, ip_address=None, usb_cam_index=None, last_used=None, resolution=None, quality=None, brightness=None, contrast=None, saturation=None, flip=None):
        """
        Saves the camera settings to the database. Initially, it saves only basic camera settings (camera type and IP address).
        then, when available, it saves additional settings (resolution, quality, brightness, etc.).

        Args:
            camera_type (str): Either 'usb' or 'esp32' camera type.
            ip_address (str): The IP address of the ESP32 camera (only relevant for 'esp32' type).
            usb_cam_index (int): The USB index of the USB camera (only relevant for 'usb' type).
            last_used (str): The last time the camera was used.
            resolution (int): Resolution value of the camera.
            quality (int): Quality setting of the camera.
            brightness (int): Brightness level.
            contrast (int): Contrast level.
            saturation (int): Saturation level.
            flip (int): Flip setting (0 for normal, 1 for flipped).
        """
        self.db_manager.save_camera_settings(
            camera_type=camera_type, 
            ip_address=ip_address, 
            usb_cam_index=usb_cam_index, 
            last_used=last_used, 
            resolution=resolution, 
            quality=quality, 
            brightness=brightness, 
            contrast=contrast, 
            saturation=saturation, 
            flip=flip
        )

