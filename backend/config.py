from pathlib import Path
import json
import hashlib
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
APP = json.loads((ROOT / 'app.json').read_text())
KIND = APP['kind']
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
os.chmod(DATA, 0o700)
INVITE = os.getenv('INVITE_CODE', '')
EXTRA_INVITES = tuple(code.strip() for code in os.getenv('INVITE_CODES', '').split(',') if code.strip())
COOKIE = 'studio_' + KIND
SECURE_COOKIE = os.getenv('SECURE_COOKIE', 'false').lower() == 'true'
MODEL_URL = os.getenv('MODEL_BASE_URL', '').rstrip('/')
MODEL_KEY = os.getenv('MODEL_API_KEY', '')
MODEL_ID = os.getenv('MODEL_ID', '')
MODEL_TIMEOUT = float(os.getenv('MODEL_TIMEOUT', '45'))
MAX_ROUNDS = int(os.getenv('MAX_ROUNDS', '8'))
RETRIES = int(os.getenv('MAX_RETRIES', '2'))
DAILY_LIMIT = int(os.getenv('DAILY_LIMIT', '20'))
INVITE_TTL = int(os.getenv('INVITE_TTL_DAYS', '2')) * 86400
PERMANENT_INVITES = frozenset(code.strip() for code in os.getenv('PERMANENT_INVITES', 'zcc-code').split(',') if code.strip())
PERMANENT_EXPIRY = 99999999999.0  # zcc-code 等长期口令不设过期（约 5138 年）
RENDER_URL = os.getenv('RENDER_URL', f"http://127.0.0.1:{APP['render_port']}")
RENDER_TOKEN = os.getenv('RENDER_TOKEN', '')
OCR_ENABLED = os.getenv('OCR_ENABLED', 'false').lower() == 'true'
OCR_TIMEOUT = float(os.getenv('OCR_TIMEOUT', '180'))

def model_ready():
    return bool(MODEL_URL and MODEL_KEY and MODEL_ID)

def invites():
    """Return configured invite codes without changing the legacy .env key."""
    return tuple(code.strip() for code in (INVITE, *EXTRA_INVITES) if code.strip())

def user_id_for_invite(invite: str) -> str:
    """Return the stable workspace identity represented by an invite code.

    The invite is intentionally the workspace key: every device that enters
    the same code should see the same works.  Keep this deterministic across
    restarts and deployments so the workspace does not move when a cookie is
    lost.
    """
    return hashlib.sha256(f'doodletoday:invite:{invite}'.encode()).hexdigest()[:32]
