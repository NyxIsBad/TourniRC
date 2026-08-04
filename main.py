import gevent.monkey
# socketio needs this before anything gets clever with threads
gevent.monkey.patch_all()

import asyncio
import asyncio_gevent
asyncio.set_event_loop_policy(asyncio_gevent.EventLoopPolicy())

import logging
import multiprocessing
import signal

from cfg import userConfig
from irclib import IrcSessionSupervisor
from irclog import create_logger
import ui


Log = create_logger('logs/irc.log', logging.DEBUG)

# signal handler was too rough
def stop_application(supervisor, ui_process):
    print('Shutting down...')
    supervisor.shutdown()
    if ui_process.is_alive():
        ui_process.terminate()
    ui_process.join()


if __name__ == "__main__":
    """
    Launch UI in a separate process;
    basically we have the option of sending UI or IRC to a separate process
    We choose UI because IRC as currently written needs the MainThread event loop
    """
    multiprocessing.freeze_support()
    # irc owns the main process; flask gets the spare one
    ui_process = multiprocessing.Process(target=ui.prod_run)
    ui_process.start()

    supervisor = IrcSessionSupervisor(Log)
    config = userConfig()
    supervisor.submit_credentials(config.get_username(), config.get_password())

    signal.signal(signal.SIGINT, lambda *_: stop_application(supervisor, ui_process))
    print("Navigate to http://localhost:5000 to access the client")

    try:
        supervisor.run()
    except KeyboardInterrupt:
        pass
    finally:
        stop_application(supervisor, ui_process)
        logging.info('Main IRC Client Thread Exiting')
