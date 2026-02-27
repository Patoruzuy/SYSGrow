import logging
import threading

import requests

# Optional OpenCV import
try:
    import cv2
    import numpy as np

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV (cv2) not available - camera features disabled")

from app.hardware.devices.camera_core import CameraBase


class CameraHandler(CameraBase):
    """
    A class to handle video streaming from multiple camera types.

    Supported types:
    - ESP32-CAM: MJPEG stream over HTTP
    - USB: Local USB camera
    - RTSP: IP cameras with RTSP protocol
    - MJPEG: Generic MJPEG streams
    - HTTP: Generic HTTP/HTTPS streams

    Now uses instance-level state to support multiple independent cameras.
    """

    def __init__(
        self, camera_type, ip_address=None, usb_cam_index=0, port=81, stream_url=None, username=None, password=None
    ):
        """
        Initializes the CameraHandler object with the specified camera type and settings.

        Parameters:
        -----------
        camera_type : str
            The type of camera to use ('esp32', 'usb', 'rtsp', 'mjpeg', 'http').
        ip_address : str, optional
            The IP address of the ESP32-CAM (for backward compatibility).
        usb_cam_index : int, optional
            The index of the USB camera to use (default is 0).
        port : int, optional
            The port of the ESP32-CAM stream (default is 81).
        stream_url : str, optional
            Full URL for RTSP, MJPEG, or HTTP streams.
        username : str, optional
            Username for authenticated camera streams.
        password : str, optional
            Password for authenticated camera streams.
        """
        super().__init__()
        self.camera_type = camera_type
        self.url = None
        self.cap = None
        self.username = username
        self.password = password

        if camera_type == "esp32":
            if not ip_address:
                raise ValueError("ip_address is required for ESP32 camera type")
            self.url = f"http://{ip_address}:{port}/stream"

        elif camera_type == "usb":
            if not CV2_AVAILABLE:
                raise RuntimeError("OpenCV (cv2) not available for USB camera")
            self.cap = cv2.VideoCapture(usb_cam_index)
            if not self.cap or not self.cap.isOpened():
                try:
                    if self.cap:
                        self.cap.release()
                except Exception as exc:
                    logging.getLogger(__name__).debug("Failed releasing unavailable USB camera: %s", exc)
                raise RuntimeError(f"USB camera index {usb_cam_index} not available")
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        elif camera_type == "rtsp":
            if not stream_url:
                raise ValueError("stream_url is required for RTSP camera type")
            if not CV2_AVAILABLE:
                raise RuntimeError("OpenCV (cv2) not available for RTSP camera")
            # Build RTSP URL with authentication if provided
            if username and password:
                # Extract protocol and rest of URL
                if "://" in stream_url:
                    protocol, rest = stream_url.split("://", 1)
                    self.url = f"{protocol}://{username}:{password}@{rest}"
                else:
                    self.url = f"rtsp://{username}:{password}@{stream_url}"
            else:
                self.url = stream_url
            self.cap = cv2.VideoCapture(self.url)
            if not self.cap or not self.cap.isOpened():
                try:
                    if self.cap:
                        self.cap.release()
                except Exception as exc:
                    logging.getLogger(__name__).debug("Failed releasing unavailable RTSP camera stream: %s", exc)
                raise RuntimeError("Failed to open RTSP stream. Check URL/credentials/network.")

        elif camera_type in ["mjpeg", "http"]:
            if not stream_url:
                raise ValueError(f"stream_url is required for {camera_type} camera type")
            self.url = stream_url

    def frames(self):
        """
        Generator that yields frames from the camera.

        Yields:
        -------
        bytes
            Frame data as JPEG bytes.
        """
        try:
            if self.camera_type in ["esp32", "mjpeg", "http"]:
                # MJPEG stream (ESP32, generic MJPEG, or HTTP)
                auth = None
                if self.username and self.password:
                    from requests.auth import HTTPBasicAuth

                    auth = HTTPBasicAuth(self.username, self.password)

                stream = requests.get(self.url, stream=True, timeout=10, auth=auth)
                bytes_data = b""

                for chunk in stream.iter_content(chunk_size=1024):
                    if not self._running:
                        break

                    bytes_data += chunk
                    a = bytes_data.find(b"\xff\xd8")  # JPEG start
                    b = bytes_data.find(b"\xff\xd9")  # JPEG end

                    if a != -1 and b != -1:
                        jpg = bytes_data[a : b + 2]
                        bytes_data = bytes_data[b + 2 :]

                        if CV2_AVAILABLE:
                            # Convert to numpy array
                            img_np = np.frombuffer(jpg, dtype=np.uint8)
                            img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

                            if img is not None:
                                yield cv2.imencode(".jpg", img)[1].tobytes()
                        else:
                            # If OpenCV not available, yield raw JPEG
                            yield jpg

            elif self.camera_type in ["usb", "rtsp"]:
                # USB camera or RTSP stream (requires OpenCV)
                while self._running:
                    ret, frame = self.cap.read()
                    if not ret:
                        logging.warning(f"Failed to grab frame from {self.camera_type} camera")
                        break

                    yield cv2.imencode(".jpg", frame)[1].tobytes()

        except requests.exceptions.RequestException as e:
            logging.error(f"Error connecting to {self.camera_type} camera: {e}")
        except Exception as e:
            logging.error(f"Unexpected error in {self.camera_type} camera frames: {e}", exc_info=True)

    def stop(self):
        """
        Stops the camera streaming and releases resources.
        """
        super().stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None


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

    def __init__(self, ip_address, port=80):
        """
        Initializes the ESP32CamController with the specified IP address and port.

        Parameters:
        -----------
        ip_address : str
            The IP address of the ESP32-CAM.
        port : int
            The control port for the ESP32-CAM (default 80, stream is usually on 81).
        """
        self.base_url = f"http://{ip_address}:{port}/control"
        self.ip_address = ip_address
        self.port = port

    def apply_settings(self, settings):
        """
        Applies multiple settings (resolution, quality, brightness, contrast, saturation, and flip) to the ESP32-CAM.

        Parameters:
        -----------
        settings : dict
            A dictionary containing all camera settings to be applied.
        """
        if not isinstance(settings, dict):
            return

        resolution = settings.get("resolution")
        if resolution is not None:
            self.set_resolution(resolution)

        quality = settings.get("quality")
        if quality is not None:
            self.set_quality(quality)

        brightness = settings.get("brightness")
        if brightness is not None:
            self.set_brightness(brightness)

        contrast = settings.get("contrast")
        if contrast is not None:
            self.set_contrast(contrast)

        saturation = settings.get("saturation")
        if saturation is not None:
            self.set_saturation(saturation)

        flip = settings.get("flip")
        if flip is not None:
            self.set_flip(flip)

    def set_resolution(self, value):
        """
        Sets the resolution of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The resolution value to be set (0 to 13).
        """
        return self._send_request("framesize", value)

    def set_quality(self, value):
        """
        Sets the image quality of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The quality value to be set (0 to 63, where lower is higher quality).
        """
        return self._send_request("quality", value)

    def set_brightness(self, value):
        """
        Sets the brightness level of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The brightness value (-2 to 2).
        """
        return self._send_request("brightness", value)

    def set_contrast(self, value):
        """
        Sets the contrast level of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The contrast value (-2 to 2).
        """
        return self._send_request("contrast", value)

    def set_saturation(self, value):
        """
        Sets the saturation level of the ESP32-CAM.

        Parameters:
        -----------
        value : int
            The saturation value (-2 to 2).
        """
        return self._send_request("saturation", value)

    def set_flip(self, value):
        """
        Sets whether the image should be flipped horizontally.

        Parameters:
        -----------
        value : int
            0 for normal, 1 for flipped.
        """
        return self._send_request("flip", value)

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
        url = f"{self.base_url}?var={var}&val={val}"
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending camera control request to {self.base_url}: {e}")
            return False


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

                if camera_settings["camera_type"] == "esp32":
                    # Initialize ESP32 with the correct settings
                    self.camera_instance = CameraHandler(camera_type="esp32", ip_address=camera_settings["ip_address"])
                    settings_instance = ESP32CameraController(ip_address=camera_settings["ip_address"])
                    # Apply settings to the ESP32CamController
                    settings_instance.apply_settings(camera_settings)

                elif camera_settings["camera_type"] == "usb":
                    # USB camera initialization
                    self.camera_instance = CameraHandler(
                        camera_type="usb", usb_cam_index=camera_settings.get("usb_cam_index")
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

    def save_camera_settings(
        self,
        camera_type,
        ip_address=None,
        usb_cam_index=None,
        last_used=None,
        resolution=None,
        quality=None,
        brightness=None,
        contrast=None,
        saturation=None,
        flip=None,
    ):
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
            flip=flip,
        )
