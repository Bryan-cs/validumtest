"""Logger centralizado con rotación de archivos."""
import logging
from logging.handlers import RotatingFileHandler
import os

_log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_log_dir, exist_ok=True)

_handler = RotatingFileHandler(
    os.path.join(_log_dir, "app.log"),
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8",
    delay=True,
)
_handler.setLevel(logging.WARNING)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logger = logging.getLogger("bbcfile")
logger.setLevel(logging.WARNING)
logger.addHandler(_handler)
