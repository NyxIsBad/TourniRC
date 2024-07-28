from irclib import *
from auth import configObj

# Debug stuff
debug = True

def debug_print(message):
    if debug:
        print(message)

if __name__ == "__main__":
    config = configObj()
    username = config.get_username().lower()
    password = config.get_password()

    # check if username or pw are empty, if so set them in the website.

    print(f"Username: {username}")
    print(f"Password: {type(password)}")
    
    me = Client(token=password, nickname=username)
    me.run()