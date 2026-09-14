import json
import os
from pathlib import Path
import socket
import subprocess
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import config,db
from backend.main import app,attempts

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DATA',tmp_path)
    monkeypatch.setattr(db,'DATA',tmp_path)
    monkeypatch.setattr(config,'INVITE','test-invitation')
    monkeypatch.setattr(config,'MODEL_URL','https://model.test/v1')
    monkeypatch.setattr(config,'MODEL_KEY','test-not-a-real-key')
    monkeypatch.setattr(config,'MODEL_ID','test-model')
    monkeypatch.setattr(config,'OCR_ENABLED',False)
    attempts.clear(); db.init()

@pytest.fixture
def client():
    # No worker lifespan: each task is explicitly driven with an injected test model.
    c=TestClient(app,headers={'X-Requested-With':'studio'})
    assert c.post('/api/session',json={'invite':'test-invitation'}).status_code==200
    yield c
    c.close()

@pytest.fixture(scope='session')
def renderer_server():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    token='local-test-renderer'
    proc=subprocess.Popen(['node','renderer/server.mjs'],cwd=config.ROOT,env={**os.environ,'RENDER_PORT':str(port),'RENDER_TOKEN':token},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            try:
                if httpx.get(url+'/health',timeout=.4).status_code==200: break
            except httpx.TransportError: pass
            if proc.poll() is not None: raise RuntimeError('Renderer failed to start')
            time.sleep(.1)
        else: raise RuntimeError('Renderer unavailable')
        yield url,token
    finally:
        proc.terminate();proc.wait(timeout=10)

@pytest.fixture
def renderer(renderer_server,monkeypatch):
    url,token=renderer_server
    monkeypatch.setattr(config,'RENDER_URL',url);monkeypatch.setattr(config,'RENDER_TOKEN',token)
