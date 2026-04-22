import re
from dataclasses import dataclass
from typing import Optional


TEAM_NONE = 'none'
TEAM_RED = 'red'
TEAM_BLUE = 'blue'
VALID_TEAMS = {TEAM_NONE, TEAM_RED, TEAM_BLUE}


@dataclass(frozen=True)
class MatchEvent:
    kind: str
    username: Optional[str] = None
    team: Optional[str] = None
    match_id: Optional[str] = None
    match_name: Optional[str] = None
    value: Optional[str] = None
    seconds: Optional[int] = None
    slot: Optional[int] = None
    ready: Optional[bool] = None
    host: Optional[bool] = None
    mods: Optional[str] = None
    map_id: Optional[str] = None
    size: Optional[int] = None


# banchobot messages
CREATE_MATCH = re.compile(
    r'^Created the tournament match https://osu\.ppy\.sh/mp/(?P<match_id>[0-9]+)'
    r'(?:\s+(?P<match_name>.+))?$'
)
SLOT = re.compile(
    r'^Slot\s+[0-9]+\s+https://osu\.ppy\.sh/(?:u|users)/[0-9]+\s+'
    r'(?P<username>.+?)\s+\[(?P<status>[^\]]*)\]$',
    re.IGNORECASE
)
SETTINGS_SLOT = re.compile(
    r'^Slot\s+(?P<slot>[0-9]+)\s+(?P<ready>Ready|Not Ready)\s+'
    r'https://osu\.ppy\.sh/(?:u|users)/[0-9]+\s+(?P<username>[^\[]*?)'
    r'(?:\s+\[(?P<status>[^\]]*)\])?\s*$',
    re.IGNORECASE
)
JOIN_SLOT = re.compile(
    r'^(?P<username>.+?)\s+joined in slot\s+(?P<slot>[0-9]+)'
    r'(?:\s+for team\s+(?P<team>red|blue|none))?\.?$',
    re.IGNORECASE
)
CHANGE_TEAM = re.compile(
    r'^(?P<username>.+?)\s+changed to\s+(?P<team>red|blue|none)\.?$',
    re.IGNORECASE
)
# banchobot responses to !mp set
SET_MATCH = re.compile(r'^Changed match settings to (?P<settings>.+)$')
ROOM_INFO = re.compile(
    r'^Room name: (?P<name>.*), History: https://osu\.ppy\.sh/mp/(?P<match_id>[0-9]+)$'
)
TEAM_MODE = re.compile(
    r'^Team mode: (?P<team_mode>[^,]+), Win condition: (?P<win_condition>.+)$'
)
PLAYERS = re.compile(r'^Players: (?P<count>[0-9]+)$')
BEATMAP = re.compile(
    r'^(?:Beatmap:|Changed beatmap to) '
    r'(?:https://osu\.ppy\.sh/b/[0-9]+\s+)?(?P<beatmap>.+)$'
)
MODS = re.compile(
    r'^(?:(?:Active mods|Mods):|Changed (?:match |active )?mods to) (?P<mods>.+)$'
)
MOD_CHANGE = re.compile(r'^(?:Enabled|Disabled) .+$', re.IGNORECASE)
MATCH_SIZE = re.compile(r'^Changed match to size (?P<size>[0-9]+)$')
HOST = re.compile(r'^(?P<username>.+?) became the host\.$', re.IGNORECASE)
HOST_CHANGE = re.compile(r'^Changed match host to (?P<username>.+)$', re.IGNORECASE)
CLEAR_HOST = re.compile(r'^Cleared match host$', re.IGNORECASE)
ALL_READY = re.compile(r'^All players are ready$', re.IGNORECASE)
HOST_MAP = re.compile(r'^Host is changing map\.\.\.$', re.IGNORECASE)
HOST_BEATMAP = re.compile(
    r'^Beatmap changed to: (?P<beatmap>.+) '
    r'\(https://osu\.ppy\.sh/b/(?P<map_id>[0-9]+)\)$'
)
LEFT = re.compile(r'^(?P<username>.+?) left the game\.?$', re.IGNORECASE)
MATCH_START = re.compile(r'^Match starts in (?P<count>[0-9]+) seconds?$', re.IGNORECASE)
COUNTDOWN = re.compile(
    r'^Countdown ends in (?P<count>[0-9]+) (?P<unit>seconds?|minutes?)$',
    re.IGNORECASE
)


def normalize_username(username: str) -> str:
    """Convert BanchoBot's display form back to its IRC nickname form."""
    return username.strip().replace(' ', '_')


def parse_banchobot_message(content: str) -> Optional[MatchEvent]:
    """Parse a complete BanchoBot message without evaluating user-provided regex."""
    if not isinstance(content, str):
        return None

    create = CREATE_MATCH.fullmatch(content)
    if create:
        return MatchEvent(
            kind='create_match',
            match_id=create.group('match_id'),
            match_name=create.group('match_name')
        )

    settings_slot = SETTINGS_SLOT.fullmatch(content)
    if settings_slot:
        status = settings_slot.group('status') or ''
        team = re.search(r'\bTeam\s+(red|blue|none)\b', status, re.IGNORECASE)
        player_mods = re.sub(r'\bHost\b|\bTeam\s+(?:red|blue|none)\b', '', status, flags=re.IGNORECASE)
        player_mods = player_mods.replace('/', ' ').strip(' ,') or None
        return MatchEvent(
            kind='slot',
            username=normalize_username(settings_slot.group('username')),
            team=team.group(1).lower() if team else TEAM_NONE,
            slot=int(settings_slot.group('slot')),
            ready=settings_slot.group('ready').casefold() == 'ready',
            host=bool(re.search(r'\bHost\b', status, re.IGNORECASE)),
            mods=player_mods
        )

    slot = SLOT.fullmatch(content)
    if slot:
        team = re.search(r'\bTeam\s+(red|blue|none)\b', slot.group('status'), re.IGNORECASE)
        return MatchEvent(
            kind='slot',
            username=normalize_username(slot.group('username')),
            team=team.group(1).lower() if team else TEAM_NONE,
            host=bool(re.search(r'\bHost\b', slot.group('status'), re.IGNORECASE))
        )

    for kind, pattern in (
        ('join_slot', JOIN_SLOT),
        ('change_team', CHANGE_TEAM)
    ):
        match = pattern.fullmatch(content)
        if match:
            team = match.group('team').lower() if match.group('team') else TEAM_NONE
            if team not in VALID_TEAMS:
                return None
            return MatchEvent(
                kind=kind,
                username=normalize_username(match.group('username')),
                team=team,
                slot=int(match.group('slot')) if kind == 'join_slot' else None
            )

    match_settings = SET_MATCH.fullmatch(content)
    if match_settings:
        return MatchEvent(kind='set_match', value=match_settings.group('settings'))

    match_size = MATCH_SIZE.fullmatch(content)
    if match_size:
        return MatchEvent(kind='match_size', size=int(match_size.group('size')))

    for pattern in (HOST, HOST_CHANGE):
        host = pattern.fullmatch(content)
        if host:
            return MatchEvent(kind='host', username=normalize_username(host.group('username')))
    if CLEAR_HOST.fullmatch(content):
        return MatchEvent(kind='clear_host')
    if ALL_READY.fullmatch(content):
        return MatchEvent(kind='all_ready')
    if HOST_MAP.fullmatch(content):
        return MatchEvent(kind='host_map')
    host_beatmap = HOST_BEATMAP.fullmatch(content)
    if host_beatmap:
        return MatchEvent(
            kind='beatmap',
            value=host_beatmap.group('beatmap'),
            map_id=host_beatmap.group('map_id')
        )

    room_info = ROOM_INFO.fullmatch(content)
    if room_info:
        return MatchEvent(
            kind='room_info',
            match_id=room_info.group('match_id'),
            match_name=room_info.group('name')
        )

    team_mode = TEAM_MODE.fullmatch(content)
    if team_mode:
        return MatchEvent(
            kind='team_mode',
            team=team_mode.group('team_mode'),
            value=team_mode.group('win_condition')
        )

    players = PLAYERS.fullmatch(content)
    if players:
        return MatchEvent(kind='players', value=players.group('count'))

    for kind, pattern in (('beatmap', BEATMAP), ('mods', MODS)):
        match = pattern.fullmatch(content)
        if match:
            value = match.group(kind)
            map_id = None
            if kind == 'beatmap':
                map_url = re.search(r'osu\.ppy\.sh/b/([0-9]+)', content)
                map_id = map_url.group(1) if map_url else None
            return MatchEvent(kind=kind, value=value, map_id=map_id)

    if MOD_CHANGE.fullmatch(content):
        enabled = re.search(r'(?:^|, )enabled (?P<mods>.+?)(?:, disabled|$)', content, re.IGNORECASE)
        return MatchEvent(kind='mods', value=enabled.group('mods') if enabled else 'None')

    left = LEFT.fullmatch(content)
    if left:
        return MatchEvent(kind='leave', username=normalize_username(left.group('username')))

    match_start = MATCH_START.fullmatch(content)
    if match_start:
        return MatchEvent(kind='start_timer', seconds=int(match_start.group('count')))

    countdown = COUNTDOWN.fullmatch(content)
    if countdown:
        seconds = int(countdown.group('count'))
        if countdown.group('unit').lower().startswith('minute'):
            seconds *= 60
        return MatchEvent(kind='match_timer', seconds=seconds)

    if content.casefold() == 'countdown aborted':
        return MatchEvent(kind='countdown_abort')
    if content.casefold() == 'aborted the match':
        return MatchEvent(kind='match_abort')

    return None


def parse_match_message(user_name: str, content: str) -> Optional[MatchEvent]:
    """Only trusted BanchoBot messages may change match state."""
    if not isinstance(user_name, str) or user_name.casefold() != 'banchobot':
        return None
    return parse_banchobot_message(content)
