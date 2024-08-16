from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, send, disconnect
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
    return datetime.strptime(time, "%H:%M:%S").replace(year=2024, month=1, day=1).timestamp()

def htime(time: str) -> float:
    return datetime.strptime(time, "%I:%M:%S %p").replace(year=2024, month=1, day=1).timestamp()

# ---------------------
# Chat Classes
# ---------------------
class Chat():
    def __init__(self, channel_name: str, channel_type: int):
        self.type = channel_type
        self.channel_name = channel_name
        self.messages: List[List] = []
        self.timer = 120 # default to 2 minutes
        self.start_timer = 5 # default to 5 seconds
        
    def add_message(self, message: Dict[str, Any]) -> None:
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
        self.username: str = None
        self.chats: Dict[str, Chat] = {}
        self.current_chat: str = None
        # Fetch username from osu_irc
        socketio.on('login', self.handle_login)

    def handle_login(self, data: Dict[str, Any]) -> None:
        self.username = data['nickname']
    
    def add_chat(self, channel_name: str, channel_type: int) -> None:
        self.chats[channel_name] = Chat(channel_name, channel_type)

    def remove_chat(self, channel_name: str) -> None:
        if channel_name in self.chats:
            self.chats.pop(channel_name)
            socketio.emit('bounce_tab_close', {
                'channel': channel_name
            })
        else:
            raise ValueError(f"Channel {channel_name} not found.")

    def get_chat(self, channel_name: str) -> Chat:
        return self.chats.get(channel_name, None)
    
    def add_message(self, message: Dict[str, Any]) -> None:
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
# API Routes
# ---------------------
@app.route('/set_theme', methods=['POST'])
def set_theme():
    data: Dict[str, Any] = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400
    # default to dark theme
    theme: str = data.get('theme', 'dark')
    if not theme:
        return jsonify(success=False, message="No theme received"), 400
    if theme in THEMES:
        config.set_theme(theme)
        return jsonify(success=True), 200
    return jsonify(success=False), 400

# ---------------------
# SocketIO Routes
# ---------------------
@socketio.on('connect')
def handle_connect():
    # Broadcast chats
    for chat in chats.chats.values():
        emit('bounce_tab_open', {
            'channel': chat.channel_name
        })
    print('A Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('A Client disconnected')

@socketio.on('tab_open')
def handle_tab_open(data: Dict[str, Any]):
    print(f"Channel join: {data['channel']}")
    chats.add_chat(data['channel'], data['type'])
    emit('bounce_tab_open', {
        'channel': data['channel']
    }, broadcast=True)

@socketio.on('send_msg')
def handle_send_msg(data: Dict[str, Any]):
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
    chats.add_message(data)

@socketio.on('tab_swap')
def handle_tab_swap(data: Dict[str, Any]):
    chats.current_chat = data['channel']
    messages = chats.get_messages(data['channel'])
    emit('tab_swap_response', {'messages': messages})

@socketio.on('tab_close')
def handle_tab_close(data: Dict[str, Any]):
    chats.remove_chat(data['tab'])

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
# Used for debug since we will call from main normally
# ---------------------
if __name__ == "__main__":
    debug_run()