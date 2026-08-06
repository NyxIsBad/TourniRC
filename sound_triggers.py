import regex


VALID_SCOPES = {'all', 'pm', 'match', 'channel'}


def trigger_errors(trigger, valid_asset_ids=None):
    """
    crashout central
    """
    if not isinstance(trigger, dict):
        return ['sound trigger must be an object.']
    errors = []
    if not str(trigger.get('name', '')).strip():
        errors.append('sound trigger needs a name.')
    mode = str(trigger.get('mode', 'literal'))
    pattern = str(trigger.get('pattern', ''))
    if mode not in {'literal', 'regex'}:
        errors.append('sound trigger mode must be literal or regex.')
    if not pattern or len(pattern) > 256:
        errors.append('sound trigger pattern must be between 1 and 256 characters.')
    if trigger.get('scope', 'all') not in VALID_SCOPES:
        errors.append('sound trigger has an invalid scope.')
    asset_id = str(trigger.get('asset_id', ''))
    if not asset_id or valid_asset_ids is not None and asset_id not in valid_asset_ids:
        errors.append('sound trigger references a missing asset.')
    if mode == 'regex' and pattern:
        try:
            regex.compile(pattern)
        except regex.error as error:
            errors.append(f'invalid regular expression: {error}')
    return errors


def normalize_triggers(triggers, valid_asset_ids=None):
    """
    make sure that triggers are reasonable
    """
    if not isinstance(triggers, list):
        raise ValueError('sound triggers must be a list.')
    result = []
    names = set()
    for raw in triggers:
        errors = trigger_errors(raw, valid_asset_ids)
        name = str(raw.get('name', '')).strip() if isinstance(raw, dict) else ''
        if name.casefold() in names:
            # because we actually index them this way
            errors.append('sound trigger names must be unique.')
        if errors:
            raise ValueError(errors[0])
        names.add(name.casefold())
        result.append({
            'id': str(raw.get('id', '')), 'name': name,
            'enabled': bool(raw.get('enabled', True)),
            'mode': str(raw.get('mode', 'literal')),
            'pattern': str(raw.get('pattern', '')),
            'case_sensitive': bool(raw.get('case_sensitive', False)),
            'sender': str(raw.get('sender', '')).strip(),
            'scope': str(raw.get('scope', 'all')),
            'asset_id': str(raw.get('asset_id', ''))
        })
    return result
