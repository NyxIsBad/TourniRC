import gevent.monkey
gevent.monkey.patch_all()

import asyncio 
import asyncio_gevent 
asyncio.set_event_loop_policy(asyncio_gevent.EventLoopPolicy())

import multiprocessing
import signal
import sys
from irclib import Client
from cfg import userConfig
from irclog import *
import ui

# Initialize the logger
Log = create_logger('logs/irc.log', logging.DEBUG)

def signal_handler(sig, frame, ui_process):
    print('Shutting down...')
    ui_process.terminate()
    ui_process.join()
    sys.exit(0)

if __name__ == "__main__":
    """
    Launch UI in a separate process;
    basically we have the option of sending UI or IRC to a separate process
    We choose UI because IRC as currently written needs the MainThread event loop
    """
    ui_process = multiprocessing.Process(target=ui.prod_run)
    ui_process.start()

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, ui_process))

    try:
        # Load the user configuration
        config = userConfig()
        username = config.get_username()
        password = config.get_password()

        # TODO: check if username or pw are empty, if so set them in the website.

        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Navigate to http://localhost:5000 to access the client")
        me = Client(token=password, nickname=username, logger=Log)
        me.run()
    except KeyboardInterrupt:
        # Handle any cleanup if necessary
        signal_handler(signal.SIGINT, None, ui_process)

    logging.info('Main IRC Client Thread Exiting')
