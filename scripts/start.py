#!/usr/bin/env python3
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[1]; os.chdir(root)
config=json.loads((root/'app.json').read_text()); children=[]
if (not (root/'.env').exists() and not (os.getenv('INVITE_CODE') and os.getenv('RENDER_TOKEN'))) or not (root/'.venv/bin/python').exists():
    raise SystemExit('请先运行 python3 scripts/setup.py')
if '--dev' not in sys.argv and not (root/'frontend/dist/index.html').exists():
    subprocess.run(['npm','run','build'],check=True)

def stop(*args):
    for child in children:
        if child.poll() is None: child.terminate()
    for child in children:
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill()
    raise SystemExit(0)

signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
commands=[['node','renderer/server.mjs'],[str(root/'.venv/bin/python'),'-m','uvicorn','backend.main:app','--host',os.getenv('API_HOST','127.0.0.1'),'--port',str(config['api_port']),'--no-access-log']]
if '--dev' in sys.argv: commands.append(['node','node_modules/vite/bin/vite.js','--config','frontend/vite.config.ts'])
for command in commands: children.append(subprocess.Popen(command))
print(f"{config['name']} → http://127.0.0.1:{config['web_port'] if '--dev' in sys.argv else config['api_port']}",flush=True)
try:
    while all(p.poll() is None for p in children): time.sleep(.5)
finally: stop()
