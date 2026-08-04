import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any


SENSITIVE_KEYS = {'password', 'token', 'irc_password'}


def _sanitize(value: Any, key: str = '') -> Any:
    """
    prevent logging passwords
    """
    if key.lower() in SENSITIVE_KEYS:
        return '[REDACTED]'
    if isinstance(value, dict):
        return {item_key: _sanitize(item, item_key) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    if isinstance(value, str) and value.lstrip().upper().startswith('PASS '):
        # raw irc gets the same treatment as structured fields
        return 'PASS [REDACTED]'
    if isinstance(value, BaseException):
        return {'type': value.__class__.__name__, 'message': str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class EventLog:
    """writes a bunch of json lines for actual events, unrelated to irc logs"""

    def __init__(self, name: str, filename: str):
        os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
        self.logger = logging.getLogger(f'tournirc.events.{name}')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            # three backups is enough evidence without eating the drive
            handler = RotatingFileHandler(
                filename, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
            )
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)

    def write(self, event: str, **fields: Any) -> None:
        # one event per line keeps this grep-friendly
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'process_id': os.getpid(),
            'event': event,
            **_sanitize(fields)
        }
        self.logger.info(json.dumps(record, ensure_ascii=False, separators=(',', ':')))
