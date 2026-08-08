"""
I know this is called ui.py, but it's really kind of like, the entire client.

It just kind of ballooned and now I don't want to refactor it. Hit me up with a PR if you do this
"""
from flask import Flask, render_template, redirect, url_for, request, send_file, jsonify
from flask_socketio import SocketIO, emit
from cfg import THEMES, roomsConfig, userConfig
from settings import SettingsRepository, SettingsError, normalize_username
from sounds import SoundStore, available_assets, matching_sounds
from tournaments import MODS, TournamentAssignments, TournamentError, TournamentRepository, fetch_beatmap_metadata, parse_mappool_text, validate_tournament

import json
import os
import re
from pathlib import Path
from typing import *
import time
import uuid

import osu_irc
from utils import *
from eventlog import EventLog
from match_parser import parse_match_message
from runtime_paths import data_dir, logs_dir, resource_root

# globals
RESOURCE_DIR = resource_root()
app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / 'templates'),
    static_folder=str(RESOURCE_DIR / 'static')
)
socketio = SocketIO(app)
DATA_DIR = data_dir()
settings_cfg = SettingsRepository(DATA_DIR / 'settings.json')
rms_cfg = roomsConfig(str(DATA_DIR / 'recentrooms.ini'), max_rooms=settings_cfg.data['chat']['room_history_limit'])
rms_cfg.set_max_rooms(settings_cfg.data['chat']['room_history_limit'])
user_cfg = userConfig(str(DATA_DIR / 'login.ini'))
sound_store = SoundStore(DATA_DIR / 'sounds')
tournament_cfg = TournamentRepository(DATA_DIR / 'tournaments')
tournament_assignments = TournamentAssignments()

# lots of states
IRC_STATE_CONNECTING = 'connecting'
IRC_STATE_AUTHENTICATED = 'authenticated'
IRC_STATE_RECONNECTING = 'reconnecting'
IRC_STATE_AUTH_FAILED = 'authentication_failed'
IRC_STATE_LOGGED_OUT = 'logged_out'

connection_state = {
    'state': IRC_STATE_CONNECTING if user_cfg.has_credentials() else IRC_STATE_LOGGED_OUT,
    'attempt': 0,
    'retry_in': 0
}
backend_instance_id = str(uuid.uuid4())
pending_credentials = None
UI_EVENTS = EventLog('ui', str(logs_dir() / 'ui-events.log'))


def log_socket_event(name: str, data: Any = None) -> None:
    UI_EVENTS.write('socket_event', name=name, data=data)


def valid_payload(name: str, data: Any, required: Dict[str, Any]) -> bool:
    # ignore bad socket data instead of killing the handler
    if not isinstance(data, dict) or any(
        key not in data or not isinstance(data[key], expected_type)
        for key, expected_type in required.items()
    ):
        UI_EVENTS.write('invalid_socket_payload', name=name, data=data)
        return False
    return True

def emit_recent_rooms() -> None:
    emit('recent_rooms_state', {
        'rooms': rms_cfg.rooms,
        'max_rooms': rms_cfg.max_rooms
    }, broadcast=True)

def emit_match_state(chat) -> None:
    payload = {
        'channel': chat.channel_name,
        'info': chat.channel_info(),
        'teams': chat.teams,
        'players': chat.players
    }
    if 'tournament_cfg' in globals():
        payload['tournament'] = tournament_overlay(chat.channel_name)
    emit('match_state', payload, broadcast=True)

def emit_tournament_match_states(tournament_id: Optional[str] = None) -> None:
    for chat in chats.chats.values():
        assignment = tournament_assignments.get(chat.channel_name)
        if assignment['tournament_id'] and (
            tournament_id is None or assignment['tournament_id'] == tournament_id
        ):
            emit_match_state(chat)

def settings_payload() -> Dict[str, Any]:
    payload = settings_cfg.snapshot()
    payload['audio']['available_assets'] = available_assets(payload)
    return payload

def settings_result(ok=True, data=None, errors=None) -> Dict[str, Any]:
    return {'ok': ok, 'data': data, 'errors': errors or []}

def tournament_result(ok=True, data=None, errors=None) -> Dict[str, Any]:
    return {'ok': ok, 'data': data, 'errors': errors or []}

def tournament_state() -> Dict[str, Any]:
    in_use = {item['id']: tournament_assignments.channels_for(item['id']) for item in tournament_cfg.items.values()}
    return {
        'enabled': tournament_cfg.enabled, 'tournaments': tournament_cfg.list(),
        'in_use': in_use, 'mods': MODS,
        'sound_assets': available_assets(settings_cfg.snapshot())
    }

def score_mods(value):
    # this might become obsolete later. we'll see
    if isinstance(value, list):
        selected = [str(mod).upper() for mod in value if str(mod).upper() in MODS]
        return ['NM'] if 'NM' in selected or not selected else selected
    compact = re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()
    if compact in {'', 'NM', 'NOMOD', 'FREEMOD', 'NONE'}:
        return ['NM']
    result = []
    while compact:
        mod = next((code for code in sorted(MODS, key=len, reverse=True) if compact.startswith(code)), None)
        if not mod:
            break
        result.append(mod)
        compact = compact[len(mod):]
    return result

def tournament_overlay(channel: str) -> Dict[str, Any]:
    assignment = tournament_assignments.get(channel)
    # match updates only need the assignment and calculated score. full
    # tournament configuration is sent by tournament_state when it changes.
    tournament = tournament_cfg.items.get(assignment['tournament_id'])
    score = None
    chat = chats.get_chat(channel) if 'chats' in globals() else None
    config = tournament.get('score_calculation', {}) if tournament else {}
    if chat and config.get('enabled'):
        totals = {'red': 0.0, 'blue': 0.0}
        rows = []
        multipliers = {str(key).upper(): float(value) for key, value in config.get('mod_multipliers', {}).items()}
        for username, player in chat.players.items():
            if player.get('score') is None or player.get('team') not in {TEAM_RED, TEAM_BLUE}:
                continue
            mods = str(player.get('mods') or 'NoMod')
            applied_mods = score_mods(chat.score_mod_overrides.get(username, player.get('score_mods', mods)))
            multiplier = 1.0
            for mod in applied_mods:
                multiplier *= multipliers.get(mod, 1.0)
            adjusted = player['score'] * multiplier
            team = 'red' if player['team'] == TEAM_RED else 'blue'
            totals[team] += adjusted
            rows.append({'username': username, 'team': team, 'score': player['score'], 'mods': mods, 'applied_mods': applied_mods, 'multiplier': multiplier, 'adjusted': adjusted})
        winner = 'red' if totals['red'] > totals['blue'] else 'blue' if totals['blue'] > totals['red'] else 'tie'
        score = {'totals': totals, 'players': rows, 'winner': winner}
    return {
        'enabled': tournament_cfg.enabled, 'assignment': assignment,
        'score': score
    }

# more globals wrt. actual ui
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

blocked_pm_notices = {}
map_pick_locks = {}

debug_flag = False

# ---------------------
# Helper Functions
# ---------------------
def create_notif(content: str, duration: int = 5000, notif_type: str = NOTIF_TYPE_DEFAULT) -> None:
    """
    Create a notification with content and duration in ms.
    """
    payload = {
        "content": content,
        "duration": duration,
        "type": notif_type
    }
    UI_EVENTS.write('notification', data=payload)
    emit('notif', payload)

def start_chat(channel_name: str, channel_type: int) -> None:
    """
    Start a chat with a channel name and type from the UI server's side.
    """
    existing_channel = chats.resolve_channel(channel_name)
    if existing_channel:
        emit('restore_tab', {'channel': existing_channel}, broadcast=True)
        return
    create_notif(f"Opening chat {channel_name}...", 5000, notif_type=NOTIF_TYPE_INFO)
    emit('cmd_req_ch', {
        'channel': channel_name,
        'type': channel_type
    }, broadcast=True)

def close_chat(channel_name: str) -> None:
    """
    Close a chat with a channel name from the UI server's side.
    """
    create_notif(f"Closing chat {channel_name}...", 5000, notif_type=NOTIF_TYPE_INFO)
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

    alias_type, alias_value = settings_cfg.resolve_alias(command)
    if alias_type == 'command':
        command = alias_value
    elif alias_type == 'macro':
        if alias_value['confirm']:
            emit('macro_confirmation', alias_value)
            return
        handle_send_msg({'content': alias_value['command']})
        return
    if command != "/query" and chats.current_chat is None:
        create_notif("No chat open.", notif_type=NOTIF_TYPE_WARNING)
        return
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
                "content": f"!mp start {chats.get_current_chat.start_timer}"
            })
        else:
            chats.get_current_chat.set_start_timer(args[0])
            emit('set_start_timer_input', {
                'timer': args[0]
            })
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
        self.unread = False
        self.messages: List[List] = []
        # 1 = red, 2 = blue, 0 = none
        self.teams: Dict[str, int] = {}
        self.players: Dict[str, Dict[str, Any]] = {}
        self.score_mod_overrides: Dict[str, List[str]] = {}
        self.timer = kwargs['timer'] if 'timer' in kwargs else 120
        self.start_timer = kwargs.get('start_timer', 5)
        self.match_name = None
        self.match_id = channel_name[4:] if channel_name.casefold().startswith('#mp_') else None
        self.team_mode = None
        self.win_condition = None
        self.player_count = 0
        self.beatmap = None
        self.map_id = None
        self.mods = None
        self.mods_host_unknown = False
        self.match_size = None
        self.host = None
        self.active_timer = None
        self.timer_ends_at = None
        self.map_started_at = None
        self.map_finished_at = None
        
    def add_message(self, message: Dict[str, Any]) -> List:
        """
        Add a message to the chat channel.
        """
        if message['room_name'].casefold() == self.channel_name.casefold():
            teams = dict(self.teams)
            for username, team in message.get('team_overrides', {}).items():
                old_username = case_insensitive_get(teams, username)
                if old_username and old_username != username:
                    teams.pop(old_username)
                teams[username] = team
            author = case_insensitive_get(teams, message['user_name'])
            state = {
                'author_team': teams.get(author, TEAM_NONE),
                'teams': teams
            }
            saved_message = [
                message['time_recv']*1000,
                message['user_name'],
                message['content'],
                state
            ]
            self.messages.append(saved_message)
            return saved_message
        else:
            create_notif(f"Something has gone terribly wrong, code MSG-001", notif_type=NOTIF_TYPE_ERROR)
            raise ValueError(f"Message not in channel {self.channel_name}")
        
    def team_change(self, user: str, team: int) -> None:
        """
        Change a user's team in the chat channel.
        """
        # Should only be 0, 1, 2
        user = case_insensitive_get(self.teams, user) or user
        self.teams[user] = team
        player = self.players.setdefault(user, {
            'team': TEAM_NONE,
            'ready': None,
            'status': None,
            'host': False,
            'mods': None,
            'slot': None
        })
        player['team'] = team
        self.player_count = len(self.teams)
        emit('team_change', {
            'username': user,
            'team': team,
            'channel': self.channel_name
        }, broadcast=True)

    def remove_player(self, user: str) -> None:
        player = case_insensitive_get(self.teams, user)
        if player:
            self.teams.pop(player)
            self.players.pop(player, None)
        if self.host and self.host.casefold() == user.casefold():
            self.host = None
        self.player_count = len(self.teams)

    def update_player(self, event) -> None:
        user = case_insensitive_get(self.players, event.username) or event.username
        team = team_map[event.team]
        self.teams[user] = team
        player = self.players.setdefault(user, {})
        player_mods = event.mods
        if player_mods is None and self.mods:
            player_mods = 'NoMod' if self.mods.casefold() == 'freemod' else self.mods
        player.update({
            'team': team,
            'ready': event.ready,
            'status': event.status,
            'host': bool(event.host),
            'mods': player_mods,
            'slot': event.slot
        })
        if event.host:
            self.set_host(user)
        self.player_count = len(self.players)

    def set_host(self, user: str = None) -> None:
        self.host = user
        for username, player in self.players.items():
            player['host'] = bool(user and username.casefold() == user.casefold())

    def set_active_timer(self, timer_type: str, seconds: int, received_at: float) -> None:
        self.active_timer = timer_type
        self.timer_ends_at = received_at + seconds

    def stop_active_timer(self) -> None:
        self.active_timer = None
        self.timer_ends_at = None

    def start_map_timer(self, received_at: float) -> None:
        # some small qol because it's good to know you're not insane during the quiet time
        self.map_started_at = received_at
        self.map_finished_at = None

    def finish_map_timer(self, received_at: float) -> None:
        # naturally
        if self.map_started_at is not None and self.map_finished_at is None:
            self.map_finished_at = max(received_at, self.map_started_at)

    def channel_info(self) -> Dict[str, Any]:
        is_match = self.type == osu_irc.CHANNEL_TYPE_ROOM and self.channel_name.casefold().startswith('#mp_')
        is_pm = self.type == osu_irc.CHANNEL_TYPE_PM
        return {
            'kind': 'match' if is_match else 'pm' if is_pm else 'channel',
            'channel': self.channel_name,
            'name': self.match_name if is_match and self.match_name else self.channel_name,
            'url': f'https://osu.ppy.sh/mp/{self.match_id}' if is_match and self.match_id else
                   f'https://osu.ppy.sh/users/{self.channel_name}' if is_pm else None,
            'match_id': self.match_id,
            'team_mode': self.team_mode,
            'win_condition': self.win_condition,
            'match_size': self.match_size,
            'player_count': self.player_count,
            'beatmap': self.beatmap,
            'map_url': f'https://osu.ppy.sh/b/{self.map_id}' if self.map_id else None,
            'mods': self.mods,
            'mods_host_unknown': self.mods_host_unknown,
            'host': self.host,
            'active_timer': self.active_timer,
            'timer_ends_at': self.timer_ends_at * 1000 if self.timer_ends_at else None,
            'map_started_at': self.map_started_at * 1000 if self.map_started_at is not None else None,
            'map_finished_at': self.map_finished_at * 1000 if self.map_finished_at is not None else None
        }

    def set_timer(self, timer: int) -> None:
        """
        Set the timer for the chat channel.
        """
        self.timer = timer

    def set_start_timer(self, start_timer: int) -> None:
        """
        Set the start timer for the chat channel.
        """
        self.start_timer = start_timer

    def set_alias(self, alias: str) -> None:
        """
        Set the alias for the chat channel.
        """
        alias = alias.strip()
        self.alias = alias if alias else self.channel_name

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
        if not isinstance(channel_name, str) or not channel_name.strip():
            raise ValueError("Channel name must be a non-empty string.")
        channel_name = channel_name.strip()
        if self.resolve_channel(channel_name):
            return
        self.chats[channel_name] = Chat(channel_name, channel_type, **kwargs)

        # We only need to do this here because all other methods of opening a channel result 
        # in a bounce to here anyway
        rms_cfg.add_room(channel_name)
        emit('bounce_tab_open', {
            'channel': channel_name,
            'alias': self.chats[channel_name].alias,
            'unread': self.chats[channel_name].unread
        }, broadcast=True)
        emit_recent_rooms()

    def remove_chat(self, channel_name: str) -> None:
        """
        Remove a chat channel from the chat list. Bounces the tab close event to the IRC client so it can PART
        """
        canonical_name = self.resolve_channel(channel_name)
        if canonical_name:
            removed_chat = self.chats.pop(canonical_name)
            socketio.emit('bounce_tab_close', {
                'channel': canonical_name,
                'type': removed_chat.type
            })
            if self.chat_count == 0:
                self.current_chat = None
            elif self.current_chat == canonical_name:
                self.current_chat = None
        else:
            create_notif(f"Something has gone terribly wrong, code CHN-001", notif_type=NOTIF_TYPE_ERROR)
            raise ValueError(f"Channel {channel_name} not found.")

    def get_chat(self, channel_name: str) -> Chat:
        """
        Get a chat channel from the chat list.
        """
        canonical_name = self.resolve_channel(channel_name)
        return self.chats.get(canonical_name) if canonical_name else None

    def resolve_channel(self, channel_name: str) -> Optional[str]:
        if not isinstance(channel_name, str):
            return None
        return case_insensitive_get(self.chats, channel_name)
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Called when a message is received from the IRC client. Adds the message to the appropriate chat channel.
        Bounces it to the UI client if the chat is currently open.
        Also bounces the tab open event if the chat is not currently open.
        """
        canonical_name = self.resolve_channel(message['room_name'])
        if canonical_name:
            message['room_name'] = canonical_name
        
        if message['room_name'] not in self.chats:
            self.add_chat(message['room_name'], message['channel_type'])
        saved_message = self.chats[message['room_name']].add_message(message)

        emit('bounce_recv_msg', {
            'channel': message['room_name'],
            'time': saved_message[0],
            'user': saved_message[1],
            'content': saved_message[2],
            'state': saved_message[3]
        }, broadcast=True)

    def set_current_chat(self, channel_name: str) -> None:
        """
        Set the current chat channel.
        """
        canonical_name = self.resolve_channel(channel_name)
        if not canonical_name:
            raise ValueError(f"Channel {channel_name} not found.")
        self.current_chat = canonical_name
        self.chats[canonical_name].unread = False

    def reorder(self, channel_names: List[str]) -> bool:
        if not isinstance(channel_names, list) or len(channel_names) != len(self.chats):
            return False
        resolved = [self.resolve_channel(channel) for channel in channel_names]
        if any(channel is None for channel in resolved):
            return False
        if len({channel.casefold() for channel in resolved}) != len(self.chats):
            return False
        self.chats = {channel: self.chats[channel] for channel in resolved}
        return True
    
    def get_messages(self, channel_name: str) -> List[List]:
        chat = self.get_chat(channel_name)
        if not chat:
            raise ValueError(f"Channel {channel_name} not found.")
        return chat.messages

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

    def session_state(self) -> Dict[str, Any]:
        return {
            'chats': [
                {'channel': chat.channel_name, 'type': chat.type}
                for chat in self.chats.values()
            ],
            'current_chat': self.current_chat
        }

    def clear(self) -> None:
        self.chats.clear()
        self.current_chat = None
        self.username = None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} num_chats={len(self.chats)}>"
    
    def __str__(self) -> str:
        return f"Chats with {len(self.chats)} channels, {self.chats}. Current chat: {self.current_chat}"

chats = Chats()
# ---------------------
# Main Routes
# ---------------------
@app.route('/')
def chat():
    cur_theme = settings_cfg.data['appearance']['theme']
    if not user_cfg.has_credentials() and pending_credentials is None:
        return redirect(url_for('login'))
    return render_template('chat.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/login')
def login():
    cur_theme = settings_cfg.data['appearance']['theme']
    return render_template('login.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/settings')
def settings():
    cur_theme = settings_cfg.data['appearance']['theme']
    return render_template('settings.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/help')
def help_page():
    cur_theme = settings_cfg.data['appearance']['theme']
    return render_template('help.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/tournaments')
def tournaments_page():
    cur_theme = settings_cfg.data['appearance']['theme']
    return render_template('tournaments.html', cur_theme=cur_theme, themes=THEMES)

@app.route('/sounds/<asset_id>')
def custom_sound(asset_id):
    asset = next((item for item in settings_cfg.data['audio']['assets'] if item['id'] == asset_id), None)
    if not asset:
        return '', 404
    path = sound_store.path_for(asset)
    return send_file(path) if path.exists() else ('', 404)

@app.route('/api/sounds', methods=['POST'])
def upload_sound():
    upload = request.files.get('sound')
    if not upload:
        return jsonify({'ok': False, 'errors': ['No sound file was provided.']}), 400
    try:
        asset = sound_store.save(upload)
        audio = settings_cfg.snapshot()['audio']
        audio['assets'].append(asset)
        settings_cfg.update_section('audio', audio)
        socketio.emit('settings_changed', settings_payload())
        return jsonify({'ok': True, 'data': asset, 'errors': []})
    except (ValueError, SettingsError) as error:
        return jsonify({'ok': False, 'errors': [str(error)]}), 400

# ---------------------
# Layout SIO Routes
# ---------------------
@socketio.on('theme')
def set_theme(data: Dict[str, Any]):
    log_socket_event('theme', data)
    if not valid_payload('theme', data, {}):
        return
    # default to dark theme
    theme: str = data.get('theme', 'dark')
    if theme in THEMES:
        appearance = settings_cfg.snapshot()['appearance']
        appearance['theme'] = theme
        settings_cfg.update_section('appearance', appearance)
    else:
        # I'd be shocked if this ever happens; it means the user edited some code and didn't know what they were doing
        raise ValueError(f"Theme {theme} not found.")

@socketio.on('settings_get')
def handle_settings_get():
    log_socket_event('settings_get')
    return settings_result(data=settings_payload())

@socketio.on('settings_update')
def handle_settings_update(data: Dict[str, Any]):
    log_socket_event('settings_update', data)
    if not valid_payload('settings_update', data, {'section': str, 'value': dict}):
        return settings_result(False, errors=['Invalid settings request.'])
    try:
        if data['section'] == 'chat':
            blocked = data['value'].get('blocked_users', [])
            forbidden = {'banchobot'}
            if chats.username:
                forbidden.add(normalize_username(chats.username))
            if any(normalize_username(username) in forbidden for username in blocked):
                raise SettingsError('BanchoBot and your own account cannot be blocked.')
        settings_cfg.update_section(data['section'], data['value'])
        if data['section'] == 'chat':
            rms_cfg.set_max_rooms(settings_cfg.data['chat']['room_history_limit'])
            emit_recent_rooms()
        payload = settings_payload()
        emit('settings_changed', payload, broadcast=True)
        return settings_result(data=payload)
    except SettingsError as error:
        return settings_result(False, errors=[str(error)])

@socketio.on('settings_reset')
def handle_settings_reset(data: Dict[str, Any]):
    log_socket_event('settings_reset', data)
    if not valid_payload('settings_reset', data, {'section': str}):
        return settings_result(False, errors=['Invalid reset request.'])
    try:
        settings_cfg.reset_section(data['section'])
        rms_cfg.set_max_rooms(settings_cfg.data['chat']['room_history_limit'])
        payload = settings_payload()
        emit('settings_changed', payload, broadcast=True)
        emit_recent_rooms()
        return settings_result(data=payload)
    except SettingsError as error:
        return settings_result(False, errors=[str(error)])

@socketio.on('sound_delete')
def handle_sound_delete(data: Dict[str, Any]):
    log_socket_event('sound_delete', data)
    if not valid_payload('sound_delete', data, {'id': str}):
        return settings_result(False, errors=['Invalid sound request.'])
    audio = settings_cfg.snapshot()['audio']
    asset = next((item for item in audio['assets'] if item['id'] == data['id']), None)
    if not asset:
        return settings_result(False, errors=['Sound not found.'])
    if any(trigger['asset_id'] == asset['id'] for trigger in audio['triggers']):
        return settings_result(False, errors=['This sound is used by a trigger.'])
    if any(
        trigger.get('asset_id') == asset['id']
        for tournament in tournament_cfg.items.values()
        for trigger in tournament.get('sound_triggers', [])
    ):
        return settings_result(False, errors=['This sound is used by a tournament trigger.'])
    sound_store.delete(asset)
    audio['assets'].remove(asset)
    settings_cfg.update_section('audio', audio)
    payload = settings_payload()
    emit('settings_changed', payload, broadcast=True)
    emit('tournament_state', tournament_state(), broadcast=True)
    return settings_result(data=payload)

@socketio.on('run_macro')
def handle_run_macro(data: Dict[str, Any]):
    log_socket_event('run_macro', data)
    if not valid_payload('run_macro', data, {'id': str}):
        return settings_result(False, errors=['Invalid macro request.'])
    macro = settings_cfg.find_macro(data['id'])
    if not macro:
        return settings_result(False, errors=['Macro not found.'])
    payload = {'content': macro['command']}
    if isinstance(data.get('channel'), str):
        payload['channel'] = data['channel']
    handle_send_msg(payload)
    return settings_result(data={'id': macro['id']})

# ---------------------
# Chat SIO Routes
# ---------------------
@socketio.on('connect')
def handle_connect():
    log_socket_event('connect')
    emit('connection_state', connection_state)
    if debug_flag:
        debug_connect()

@socketio.on('backend_identity_request')
def handle_backend_identity_request():
    log_socket_event('backend_identity_request')
    emit('backend_identity', {
        'instance_id': backend_instance_id,
        'has_credentials': user_cfg.has_credentials() or pending_credentials is not None
    })

@socketio.on('browser_ready')
def handle_browser_ready():
    log_socket_event('browser_ready')
    for chat in chats.chats.values():
        emit('bounce_tab_open', {
            'channel': chat.channel_name,
            'alias': chat.alias,
            'unread': chat.unread
        })
    emit('recent_rooms_state', {
        'rooms': rms_cfg.rooms,
        'max_rooms': rms_cfg.max_rooms
    })
    emit('connection_state', connection_state)
    emit('tournament_state', tournament_state())
    if chats.current_chat:
        emit('restore_tab', {'channel': chats.current_chat})

@socketio.on('nickname')
def handle_nickname(data: Dict[str, Any]):
    log_socket_event('nickname', data)
    if not valid_payload('nickname', data, {'nickname': str}) or not data['nickname'].strip():
        return
    chats.username = data['nickname']

@socketio.on('disconnect')
def handle_disconnect():
    log_socket_event('disconnect')
    print('A Client disconnected')

@socketio.on('tab_open')
def handle_tab_open(data: Dict[str, Any]):
    log_socket_event('tab_open', data)
    if not valid_payload('tab_open', data, {'channel': str, 'type': int}):
        return
    if not data['channel'].strip() or data['type'] not in {
        osu_irc.CHANNEL_TYPE_ROOM, osu_irc.CHANNEL_TYPE_PM
    }:
        UI_EVENTS.write('invalid_socket_payload', name='tab_open', data=data)
        return
    chats.add_chat(data['channel'], data['type'])

@socketio.on('send_msg')
def handle_send_msg(data: Dict[str, Any]):
    log_socket_event('send_msg', data)
    if not valid_payload('send_msg', data, {'content': str}):
        return
    if connection_state['state'] != IRC_STATE_AUTHENTICATED:
        create_notif("Messages cannot be sent while disconnected.", notif_type=NOTIF_TYPE_WARNING)
        return
    # Prevent sending attempting to send messages to a nonexistent chat unless
    # It's a slash command because /q is a thing
    content = str(data.get("content", "")).strip()
    if not content:
        return
    data["content"] = content
    if chats.current_chat is None and content[0] != "/":
        create_notif("No chat open.", notif_type=NOTIF_TYPE_WARNING)
        return
    # Failsafe, this case occurs actually not infrequently, eg. the buttons
    if "channel" not in data:
        data["channel"] = chats.current_chat
    # Prevent a message send if the chat is not created yet
    elif not chats.resolve_channel(data["channel"]):
        create_notif(f"Chat {data['channel']} not found.", notif_type=NOTIF_TYPE_ERROR)
        return
    else:
        data['channel'] = chats.resolve_channel(data['channel'])
    # Slash commands
    if data["content"][0] == "/":
        command_parse(data["content"])
        return
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
    log_socket_event('recv_msg', data)
    if not valid_payload('recv_msg', data, {
        'user_name': str,
        'room_name': str,
        'content': str,
        'channel_type': int,
        'time_recv': (int, float)
    }):
        return
    if data['channel_type'] not in {osu_irc.CHANNEL_TYPE_ROOM, osu_irc.CHANNEL_TYPE_PM}:
        UI_EVENTS.write('invalid_socket_payload', name='recv_msg', data=data)
        return
    if data["channel_type"] == osu_irc.CHANNEL_TYPE_ROOM:
        data["room_name"] = f"#{data['room_name']}"
    if chats.username and data["room_name"].casefold() == chats.username.casefold():
        data["room_name"] = data["user_name"]
    if data['channel_type'] == osu_irc.CHANNEL_TYPE_PM and settings_cfg.is_blocked(data['user_name']):
        sender = data['user_name']
        key = normalize_username(sender)
        now = time.monotonic()
        previous = blocked_pm_notices.get(key)
        count = previous['count'] + 1 if previous and now - previous['time'] <= 120 else 1
        blocked_pm_notices[key] = {'time': now, 'count': count}
        emit('blocked_pm', {'sender': sender, 'count': count, 'key': key}, broadcast=True)
        return
    # blocking, sounds, and match regex happen here
    # regex for team changes here (must be issued by banchobot)
    event = parse_match_message(data["user_name"], data["content"])
    if event and event.kind in {'slot', 'join_slot', 'change_team'}:
        data['team_overrides'] = {event.username: team_map[event.team]}
    chats.add_message(data)
    sounds = matching_sounds(
        settings_cfg.data, data['user_name'], data['content'], data['room_name'], data['channel_type']
    )
    if sounds:
        emit('play_sounds', {'sounds': sounds}, broadcast=True)
    assignment = tournament_assignments.get(data['room_name'])
    tournament = tournament_cfg.items.get(assignment['tournament_id'])
    if tournament_cfg.enabled and tournament:
        triggers = [{
            'id': trigger.get('id', ''), 'name': trigger.get('name', ''),
            'enabled': trigger.get('enabled', True), 'mode': trigger.get('mode', 'literal'),
            'pattern': trigger.get('pattern', ''), 'case_sensitive': trigger.get('case_sensitive', False),
            'sender': trigger.get('sender', ''), 'scope': trigger.get('scope', 'all'),
            'asset_id': trigger.get('asset_id', '')
        } for trigger in tournament.get('sound_triggers', [])]
        tournament_sound_settings = {'audio': {
            'volume': settings_cfg.data['audio']['volume'], 'muted': settings_cfg.data['audio']['muted'],
            'assets': settings_cfg.data['audio']['assets'], 'triggers': triggers
        }}
        tournament_sounds = matching_sounds(
            tournament_sound_settings, data['user_name'], data['content'], data['room_name'], data['channel_type']
        )
        if tournament_sounds:
            emit('play_sounds', {'sounds': tournament_sounds}, broadcast=True)
    if event:
        if event.kind == 'create_match':
            start_chat(f"#mp_{event.match_id}", osu_irc.CHANNEL_TYPE_ROOM)
            return
        chat = chats.get_chat(data['room_name'])
        if event.kind in {'slot', 'join_slot'}:
            chat.update_player(event)
            emit_match_state(chat)
            return
        if event.kind == 'change_team':
            chat.team_change(event.username, team_map[event.team])
            emit_match_state(chat)
            return
        if event.kind == 'leave':
            chat.remove_player(event.username)
        elif event.kind == 'room_info':
            chat.match_id = event.match_id
            chat.match_name = event.match_name
        elif event.kind == 'team_mode':
            chat.team_mode = event.team
            chat.win_condition = event.value
            if chat.team_mode.casefold() in {'headtohead', 'tagcoop'}:
                for username in chat.teams:
                    chat.teams[username] = TEAM_NONE
                    chat.players[username]['team'] = TEAM_NONE
        elif event.kind == 'players':
            chat.teams.clear()
            chat.players.clear()
            chat.player_count = int(event.value)
        elif event.kind == 'player_score':
            username = case_insensitive_get(chat.players, event.username) or event.username
            player = chat.players.setdefault(username, {'team': TEAM_NONE, 'ready': None, 'status': None, 'host': False, 'mods': None, 'slot': None})
            player['score'] = event.score
            player['passed'] = event.passed
            player['score_mods'] = score_mods(chat.score_mod_overrides.get(username, player.get('mods')))
        elif event.kind == 'beatmap':
            chat.beatmap = event.value
            chat.map_id = event.map_id
            chat.map_started_at = None
            chat.map_finished_at = None
            chat.score_mod_overrides.clear()
            for player in chat.players.values():
                player.pop('score', None)
                player.pop('passed', None)
                player.pop('score_mods', None)
        elif event.kind == 'mods':
            chat.mods = event.value
            chat.mods_host_unknown = bool(chat.host)
            player_mods = 'NoMod' if event.value.casefold() == 'freemod' else event.value
            for player in chat.players.values():
                player['mods'] = player_mods
        elif event.kind == 'set_match':
            settings = [setting.strip() for setting in event.value.split(',')]
            if settings:
                chat.team_mode = settings[0]
                if chat.team_mode.casefold() in {'headtohead', 'tagcoop'}:
                    for username in chat.teams:
                        chat.teams[username] = TEAM_NONE
                        chat.players[username]['team'] = TEAM_NONE
            if len(settings) > 1:
                chat.win_condition = settings[1]
            if len(settings) > 2 and settings[2].isdigit():
                chat.match_size = int(settings[2])
        elif event.kind == 'match_size':
            chat.match_size = event.size
        elif event.kind == 'move_slot':
            username = case_insensitive_get(chat.players, event.username)
            if username:
                chat.players[username]['slot'] = event.slot
        elif event.kind == 'host':
            chat.set_host(event.username)
            chat.mods_host_unknown = True
        elif event.kind == 'clear_host':
            chat.set_host()
        elif event.kind == 'all_ready':
            for player in chat.players.values():
                player['ready'] = True
                player['status'] = 'Ready'
        elif event.kind == 'host_map':
            chat.mods = None
            chat.mods_host_unknown = True
            chat.map_started_at = None
            chat.map_finished_at = None
        elif event.kind in {'timer', 'start_timer'}:
            chat.set_active_timer(event.kind, event.seconds, data['time_recv'])
        elif event.kind == 'countdown_abort':
            chat.stop_active_timer()
        elif event.kind == 'match_abort' and chat.active_timer == 'start_timer':
            chat.stop_active_timer()
        if event.kind == 'match_started':
            chat.start_map_timer(data['time_recv'])
            chat.stop_active_timer()
        elif event.kind == 'match_finished':
            chat.finish_map_timer(data['time_recv'])
        elif event.kind == 'match_abort':
            chat.finish_map_timer(data['time_recv'])
        emit_match_state(chat)

@socketio.on('tab_swap')
def handle_tab_swap(data: Dict[str, Any]):
    log_socket_event('tab_swap', data)
    if not valid_payload('tab_swap', data, {'channel': str}):
        return
    if not chats.get_chat(data['channel']):
        UI_EVENTS.write('invalid_socket_payload', name='tab_swap', data=data)
        return
    chats.set_current_chat(data['channel'])
    channel = chats.current_chat
    messages = chats.get_messages(channel)
    return {
        'alias': chats.get_chat(channel).alias,
        'channel': channel,
        'messages': messages,
        'timer': chats.get_chat(channel).timer,
        'start_timer': chats.get_chat(channel).start_timer,
        'teams': json.dumps(chats.get_chat(channel).teams),
        'players': chats.get_chat(channel).players,
        'channel_info': chats.get_chat(channel).channel_info(),
        'recent_rooms': rms_cfg.rooms,
        'recent_rooms_limit': rms_cfg.max_rooms,
        'tournament': tournament_overlay(channel)
    }

@socketio.on('tab_close')
def handle_tab_close(data: Dict[str, Any]):
    log_socket_event('tab_close', data)
    if not valid_payload('tab_close', data, {'channel': str}) or not chats.get_chat(data['channel']):
        return
    tournament_assignments.remove(data['channel'])
    chats.remove_chat(data['channel'])

@socketio.on('tab_reorder')
def handle_tab_reorder(data: Dict[str, Any]):
    log_socket_event('tab_reorder', data)
    if not valid_payload('tab_reorder', data, {'channels': list}):
        return
    if not chats.reorder(data['channels']):
        UI_EVENTS.write('invalid_socket_payload', name='tab_reorder', data=data)

@socketio.on('recent_room_open')
def handle_recent_room_open(data: Dict[str, Any]):
    log_socket_event('recent_room_open', data)
    if not valid_payload('recent_room_open', data, {'channel': str}):
        return
    channel = next(
        (room for room in rms_cfg.rooms if room.casefold() == data['channel'].casefold()),
        None
    )
    if channel:
        start_chat(channel, osu_irc.CHANNEL_TYPE_ROOM)

@socketio.on('recent_room_remove')
def handle_recent_room_remove(data: Dict[str, Any]):
    log_socket_event('recent_room_remove', data)
    if not valid_payload('recent_room_remove', data, {'channel': str}):
        return
    rms_cfg.remove_room(data['channel'])
    emit_recent_rooms()

@socketio.on('recent_rooms_clear')
def handle_recent_rooms_clear():
    log_socket_event('recent_rooms_clear')
    rms_cfg.clear_rooms()
    emit_recent_rooms()

@socketio.on('recent_rooms_limit')
def handle_recent_rooms_limit(data: Dict[str, Any]):
    log_socket_event('recent_rooms_limit', data)
    if not valid_payload('recent_rooms_limit', data, {'limit': (int, str)}):
        return
    rms_cfg.set_max_rooms(data['limit'])
    chat_settings = settings_cfg.snapshot()['chat']
    chat_settings['room_history_limit'] = rms_cfg.max_rooms
    settings_cfg.update_section('chat', chat_settings)
    emit_recent_rooms()

# ---------------------
# IRC Session Routes
# ---------------------
@socketio.on('login_submit')
def handle_login_submit(data: Dict[str, Any]):
    # try to login with pending credentials
    log_socket_event('login_submit', data)
    global pending_credentials
    if not valid_payload('login_submit', data, {}):
        emit('login_result', {'ok': False, 'error': 'Invalid login request.'})
        return
    username = str(data.get('username', '')).strip()
    password = str(data.get('password', '')).strip()
    if not username or not password:
        # if we suck, try again
        emit('login_result', {'ok': False, 'error': 'Please fill in both username and IRC password.'})
        return

    pending_credentials = (username, password)
    connection_state.update({'state': IRC_STATE_CONNECTING, 'attempt': 0, 'retry_in': 0})
    emit('cmd_login', {'username': username, 'password': password}, broadcast=True)
    emit('connection_state', connection_state, broadcast=True)
    emit('login_result', {'ok': True})

@socketio.on('irc_retry')
def handle_irc_retry():
    # gonna have lots of logging
    log_socket_event('irc_retry')
    emit('cmd_reconnect', {}, broadcast=True)

@socketio.on('logout')
def handle_logout():
    log_socket_event('logout')
    global pending_credentials
    pending_credentials = None
    user_cfg.clear_credentials()
    chats.clear()
    rms_cfg.clear_rooms()
    connection_state.update({'state': IRC_STATE_LOGGED_OUT, 'attempt': 0, 'retry_in': 0})
    emit('cmd_logout', {}, broadcast=True)
    emit('connection_state', connection_state, broadcast=True)
    emit('logout_complete')

@socketio.on('irc_state')
def handle_irc_state(data: Dict[str, Any]):
    log_socket_event('irc_state', data)
    global pending_credentials
    if not valid_payload('irc_state', data, {'state': str}) or data['state'] not in {
        IRC_STATE_CONNECTING, IRC_STATE_AUTHENTICATED, IRC_STATE_RECONNECTING,
        IRC_STATE_AUTH_FAILED, IRC_STATE_LOGGED_OUT
    }:
        return
    if data.get('state') == IRC_STATE_AUTHENTICATED and pending_credentials:
        user_cfg.set_credentials(*pending_credentials)
        pending_credentials = None
    elif data.get('state') == IRC_STATE_AUTH_FAILED:
        pending_credentials = None
    connection_state.clear()
    connection_state.update(data)
    emit('connection_state', connection_state, broadcast=True)

@socketio.on('session_state')
def handle_session_state():
    log_socket_event('session_state')
    return chats.session_state()

@socketio.on('set_timer')
def handle_set_timer(data: Dict[str, Any]):
    log_socket_event('set_timer', data)
    if not valid_payload('set_timer', data, {'timer': (int, str)}) or not chats.get_current_chat:
        return
    chats.get_current_chat.set_timer(data['timer'])

@socketio.on('set_start_timer')
def handle_set_start_timer(data: Dict[str, Any]):
    log_socket_event('set_start_timer', data)
    if not valid_payload('set_start_timer', data, {'timer': (int, str)}) or not chats.get_current_chat:
        return
    chats.get_current_chat.set_start_timer(data['timer'])

@socketio.on('change_alias')
def change_alias(data: Dict[str, Any]):
    log_socket_event('change_alias', data)
    if not valid_payload('change_alias', data, {'channel': str, 'alias': str}):
        return
    chat = chats.get_chat(data['channel'])
    if not chat or len(data['alias'].strip()) > 64:
        return
    chat.set_alias(data['alias'])
    emit('alias_changed', {
        'channel': chat.channel_name,
        'alias': chat.alias,
        'info': chat.channel_info(),
        'teams': chat.teams,
        'players': chat.players
    }, broadcast=True)

# ---------------------
# Tournament Routes
# ---------------------
@socketio.on('tournament_list')
def handle_tournament_list():
    log_socket_event('tournament_list')
    return tournament_result(data=tournament_state())

@socketio.on('tournament_create')
def handle_tournament_create(data=None):
    item = tournament_cfg.create()
    payload = tournament_state()
    emit('tournament_state', payload, broadcast=True)
    return tournament_result(data={'tournament': item, 'state': payload})

@socketio.on('tournament_validate')
def handle_tournament_validate(data: Dict[str, Any]):
    if not valid_payload('tournament_validate', data, {'tournament': dict}):
        return tournament_result(False, errors=['invalid tournament request.'])
    errors = validate_tournament(data['tournament'])
    return tournament_result(not errors, data={'valid': not errors}, errors=errors)

@socketio.on('tournament_import_mappool')
def handle_tournament_import_mappool(data: Dict[str, Any]):
    if not valid_payload('tournament_import_mappool', data, {'text': str}):
        return tournament_result(False, errors=['invalid mappool import request.'])
    try:
        return tournament_result(data={'maps': parse_mappool_text(data['text'])})
    except ValueError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_fetch_map_metadata')
def handle_tournament_fetch_map_metadata(data: Dict[str, Any]):
    if not valid_payload('tournament_fetch_map_metadata', data, {'map_id': (int, str)}):
        return tournament_result(False, errors=['invalid metadata request.'])
    try:
        return tournament_result(data=fetch_beatmap_metadata(data['map_id']))
    except ValueError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_save')
def handle_tournament_save(data: Dict[str, Any]):
    if not valid_payload('tournament_save', data, {'tournament': dict}):
        return tournament_result(False, errors=['invalid tournament request.'])
    try:
        item = data['tournament']
        tournament_id = str(item.get('id', ''))
        assigned = tournament_assignments.channels_for(tournament_id)
        if assigned and validate_tournament(item):
            raise TournamentError('an in-use tournament cannot be saved as an invalid draft.')
        old = tournament_cfg.items.get(tournament_id)
        if assigned and old:
            removed = set(old.get('mappools', {})) - set(item.get('mappools', {}))
            if any(tournament_assignments.get(channel)['pool_id'] in removed for channel in assigned):
                raise TournamentError('an assigned mappool cannot be removed.')
        saved = tournament_cfg.save(item)
        payload = tournament_state()
        emit('tournament_state', payload, broadcast=True)
        emit_tournament_match_states(tournament_id)
        return tournament_result(data={'tournament': saved, 'state': payload})
    except TournamentError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_duplicate')
def handle_tournament_duplicate(data: Dict[str, Any]):
    if not valid_payload('tournament_duplicate', data, {'id': str}):
        return tournament_result(False, errors=['invalid tournament request.'])
    try:
        item = tournament_cfg.duplicate(data['id'])
        payload = tournament_state()
        emit('tournament_state', payload, broadcast=True)
        return tournament_result(data={'tournament': item, 'state': payload})
    except TournamentError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_delete')
def handle_tournament_delete(data: Dict[str, Any]):
    if not valid_payload('tournament_delete', data, {'id': str}):
        return tournament_result(False, errors=['invalid tournament request.'])
    if tournament_assignments.channels_for(data['id']):
        return tournament_result(False, errors=['clear this tournament\'s assignments before deleting it.'])
    try:
        tournament_cfg.delete(data['id'])
        payload = tournament_state()
        emit('tournament_state', payload, broadcast=True)
        return tournament_result(data=payload)
    except TournamentError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_toggle')
def handle_tournament_toggle(data: Dict[str, Any]):
    if not valid_payload('tournament_toggle', data, {'enabled': bool}):
        return tournament_result(False, errors=['invalid tournament request.'])
    try:
        tournament_cfg.set_enabled(data['enabled'])
        payload = tournament_state()
        emit('tournament_state', payload, broadcast=True)
        emit_tournament_match_states()
        return tournament_result(data=payload)
    except TournamentError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_clear_assignments')
def handle_tournament_clear_assignments(data: Dict[str, Any]):
    if not valid_payload('tournament_clear_assignments', data, {'id': str}):
        return tournament_result(False, errors=['invalid tournament request.'])
    affected = tournament_assignments.clear_tournament(data['id'])
    for channel in affected:
        chat = chats.get_chat(channel)
        if chat:
            emit_match_state(chat)
    emit('tournament_state', tournament_state(), broadcast=True)
    return tournament_result(data={'channels': affected})

@socketio.on('tournament_assign')
def handle_tournament_assign(data: Dict[str, Any]):
    if not valid_payload('tournament_assign', data, {'channel': str, 'tournament_id': str}):
        return tournament_result(False, errors=['invalid assignment request.'])
    chat = chats.get_chat(data['channel'])
    tournament = tournament_cfg.get(data['tournament_id']) if data['tournament_id'] else None
    if not chat or not data['channel'].casefold().startswith('#mp_'):
        return tournament_result(False, errors=['tournaments can only be assigned to open match rooms.'])
    if data['tournament_id'] and (not tournament_cfg.enabled or not tournament or not tournament['valid']):
        return tournament_result(False, errors=['select a valid tournament while tournaments are enabled.'])
    try:
        tournament_assignments.assign(data['channel'], data['tournament_id'])
        if tournament:
            chat.set_timer(tournament['timer'])
            chat.set_start_timer(tournament['start_timer'])
            emit('set_timer_input', {'timer': tournament['timer']})
            emit('set_start_timer_input', {'timer': tournament['start_timer']})
        payload = tournament_overlay(data['channel'])
        emit_match_state(chat)
        emit('tournament_state', tournament_state(), broadcast=True)
        return tournament_result(data=payload)
    except ValueError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_select_pool')
def handle_tournament_select_pool(data: Dict[str, Any]):
    if not valid_payload('tournament_select_pool', data, {'channel': str, 'pool_id': str}):
        return tournament_result(False, errors=['invalid mappool request.'])
    assignment = tournament_assignments.get(data['channel'])
    tournament = tournament_cfg.items.get(assignment['tournament_id'])
    if not tournament or (data['pool_id'] and data['pool_id'] not in tournament['mappools']):
        return tournament_result(False, errors=['mappool not found.'])
    try:
        tournament_assignments.select_pool(data['channel'], data['pool_id'])
        payload = tournament_overlay(data['channel'])
        chat = chats.get_chat(data['channel'])
        if chat:
            emit_match_state(chat)
        return tournament_result(data=payload)
    except ValueError as error:
        return tournament_result(False, errors=[str(error)])

@socketio.on('tournament_pick_map')
def handle_tournament_pick_map(data: Dict[str, Any]):
    if not valid_payload('tournament_pick_map', data, {'channel': str, 'map_id': str}):
        return tournament_result(False, errors=['invalid map request.'])
    assignment = tournament_assignments.get(data['channel'])
    tournament = tournament_cfg.items.get(assignment['tournament_id'])
    pool = tournament.get('mappools', {}).get(assignment['pool_id']) if tournament else None
    beatmap = pool.get('maps', {}).get(data['map_id']) if pool else None
    if not tournament_cfg.enabled or not beatmap:
        return tournament_result(False, errors=['map is not available for this tab.'])
    if connection_state['state'] != IRC_STATE_AUTHENTICATED:
        return tournament_result(False, errors=['messages cannot be sent while disconnected.'])
    lock_key = data['channel'].casefold()
    now = time.monotonic()
    if now - map_pick_locks.get(lock_key, 0) < 1:
        return tournament_result(False, errors=['wait a moment before selecting another map.'])
    map_pick_locks[lock_key] = now
    handle_send_msg({'channel': data['channel'], 'content': beatmap.get('map_command')})
    handle_send_msg({'channel': data['channel'], 'content': beatmap.get('mods_command')})
    chat = chats.get_chat(data['channel'])
    if tournament.get('timer_on_map_select') and chat:
        handle_send_msg({'channel': data['channel'], 'content': f'!mp timer {chat.timer}'})
        # when you selected a map before, i forgot to set the active timer.
        # I am aware that this ends up being a bit disconnected, because of
        # bancho lag / send time / ping / etc but i think it's more important
        # to just have an idea of where the timer is, and know that it started. 
        # if bancho sends a "map timer" later, it will resynchronize
        chat.set_active_timer('timer', int(chat.timer), time.time())
        emit_match_state(chat)
    return tournament_result(data={'map_id': data['map_id']})

@socketio.on('tournament_score_mods')
def handle_tournament_score_mods(data: Dict[str, Any]):
    if not valid_payload('tournament_score_mods', data, {'channel': str, 'username': str, 'mods': list}):
        return tournament_result(False, errors=['invalid score mod request.'])
    chat = chats.get_chat(data['channel'])
    username = case_insensitive_get(chat.players, data['username']) if chat else None
    if not chat or not username or not all(isinstance(mod, str) and mod in MODS for mod in data['mods']):
        return tournament_result(False, errors=['player or mod not found.'])
    mods = list(dict.fromkeys(data['mods']))
    chat.score_mod_overrides[username] = ['NM'] if 'NM' in mods or not mods else mods
    payload = tournament_overlay(data['channel'])
    emit_match_state(chat)
    return tournament_result(data=payload)

@socketio.on('debug')
def debug(data: Dict[str, Any]):
    log_socket_event('debug', data)
    print(f'debug flag: {debug_flag}')
    print(data)
    print(rms_cfg)
    print(chats)
# ---------------------
# Starting webserver
# ---------------------
def debug_run():
    # This is meant when the UI is being run standalone, so we need to make some fake chats
    # Adding chats is optional, since any non empty chat will automatically be added
    # However the fake mp is empty so we add it here
    global debug_flag
    debug_flag = True
    socketio.run(app, debug=True, host='localhost', port=5000)

def debug_connect():
    global debug_flag
    # Careful to only run this once
    debug_flag = False
    chats.username = "HijiriS"
    chats.add_chat("#testchat1", osu_irc.CHANNEL_TYPE_ROOM, timer=120, start_timer=5)
    chats.add_chat("testpm1", osu_irc.CHANNEL_TYPE_PM)
    chats.add_chat("#mp_12345678", osu_irc.CHANNEL_TYPE_ROOM, timer=90, start_timer=10)
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
