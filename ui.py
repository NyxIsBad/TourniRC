from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from cfg import uiConfig, THEMES

from typing import *
import time
from datetime import datetime
import osu_irc

app = Flask(__name__)
socketio = SocketIO(app)
config = uiConfig()

# ---------------------
# Helper Functions
# ---------------------
def mtime(time: str) -> float:
    """
    Convert a time string in the format of HH:MM:SS to a timestamp compatible with time.time()
    """
    return datetime.strptime(time, "%H:%M:%S").replace(year=2024, month=1, day=1).timestamp()

def htime(time: str) -> float:
    """
    Convert a time string in the format of HH:MM:SS AM/PM to a timestamp compatible with time.time()
    """
    return datetime.strptime(time, "%I:%M:%S %p").replace(year=2024, month=1, day=1).timestamp()

def case_insensitive_get(d: Dict[str, Any], key: str) -> Any:
    """
    Get channel name from Chats dictionary in a case insensitive manner.
    """
    for k in d.keys():
        if k.lower() == key.lower():
            return k
    return None

def start_chat(channel_name: str, channel_type: int) -> None:
    """
    Start a chat with a channel name and type from the UI server's side.
    """
    emit('cmd_req_ch', {
        'channel': channel_name,
        'type': channel_type
    }, broadcast=True)

def close_chat(channel_name: str) -> None:
    """
    Close a chat with a channel name from the UI server's side.
    """
    emit('cmd_part', {
        'channel': channel_name
    }, broadcast=True)

def command_parse(command: str) -> None:
    """
    Parse a command string and execute it.
    Commands: query, part, clear, timer, matchtimer
    """
    parts = command.strip().split(" ")
    command = parts[0].lower()
    args = parts[1:]

    aliases = {
        "/q": "/query",
        "/chat": "/query",
        "/pm": "/query",
        "/join": "/query",
        "/leave": "/part",
        "/l": "/part",
        "/close": "/part",
        "/t": "/timer",
        "/mt": "/matchtimer"
    }

    command = aliases.get(command, command)

    if command == "/query":
        if len(args) == 0:
            print("Usage: /query <channel>")
            return
        start_chat(args[0], osu_irc.CHANNEL_TYPE_ROOM if args[0].startswith("#") else osu_irc.CHANNEL_TYPE_PM)
    elif command == "/part":
        if len(args) == 0:
            close_chat(chats.current_chat)
            return
        close_chat(args[0])
    elif command == "/clear":
        chats.get_chat(chats.current_chat).clear_messages()
        emit('cmd_clear', {}, broadcast=True)
    elif command == "/timer":
        if len(args) == 0:
            handle_send_msg({
                "content": f"!mp timer {chats.get_chat(chats.current_chat).timer}"
            })
            return
        handle_send_msg({
            "content": f"!mp timer {args[0]}"
        })
    elif command == "/matchtimer":
        if len(args) == 0:
            handle_send_msg({
                "content": f"!mp start {chats.get_chat(chats.current_chat).start_timer}"
            })
            return
        handle_send_msg({
            "content": f"!mp start {args[0]}"
        })
    else:
        print(f"Command {command} not found.")

# ---------------------
# Chat Classes
# ---------------------
class Chat():
    def __init__(self, channel_name: str, channel_type: int):
        """
        Class for a chat channel. Should only ever be created by the Chats class.
        """
        self.type = channel_type
        self.channel_name = channel_name
        self.messages: List[List] = []
        self.timer = 120 # default to 2 minutes
        self.start_timer = 5 # default to 5 seconds
        
    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Add a message to the chat channel.
        """
        if message['room_name'] == self.channel_name:
            self.messages.append([message['time_recv']*1000, message['user_name'], message['content']])
        else:
            raise ValueError(f"Message not in channel {self.channel_name}")
        
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} channel_name='{self.channel_name}' num_messages={len(self.messages)}>"

    def __str__(self) -> str:
        return f"Chat on channel {self.channel_name} with {len(self.messages)} messages."

    @property 
    def message_count(self) -> int:
        return len(self.messages)
    
    def clear_messages(self):
        self.messages.clear()

class Chats():
    def __init__(self):
        """
        Main class for handling chat messages. Should only ever be created once. Note that username is read directly from the cfg. file and not validated for case by the API.
        """
        self.username: str = None
        self.chats: Dict[str, Chat] = {}
        self.current_chat: str = None
        # Fetch username from osu_irc
        socketio.on('nickname', self.change_nickname)

    def change_nickname(self, data: Dict[str, Any]) -> None:
        """
        Pretty important function, since we start with not having a username. This is called when the user logs in.
        """
        print(f"User logged in: {data['nickname']}")
        self.username = data['nickname']
    
    def add_chat(self, channel_name: str, channel_type: int) -> None:
        """
        Add a chat channel to the chat list.
        Called when a message comes in that isn't in the chat list or when a new chat is opened (query/add/etc)
        """
        if case_insensitive_get(self.chats, channel_name):
            return
        self.chats[channel_name] = Chat(channel_name, channel_type)
        emit('bounce_tab_open', {
            'channel': channel_name
        }, broadcast=True)

    def remove_chat(self, channel_name: str) -> None:
        """
        Remove a chat channel from the chat list. Bounces the tab close event to the IRC client so it can PART
        """
        if channel_name in self.chats:
            self.chats.pop(channel_name)
            socketio.emit('bounce_tab_close', {
                'channel': channel_name
            })
        else:
            raise ValueError(f"Channel {channel_name} not found.")

    def get_chat(self, channel_name: str) -> Chat:
        """
        Get a chat channel from the chat list.
        """
        return self.chats.get(channel_name, None)
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Called when a message is received from the IRC client. Adds the message to the appropriate chat channel.
        Bounces it to the UI client if the chat is currently open.
        Also bounces the tab open event if the chat is not currently open.
        """
        if case_insensitive_get(self.chats, message['room_name']):
            message['room_name'] = case_insensitive_get(self.chats, message['room_name'])
        
        if message['room_name'] in self.chats:
            self.chats[message['room_name']].add_message(message)
        else:
            self.add_chat(message['room_name'], message['channel_type'])
            self.chats[message['room_name']].add_message(message)
        if self.current_chat == message['room_name']:
            emit('bounce_recv_msg', {
                'time': message["time_recv"]*1000, # convert to ms
                'user': message["user_name"],
                'content': message["content"]
            }, broadcast=True)
    
    def get_messages(self, channel_name: str) -> List[List]:
        return self.chats[channel_name].messages

    @property 
    def chat_count(self) -> int:
        return len(self.chats)
    
    @property 
    def message_count(self) -> int:
        return sum([chat.message_count for chat in self.chats.values()])
    
    @property 
    def channel_names(self) -> List[str]:
        return list(self.chats.keys())

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} num_chats={len(self.chats)}>"
    
    def __str__(self) -> str:
        return f"Chats with {len(self.chats)} channels."

chats = Chats()
# ---------------------
# Main Routes
# ---------------------
@app.route('/')
def chat():
    cur_theme = config.get_theme()
    return render_template('chat.html', cur_theme=cur_theme, themes=THEMES)

# ---------------------
# Layout SIO Routes
# ---------------------
@socketio.on('theme')
def set_theme(data: Dict[str, Any]):
    # default to dark theme
    theme: str = data.get('theme', 'dark')
    if theme in THEMES:
        config.set_theme(theme)
    else:
        raise ValueError(f"Theme {theme} not found.")

# ---------------------
# Chat SIO Routes
# ---------------------
@socketio.on('connect')
def handle_connect():
    # Broadcast chats
    for chat in chats.chats.values():
        emit('bounce_tab_open', {
            'channel': chat.channel_name
        })
    print('A Client connected')

@socketio.on('nickname')
def handle_nickname(data: Dict[str, Any]):
    chats.username = data['nickname']
    print(f"User logged in: {data['nickname']}")

@socketio.on('disconnect')
def handle_disconnect():
    print('A Client disconnected')

@socketio.on('tab_open')
def handle_tab_open(data: Dict[str, Any]):
    print(f"Channel join: {data['channel']}")
    chats.add_chat(data['channel'], data['type'])

@socketio.on('send_msg')
def handle_send_msg(data: Dict[str, Any]):
    # Failsafe, if we have left every chat, to prevent the buttons from sending messages if it's additionally not a slash command
    if (chats.current_chat is None or "") and (data["content"][0] != "/"):
        print("No current chat")
        return
    if data["content"][0] == "/":
        command_parse(data["content"])
        return
    # Failsafe, this case occurs actually not infrequently, eg. the buttons
    if "channel" not in data:
        data["channel"] = chats.current_chat
    emit('bounce_send_msg', {
        'content': data["content"].strip(),
        'channel': data["channel"],
        'type': chats.get_chat(data["channel"]).type
    }, broadcast=True)
    chats.add_message({
        'room_name': data["channel"],
        'time_recv': time.time(),
        'user_name': chats.username,
        'content': data["content"].strip()
    })

@socketio.on('recv_msg')
def handle_recv_msg(data: Dict[str, Any]):
    if data["channel_type"] == osu_irc.CHANNEL_TYPE_ROOM:
        data["room_name"] = f"#{data['room_name']}"
    if str(data["room_name"]).lower() == chats.username.lower():
        data["room_name"] = data["user_name"]
    chats.add_message(data)

@socketio.on('tab_swap')
def handle_tab_swap(data: Dict[str, Any]):
    chats.current_chat = data['channel']
    print(f"Current Chat: {chats.current_chat}")
    messages = chats.get_messages(data['channel'])
    emit('tab_swap_response', {'messages': messages})

@socketio.on('tab_close')
def handle_tab_close(data: Dict[str, Any]):
    if data['channel'] == '':
        chats.current_chat = None
        print(f"Current Chat: {chats.current_chat}")
        return
    chats.remove_chat(data['channel'])

# ---------------------
# Starting webserver
# ---------------------
def debug_run():
    # This is meant when the UI is being run standalone, so we need to make some fake chats
    # Adding chats is optional, since any non empty chat will automatically be added
    # However the fake mp is empty so we add it here
    chats.username = "HijiriS"
    chats.add_chat("#testchat1", osu_irc.CHANNEL_TYPE_ROOM)
    chats.add_chat("testpm1", osu_irc.CHANNEL_TYPE_PM)
    chats.add_chat("#mp_12345678", osu_irc.CHANNEL_TYPE_ROOM)
    chats.add_message({
        'room_name': "#testchat1",
        'time_recv': htime("12:00:01 PM"),
        'user_name': "HijiriS",
        'content': "Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message",
        'channel_type': osu_irc.CHANNEL_TYPE_ROOM
    })
    chats.add_message({
        'room_name': "#testchat1",
        'time_recv': mtime("18:00:02"),
        'user_name': "Test User",
        'content': "TourniRC Test Message",
        'channel_type': osu_irc.CHANNEL_TYPE_ROOM
    })
    chats.add_message({
        'room_name': "testpm1",
        'time_recv': htime("8:00:01 AM"),
        'user_name': "HijiriS",
        'content': "Test PM",
        'channel_type': osu_irc.CHANNEL_TYPE_PM
    })
    socketio.run(app, debug=True, host='localhost', port=5000)

def prod_run():
    socketio.run(app, debug=False, host='localhost', port=5000)

# ---------------------
# Used for debug since we will call all methods from main.py normally
# ---------------------
if __name__ == "__main__":
    debug_run()