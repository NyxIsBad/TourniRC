import gevent.monkey
# socketio needs this before anything gets clever with threads
gevent.monkey.patch_all()

import sys
import asyncio
import asyncio_gevent
asyncio.set_event_loop_policy(asyncio_gevent.EventLoopPolicy())

import logging
import multiprocessing
import signal

from cfg import WEB_HOST, find_web_port, userConfig
from irclog import create_logger
from runtime_paths import data_dir, logs_dir

if "--build-test" in sys.argv:
    import requests
    import websocket
    raise SystemExit(0)

def stop_application(supervisor, ui_process):
    print('Shutting down...')
    if supervisor is not None:
        supervisor.shutdown()
    if ui_process.is_alive():
        ui_process.terminate()
    ui_process.join()


def register_console_close_handler(supervisor, ui_process):
    """
    kill child when we close the executable console
    """
    if sys.platform != 'win32':
        return None

    import ctypes

    handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

    @handler_type
    def on_console_close(control_type):
        # CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, and CTRL_SHUTDOWN_EVENT.
        if control_type in (2, 5, 6):
            stop_application(supervisor, ui_process)
        return False

    ctypes.windll.kernel32.SetConsoleCtrlHandler(on_console_close, True)
    return on_console_close  # Keep the callback alive for the process lifetime.


if __name__ == "__main__":
    """
    Launch UI in a separate process;
    basically we have the option of sending UI or IRC to a separate process
    We choose UI because IRC as currently written needs the MainThread event loop
    """
    multiprocessing.freeze_support()
    import ui
    from irclib import IrcSessionSupervisor

    # irc owns the main process; flask gets the spare one
    web_port = find_web_port()
    ui_process = multiprocessing.Process(target=ui.prod_run, args=(web_port,))
    ui_process.daemon = True
    log = create_logger(str(logs_dir() / 'irc.log'), logging.DEBUG)
    ui_process.start()

    supervisor = IrcSessionSupervisor(
        log,
        server_url=f'http://{WEB_HOST}:{web_port}',
        ui_is_alive=ui_process.is_alive,
        ui_exitcode=lambda: ui_process.exitcode,
    )
    config = userConfig(str(data_dir() / 'login.ini'))
    supervisor.submit_credentials(config.get_username(), config.get_password())

    signal.signal(signal.SIGINT, lambda *_: supervisor.shutdown())
    signal.signal(signal.SIGTERM, lambda *_: supervisor.shutdown())
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, lambda *_: supervisor.shutdown())
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, lambda *_: supervisor.shutdown())
    console_close_handler = register_console_close_handler(supervisor, ui_process)
    print(f"Navigate to http://{WEB_HOST}:{web_port} to access the client")

    try:
        supervisor.run()
    except KeyboardInterrupt:
        pass
    finally:
        stop_application(supervisor, ui_process)
        logging.info('Main IRC Client Thread Exiting')
