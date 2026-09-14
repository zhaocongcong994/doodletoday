from contextlib import contextmanager
import sqlite3
import json
import shutil
import time
import uuid
from .config import DATA

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS works (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, input TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS versions (id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE, content TEXT NOT NULL, files TEXT NOT NULL, created REAL NOT NULL, task_id TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE, hash TEXT NOT NULL, position INTEGER NOT NULL, meta TEXT NOT NULL, UNIQUE(work_id,hash));
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE, user_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS preferences (user_id TEXT PRIMARY KEY, style TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quota (user_id TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL, PRIMARY KEY(user_id,day));
CREATE TABLE IF NOT EXISTS invite_activations (user_id TEXT PRIMARY KEY, invite TEXT NOT NULL, activated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS traces (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE, event TEXT NOT NULL, detail TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS works_owner ON works(user_id);
CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status,created);
'''

@contextmanager
def connect():
    c = sqlite3.connect(DATA / 'studio.sqlite', timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()

def init():
    with connect() as c:
        c.executescript(SCHEMA)

def uid():
    return uuid.uuid4().hex

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)

def one(sql, args=()):
    with connect() as c:
        row = c.execute(sql, args).fetchone()
        return dict(row) if row else None

def rows(sql, args=()):
    with connect() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]

def run(sql, args=()):
    with connect() as c:
        c.execute(sql, args)

def merge_user(old_user_id: str, new_user_id: str):
    """Move an old browser-local account into its invite workspace.

    Older sessions used random user IDs.  On the first re-login after the
    stable invite identity is enabled, migrate all user-owned data in one
    transaction so existing works remain available on every device.
    """
    if not old_user_id or old_user_id == new_user_id:
        return
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('UPDATE works SET user_id=? WHERE user_id=?', (new_user_id, old_user_id))
        c.execute('UPDATE tasks SET user_id=? WHERE user_id=?', (new_user_id, old_user_id))
        c.execute('UPDATE sessions SET user_id=? WHERE user_id=?', (new_user_id, old_user_id))

        # Keep the workspace preference if it already exists; otherwise carry
        # over the old browser's choice.
        c.execute(
            'INSERT OR IGNORE INTO preferences(user_id,style) '
            'SELECT ?,style FROM preferences WHERE user_id=?',
            (new_user_id, old_user_id),
        )
        c.execute('DELETE FROM preferences WHERE user_id=?', (old_user_id,))

        # Quota is a shared workspace limit. Merge usage rather than allowing
        # two old browser accounts to double the daily allowance.
        for row in c.execute('SELECT day,used FROM quota WHERE user_id=?', (old_user_id,)).fetchall():
            c.execute(
                'INSERT INTO quota(user_id,day,used) VALUES(?,?,?) '
                'ON CONFLICT(user_id,day) DO UPDATE SET used=used+excluded.used',
                (new_user_id, row['day'], row['used']),
            )
        c.execute('DELETE FROM quota WHERE user_id=?', (old_user_id,))

def purge_user(user_id: str):
    """Delete everything an expired invite workspace owns, including files on disk.

    Works cascade to versions/assets/tasks/traces through foreign keys. The
    invite_activations row is kept so an expired code cannot restart its
    two-day window by deleting and re-entering.
    """
    ids = [r['id'] for r in rows('SELECT id FROM works WHERE user_id=?', (user_id,))]
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM works WHERE user_id=?', (user_id,))
        c.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        c.execute('DELETE FROM preferences WHERE user_id=?', (user_id,))
        c.execute('DELETE FROM quota WHERE user_id=?', (user_id,))
    for wid in ids:
        shutil.rmtree(DATA / wid, ignore_errors=True)

def trace(task_id, event, **detail):
    # Allowlisted numeric telemetry only. Never persist prompts, OCR, args or provider bodies.
    safe = {k: v for k, v in detail.items() if k in {'tool','ok','ms','round','prompt_tokens','completion_tokens','pages','code'}}
    run('INSERT INTO traces(task_id,event,detail,created) VALUES(?,?,?,?)', (task_id,event,dumps(safe),time.time()))
