import logging
import os


def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.WARN)

    logger.handlers.clear()  # important within kiCad to avoid duplicate logs

    home_directory = os.path.expanduser('~')
    path = os.path.join(home_directory, 'Documents', 'KiCad', '7.0', 'scripting', 'plugins', 'ergogen.log')
    fh = logging.FileHandler(path)  # goes to /Applications/KiCad/ergogen.log on Mac

    # fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    logger.addHandler(fh)

    return logger
