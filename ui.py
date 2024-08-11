from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, send, close_room, rooms, disconnect
from cfg import uiConfig, THEMES

from typing import *

app = Flask(__name__)
socketio = SocketIO(app)
config = uiConfig()

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

@app.route('/send_message', methods=['POST'])
def send_message():
    data: Dict[str, Any] = request.get_json()
    message_content: str = data.get('message', None).strip()
    if message_content:
        print(f"Message sent: {message_content}")
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

@socketio.on('irc_msg')
def handle_irc_msg(data):
    print(f"Message received: {data}")
    emit('irc_msg', data, broadcast=True)

# ---------------------
# Starting webserver
# ---------------------
def debug_run():
    socketio.run(app, debug=True)

def prod_run():
    socketio.run(app, debug=False)

# ---------------------
# Used for debug since we will call from main normally
# ---------------------
if __name__ == "__main__":
    debug_run()