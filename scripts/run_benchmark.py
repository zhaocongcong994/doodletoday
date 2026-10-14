#!/usr/bin/env python3
"""Run the 20-scenario model selection benchmark against a local DoodleToday backend.

Mirrors docs/评测/评测集-模型选型.csv. Per provider it creates 22 tasks
(17 creates + 2 create/revise pairs), polls each to completion, then saves
task traces, version contents and rendered PNGs under --out.
"""
import argparse
import json
import time
import urllib.request
import http.cookiejar
from pathlib import Path

MEMORY = '人工构造的日常样例。'
# case_id, states, revise_feedback, revise_style  (None = single-shot create)
CASES = [
    ('S01', ['困', '想出门', '不想社交'], None, None),
    ('S02', ['平静', '想独处', '满足'], None, None),
    ('S03', ['兴奋', '想创作', '有点饿'], None, None),
    ('S04', ['很困', '很期待', '不想加班'], None, None),
    ('S05', ['开心', '有点烦', '想散步'], None, None),
    ('S06', ['想见朋友', '不想讲话', '纠结'], None, None),
    ('S07', ['紧张', '想出发', '睡不着'], None, None),
    ('S08', ['放空', '想躺平', '随便'], None, None),
    ('S09', ['专注', '累', '轻松'], None, None),
    ('S10', ['想听雨', '懒洋洋', '想喝茶'], None, None),
    ('S11', ['酸痛', '开心', '想睡觉'], None, None),
    ('S12', ['好奇', '安静', '脑洞大开'], None, None),
    ('S13', ['期待', '害羞', '想打扮'], None, None),
    ('S14', ['灵感过载', '精力充沛', '不知先做什么'], None, None),
    ('S15', ['有点失落', '想走走', '不想解释'], None, None),
    ('S16', ['满足', '想吃甜的', '慢一点'], None, None),
    ('S17', ['想重新开始', '谨慎', '有盼头'], None, None),
    ('S18', ['困', '自由', '冷幽默'], '只改标题，副标题和标签保持上一版不变。', None),
    ('S19', ['清醒', '简洁', '有条理'], '把风格换成 neon（夜航霓虹）。', 'neon'),
    ('S20', ['中' * 20, '文' * 20, '字' * 20], None, None),
]
POLL_INTERVAL = 2
POLL_TIMEOUT = 720


class Client:
    def __init__(self, base, invite):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self._request('/api/session', {'invite': invite})

    def _request(self, path, data=None):
        payload = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={
            'Content-Type': 'application/json', 'X-Requested-With': 'studio'})
        with self.opener.open(req, timeout=60) as r:
            return json.loads(r.read())

    def get(self, path):
        return self._request(path)

    def post(self, path, data):
        return self._request(path, data)

    def poll(self, task_id):
        deadline = time.time() + POLL_TIMEOUT
        while time.time() < deadline:
            task = self.get(f'/api/tasks/{task_id}')
            if task['status'] in ('completed', 'failed'):
                return task
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(f'task {task_id} did not finish within {POLL_TIMEOUT}s')


def analyze(task):
    traces = task.get('traces') or []
    model = [t for t in traces if t['event'] == 'model']
    tools = [t for t in traces if t['event'] == 'tool']
    return {
        'status': task['status'],
        'rounds': len(model),
        'prompt_tokens': sum(t.get('prompt_tokens', 0) for t in model),
        'completion_tokens': sum(t.get('completion_tokens', 0) for t in model),
        'tool_calls': len(tools),
        'tool_failures': sum(1 for t in tools if not t.get('ok')),
        'tool_names': [t.get('tool') for t in tools],
        'error': task.get('error'),
        'duration_s': round((task['updated'] - task['created']), 1) if task.get('updated') else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', default='http://127.0.0.1:8101')
    ap.add_argument('--invite', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    health = json.loads(urllib.request.urlopen(args.api + '/api/health', timeout=10).read())
    if not health['model_ready']:
        raise SystemExit('model not configured on backend')
    print(f"health: {health}", flush=True)

    client = Client(args.api, args.invite)
    summary = []
    for case_id, states, feedback, style in CASES:
        record = {'case_id': case_id, 'states': states, 'tasks': []}
        try:
            created = client.post('/api/cards', {'states': states, 'memory': MEMORY})
            work_id = created['work_id']
            record['work_id'] = work_id
            first = client.poll(created['task_id'])
            record['tasks'].append({'phase': 'create', 'task_id': created['task_id'], **analyze(first)})
            if feedback and first['status'] == 'completed':
                revision = {'feedback': feedback}
                if style:
                    revision['style'] = style
                revised = client.post(f'/api/works/{work_id}/revise', revision)
                second = client.poll(revised['task_id'])
                record['tasks'].append({'phase': 'revise', 'task_id': revised['task_id'], **analyze(second)})
            work = client.get(f'/api/works/{work_id}')
            record['versions'] = [
                {'version_id': v['id'], 'content': v['content'], 'files': v['files']}
                for v in work['versions']
            ]
            for v in work['versions']:
                for name in v['files']:
                    if name.endswith('.png'):
                        dest = out / f"{case_id}-{v['id']}-{name}"
                        req = urllib.request.Request(
                            f"{args.api}/api/works/{work_id}/versions/{v['id']}/{name}",
                            headers={'X-Requested-With': 'studio'})
                        with client.opener.open(req, timeout=60) as r:
                            dest.write_bytes(r.read())
        except Exception as e:  # keep the run going; record the failure
            record['runner_error'] = f'{type(e).__name__}: {e}'
        summary.append(record)
        done = record['tasks'][-1]['status'] if record['tasks'] else 'runner_error'
        print(f"{case_id}: {done}", flush=True)
        (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))

    ok = sum(1 for r in summary if r['tasks'] and r['tasks'][-1]['status'] == 'completed')
    rounds = [r['tasks'][-1]['rounds'] for r in summary if r['tasks'] and r['tasks'][-1]['status'] == 'completed']
    pt = sum(t['prompt_tokens'] for r in summary for t in r['tasks'])
    ct = sum(t['completion_tokens'] for r in summary for t in r['tasks'])
    print(f"DONE {ok}/{len(summary)} completed; avg_rounds={sum(rounds) / max(len(rounds), 1):.2f}; "
          f"tokens prompt={pt} completion={ct}", flush=True)


if __name__ == '__main__':
    main()
