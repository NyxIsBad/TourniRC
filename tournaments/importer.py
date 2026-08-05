import re
import uuid


MAP_ID = re.compile(r'^!mp\s+map\s+([0-9]+)(?:\s|$)', re.IGNORECASE)
ENTRY = re.compile(
    r'(?is)(?P<designator>\S+)\s+'
    r'(?P<mods>!mp mods\b.*?)(?=\s+!mp map\b)\s+'
    r'(?P<map>!mp map\b.*?)(?=\s+\S+\s+!mp mods\b|\s*$)'
)


def parse_mappool_text(value):
    if not isinstance(value, str):
        raise ValueError('mappool import must be text.')
    if not value.strip():
        raise ValueError('paste at least one map.')
    maps = []
    position = 0
    for match in ENTRY.finditer(value):
        if value[position:match.start()].strip():
            raise ValueError('expected a designator, !mp mods command, and !mp map command.')
        designator = match.group('designator').strip()
        mods_command = match.group('mods').strip()
        map_command = match.group('map').strip()
        found_id = MAP_ID.match(map_command)
        maps.append({
            'id': str(uuid.uuid4()), 'designator': designator,
            'map_command': map_command, 'mods_command': mods_command,
            'name': '', 'map_id': int(found_id.group(1)) if found_id else None,
            'mods': []
        })
        position = match.end()
    if not maps or value[position:].strip():
        raise ValueError('expected a designator, !mp mods command, and !mp map command.')
    return maps
