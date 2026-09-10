import logging
from logging.handlers import RotatingFileHandler
from PySide6.QtCore import QObject, Signal
from pathlib import Path
import traceback
import re, sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT_STR = str(PROJECT_ROOT).replace("\\", "/")

def clean_traceback(text: str) -> str:
    text = text.replace("\\", "/")
    return re.sub(re.escape(PROJECT_ROOT_STR), "<root>", text, flags=re.IGNORECASE)

def format_exc_clean():
    return clean_traceback("".join(traceback.format_exception(*sys.exc_info())))

class CleanFormatter(logging.Formatter):
    def formatException(self, exc_info):
        tb = "".join(traceback.format_exception(*exc_info))
        return clean_traceback(tb)
    
formatter = CleanFormatter("%(name)s: %(message)s")
file_formatter = CleanFormatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback))
    
class LogEmitter(QObject):
    message = Signal(object)

class QtLogHandler(logging.Handler):
    def __init__(self, signal: Signal, emitter: LogEmitter):
        super().__init__()
        self.emitter = emitter
        self.signal = signal

    def emit(self, record):
        self.emitter.message.emit(record)

def addQtHandler(logger, signal, emitter):
    handler = QtLogHandler(signal, emitter)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def setuplog():
    logger = logging.getLogger()

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    
    # log file
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file = RotatingFileHandler(log_dir/"DSTS.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(file_formatter)
    logger.addHandler(file)

    return logger
