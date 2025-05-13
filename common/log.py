import os
import logging
import colorama
import logzero
from logzero import setup_logger, LogFormatter
from .variable import LOG_FILE, DEBUG_MODE

if not os.path.exists("./logs"):
    os.makedirs("./logs")


def log(name: str) -> logging.Logger:
    """Set up a logger with console and file output."""
    level = logzero.DEBUG if DEBUG_MODE else logzero.INFO

    colors = {
        logzero.DEBUG: colorama.Fore.CYAN,
        logzero.INFO: colorama.Fore.GREEN,
        logzero.WARNING: colorama.Fore.YELLOW,
        logzero.ERROR: colorama.Fore.RED,
        logzero.CRITICAL: colorama.Fore.MAGENTA,
    }

    terminal_formatter = LogFormatter(
        color=True,
        fmt="%(color)s%(message)s%(end_color)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        colors=colors,
    )

    logger = setup_logger(name, level=level, formatter=terminal_formatter)

    if LOG_FILE:
        logfile = f"./logs/{name}.log"
        file_handler = logging.FileHandler(logfile)
        file_formatter = logging.Formatter(
            "[%(asctime)s] | [%(name)s:%(levelname)s] | [%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger