import logging
import sys


def setup_logger(name: str = None) -> logging.Logger:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(name)-26s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        # Quiet the per-request/polling spam, keep their warnings
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger(name or __name__)
