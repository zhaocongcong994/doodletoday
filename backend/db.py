from contextlib import contextmanager
import sqlite3
import json
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

def trace(task_id, event, **detail):
    # Allowlisted numeric telemetry only. Never persist prompts, OCR, args or provider bodies.
    safe = {k: v for k, v in detail.items() if k in {'tool','ok','ms','round','prompt_tokens','completion_tokens','pages','code'}}
    run('INSERT INTO traces(task_id,event,detail,created) VALUES(?,?,?,?)', (task_id,event,dumps(safe),time.time()))
