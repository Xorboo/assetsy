import logging
import re
import sys
import traceback

# chromedriver appends its own C++ frames to the exception message; they carry no useful information
_CHROME_FRAME = re.compile(r"^[\s|+]*(Stacktrace:\s*$|#\d+ 0x[0-9a-f]+)")


def strip_chrome_frames(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _CHROME_FRAME.match(line))


def format_exception(exception: BaseException) -> str:
    return strip_chrome_frames("".join(traceback.format_exception(type(exception), exception, exception.__traceback__)))


class _Formatter(logging.Formatter):
    def formatException(self, exc_info) -> str:
        return strip_chrome_frames(super().formatException(exc_info))


def setup_logger(name: str = None) -> logging.Logger:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_Formatter(fmt="%(asctime)s | %(name)-26s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        # Quiet the per-request/polling spam, keep their warnings
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger(name or __name__)
