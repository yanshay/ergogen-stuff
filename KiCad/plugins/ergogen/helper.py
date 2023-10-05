import logging
import pathlib

print(pathlib.Path(__file__).parent.resolve().parent.resolve())

def get_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    logger.handlers.clear()  # important within kiCad to avoid duplicate logs

    path = pathlib.Path(__file__).parent.resolve().joinpath('ergogen.log')
    
    fh = logging.FileHandler(path)  # goes to /Applications/KiCad/ergogen.log on Mac

    # fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)

    logger.addHandler(fh)

    return logger
