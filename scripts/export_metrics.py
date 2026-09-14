#!/usr/bin/env python3
"""Export current project's numeric trial telemetry; excludes user text and images."""
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import db

db.init()
w=csv.writer(sys.stdout);w.writerow(['task_id','kind','status','elapsed_ms','prompt_tokens','completion_tokens','tool_failures','export_requests','pages'])
for task in db.rows('SELECT * FROM tasks ORDER BY created'):
    totals=dict(elapsed_ms=0,prompt_tokens=0,completion_tokens=0,tool_failures=0,export_requests=0,pages=0)
    for t in db.rows('SELECT event,detail FROM traces WHERE task_id=?',(task['id'],)):
        detail=json.loads(t['detail'])
        if t['event']=='model':
            for key in ['prompt_tokens','completion_tokens']: totals[key]+=detail.get(key,0)
        if t['event']=='tool' and not detail.get('ok'):totals['tool_failures']+=1
        if t['event']=='task':totals['elapsed_ms']=detail.get('ms',0)
        if t['event']=='render':totals['pages']=detail.get('pages',0)
        if t['event']=='export':totals['export_requests']+=1
    w.writerow([task['id'],task['kind'],task['status'],*totals.values()])
