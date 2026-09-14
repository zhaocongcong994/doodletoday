import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
import hashlib
import hmac
import io
import json
import secrets
import shutil
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from . import config, db, schemas
from .tools import save_preference
from .worker import worker_loop, recover

Image.MAX_IMAGE_PIXELS=25_000_000

@asynccontextmanager
async def lifespan(app):
    db.init(); recover()
    worker=asyncio.create_task(worker_loop())
    yield
    worker.cancel()
    with suppress(asyncio.CancelledError): await worker

app=FastAPI(title=config.APP['name'],lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url='/api/openapi.json')
attempts=defaultdict(deque)

@app.middleware('http')
async def boundaries(request,call_next):
    if request.url.path.startswith('/api') and request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if request.headers.get('x-requested-with')!='studio' or (origin and urlsplit(origin).netloc!=request.headers.get('host')):
            return JSONResponse({'detail':'请从同源页面操作'},status_code=403)
        length=request.headers.get('content-length','0')
        if not length.isdigit() or int(length)>105_000_000:
            return JSONResponse({'detail':'请求过大'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control']='no-store'
    else:
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return response

def user(request:Request):
    raw=request.cookies.get(config.COOKIE,'')
    token=hashlib.sha256(raw.encode()).hexdigest()
    row=db.one('SELECT user_id FROM sessions WHERE token=? AND expires>?',(token,time.time()))
    if not row: raise HTTPException(401,'请先输入邀请口令')
    return row['user_id']

def own(work_id,user_id):
    row=db.one('SELECT * FROM works WHERE id=? AND user_id=?',(work_id,user_id))
    if not row: raise HTTPException(404,'作品不存在')
    return row

def kind(expected):
    if config.KIND!=expected: raise HTTPException(404,'接口不存在')

def require_model():
    if not config.model_ready(): raise HTTPException(503,'模型尚未配置，暂时无法生成。请在项目 .env 配置模型后重启。')

def idle(work_id):
    if db.one('SELECT id FROM tasks WHERE work_id=? AND status IN ("queued","running")',(work_id,)):
        raise HTTPException(409,'作品仍在处理中，请完成后再操作')

def quota(c,user_id):
    day=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    c.execute('INSERT OR IGNORE INTO quota VALUES(?,?,0)',(user_id,day))
    row=c.execute('SELECT used FROM quota WHERE user_id=? AND day=?',(user_id,day)).fetchone()
    if row['used']>=config.DAILY_LIMIT: raise HTTPException(429,'今日生成额度已用完，请明天再来')
    c.execute('UPDATE quota SET used=used+1 WHERE user_id=? AND day=?',(user_id,day))

def enqueue(work_id,user_id,task_kind,payload,c=None):
    if c is None:
        with db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            return enqueue(work_id,user_id,task_kind,payload,conn)
    if c.execute('SELECT id FROM tasks WHERE work_id=? AND status IN ("queued","running")',(work_id,)).fetchone():
        raise HTTPException(409,'作品仍在处理中')
    if task_kind!='inspect': quota(c,user_id)
    c.execute('UPDATE tasks SET status="superseded",updated=? WHERE work_id=? AND status="awaiting_details"',(time.time(),work_id))
    task_id=db.uid(); now=time.time()
    c.execute('INSERT INTO tasks(id,work_id,user_id,kind,status,payload,created,updated) VALUES(?,?,?,?,?,?,?,?)',(task_id,work_id,user_id,task_kind,'queued',db.dumps(payload),now,now))
    return {'work_id':work_id,'task_id':task_id}

@app.get('/api/health')
def health():
    return {'name':config.APP['name'],'kind':config.KIND,'model_ready':config.model_ready(),'ocr_enabled':config.OCR_ENABLED,'invite_ready':bool(config.invites())}

@app.post('/api/session')
def login(body:schemas.Login,request:Request,response:Response):
    ip=request.client.host if request.client else 'local'
    now=time.time(); bucket=attempts[ip]
    while bucket and bucket[0]<now-300: bucket.popleft()
    if len(bucket)>=10: raise HTTPException(429,'尝试过于频繁，请 5 分钟后再试')
    codes=config.invites()
    if not codes: raise HTTPException(503,'邀请口令尚未配置，请运行初始化脚本')
    bucket.append(now)
    accepted = next((code for code in codes if hmac.compare_digest(body.invite.encode(), code.encode())), None)
    if accepted is None: raise HTTPException(401,'邀请口令不正确')
    workspace_user_id = config.user_id_for_invite(accepted)
    try:
        existing=user(request)
        if existing != workspace_user_id:
            db.merge_user(existing, workspace_user_id)
        return {'user_id':workspace_user_id}
    except HTTPException: pass
    raw=secrets.token_urlsafe(32)
    db.run('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),workspace_user_id,now+30*86400))
    response.set_cookie(config.COOKIE,raw,httponly=True,secure=config.SECURE_COOKIE,samesite='strict',max_age=30*86400)
    return {'user_id':workspace_user_id}

@app.delete('/api/session')
def logout(request:Request,response:Response):
    raw=request.cookies.get(config.COOKIE,'')
    if raw:
        db.run('DELETE FROM sessions WHERE token=?',(hashlib.sha256(raw.encode()).hexdigest(),))
    response.delete_cookie(config.COOKIE,httponly=True,secure=config.SECURE_COOKIE,samesite='strict')
    return {'ok':True}

@app.get('/api/session')
def me(user_id=Depends(user)):
    pref=db.one('SELECT style FROM preferences WHERE user_id=?',(user_id,))
    day=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    used=db.one('SELECT used FROM quota WHERE user_id=? AND day=?',(user_id,day))
    return {'user_id':user_id,'preference':pref['style'] if pref else None,'used':used['used'] if used else 0,'limit':config.DAILY_LIMIT}

@app.get('/api/works')
def works(user_id=Depends(user)):
    return db.rows('SELECT id,title,created FROM works WHERE user_id=? ORDER BY created DESC',(user_id,))

@app.get('/api/works/{work_id}')
def get_work(work_id:str,user_id=Depends(user)):
    work=own(work_id,user_id)
    work['input']=json.loads(work['input']); work.pop('user_id')
    work['versions']=[{**v,'content':json.loads(v['content']),'files':json.loads(v['files'])} for v in db.rows('SELECT id,content,files,created FROM versions WHERE work_id=? ORDER BY created DESC',(work_id,))]
    work['assets']=[{'id':a['id'],'position':a['position'],**json.loads(a['meta'])} for a in db.rows('SELECT * FROM assets WHERE work_id=? ORDER BY position',(work_id,))]
    task=db.one('SELECT id,status,result,error,kind FROM tasks WHERE work_id=? ORDER BY created DESC LIMIT 1',(work_id,))
    if task and task['result']: task['result']=json.loads(task['result'])
    work['task']=task
    return work

@app.post('/api/cards')
def create_card(body:schemas.CardInput,user_id=Depends(user)):
    kind('card'); require_model()
    payload=body.model_dump()
    # Browser users choose a style explicitly. For API clients that omit it,
    # persist the effective preference/default so the model cannot select a
    # different template later in the task.
    if payload['style'] is None:
        pref=db.one('SELECT style FROM preferences WHERE user_id=?',(user_id,))
        payload['style']=pref['style'] if pref else 'magazine'
    work_id=db.uid()
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO works VALUES(?,?,?,?,?)',(work_id,user_id,'未命名的今日',db.dumps(payload),time.time()))
        result=enqueue(work_id,user_id,'generate',payload,c)
    return result

@app.post('/api/works/{work_id}/revise')
def revise(work_id:str,body:schemas.Revision,user_id=Depends(user)):
    own(work_id,user_id); require_model(); idle(work_id)
    base=db.one('SELECT id,content FROM versions WHERE id=? AND work_id=?',(body.base_version_id,work_id)) if body.base_version_id else db.one('SELECT id,content FROM versions WHERE work_id=? ORDER BY created DESC LIMIT 1',(work_id,))
    if not base:
        if body.base_version_id: raise HTTPException(404,'版本不存在')
        raise HTTPException(409,'请先完成第一版')
    payload=body.model_dump()
    # A feedback-only revision must preserve both its concrete base version
    # and template unless the user explicitly selects another style.
    payload['base_version_id']=base['id']
    if payload['style'] is None:
        payload['style']=json.loads(base['content']).get('style','magazine')
    return enqueue(work_id,user_id,'generate',payload)

@app.put('/api/preferences')
def preference(body:schemas.Preference,user_id=Depends(user)):
    kind('card')
    return save_preference(user_id,body.style,explicit=True)

@app.delete('/api/preferences')
def clear_preference(user_id=Depends(user)):
    db.run('DELETE FROM preferences WHERE user_id=?',(user_id,))
    return {'ok':True}

@app.post('/api/works/{work_id}/card-content')
def edit_card(work_id:str,body:schemas.Card,user_id=Depends(user)):
    kind('card'); own(work_id,user_id)
    return enqueue(work_id,user_id,'manual',{'content':body.model_dump()})

@app.post('/api/albums')
async def create_album(files:list[UploadFile]=File(...),memory:str=Form(''),cloud_vision:bool=Form(False),user_id=Depends(user)):
    kind('album')
    if not 1<=len(files)<=10: raise HTTPException(422,'请上传 1–10 张素材')
    if len(memory)>1000: raise HTTPException(422,'回忆最多 1000 字')
    if cloud_vision: require_model()
    work_id=db.uid(); folder=config.DATA/work_id/'assets'; folder.mkdir(parents=True)
    records=[]; hashes=set(); total=0; duplicates=0
    try:
        for file in files:
            raw=await file.read(20_000_001); await file.close()
            total+=len(raw)
            if len(raw)>20_000_000 or total>100_000_000: raise HTTPException(413,'单张最多 20MB，总计最多 100MB')
            try:
                im=Image.open(io.BytesIO(raw))
                if im.format not in ('JPEG','PNG','WEBP'): raise ValueError('format')
                if im.width*im.height>25_000_000 or min(im.size)<32: raise ValueError('size')
                im=ImageOps.exif_transpose(im).convert('RGB')
                im.thumbnail((2400,2400))
                out=io.BytesIO(); im.save(out,'JPEG',quality=94)
                data=out.getvalue()
            except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
                raise HTTPException(422,'素材需要有效的 JPEG、PNG 或 WebP 图片，最多 2500 万像素') from None
            digest=hashlib.sha256(data).hexdigest()
            if digest in hashes: duplicates+=1; continue
            hashes.add(digest)
            aid=db.uid(); (folder/f'{aid}.jpg').write_bytes(data)
            records.append((aid,work_id,digest,len(records),db.dumps({'rotation':0,'crop':[0,0,1,1],'reviewed':False,'confirmed':{}})))
        with db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('INSERT INTO works VALUES(?,?,?,?,?)',(work_id,user_id,'一段待整理的回忆',db.dumps({'memory':memory,'cloud_vision':cloud_vision}),time.time()))
            c.executemany('INSERT INTO assets VALUES(?,?,?,?,?)',records)
            result=enqueue(work_id,user_id,'inspect',{'cloud_vision':cloud_vision},c)
        return {**result,'duplicates':duplicates}
    except BaseException:
        shutil.rmtree(config.DATA/work_id,ignore_errors=True)
        raise

def update_details(c,work_id,body):
    assets=c.execute('SELECT * FROM assets WHERE work_id=?',(work_id,)).fetchall()
    if len(body.assets)!=len(assets) or {a.id for a in body.assets}!={a['id'] for a in assets}:
        raise HTTPException(422,'核对表必须恰好包含当前全部素材')
    old={a['id']:json.loads(a['meta']) for a in assets}
    for i,a in enumerate(body.assets):
        meta=old[a.id]
        # Skip means all missing facts stay blank; never promote OCR automatically.
        meta.update(reviewed=True,rotation=a.rotation,crop=a.crop,confirmed={'date':a.date,'place':a.place,'source':'user_confirmed' if a.date or a.place else 'blank'})
        c.execute('UPDATE assets SET position=?,meta=? WHERE id=?',(i,db.dumps(meta),a.id))
    inp=json.loads(c.execute('SELECT input FROM works WHERE id=?',(work_id,)).fetchone()['input'])
    inp['memory']=body.memory
    c.execute('UPDATE works SET input=? WHERE id=?',(db.dumps(inp),work_id))

@app.post('/api/works/{work_id}/details')
def details(work_id:str,body:schemas.Details,user_id=Depends(user)):
    kind('album'); own(work_id,user_id); require_model()
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        result=enqueue(work_id,user_id,'generate',{'skip':body.skip},c)
        update_details(c,work_id,body)
    return result

@app.post('/api/works/{work_id}/album-content')
def edit_album(work_id:str,body:schemas.AlbumEdit,user_id=Depends(user)):
    kind('album'); own(work_id,user_id)
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        result=enqueue(work_id,user_id,'manual',{'content':body.draft.model_dump()},c)
        update_details(c,work_id,body.details)
    return result

@app.get('/api/tasks/{task_id}')
def task_status(task_id:str,user_id=Depends(user)):
    task=db.one('SELECT id,work_id,status,result,error,created,updated FROM tasks WHERE id=? AND user_id=?',(task_id,user_id))
    if not task: raise HTTPException(404,'任务不存在')
    if task['result']: task['result']=json.loads(task['result'])
    task['traces']=[{'event':r['event'],**json.loads(r['detail'])} for r in db.rows('SELECT event,detail FROM traces WHERE task_id=? ORDER BY id',(task_id,))]
    return task

@app.post('/api/tasks/{task_id}/retry')
def retry(task_id:str,user_id=Depends(user)):
    task=db.one('SELECT * FROM tasks WHERE id=? AND user_id=?',(task_id,user_id))
    if not task: raise HTTPException(404,'任务不存在')
    if task['status']!='failed': raise HTTPException(409,'仅失败任务可重试')
    if task['kind']=='generate': require_model()
    latest=db.one('SELECT id FROM tasks WHERE work_id=? ORDER BY created DESC LIMIT 1',(task['work_id'],))
    if latest['id']!=task_id: raise HTTPException(409,'请重试最新任务，避免覆盖后续修改')
    return enqueue(task['work_id'],user_id,task['kind'],json.loads(task['payload']))

@app.get('/api/works/{work_id}/assets/{asset_id}')
def asset_file(work_id:str,asset_id:str,user_id=Depends(user)):
    own(work_id,user_id)
    if not db.one('SELECT id FROM assets WHERE id=? AND work_id=?',(asset_id,work_id)): raise HTTPException(404,'素材不存在')
    return FileResponse(config.DATA/work_id/'assets'/f'{asset_id}.jpg',media_type='image/jpeg')

@app.get('/api/works/{work_id}/versions/{version_id}/{filename}')
def download(work_id:str,version_id:str,filename:str,download:bool=False,user_id=Depends(user)):
    own(work_id,user_id)
    version=db.one('SELECT files,task_id FROM versions WHERE id=? AND work_id=?',(version_id,work_id))
    if not version or filename not in json.loads(version['files']): raise HTTPException(404,'产物不存在')
    path=config.DATA/work_id/version_id/filename
    if not path.is_file(): raise HTTPException(404,'产物文件缺失，请重新生成')
    if download: db.trace(version['task_id'],'export',ok=True)
    return FileResponse(path,media_type='application/zip' if filename.endswith('.zip') else 'image/png',filename=filename if download else None)

@app.delete('/api/works/{work_id}')
def delete_work(work_id:str,user_id=Depends(user)):
    own(work_id,user_id)
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT id FROM tasks WHERE work_id=? AND status IN ("queued","running")',(work_id,)).fetchone(): raise HTTPException(409,'作品仍在处理中，请完成后再删除')
        c.execute('DELETE FROM works WHERE id=? AND user_id=?',(work_id,user_id))
    shutil.rmtree(config.DATA/work_id,ignore_errors=True)
    return {'ok':True}

# Explicit API catchall prevents the SPA fallback from disguising missing API routes.
@app.api_route('/api/{path:path}',methods=['GET','POST','PUT','DELETE','PATCH'])
def missing_api(path:str): raise HTTPException(404,'接口不存在')

if (config.ROOT/'frontend/dist').exists():
    app.mount('/',StaticFiles(directory=config.ROOT/'frontend/dist',html=True),name='frontend')
