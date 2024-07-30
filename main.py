from irclib import *
from cfg import userConfig
from irclog import *
import ui

# Initialize the logger
Log = create_logger('logs/irc.log')

if __name__ == "__main__":
    # Load the user configuration
    config = userConfig()
    username = config.get_username().lower()
    password = config.get_password()

    # TODO: check if username or pw are empty, if so set them in the website.

    print(f"Username: {username}")
    print(f"Password: {type(password)}")
    
    me = Client(token=password, nickname=username, logger=Log)
    me.run()

logging.info('Program Exited')