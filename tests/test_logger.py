from utils.logger import format_exception

CHROME_MESSAGE = """Message: no such element: Unable to locate element: {"method":"tag name","selector":"h2"}
  (Session info: chrome=149.0.7827.155); For documentation on this error, please visit: https://www.selenium.dev/
Stacktrace:
#0 0x55b8aa1c63da <unknown>
#18 0x7d9498d1fa64 __clone"""


def test_format_exception_drops_chrome_frames_keeps_python_ones():
    try:
        raise ValueError(CHROME_MESSAGE)
    except ValueError as e:
        text = format_exception(e)

    assert "<unknown>" not in text
    assert "__clone" not in text
    assert "Stacktrace:" not in text
    assert 'selector":"h2"' in text
    assert "test_logger.py" in text


def test_format_exception_keeps_chrome_frames_of_grouped_errors_out():
    try:
        raise ExceptionGroup("Some scrapers failed", [ValueError(CHROME_MESSAGE)])
    except ExceptionGroup as e:
        text = format_exception(e)

    assert "<unknown>" not in text
    assert "Some scrapers failed" in text
    assert 'selector":"h2"' in text
