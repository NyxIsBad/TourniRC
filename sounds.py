import mimetypes
import re
import uuid
from pathlib import Path

try:
    # this one has timeouts; stdlib re is the emergency spare
    import regex as safe_regex
except ImportError:
    safe_regex = None

from settings import BUILTIN_AUDIO_IDS, VALID_AUDIO_EXTENSIONS, normalize_username


BUILTIN_SOUNDS = [asset_id.split(':', 1)[1] for asset_id in sorted(BUILTIN_AUDIO_IDS)]


def asset_url(asset_id):
    if asset_id.startswith('builtin:'):
        return f'/static/sounds/{asset_id.split(":", 1)[1]}'
    return f'/sounds/{asset_id}'


def available_assets(settings):
    # builtins are read-only, uploads are very much not
    builtins = [
        {'id': f'builtin:{name}', 'name': name, 'builtin': True, 'url': asset_url(f'builtin:{name}')}
        for name in BUILTIN_SOUNDS
    ]
    custom = [dict(asset, builtin=False, url=asset_url(asset['id'])) for asset in settings['audio']['assets']]
    return builtins + custom


def message_scope(channel, channel_type):
    if channel_type == 2:
        return 'pm'
    if str(channel).casefold().startswith('#mp_'):
        return 'match'
    return 'channel'


def matching_sounds(settings, sender, content, channel, channel_type):
    audio = settings['audio']
    if audio['muted'] or audio['volume'] <= 0:
        return []
    scope = message_scope(channel, channel_type)
    matches = []
    for trigger in audio['triggers']:
        # cheap filters first, regex last
        if not trigger['enabled'] or trigger['scope'] not in {'all', scope}:
            continue
        if trigger['sender'] and normalize_username(trigger['sender']) != normalize_username(sender):
            continue
        source = content if trigger['case_sensitive'] else content.casefold()
        pattern = trigger['pattern'] if trigger['case_sensitive'] else trigger['pattern'].casefold()
        try:
            if trigger['mode'] == 'literal':
                matched = pattern in source
            elif safe_regex:
                flags = 0 if trigger['case_sensitive'] else safe_regex.IGNORECASE
                matched = safe_regex.search(trigger['pattern'], content, flags=flags, timeout=.02) is not None
            else:
                flags = 0 if trigger['case_sensitive'] else re.IGNORECASE
                matched = re.search(trigger['pattern'], content, flags=flags) is not None
        except Exception:
            # an alert regex does not get to take down chat
            matched = False
        if matched:
            matches.append({'id': trigger['asset_id'], 'url': asset_url(trigger['asset_id']), 'volume': audio['volume']})
    return matches


class SoundStore:
    def __init__(self, directory='cfg/sounds'):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, upload):
        # never trust the browser's filename or mime type on its own
        name = Path(upload.filename or '').name
        extension = Path(name).suffix.lower()
        if extension not in VALID_AUDIO_EXTENSIONS:
            raise ValueError('Only MP3, WAV, and OGG files are supported.')
        upload.stream.seek(0, 2)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size <= 0 or size > 5 * 1024 * 1024:
            raise ValueError('Sound files must be between 1 byte and 5 MB.')
        mime = (upload.mimetype or mimetypes.guess_type(name)[0] or '').casefold()
        if not (mime.startswith('audio/') or mime == 'application/ogg'):
            raise ValueError('The uploaded file is not recognized as audio.')
        asset_id = str(uuid.uuid4())
        upload.save(self.directory / f'{asset_id}{extension}')
        return {'id': asset_id, 'name': name, 'extension': extension}

    def path_for(self, asset):
        # uuids should make traversal impossible. still checking.
        path = (self.directory / f'{asset["id"]}{asset["extension"]}').resolve()
        if self.directory.resolve() not in path.parents:
            raise ValueError('Invalid sound path.')
        return path

    def delete(self, asset):
        path = self.path_for(asset)
        if path.exists():
            path.unlink()
