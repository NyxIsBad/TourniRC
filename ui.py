from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, send, disconnect
from cfg import uiConfig, THEMES

from typing import *
import time
import osu_irc

app = Flask(__name__)
socketio = SocketIO(app)
config = uiConfig()

#---------------------
# Chat Classes
#---------------------
class Chat():
    def __init__(self, channel_name: str, channel_type: int):
        self.type = channel_type
        self.channel_name = channel_name
        self.messages: List[List] = []
        self.timer = 120 # default to 2 minutes
        self.start_timer = 5 # default to 5 seconds
        
    def add_message(self, message: Dict[str, Any]) -> None:
        if message['room_name'] == self.channel_name:
            self.messages.append([message['time_recv'], message['user_name'], message['content']])
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
        self.chats: Dict[str, Chat] = {}
    
    def add_chat(self, channel_name: str, channel_type: int) -> None:
        self.chats[channel_name] = Chat(channel_name, channel_type)

    def remove_chat(self, channel_name: str) -> None:
        if channel_name in self.chats:
            self.chats.pop(channel_name)
            socketio.emit('bounce_chat_removed', {
                'name': channel_name
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
    print(cur_theme)
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
    print('A Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('A Client disconnected')

@socketio.on('send_msg')
def handle_send_msg(data: Dict[str, Any]):
    # print(f"Message sent: {data.get('message', None).strip()}")
    emit('bounce_send_msg', {
        'content': data.get('message', None).strip()
    }, broadcast=True)

@socketio.on('recv_msg')
def handle_recv_msg(data: Dict[str, Any]):
    chats.add_message(data)
    emit('bounce_recv_msg', {
        'time': data["time_recv"]*1000, # convert to ms
        'user': data["user_name"],
        'content': data["content"]
    }, broadcast=True)

@socketio.on('tab_swap')
def handle_tab_swap(data: Dict[str, Any]):
    print(f"Tab swap: {data['tab']}")

# ---------------------
# Starting webserver
# ---------------------
def start():
    debug_run()

def debug_run():
    socketio.run(app, debug=True, host='localhost', port=5000)

def prod_run():
    socketio.run(app, debug=False, host='localhost', port=5000)

# ---------------------
# Used for debug since we will call from main normally
# ---------------------
if __name__ == "__main__":
    debug_run()