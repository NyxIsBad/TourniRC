import copy
import re
import uuid
from sound_triggers import trigger_errors


COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
DESIGNATOR = re.compile(r'^[A-Za-z0-9_-]+$')
MODS = {
    'NM': 'No Mod', 'EZ': 'Easy', 'NF': 'No Fail', 'HT': 'Half Time',
    'HR': 'Hard Rock', 'SD': 'Sudden Death', 'PF': 'Perfect',
    'DT': 'Double Time', 'NC': 'Nightcore', 'HD': 'Hidden',
    'FI': 'Fade In', 'FL': 'Flashlight', 'RL': 'Relax',
    'AP': 'Autopilot', 'SO': 'Spun Out',
    '1K': '1 Key', '2K': '2 Keys', '3K': '3 Keys',
    '4K': '4 Keys', '5K': '5 Keys', '6K': '6 Keys',
    '7K': '7 Keys', '8K': '8 Keys', '9K': '9 Keys',
    'CP': 'Co-op', 'MR': 'Mirror', 'RD': 'Random',
    'AT': 'Auto', 'CM': 'Cinema', 'SV2': 'ScoreV2',
    'TP': 'Target Practice'
}


def new_tournament(name='New Tournament'):
    return {
        'id': str(uuid.uuid4()), 'name': name,
        'color': '#7c3aed', 'timer': 120, 'start_timer': 10,
        'mappools': {}, 'mappool_order': [], 'sound_triggers': [],
        'score_calculation': {
            'enabled': False,
            'mod_multipliers': {mod: 1.0 for mod in MODS}
        }
    }


def validate_tournament(value):
    errors = []
    if not isinstance(value, dict):
        return ['tournament must be an object.']
    if not str(value.get('id', '')).strip():
        errors.append('tournament id is required.')
    else:
        try:
            if str(uuid.UUID(str(value['id']))) != str(value['id']):
                raise ValueError
        except (ValueError, AttributeError):
            errors.append('tournament id must be a canonical UUID.')
    if not str(value.get('name', '')).strip():
        errors.append('tournament name is required.')
    if not COLOR.fullmatch(str(value.get('color', ''))):
        errors.append('color must use #RRGGBB.')
    for key, label in (('timer', 'timer'), ('start_timer', 'start timer')):
        try:
            if int(value.get(key, 0)) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f'{label} must be positive.')

    pools = value.get('mappools', {})
    order = value.get('mappool_order', [])
    if not isinstance(pools, dict) or not isinstance(order, list):
        return errors + ['mappools and mappool order are invalid.']
    if set(order) != set(pools) or len(order) != len(set(order)):
        errors.append('mappool order must contain every pool exactly once.')
    pool_names = set()
    valid_maps = 0
    for pool_id, pool in pools.items():
        if not isinstance(pool, dict) or str(pool.get('id', '')) != pool_id:
            errors.append(f'mappool {pool_id} has an invalid id.')
            continue
        name = str(pool.get('name', '')).strip()
        if not name or name.casefold() in pool_names:
            errors.append('mappool names must be present and unique.')
        pool_names.add(name.casefold())
        maps = pool.get('maps', {})
        map_order = pool.get('map_order', [])
        if not isinstance(maps, dict) or not isinstance(map_order, list) or set(map_order) != set(maps) or len(map_order) != len(set(map_order)):
            errors.append(f'{name or pool_id} has an invalid map order.')
        if not isinstance(maps, dict):
            continue
        designators = set()
        for map_id, beatmap in maps.items():
            if not isinstance(beatmap, dict) or str(beatmap.get('id', '')) != map_id:
                errors.append(f'{name or pool_id} has a map with an invalid id.')
                continue
            designator = str(beatmap.get('designator', '')).strip()
            if not DESIGNATOR.fullmatch(designator) or designator.casefold() in designators:
                errors.append(f'{name or pool_id} has an invalid or duplicate designator.')
            designators.add(designator.casefold())
            osu_map_id = beatmap.get('map_id')
            if osu_map_id is not None and osu_map_id != '':
                try:
                    if int(osu_map_id) <= 0:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append(f'{designator or "map"} has an invalid map id.')
            mods = beatmap.get('mods', [])
            if not isinstance(mods, list) or not all(isinstance(mod, str) and mod.strip() for mod in mods):
                errors.append(f'{designator or "map"} has invalid display mods.')
            if not isinstance(beatmap.get('map_command'), str) or not beatmap['map_command'].strip():
                errors.append(f'{designator or "map"} needs a map command.')
            if not isinstance(beatmap.get('mods_command'), str) or not beatmap['mods_command'].strip():
                errors.append(f'{designator or "map"} needs a mods command.')
            valid_maps += 1
    if not pools or valid_maps == 0:
        errors.append('at least one mappool with one map is required.')
    score = value.get('score_calculation', {})
    if not isinstance(score, dict) or not isinstance(score.get('mod_multipliers'), dict):
        errors.append('score calculation settings are invalid.')
    else:
        multipliers = score['mod_multipliers']
        if set(multipliers) != set(MODS):
            errors.append('score calculation needs one multiplier for every mod.')
        for multiplier in multipliers.values():
            try:
                if multiplier == '' or float(multiplier) <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append('mod multipliers must be nonempty numbers above zero.')
                break
    triggers = value.get('sound_triggers', [])
    if not isinstance(triggers, list):
        errors.append('sound triggers must be a list.')
    else:
        names = set()
        for trigger in triggers:
            errors.extend(trigger_errors(trigger))
            name = str(trigger.get('name', '')).strip().casefold() if isinstance(trigger, dict) else ''
            if name in names:
                errors.append('sound trigger names must be unique.')
            names.add(name)
    return errors


def normalize_tournament(value):
    result = copy.deepcopy(value)
    result['id'] = str(result.get('id') or uuid.uuid4())
    result['name'] = str(result.get('name', '')).strip()
    result['color'] = str(result.get('color', '#7c3aed'))
    for key, fallback in (('timer', 120), ('start_timer', 10)):
        try:
            result[key] = int(result.get(key, fallback))
        except (TypeError, ValueError):
            result[key] = 0
    result.setdefault('mappools', {})
    result.setdefault('mappool_order', list(result['mappools']))
    result.setdefault('sound_triggers', [])
    result.setdefault('score_calculation', {
        'enabled': False,
        'mod_multipliers': {mod: 1.0 for mod in MODS}
    })
    return result
