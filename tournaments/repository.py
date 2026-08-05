import copy
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from .validation import new_tournament, normalize_tournament, validate_tournament


class TournamentError(ValueError):
    pass


class TournamentRepository:
    def __init__(self, root='cfg/tournaments'):
        self.root = Path(root)
        self.presets = self.root / 'presets'
        self.state_path = self.root / 'state.json'
        self.items = {}
        self.enabled = False
        self.presets.mkdir(parents=True, exist_ok=True)
        self.load()

    @staticmethod
    def _write(path, value):
        handle, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as file:
                json.dump(value, file, ensure_ascii=False, indent=2)
                file.write('\n')
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _backup(self, path):
        backup = path.with_name(f'{path.stem}.invalid-{int(time.time())}{path.suffix}')
        try:
            shutil.copy2(path, backup)
        except OSError:
            pass

    def load(self):
        self.items = {}
        for path in self.presets.glob('*.json'):
            if '.invalid-' in path.stem:
                continue
            try:
                value = normalize_tournament(json.loads(path.read_text(encoding='utf-8')))
                if str(uuid.UUID(path.stem)) != path.stem or value['id'] != path.stem:
                    raise ValueError('preset filename and tournament id do not match')
                self.items[value['id']] = value
            except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError):
                self._backup(path)
        try:
            state = json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
            self.enabled = bool(state.get('enabled', False)) and bool(self.valid_items())
        except (OSError, ValueError, json.JSONDecodeError):
            self._backup(self.state_path)
            self.enabled = False
        self.save_state()

    def save_state(self):
        self._write(self.state_path, {'enabled': self.enabled})

    def list(self):
        return [self.describe(item) for item in sorted(self.items.values(), key=lambda item: item['name'].casefold())]

    def describe(self, item):
        errors = validate_tournament(item)
        return {**copy.deepcopy(item), 'valid': not errors, 'errors': errors}

    def get(self, tournament_id):
        item = self.items.get(tournament_id)
        return self.describe(item) if item else None

    def valid_items(self):
        return [item for item in self.items.values() if not validate_tournament(item)]

    def save(self, value):
        item = normalize_tournament(value)
        try:
            tournament_id = str(uuid.UUID(item['id']))
        except (ValueError, AttributeError, TypeError):
            raise TournamentError('tournament id must be a UUID.')
        if tournament_id != item['id']:
            raise TournamentError('tournament id must be a canonical UUID.')
        if any(other['name'].casefold() == item['name'].casefold() and other_id != item['id'] for other_id, other in self.items.items()):
            raise TournamentError('tournament names must be unique.')
        self.items[item['id']] = item
        self._write(self.presets / f'{tournament_id}.json', item)
        if self.enabled and not self.valid_items():
            self.enabled = False
            self.save_state()
        return self.describe(item)

    def create(self):
        base = 'New Tournament'
        names = {item['name'].casefold() for item in self.items.values()}
        name = base
        index = 2
        while name.casefold() in names:
            name = f'{base} {index}'
            index += 1
        return self.save(new_tournament(name))

    def duplicate(self, tournament_id):
        source = self.items.get(tournament_id)
        if not source:
            raise TournamentError('tournament not found.')
        duplicate = copy.deepcopy(source)
        duplicate['id'] = str(uuid.uuid4())
        base = f'{source["name"]} Copy'
        names = {item['name'].casefold() for item in self.items.values()}
        duplicate['name'] = base
        index = 2
        while duplicate['name'].casefold() in names:
            duplicate['name'] = f'{base} {index}'
            index += 1
        return self.save(duplicate)

    def delete(self, tournament_id):
        try:
            tournament_id = str(uuid.UUID(tournament_id))
        except (ValueError, AttributeError, TypeError):
            raise TournamentError('tournament id must be a UUID.')
        if tournament_id not in self.items:
            raise TournamentError('tournament not found.')
        self.items.pop(tournament_id)
        path = self.presets / f'{tournament_id}.json'
        if path.exists():
            path.unlink()
        if self.enabled and not self.valid_items():
            self.enabled = False
            self.save_state()

    def set_enabled(self, enabled):
        if enabled and not self.valid_items():
            raise TournamentError('create a valid tournament before enabling tournaments.')
        self.enabled = bool(enabled)
        self.save_state()
        return self.enabled
