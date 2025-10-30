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


# banchobot messages
CREATE_MATCH = re.compile(
    r'^Created the tournament match https://osu\.ppy\.sh/mp/(?P<match_id>[0-9]+)'
    r'(?:\s+(?P<match_name>.+))?$'
)
SLOT = re.compile(
    r'^Slot\s+[0-9]+\s+https://osu\.ppy\.sh/(?:u|users)/[0-9]+\s+'
    r'(?P<username>.+?)\s+\[.*?\bTeam\s+(?P<team>red|blue|none)\b.*\]$',
    re.IGNORECASE
)
JOIN_SLOT = re.compile(
    r'^(?P<username>.+?)\s+joined in slot\s+[0-9]+\s+for team\s+'
    r'(?P<team>red|blue|none)\.?$',
    re.IGNORECASE
)
CHANGE_TEAM = re.compile(
    r'^(?P<username>.+?)\s+changed to\s+(?P<team>red|blue|none)\.?$',
    re.IGNORECASE
)
# banchobot responses to !mp set
SET_MATCH = re.compile(r'^Changed match settings to (?P<settings>.+)$')


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

    for kind, pattern in (
        ('slot', SLOT),
        ('join_slot', JOIN_SLOT),
        ('change_team', CHANGE_TEAM)
    ):
        match = pattern.fullmatch(content)
        if match:
            team = match.group('team').lower()
            if team not in VALID_TEAMS:
                return None
            return MatchEvent(
                kind=kind,
                username=normalize_username(match.group('username')),
                team=team
            )

    match_settings = SET_MATCH.fullmatch(content)
    if match_settings:
        return MatchEvent(kind='set_match')

    return None


def parse_match_message(user_name: str, content: str) -> Optional[MatchEvent]:
    """Only trusted BanchoBot messages may change match state."""
    if not isinstance(user_name, str) or user_name.casefold() != 'banchobot':
        return None
    return parse_banchobot_message(content)
