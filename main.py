import gevent.monkey
gevent.monkey.patch_all()

import asyncio 
import asyncio_gevent 
asyncio.set_event_loop_policy(asyncio_gevent.EventLoopPolicy())

import multiprocessing
import signal
import sys
from irclib import *
from cfg import userConfig
from irclog import *
import ui

# Initialize the logger
Log = create_logger('logs/irc.log')

def start_ui():
    ui.prod_run()

def signal_handler(sig, frame, ui_process):
    print('Shutting down...')
    ui_process.terminate()
    ui_process.join()
    sys.exit(0)

if __name__ == "__main__":
    # Launch UI in a separate process
    ui_process = multiprocessing.Process(target=start_ui)
    ui_process.start()

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, ui_process))

    try:
        # Load the user configuration
        config = userConfig()
        username = config.get_username().lower()
        password = config.get_password()

        # TODO: check if username or pw are empty, if so set them in the website.

        print(f"Username: {username}")
        print(f"Password: {type(password)}")
        print(f"Making client")
        me = Client(token=password, nickname=username, logger=Log)
        print(f"Starting client")
        me.run()
    except KeyboardInterrupt:
        # Handle any cleanup if necessary
        signal_handler(signal.SIGINT, None, ui_process)

    logging.info('Program Exited')
