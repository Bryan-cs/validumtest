"""Logger centralizado — stdout en formato JSON para Railway dashboard."""
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.INFO)
_handler.setFormatter(JsonFormatter())

logger = logging.getLogger("bbcfile")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
