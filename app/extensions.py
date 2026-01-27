"""Flask Extension Instances and Initialisation."""
import os
import logging

from flask import Flask
from flask_socketio import SocketIO


def _socketio_transports() -> list[str]:
    """Return allowed Engine.IO transports.

    Default to polling-only to avoid Werkzeug websocket upgrade crashes.
    Override with `SYSGROW_SOCKETIO_TRANSPORTS`, e.g. `polling,websocket`.
    """
    raw = os.getenv("SYSGROW_SOCKETIO_TRANSPORTS")
    if raw:
        transports = [t.strip() for t in raw.split(",") if t.strip()]
        if transports:
            return transports

    return ["polling"]


# Using threading mode for Windows compatibility
socketio = SocketIO(
    async_mode="threading",
    cors_allowed_origins=[],
    logger=True,
        # Keep Socket.IO logging enabled but avoid noisy Engine.IO INFO logs
        # (e.g. repeated "Invalid transport" from external clients/extensions).
        engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    transports=_socketio_transports(),
)


def init_extensions(app: Flask, cors_origins: str) -> None:
    """Initialise Flask extension objects."""
    origins = cors_origins if isinstance(cors_origins, str) else "*"
    
    try:
        # Ensure engineio logger does not emit INFO-level messages
        logging.getLogger('engineio').setLevel(logging.WARNING)
        logging.getLogger('socketio').setLevel(logging.INFO)

        socketio.init_app(
            app,
            cors_allowed_origins=origins,
            logger=logging.getLogger("socketio"),
            engineio_logger=False
        )
        logging.info(f"✅ Socket.IO initialized with CORS origins: {origins}")
    except Exception as e:
        logging.error(f"Failed to initialize Socket.IO: {e}", exc_info=True)
        raise
