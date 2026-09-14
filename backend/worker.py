import asyncio
import json
import time
from . import config, db, schemas
from .agent import run_agent
from .provider import Provider, ModelUnavailable, ModelFailure
from .tools import Context, ToolError

async def process(task, provider=None):
    payload=json.loads(task['payload'])
    ctx=Context(task['user_id'],task['work_id'],task['id'],payload,provider or Provider())
    start=time.monotonic()
    try:
        prior=db.one('SELECT id,files FROM versions WHERE task_id=?',(task['id'],))
        if prior:
            result={'status':'completed','version_id':prior['id'],'files':json.loads(prior['files'])}
        elif task['kind']=='inspect':
            assets=ctx.assets()
            await ctx.execute('inspect_assets',{'asset_ids':[a['id'] for a in assets]})
            result=await ctx.execute('request_details',{'questions':['请核对每张素材的日期、地点与顺序；不记得的信息可以留白。']})
        elif task['kind']=='manual':
            if config.KIND=='card': await ctx.execute('render_card',payload['content'])
            else:
                await ctx.execute('update_album',payload['content'])
                await ctx.execute('render_album',{})
            result={'status':'completed',**ctx.completed}
        else:
            result=await run_agent(ctx)
        db.run('UPDATE tasks SET status=?,result=?,error=NULL,updated=? WHERE id=?',(result['status'],db.dumps(result),time.time(),task['id']))
        db.trace(task['id'],'task',ok=True,ms=int((time.monotonic()-start)*1000))
    except (ToolError,ModelFailure,ModelUnavailable) as e:
        db.run('UPDATE tasks SET status="failed",error=?,updated=? WHERE id=?',(str(e),time.time(),task['id']))
        db.trace(task['id'],'task',ok=False,code=type(e).__name__,ms=int((time.monotonic()-start)*1000))
    except Exception:
        db.run('UPDATE tasks SET status="failed",error=?,updated=? WHERE id=?',('处理失败，作品已保留，请重试。',time.time(),task['id']))
        db.trace(task['id'],'task',ok=False,code='internal_error',ms=int((time.monotonic()-start)*1000))

async def worker_loop():
    while True:
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM tasks WHERE status="queued" ORDER BY created LIMIT 1').fetchone()
            task=dict(row) if row else None
            if task:
                c.execute('UPDATE tasks SET status="running",attempts=attempts+1,updated=? WHERE id=?',(time.time(),task['id']))
        if task: await process(task)
        else: await asyncio.sleep(.4)

def recover():
    with db.connect() as c:
        c.execute('UPDATE tasks SET status="failed",error="重启恢复次数已达上限，请手动重试。" WHERE status IN ("running","queued") AND attempts>=?',(config.RETRIES+1,))
        c.execute('UPDATE tasks SET status="queued",updated=? WHERE status="running"',(time.time(),))
    # Files written before a crashed DB commit are not reachable and can be removed.
    import shutil
    for folder in config.DATA.glob('*/*'):
        if folder.is_dir() and folder.name!='assets' and not db.one('SELECT id FROM versions WHERE id=?',(folder.name,)):
            shutil.rmtree(folder,ignore_errors=True)
