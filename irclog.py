import logging
import os

def create_logger(fname: str, level: int = logging.DEBUG) -> logging.Logger:
    # the readable log starts fresh on every run
    os.makedirs(os.path.dirname(fname) or '.', exist_ok=True)
    with open(fname, 'w'):
        pass
    Log = logging.getLogger("osu_irc")
    Log.setLevel(level)
    logfile = logging.FileHandler(fname, encoding='utf-8')
    logfile.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logfile.setFormatter(formatter)
    Log.addHandler(logfile)
    Log.propagate = False
    logging.info('Logger Initialized')
    return Log
