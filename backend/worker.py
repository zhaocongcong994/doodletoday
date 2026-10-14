import asyncio
import base64
import io
import json
import time
import httpx
from PIL import Image
from . import config, db, schemas, styles
from .agent import run_agent
from .provider import Provider, ModelUnavailable, ModelFailure
from .tools import Context, ToolError

SAMPLE_PREVIEW={'title':'今日精神状态','subtitle':'三个状态，一张封面，只记录此刻的自己。','tags':['状态一','状态二','状态三']}

async def render_preview(task,payload):
    content={**SAMPLE_PREVIEW,'style':'preview','style_snapshot':{'id':'preview','name':'风格预览','registry_version':styles.REGISTRY_VERSION,'recipe':payload['recipe']}}
    body={'kind':'card','content':content,'images':{}}
    pages=None
    for attempt in range(config.RETRIES+1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r=await client.post(config.RENDER_URL+'/render',headers={'X-Render-Token':config.RENDER_TOKEN},json=body)
                r.raise_for_status()
                pages=r.json()['pages']
                if len(pages)!=1: raise ValueError('page count mismatch')
                break
        except (httpx.HTTPError,ValueError,KeyError):
            if attempt==config.RETRIES: raise ToolError('渲染服务失败，请检查服务后重试') from None
            await asyncio.sleep(.3*(attempt+1))
    folder=config.DATA/'previews'/task['id']
    folder.mkdir(parents=True,exist_ok=True)
    data=base64.b64decode(pages[0],validate=True)
    im=Image.open(io.BytesIO(data)); im.verify()
    if im.size!=(1080,1440) or im.format!='PNG': raise ToolError('渲染尺寸或格式无效')
    (folder/'page-01.png').write_bytes(data)
    return {'status':'completed','files':['page-01.png']}

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
        elif task['kind']=='preview':
            result=await render_preview(task,payload)
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
