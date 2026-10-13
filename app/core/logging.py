import logging
import sys
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        if hasattr(record, "node"):
            log_data["node"] = record.node
        return json.dumps(log_data)

def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[handler]
    )

def get_logger(name: str, trace_id: str = None):
    logger = logging.getLogger(name)
    if trace_id:
        old_log = logger.log
        def log_with_trace(level, msg, *args, **kwargs):
            extra = kwargs.get("extra", {})
            extra["trace_id"] = trace_id
            kwargs["extra"] = extra
            old_log(level, msg, *args, **kwargs)
        logger.log = log_with_trace
    return logger