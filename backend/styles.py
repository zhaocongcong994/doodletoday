"""Trusted style registry shared by the API and the PNG renderer.

Only registry entries may become a card style.  A future user-created style is
stored as a separately validated recipe and will be snapshotted into a version;
it must never be accepted as arbitrary CSS or renderer input.
"""
import json
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parents[1] / 'style-registry.json'
_REGISTRY = json.loads(_REGISTRY_PATH.read_text(encoding='utf-8'))
REGISTRY_VERSION = _REGISTRY['version']
STYLES = {style['id']: style for style in _REGISTRY['styles']}
STYLE_IDS = frozenset(STYLES)

def require(style: str) -> str:
    if style not in STYLE_IDS:
        raise ValueError('不支持该表达风格')
    return style

def snapshot(style: str) -> dict:
    """Return an immutable, JSON-safe snapshot saved with each rendered card."""
    require(style)
    item = STYLES[style]
    return {
        'id': item['id'],
        'name': item['name'],
        'registry_version': REGISTRY_VERSION,
        'recipe': item['recipe'],
    }

def context() -> list[dict]:
    """Small model-facing descriptions; visual implementation stays server-owned."""
    return [
        {'id': item['id'], 'name': item['name'], 'description': item['description'], 'copy_tone': item['recipe']['copy_tone']}
        for item in _REGISTRY['styles']
    ]
