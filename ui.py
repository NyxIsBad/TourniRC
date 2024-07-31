from flask import Flask, render_template, request, redirect, url_for, jsonify
from waitress import serve
from cfg import uiConfig, THEMES

from typing import *

app = Flask(__name__)
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

# ---------------------
# Starting webserver
# ---------------------

def debug_run():
    app.run()

def prod_run():
    serve(app=app, host="0.0.0.0", port=5000)

# ---------------------
# Used for debug since we will call from main normally
# ---------------------
if __name__ == "__main__":
    debug_run()