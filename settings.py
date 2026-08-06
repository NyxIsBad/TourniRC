import copy
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from sound_triggers import normalize_triggers


# defaults live here so resets and first runs cannot disagree
DEFAULT_ALIASES = {
    '/q': '/query', '/pm': '/query', '/chat': '/query', '/join': '/query',
    '/l': '/part', '/leave': '/part', '/close': '/part', '/t': '/timer',
    '/mt': '/matchtimer', '/s': '/savelog'
}
DEFAULT_HOTKEYS = {
    'previous_tab': 'Alt+ArrowLeft',
    'next_tab': 'Alt+ArrowRight',
    **{f'tab_{index}': f'Alt+{index}' for index in range(1, 10)}
}
DEFAULT_SETTINGS = {
    'appearance': {'theme': 'dark'},
    'chat': {'room_history_limit': 5, 'blocked_users': []},
    'controls': {
        'aliases': DEFAULT_ALIASES,
        'hotkeys': DEFAULT_HOTKEYS,
        'macros': []
    },
    'audio': {
        'volume': 1.0,
        'muted': False,
        'assets': [],
        'triggers': []
    }
}

ALIAS = re.compile(r'^/[A-Za-z0-9_-]+$')
VALID_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg'}
BUILTIN_AUDIO_IDS = {
    'builtin:alert-metalgear.mp3', 'builtin:alert-pokemon.mp3',
    'builtin:alert-scifi.mp3', 'builtin:anime-wow.mp3',
    'builtin:hitwhistle.wav', 'builtin:incoming-transmission.mp3',
    'builtin:nice.mp3'
}


def normalize_username(username):
    return re.sub(r'\s+', '_', str(username).strip()).casefold()


class SettingsError(ValueError):
    pass


class SettingsRepository:
    def __init__(self, path='cfg/settings.json'):
        self.path = Path(path)
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self):
        if not self.path.exists():
            self.save()
            return self.data
        try:
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
            self.data = self._validate(loaded)
        except (OSError, ValueError, json.JSONDecodeError):
            # keep the broken file around; guessing would be worse
            backup = self.path.with_name(f'{self.path.stem}.invalid-{int(time.time())}{self.path.suffix}')
            try:
                shutil.copy2(self.path, backup)
            except OSError:
                pass
            self.data = copy.deepcopy(DEFAULT_SETTINGS)
            self.save()
        return self.data

    def save(self):
        # replace atomically so a bad shutdown cannot cut json in half
        payload = json.dumps(self.data, indent=2, ensure_ascii=False) + '\n'
        handle, temporary = tempfile.mkstemp(prefix=f'.{self.path.name}.', dir=self.path.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot(self):
        return copy.deepcopy(self.data)

    def update_section(self, section, value):
        if section not in {'appearance', 'chat', 'controls', 'audio'} or not isinstance(value, dict):
            raise SettingsError('Invalid settings section.')
        candidate = self.snapshot()
        candidate[section] = value
        self.data = self._validate(candidate)
        self.save()
        return copy.deepcopy(self.data[section])

    def reset_section(self, section):
        # resets only own their visible fields
        if section == 'general':
            self.data['chat']['room_history_limit'] = DEFAULT_SETTINGS['chat']['room_history_limit']
        elif section == 'chat':
            self.data['chat']['blocked_users'] = []
        elif section == 'controls':
            self.data['controls']['aliases'] = copy.deepcopy(DEFAULT_ALIASES)
            self.data['controls']['hotkeys'] = copy.deepcopy(DEFAULT_HOTKEYS)
        elif section == 'audio':
            self.data['audio']['volume'] = 1.0
            self.data['audio']['muted'] = False
            self.data['audio']['triggers'] = []
        else:
            raise SettingsError('Invalid reset section.')
        self.data = self._validate(self.data)
        self.save()
        return self.snapshot()

    def find_macro(self, macro_id):
        return next((macro for macro in self.data['controls']['macros'] if macro['id'] == macro_id), None)

    def resolve_alias(self, alias):
        # macros get their own type because they send instead of recurse
        alias = alias.casefold()
        built_in = self.data['controls']['aliases'].get(alias)
        if built_in:
            return ('command', built_in)
        macro = next((item for item in self.data['controls']['macros'] if item.get('alias', '').casefold() == alias), None)
        return ('macro', macro) if macro else (None, None)

    def is_blocked(self, username):
        target = normalize_username(username)
        return any(normalize_username(item) == target for item in self.data['chat']['blocked_users'])

    def _validate(self, candidate):
        if not isinstance(candidate, dict):
            raise SettingsError('Settings must be an object.')
        result = copy.deepcopy(DEFAULT_SETTINGS)

        # appearance
        appearance = candidate.get('appearance', {})
        theme = str(appearance.get('theme', result['appearance']['theme']))
        result['appearance'] = {'theme': theme}

        # chat and blocking
        chat = candidate.get('chat', {})
        blocked = chat.get('blocked_users', [])
        if not isinstance(blocked, list):
            raise SettingsError('Blocked users must be a list.')
        cleaned = []
        seen = set()
        for username in blocked:
            username = str(username).strip()
            if not username or len(username) > 64 or any(ord(char) < 32 for char in username):
                raise SettingsError('Invalid blocked username.')
            key = normalize_username(username)
            if key not in seen:
                seen.add(key)
                cleaned.append(username)
        result['chat'] = {'room_history_limit': self._limit(chat.get('room_history_limit', 5)), 'blocked_users': cleaned}

        # aliases, hotkeys, and things that can send commands
        controls = candidate.get('controls', {})
        aliases = controls.get('aliases', DEFAULT_ALIASES)
        hotkeys = controls.get('hotkeys', DEFAULT_HOTKEYS)
        macros = controls.get('macros', [])
        if not isinstance(aliases, dict) or not isinstance(hotkeys, dict) or not isinstance(macros, list):
            raise SettingsError('Invalid controls configuration.')
        clean_aliases = {}
        for alias, command in aliases.items():
            alias = str(alias).casefold()
            if not ALIAS.fullmatch(alias) or not str(command).startswith('/'):
                raise SettingsError('Invalid command alias.')
            clean_aliases[alias] = str(command).casefold()
        clean_hotkeys = {str(action): self._hotkey(chord) for action, chord in hotkeys.items()}
        clean_macros = []
        macro_names = set()
        macro_aliases = set(clean_aliases)
        used_hotkeys = {chord.casefold() for chord in clean_hotkeys.values() if chord}
        for raw in macros:
            if not isinstance(raw, dict):
                raise SettingsError('Invalid macro.')
            name = str(raw.get('name', '')).strip()
            command = str(raw.get('command', '')).strip()
            alias = str(raw.get('alias', '')).strip().casefold()
            hotkey = self._hotkey(raw.get('hotkey', ''))
            button = bool(raw.get('button', False))
            if not name or name.casefold() in macro_names or not command or '\n' in command or '\r' in command or len(command.encode('utf-8')) > 400:
                raise SettingsError('Invalid macro name or command.')
            if alias and (not ALIAS.fullmatch(alias) or alias in macro_aliases):
                raise SettingsError('Macro alias is invalid or already used.')
            if hotkey and hotkey.casefold() in used_hotkeys:
                raise SettingsError('Hotkey is already used.')
            if not alias and not hotkey and not button:
                raise SettingsError('A macro needs an alias, hotkey, or button.')
            macro_names.add(name.casefold())
            if alias:
                macro_aliases.add(alias)
            if hotkey:
                used_hotkeys.add(hotkey.casefold())
            clean_macros.append({
                'id': str(raw.get('id') or uuid.uuid4()), 'name': name, 'command': command,
                'alias': alias, 'hotkey': hotkey, 'button': button,
                'confirm': bool(raw.get('confirm', False))
            })
        result['controls'] = {'aliases': clean_aliases, 'hotkeys': clean_hotkeys, 'macros': clean_macros}

        # sounds are data here; playback belongs somewhere else
        audio = candidate.get('audio', {})
        try:
            volume = max(0.0, min(float(audio.get('volume', 1.0)), 1.0))
        except (TypeError, ValueError):
            raise SettingsError('Invalid audio volume.')
        assets = audio.get('assets', [])
        triggers = audio.get('triggers', [])
        if not isinstance(assets, list) or not isinstance(triggers, list):
            raise SettingsError('Invalid audio configuration.')
        clean_assets = []
        asset_ids = set()
        for asset in assets:
            asset_id = str(asset.get('id', ''))
            extension = str(asset.get('extension', '')).lower()
            if not asset_id or extension not in VALID_AUDIO_EXTENSIONS:
                raise SettingsError('Invalid audio asset.')
            asset_ids.add(asset_id)
            clean_assets.append({'id': asset_id, 'name': str(asset.get('name', asset_id)), 'extension': extension})
        try:
            clean_triggers = normalize_triggers(triggers, asset_ids | BUILTIN_AUDIO_IDS)
        except ValueError as error:
            raise SettingsError(str(error))
        for trigger in clean_triggers:
            trigger['id'] = trigger['id'] or str(uuid.uuid4())
        result['audio'] = {'volume': volume, 'muted': bool(audio.get('muted', False)), 'assets': clean_assets, 'triggers': clean_triggers}
        return result

    @staticmethod
    def _limit(value):
        try:
            return max(1, min(int(value), 50))
        except (TypeError, ValueError):
            return 5

    @staticmethod
    def _hotkey(value):
        value = str(value or '').strip()
        if not value:
            return ''
        parts = value.split('+')
        if len(parts) < 2 or not any(part in {'Alt', 'Ctrl', 'Shift'} for part in parts[:-1]):
            raise SettingsError('Hotkeys require a modifier.')
        return '+'.join(parts)
