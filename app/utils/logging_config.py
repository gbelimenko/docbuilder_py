import os
import logging
import queue

class QueueLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_queue = queue.Queue()

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put((msg, record.levelname))
        except Exception:
            self.handleError(record)

# Global instances
queue_log_handler = QueueLogHandler()

def setup_logging(logs_dir: str = "logs") -> str:
    """
    Configures application logging to log to a file and console,
    and registers the QtLogHandler for PySide6 GUI integration.
    """
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, exist_ok=True)
        
    log_file_path = os.path.join(logs_dir, "docbuilder_python.log")
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Queue Log Handler
    queue_log_handler.setFormatter(formatter)
    root_logger.addHandler(queue_log_handler)
    
    logging.info(f"Logging initialized. File: {log_file_path}")
    return log_file_path
