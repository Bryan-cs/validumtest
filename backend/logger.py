"""Logger centralizado — stdout para que Railway capture los logs automáticamente."""
import logging
import sys

_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logger = logging.getLogger("bbcfile")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
