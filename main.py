from irclib import *
from cfg import userConfig

# Debug stuff
debug = True

def debug_print(message):
    if debug:
        print(message)

if __name__ == "__main__":
    config = userConfig()
    username = config.get_username().lower()
    password = config.get_password()

    # check if username or pw are empty, if so set them in the website.

    print(f"Username: {username}")
    print(f"Password: {type(password)}")
    
    me = Client(token=password, nickname=username)
    me.run()