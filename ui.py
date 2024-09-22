from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from cfg import *

import json
from typing import *
import time
from datetime import datetime
import osu_irc
import re

app = Flask(__name__)
socketio = SocketIO(app)
ui_cfg = uiConfig()
rms_cfg = roomsConfig()

TEAM_RED = 1
TEAM_BLUE = 2
TEAM_NONE = 0

NOTIF_TYPE_INFO = 'info'
NOTIF_TYPE_WARNING = 'warning'
NOTIF_TYPE_ERROR = 'error'
NOTIF_TYPE_SUCCESS = 'success'
NOTIF_TYPE_DEFAULT = ''

team_map = {
    'red': TEAM_RED,
    'blue': TEAM_BLUE,
    'none': TEAM_NONE
}

# TODO: Implement cfg for this and settings
debug_block_list = [
    "BLOCKED_USER_DEBUG"
]
debug_block_list = [name.lower() for name in debug_block_list]

debug = False

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

def create_notif(content: str, duration: int = 5000, notif_type: str = NOTIF_TYPE_DEFAULT) -> None:
    """
    Create a notification with content and duration in ms.
    """
    emit('notif', {
        "content": content,
        "duration": duration,
        "type": notif_type
    })

def start_chat(channel_name: str, channel_type: int) -> None:
    """
    Start a chat with a channel name and type from the UI server's side.
    """
    create_notif(f"Opening chat {channel_name}...", 500, notif_type=NOTIF_TYPE_INFO)
    emit('cmd_req_ch', {
        'channel': channel_name,
        'type': channel_type
    }, broadcast=True)

def close_chat(channel_name: str) -> None:
    """
    Close a chat with a channel name from the UI server's side.
    """
    create_notif(f"Closing chat {channel_name}...", 500, notif_type=NOTIF_TYPE_INFO)
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
        "/pm": "/query",
        "/chat": "/query",
        "/join": "/query",
        "/l": "/part",
        "/leave": "/part",
        "/close": "/part",
        "/t": "/timer",
        "/mt": "/matchtimer",
        "/s": "/savelog"
    }

    command = aliases.get(command, command)

    if command == "/query":
        if len(args) == 0:
            create_notif("Usage: /query <channel>", notif_type=NOTIF_TYPE_WARNING)
        else:
            start_chat(args[0], osu_irc.CHANNEL_TYPE_ROOM if args[0].startswith("#") else osu_irc.CHANNEL_TYPE_PM)
    elif command == "/part":
        close_chat(chats.current_chat) if len(args) == 0 else close_chat(args[0])
    elif command == "/clear":
        chats.get_current_chat.clear_messages()
        emit('cmd_clear', {}, broadcast=True)
    elif command == "/timer":
        if len(args) == 0:
            handle_send_msg({
                "content": f"!mp timer {chats.get_current_chat.timer}"
            })
        else:
            handle_send_msg({
                "content": f"!mp timer {args[0]}"
            })
            chats.get_current_chat.set_timer(args[0])
            emit('set_timer_input', {
                'timer': args[0]
            })
    elif command == "/matchtimer":
        if len(args) == 0:
            handle_send_msg({
                "content": f"!mp start {chats.get_current_chat.match_timer}"
            })
        else:
            chats.get_current_chat.set_match_timer(args[0])
            emit('set_match_timer_input', {
                'timer': args[0]
            })
            # TODO: match timer logic here
            handle_send_msg({
                "content": f"!mp start {args[0]}"
            })
    elif command == "/savelog":
        if len(args) == 0:
            emit('cmd_savelog_response', {
                'messages': chats.get_messages(chats.get_current_chat.channel_name),
                'channel': chats.get_current_chat.channel_name
            })
        else:
            ch_insensitive = case_insensitive_get(chats.chats, args[0])
            if ch_insensitive:
                args[0] = ch_insensitive
            else:
                create_notif(f"Channel {args[0]} not found.", notif_type=NOTIF_TYPE_ERROR)
                return
            emit('cmd_savelog_response', {
                'messages': chats.get_messages(args[0]),
                'channel': args[0]
            })
    else:
        create_notif(f"Command {command} not found.", notif_type=NOTIF_TYPE_WARNING)

# ---------------------
# Chat Classes
# ---------------------
class Chat():
    def __init__(self, channel_name: str, channel_type: int, **kwargs):
        """
        Class for a chat channel. Should only ever be created by the Chats class.
        """

        self.type = channel_type
        self.channel_name = channel_name
        self.alias = self.channel_name
        self.messages: List[List] = []
        # TODO: implement this or delete it depending on feedback
        # 1 = red, 2 = blue, 0 = none
        self.teams: Dict[str, int] = {}
        self.timer = kwargs['timer'] if 'timer' in kwargs else 120
        self.match_timer = kwargs['match_timer'] if 'match_timer' in kwargs else 5
        
    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Add a message to the chat channel.
        """
        # Regex for team changes here (must be issued by BanchoBot)
        if message['room_name'] == self.channel_name:
            self.messages.append([message['time_recv']*1000, message['user_name'], message['content']])
        else:
            create_notif(f"Something has gone terribly wrong, code MSG-001", notif_type=NOTIF_TYPE_ERROR)
            raise ValueError(f"Message not in channel {self.channel_name}")
        
    # TODO: Implement this or delete it depending on feedback
    def team_change(self, user: str, team: int) -> None:
        """
        Change a user's team in the chat channel.
        """
        # Should only be 0, 1, 2
        self.teams[user] = team
        emit('team_change', {
            'username': user,
            'team': team,
            'channel': self.channel_name
        }, broadcast=True)

    def set_timer(self, timer: int) -> None:
        """
        Set the timer for the chat channel.
        """
        self.timer = timer

    def set_match_timer(self, match_timer: int) -> None:
        """
        Set the start timer for the chat channel.
        """
        self.match_timer = match_timer

    def set_alias(self, alias: str) -> None:
        """
        Set the alias for the chat channel.
        """
        self.alias = alias

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
    
    def add_chat(self, channel_name: str, channel_type: int, **kwargs) -> None:
        """
        Add a chat channel to the chat list.
        Called when a message comes in that isn't in the chat list or when a new chat is opened (query/add/etc)
        """
        if case_insensitive_get(self.chats, channel_name):
            return
        self.chats[channel_name] = Chat(channel_name, channel_type, **kwargs)

        # We only need to do this here because all other methods of opening a channel result 
        # in a bounce to here anyway
        rms_cfg.add_room(channel_name)
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
            if self.chat_count == 0:
                self.current_chat = None
        else:
            create_notif(f"Something has gone terribly wrong, code CHN-001", notif_type=NOTIF_TYPE_ERROR)
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
        
        if message['room_name'] not in self.chats:
            self.add_chat(message['room_name'], message['channel_type'])
        self.chats[message['room_name']].add_message(message)

        if self.current_chat == message['room_name']:
            emit('bounce_recv_msg', {
                'time': message["time_recv"]*1000, # convert to ms
                'user': message["user_name"],
                'content': message["content"],
                'team': self.chats[message['room_name']].teams.get(message["user_name"], TEAM_NONE)
            }, broadcast=True)
        else:
            # TODO: unread indicator
            # This should be conditional and only sent once based on the unread flag.
            create_notif(f"New message in {message['room_name']}", notif_type=NOTIF_TYPE_INFO)

    def set_current_chat(self, channel_name: str) -> None:
        """
        Set the current chat channel.
        """
        self.current_chat = channel_name
    
    def get_messages(self, channel_name: str) -> List[List]:
        return self.chats[channel_name].messages

    @property
    def get_current_chat(self) -> Chat:
        """
        Get the current chat channel from the chat list.
        """
        return self.chats.get(self.current_chat, None)

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
    cur_theme = ui_cfg.get_theme()
    # TODO: conditionall reroute to login if not logged in
    return render_template('chat.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/login')
def login():
    cur_theme = ui_cfg.get_theme()
    return render_template('login.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/settings')
def settings():
    cur_theme = ui_cfg.get_theme()
    return render_template('settings.html', cur_theme=cur_theme, themes=THEMES)

# ---------------------
# Layout SIO Routes
# ---------------------
@socketio.on('theme')
def set_theme(data: Dict[str, Any]):
    # default to dark theme
    theme: str = data.get('theme', 'dark')
    if theme in THEMES:
        ui_cfg.set_theme(theme)
    else:
        # I'd be shocked if this ever happens; it means the user edited some code and didn't know what they were doing
        raise ValueError(f"Theme {theme} not found.")

# ---------------------
# Chat SIO Routes
# ---------------------
@socketio.on('connect')
def handle_connect():
    # For the sake of simplicity we won't have
    # any ident procedures
    for chat in chats.chats.values():
        emit('bounce_tab_open', {
            'channel': chat.channel_name
        })
    if debug:
        debug_connect()

@socketio.on('nickname')
def handle_nickname(data: Dict[str, Any]):
    chats.username = data['nickname']

@socketio.on('disconnect')
def handle_disconnect():
    print('A Client disconnected')

@socketio.on('tab_open')
def handle_tab_open(data: Dict[str, Any]):
    chats.add_chat(data['channel'], data['type'])

@socketio.on('send_msg')
def handle_send_msg(data: Dict[str, Any]):
    # Prevent sending attempting to send messages to a nonexistent chat unless
    # It's a slash command because /q is a thing
    if (chats.current_chat is None or "") and (data["content"][0] != "/"):
        return
    # Prevent a message send if the chat is not created yet
    if data["channel"] not in chats.chats:
        create_notif(f"Chat {data['channel']} not found.", notif_type=NOTIF_TYPE_ERROR)
    # Slash commands
    if data["content"][0] == "/":
        command_parse(data["content"])
        return
    # Failsafe, this case occurs actually not infrequently, eg. the buttons
    if "channel" not in data:
        data["channel"] = chats.current_chat
    emit('bounce_send_msg', {
        'content': data["content"],
        'channel': data["channel"],
        'type': chats.get_chat(data["channel"]).type
    }, broadcast=True)
    chats.add_message({
        'room_name': data["channel"],
        'time_recv': time.time(),
        'user_name': chats.username,
        'content': data["content"]
    })

@socketio.on('recv_msg')
def handle_recv_msg(data: Dict[str, Any]):
    if data["user_name"].lower() in debug_block_list:
        return
    if data["channel_type"] == osu_irc.CHANNEL_TYPE_ROOM:
        data["room_name"] = f"#{data['room_name']}"
    if str(data["room_name"]).lower() == chats.username.lower():
        data["room_name"] = data["user_name"]
    chats.add_message(data)
    # TODO: implement blocking, sound alerts, any required regex here
    
    if data["user_name"].lower() == "banchobot":
        create = osu_irc.ReCreateMatch.match(data["content"])
        if create:
            start_chat(f"#mp_{create.group(1)}", osu_irc.CHANNEL_TYPE_ROOM)
            return
        # TODO: detect a tournament acronym here
        slot = osu_irc.ReSlot.match(data["content"])
        if slot:
            username = slot.group(1).strip().replace(" ", "_")
            team = team_map.get(slot.group(2).strip().lower(), TEAM_NONE)
            chats.get_chat(data['room_name']).team_change(username, team)
            return
        join = osu_irc.ReJoinSlot.match(data["content"])
        if join:
            username = join.group(1).strip().replace(" ", "_")
            team = team_map.get(join.group(2).strip().lower(), TEAM_NONE)
            chats.get_chat(data['room_name']).team_change(username, team)
            return 
        change = osu_irc.ReChangeTeam.match(data["content"])
        if change:
            username = change.group(1).strip().strip().replace(" ", "_")
            team = team_map.get(change.group(2).strip().lower(), TEAM_NONE)
            chats.get_chat(data['room_name']).team_change(username, team)
            return

@socketio.on('tab_swap')
def handle_tab_swap(data: Dict[str, Any]):
    chats.set_current_chat(data['channel'])
    messages = chats.get_messages(data['channel'])
    emit('tab_swap_response', {
        'alias': chats.get_chat(data['channel']).alias,
        'messages': messages,
        'timer': chats.get_chat(data['channel']).timer,
        'match_timer': chats.get_chat(data['channel']).match_timer,
        'teams': json.dumps(chats.get_chat(data['channel']).teams),
        'recent_rooms': rms_cfg.rooms
    })

@socketio.on('tab_close')
def handle_tab_close(data: Dict[str, Any]):
    chats.remove_chat(data['channel'])

@socketio.on('set_timer')
def handle_set_timer(data: Dict[str, Any]):
    chats.get_current_chat.set_timer(data['timer'])

@socketio.on('set_match_timer')
def handle_set_match_timer(data: Dict[str, Any]):
    chats.get_current_chat.set_match_timer(data['timer'])

@socketio.on('change_alias')
def change_alias(data: Dict[str, Any]):
    chats.get_chat(data['channel']).set_alias(data['alias'])

@socketio.on('debug')
def debug(data: Dict[str, Any]):
    print(data)
    print(rms_cfg)
# ---------------------
# Starting webserver
# ---------------------
def debug_run():
    # This is meant when the UI is being run standalone, so we need to make some fake chats
    # Adding chats is optional, since any non empty chat will automatically be added
    # However the fake mp is empty so we add it here
    global debug
    debug = True
    socketio.run(app, debug=True, host='localhost', port=5000)

def debug_connect():
    global debug
    # Careful to only run this once
    debug = False
    chats.username = "HijiriS"
    chats.add_chat("#testchat1", osu_irc.CHANNEL_TYPE_ROOM, timer=120, match_timer=5)
    chats.add_chat("testpm1", osu_irc.CHANNEL_TYPE_PM)
    chats.add_chat("#mp_12345678", osu_irc.CHANNEL_TYPE_ROOM, timer=90, match_timer=10)
    chats.add_message({
        'room_name': "#testchat1",
        'time_recv': htime("12:00:01 PM"),
        'user_name': "HijiriS",
        'content': "Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message Test Message",
        'channel_type': osu_irc.CHANNEL_TYPE_ROOM
    })
    chats.add_message({
        'room_name': "#testchat1",
        'time_recv': htime("12:00:01 PM"),
        'user_name': "HijiriS",
        'content': "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
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
    chats.add_message({
        'room_name': "#mp_12345678",
        'time_recv': htime("8:00:01 AM"),
        'user_name': "HijiriS",
        'content': "Test Message for Teams",
        'channel_type': osu_irc.CHANNEL_TYPE_ROOM
    })
    chats.add_message({
        'room_name': "#mp_12345678",
        'time_recv': htime("8:00:01 AM"),
        'user_name': "Pof",
        'content': "Test Message for Teams",
        'channel_type': osu_irc.CHANNEL_TYPE_ROOM
    })
    chats.get_chat("#mp_12345678").team_change("HijiriS", TEAM_RED)
    chats.get_chat("#mp_12345678").team_change("Pof", TEAM_BLUE)

def prod_run():
    socketio.run(app, debug=False, host='localhost', port=5000)

# ---------------------
# Used for debug since we will call all methods from main.py normally
# ---------------------
if __name__ == "__main__":
    print(f"http://localhost:5000")
    debug_run()