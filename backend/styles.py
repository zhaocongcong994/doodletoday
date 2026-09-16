"""Trusted style registry shared by the API and the PNG renderer.

Only registry entries may become a card style.  A user-created style is a
validated recombination of server-owned layout primitives (base_layout +
palette + decorations + typography + copy_tone); it is snapshotted into each
version that uses it and must never be accepted as arbitrary CSS or renderer
input.
"""
import json
import re
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parents[1] / 'style-registry.json'
_REGISTRY = json.loads(_REGISTRY_PATH.read_text(encoding='utf-8'))
REGISTRY_VERSION = _REGISTRY['version']
STYLES = {style['id']: style for style in _REGISTRY['styles']}
STYLE_IDS = frozenset(STYLES)
CUSTOM_ID = re.compile(r'^u_[0-9a-f]{8}$')
MAX_CUSTOM_STYLES = 3
HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
TYPOGRAPHY = frozenset({'display-sans', 'editorial-serif', 'friendly-sans', 'mono-editorial'})
LAYOUT_DECORATIONS = {
    item['recipe']['base_layout']: frozenset(item['recipe']['decoration'])
    for item in _REGISTRY['styles']
}
LAYOUT_NAMES = {item['recipe']['base_layout']: item['name'] for item in _REGISTRY['styles']}

class StyleError(ValueError):
    pass

def require(style: str) -> str:
    if style not in STYLE_IDS and not CUSTOM_ID.match(style):
        raise ValueError('不支持该表达风格')
    return style

def validate_recipe(recipe) -> dict:
    """Whitelist a StyleRecipe payload; returns a normalized JSON-safe dict.

    Runs after pydantic field validation; rejects values that are well-formed
    but outside the server-owned vocabulary.
    """
    data = recipe.model_dump() if hasattr(recipe, 'model_dump') else dict(recipe)
    if data['base_layout'] not in LAYOUT_DECORATIONS:
        raise StyleError('不支持该布局原语')
    if data['typography'] not in TYPOGRAPHY:
        raise StyleError('不支持该字体角色')
    palette = [str(c).lower() for c in data['palette']]
    if any(not HEX_COLOR.match(c) for c in palette):
        raise StyleError('色板只接受 #rrggbb 颜色')
    allowed = LAYOUT_DECORATIONS[data['base_layout']]
    decoration = list(dict.fromkeys(data['decoration']))
    if any(d not in allowed for d in decoration):
        raise StyleError('该布局不支持所选装饰')
    return {'base_layout': data['base_layout'], 'palette': palette,
            'decoration': decoration, 'typography': data['typography'],
            'copy_tone': data['copy_tone']}

def _custom_row(style: str, user_id):
    from . import db
    return db.one('SELECT * FROM user_styles WHERE id=? AND user_id=?', (style, user_id)) if user_id else None

def resolve(style: str, user_id=None) -> dict:
    """Resolve a style id to its recipe for this user; builtin or owned custom."""
    if style in STYLE_IDS:
        item = STYLES[style]
        return {'name': item['name'], 'recipe': item['recipe']}
    row = _custom_row(style, user_id)
    if row:
        return {'name': row['name'], 'recipe': json.loads(row['recipe'])}
    raise StyleError('不支持该表达风格')

def snapshot(style: str, user_id=None) -> dict:
    """Immutable snapshot saved with each rendered card."""
    require(style)
    info = resolve(style, user_id)
    return {'id': style, 'name': info['name'], 'registry_version': REGISTRY_VERSION,
            'recipe': info['recipe']}

def context(user_id=None) -> list:
    """Small model-facing descriptions; visual implementation stays server-owned."""
    builtin = [{'id': item['id'], 'name': item['name'], 'description': item['description'],
                'copy_tone': item['recipe']['copy_tone']} for item in _REGISTRY['styles']]
    customs = []
    if user_id:
        from . import db
        for row in db.rows('SELECT * FROM user_styles WHERE user_id=? ORDER BY created', (user_id,)):
            recipe = json.loads(row['recipe'])
            customs.append({'id': row['id'], 'name': row['name'],
                            'description': f"自定义风格（{LAYOUT_NAMES[recipe['base_layout']]}布局）",
                            'copy_tone': recipe['copy_tone']})
    return builtin + customs

def custom_count(user_id) -> int:
    from . import db
    return db.one('SELECT COUNT(*) n FROM user_styles WHERE user_id=?', (user_id,))['n']

def fixed_name(base_layout: str, existing: set) -> str:
    """Deterministic name for model-created styles: 自定义·{布局名}[ 序号]。"""
    base = f"自定义·{LAYOUT_NAMES[base_layout]}"
    name, index = base, 2
    while name in existing:
        name = f'{base} {index}'
        index += 1
    return name
