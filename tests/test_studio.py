import asyncio
import base64
import io
import json
from pathlib import Path
import time
import zipfile
import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from backend import config,db,schemas,styles
from backend.agent import run_agent
from backend.main import app
from backend.ocr import redact
from backend.provider import Provider, ModelFailure, ModelUnavailable
from backend.tools import Context,ToolError,save_preference
from backend.worker import process,recover

CARD={'title':'低电量城市漫游者','subtitle':'出门是为了透气，不是为了加入群聊。','tags':['省电模式','随便走走','社交免打扰'],'style':'magazine'}

def call(name,args):
    return {'role':'assistant','content':None,'tool_calls':[{'id':db.uid(),'type':'function','function':{'name':name,'arguments':json.dumps(args,ensure_ascii=False)}}]}

class Scripted:
    def __init__(self,*steps):self.steps=list(steps);self.messages=[]
    async def complete(self,messages,tools=None):
        self.messages.append(json.loads(json.dumps(messages)))
        return self.steps.pop(0) if self.steps else {'role':'assistant','content':'还没有渲染'}, {'prompt_tokens':20,'completion_tokens':10}

def task(tid):return db.one('SELECT * FROM tasks WHERE id=?',(tid,))
def drive(result,provider=None):
    asyncio.run(process(task(result['task_id']),provider))
    return task(result['task_id'])

def create(client):return client.post('/api/cards',json={'states':['困','想出门','不想社交']}).json()
def photo(index=0):
    out=io.BytesIO();im=Image.new('RGB',(240,160),(30+index*10,80,120));im.save(out,'PNG');return out.getvalue()
def upload(client,count=1,duplicate=False):
    return client.post('/api/albums',files=[('files',(f'{i}.png',photo(0 if duplicate else i),'image/png')) for i in range(count)],data={'memory':'那天看了一场展览。'})
def review(client,wid,skip=True):
    work=client.get('/api/works/'+wid).json()
    return {'assets':[{'id':a['id'],'date':'','place':'','rotation':0,'crop':[0,0,1,1]} for a in work['assets']],'memory':'那天看了一场展览。','skip':skip}
def album_for(detail):
    ids=[a['id'] for a in detail['assets']]
    return {'title':'那些在场的日子','subtitle':'一份私人收藏','pages':[{'asset_ids':ids[i:i+2],'caption':'那天看了一场展览。','caption_kind':'excerpt'} for i in range(0,len(ids),2)]}

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_card_loop_revision_preference_export_delete(client,renderer):
    assert client.put('/api/preferences',json={'style':'minimal'}).json()=={'style':'minimal'}
    chosen={**CARD,'style':'minimal'}
    result=create(client);model=Scripted(call('get_style_context',{}),call('render_card',chosen))
    assert drive(result,model)['status']=='completed'
    assert 'minimal' in json.dumps(model.messages[-1],ensure_ascii=False)
    wid=result['work_id'];work=client.get('/api/works/'+wid).json();v=work['versions'][0]
    url=f'/api/works/{wid}/versions/{v["id"]}/page-01.png'
    preview=client.get(url);export=client.get(url+'?download=true')
    assert preview.content==export.content
    assert Image.open(io.BytesIO(preview.content)).size==(1080,1440)
    revised={**chosen,'subtitle':'今日营业，但不接待。'}
    result2=client.post(f'/api/works/{wid}/revise',json={'feedback':'只修改副标题，更冷幽默'}).json()
    m=Scripted(call('render_card',revised));assert drive(result2,m)['status']=='completed'
    assert chosen['title'] in m.messages[0][1]['content'] and '只修改副标题' in m.messages[0][1]['content']
    versions=client.get('/api/works/'+wid).json()['versions'];assert len(versions)==2
    assert {k:v for k,v in versions[1]['content'].items() if k!='style_snapshot'}==chosen
    assert versions[1]['content']['style_snapshot']==styles.snapshot('minimal')
    client.delete('/api/preferences');assert client.get('/api/session').json()['preference'] is None
    assert client.delete('/api/works/'+wid).status_code==200
    assert not (config.DATA/wid).exists()
    assert not db.rows('SELECT * FROM tasks') and not db.rows('SELECT * FROM traces')
    assert client.get(url).status_code==404

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_card_effective_style_is_persisted_for_create_and_feedback_revision(client,renderer):
    assert client.put('/api/preferences',json={'style':'minimal'}).status_code==200
    created=create(client)
    assert json.loads(task(created['task_id'])['payload'])['style']=='minimal'
    rendered={**CARD,'style':'minimal'}
    assert drive(created,Scripted(call('render_card',rendered)))['status']=='completed'
    work=client.get('/api/works/'+created['work_id']).json()
    revision=client.post(f"/api/works/{created['work_id']}/revise",json={'feedback':'只把副标题短一点'}).json()
    payload=json.loads(task(revision['task_id'])['payload'])
    assert payload['base_version_id']==work['versions'][0]['id']
    assert payload['style']=='minimal'

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_registered_styles_render_and_snapshot_is_server_owned(client,renderer):
    for style in styles.STYLE_IDS:
        result=client.post('/api/cards',json={'states':['困','想出门','不想社交'],'style':style}).json()
        spoofed=styles.snapshot(style);spoofed['id']='spoofed'
        rendered={**CARD,'style':style,'style_snapshot':spoofed}
        assert drive(result,Scripted(call('render_card',rendered)))['status']=='completed'
        version=client.get('/api/works/'+result['work_id']).json()['versions'][0]
        assert version['content']['style_snapshot']==styles.snapshot(style)
    assert client.post('/api/cards',json={'states':['困','想出门','不想社交'],'style':'<style>bad</style>'}).status_code==422

@pytest.mark.skipif(config.KIND!='card',reason='card project')
@pytest.mark.parametrize('states',[[],['','',''],['很'*21,'想出门','不社交'],['  ','困','开心'],['困','开心']])
def test_card_bad_inputs(client,states):
    assert client.post('/api/cards',json={'states':states}).status_code==422
    assert not db.rows('SELECT * FROM works')

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_card_model_missing_and_limits(client,monkeypatch):
    monkeypatch.setattr(config,'MODEL_KEY','');assert client.post('/api/cards',json={'states':['困','开心','矛盾']}).status_code==503
    assert not db.rows('SELECT * FROM works')
    monkeypatch.setattr(config,'MODEL_KEY','test');monkeypatch.setattr(config,'DAILY_LIMIT',1)
    assert client.post('/api/cards',json={'states':['困','开心','矛盾']}).status_code==200
    assert client.post('/api/cards',json={'states':['困','开心','矛盾']}).status_code==429
    assert len(db.rows('SELECT * FROM works'))==1

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_unknown_invalid_tool_and_injection_permissions(client,renderer):
    result=create(client);u=client.get('/api/session').json()['user_id']
    m=Scripted(call('read_file',{'path':'/etc/passwd'}),call('save_preference',{'style':'minimal'}),call('render_card',{**CARD,'user_id':'other'}),call('render_card',{**CARD,'title':'字'*25}),call('render_card',CARD))
    assert drive(result,m)['status']=='completed'
    errors=db.rows('SELECT detail FROM traces WHERE event="tool"')
    assert sum(not json.loads(x['detail'])['ok'] for x in errors)==4
    assert db.one('SELECT * FROM preferences WHERE user_id=?',(u,)) is None
    with pytest.raises(ToolError):save_preference(u,'minimal')

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_round_limit_retry_and_render_failure(client,renderer,monkeypatch):
    result=create(client);monkeypatch.setattr(config,'MAX_ROUNDS',2)
    assert drive(result,Scripted())['status']=='failed'
    retry=client.post('/api/tasks/'+result['task_id']+'/retry').json()
    real_url=config.RENDER_URL;monkeypatch.setattr(config,'RENDER_URL','http://127.0.0.1:1');monkeypatch.setattr(config,'RETRIES',0)
    assert drive(retry,Scripted(call('render_card',CARD)))['status']=='failed'
    assert not db.rows('SELECT * FROM versions')
    monkeypatch.setattr(config,'RENDER_URL',real_url)
    last=client.post('/api/tasks/'+retry['task_id']+'/retry').json()
    assert drive(last,Scripted(call('render_card',CARD)))['status']=='completed'
    assert client.post('/api/tasks/'+result['task_id']+'/retry').status_code==409

@pytest.mark.skipif(config.KIND!='album',reason='album project')
def test_album_ten_assets_skip_correction_zip(client,renderer):
    result=upload(client,10).json();wid=result['work_id']
    assert drive(result)['status']=='awaiting_details'
    work=client.get('/api/works/'+wid).json()
    assert all(a['inspection']['source']=='ocr_unavailable' for a in work['assets'])
    detail=review(client,wid);detail['assets'].reverse();detail['assets'][0].update(date='2026-09-12',place='用户确认的展馆',rotation=90,crop=[.1,.1,.8,.8])
    result2=client.post(f'/api/works/{wid}/details',json=detail).json()
    album=album_for(detail);m=Scripted(call('request_details',{'questions':['同行者是谁？']}),call('update_album',album),call('render_album',{}))
    assert drive(result2,m)['status']=='completed'
    work=client.get('/api/works/'+wid).json();v=work['versions'][0]
    assert len(v['files'])==7
    assert v['content']['facts'][detail['assets'][0]['id']]['place']=='用户确认的展馆'
    assert all(not f.get('date') for aid,f in v['content']['facts'].items() if aid!=detail['assets'][0]['id'])
    zipped=client.get(f'/api/works/{wid}/versions/{v["id"]}/album.zip?download=true')
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as z:
        assert len(z.namelist())==6
        for name in z.namelist():assert Image.open(io.BytesIO(z.read(name))).size==(1080,1440)
    # Re-render after a user correction, preserve previous immutable version.
    detail['assets'][0]['date']='2026-09-11'
    result3=client.post(f'/api/works/{wid}/album-content',json={'draft':album,'details':detail}).json()
    assert drive(result3)['status']=='completed'
    versions=client.get('/api/works/'+wid).json()['versions'];assert len(versions)==2
    assert versions[0]['content']['facts'][detail['assets'][0]['id']]['date']=='2026-09-11'
    assert versions[1]['content']['facts'][detail['assets'][0]['id']]['date']=='2026-09-12'
    assert client.delete('/api/works/'+wid).status_code==200
    assert not (config.DATA/wid).exists() and not db.rows('SELECT * FROM assets')

@pytest.mark.skipif(config.KIND!='album',reason='album project')
def test_album_upload_bounds_dedup_and_cloud_optin(client,monkeypatch):
    result=upload(client,2,duplicate=True).json();assert result['duplicates']==1
    assert len(client.get('/api/works/'+result['work_id']).json()['assets'])==1
    assert upload(client,11).status_code==422
    bad=client.post('/api/albums',files={'files':('bad.png',b'not an image','image/png')});assert bad.status_code==422
    monkeypatch.setattr(config,'MODEL_KEY','')
    cloud=client.post('/api/albums',files={'files':('ok.png',photo(),'image/png')},data={'cloud_vision':'true'});assert cloud.status_code==503
    assert len(db.rows('SELECT * FROM works'))==1

@pytest.mark.skipif(config.KIND!='album',reason='album project')
def test_album_sources_coverage_and_clarification(client,renderer):
    result=upload(client,2).json();drive(result);wid=result['work_id'];detail=review(client,wid,skip=False)
    result2=client.post(f'/api/works/{wid}/details',json=detail).json()
    draft=album_for(detail)
    bad={**draft,'pages':[{'asset_ids':[detail['assets'][0]['id']],'caption':'我和小王在雨中','caption_kind':'excerpt'}]}
    duplicate={**draft,'pages':[{'asset_ids':[detail['assets'][0]['id']]*2,'caption':'','caption_kind':'creative'}]}
    hallucinated={**draft,'pages':[{'asset_ids':[x['id'] for x in detail['assets']],'caption':'我和小王在雨中','caption_kind':'excerpt'}]}
    m=Scripted(call('update_album',bad),call('update_album',duplicate),call('update_album',hallucinated),call('request_details',{'questions':['活动地点需要补充吗？']}))
    assert drive(result2,m)['status']=='awaiting_details'
    assert not db.rows('SELECT * FROM versions')
    detail['skip']=True;result3=client.post(f'/api/works/{wid}/details',json=detail).json()
    assert drive(result3,Scripted(call('update_album',draft),call('render_album',{})))['status']=='completed'

@pytest.mark.skipif(config.KIND!='album',reason='album project')
def test_album_cloud_disabled_never_calls_provider(client,monkeypatch):
    class FailIfCalled:
        async def complete(self,*args):raise AssertionError('Image sent to cloud without consent')
    result=upload(client).json()
    assert drive(result,FailIfCalled())['status']=='awaiting_details'
    wid=result['work_id'];detail=review(client,wid)
    monkeypatch.setattr(config,'MODEL_KEY','')
    assert client.post(f'/api/works/{wid}/details',json=detail).status_code==503
    assert not json.loads(db.rows('SELECT * FROM assets')[0]['meta']).get('reviewed')

@pytest.mark.skipif(config.KIND!='album',reason='album project')
def test_album_cross_asset_injection(client):
    first=upload(client).json();second=upload(client).json()
    uid=client.get('/api/session').json()['user_id'];foreign=db.rows('SELECT id FROM assets WHERE work_id=?',(second['work_id'],))[0]['id']
    ctx=Context(uid,first['work_id'],first['task_id'],{},None)
    with pytest.raises(ToolError):asyncio.run(ctx.execute('inspect_assets',{'asset_ids':[foreign]}))
    assert not db.rows('SELECT * FROM preferences')

@pytest.mark.parametrize('field,value',[('date','2026-02-30'),('date','2026-9-1'),('crop',[.8,0,.5,1]),('crop',[0,0,float('nan'),1]),('rotation',45)])
def test_details_strict(field,value):
    with pytest.raises(ValidationError):schemas.AssetDetail.model_validate({'id':'a'*32,field:value})

def test_csrf_auth_private_boundaries(client):
    if config.KIND=='card':result=create(client)
    else:result=upload(client).json()
    wid=result['work_id'];tid=result['task_id']
    other=TestClient(app,headers={'X-Requested-With':'studio'})
    assert other.get('/api/works/'+wid).status_code==401
    other.post('/api/session',json={'invite':'test-invitation'})
    for path in ['/api/works/'+wid,'/api/tasks/'+tid,f'/api/works/{wid}/versions/x/page-01.png',f'/api/works/{wid}/assets/x']:
        assert other.get(path).status_code==404
    assert other.delete('/api/works/'+wid).status_code==404
    assert other.post('/api/tasks/'+tid+'/retry').status_code==404
    assert client.delete('/api/works/'+wid).status_code==409
    assert client.post('/api/session',json={'invite':'test-invitation'},headers={'Origin':'https://evil.example'}).status_code==403
    assert TestClient(app).post('/api/session',json={'invite':'test-invitation'}).status_code==403
    ctx=Context('foreign',wid,tid,{},None)
    with pytest.raises(ToolError):ctx.work()
    assert 'HttpOnly' in client.post('/api/session',json={'invite':'test-invitation'}).headers.get('set-cookie','') or client.cookies

def test_extra_invite_and_logout_revoke_browser_session(monkeypatch):
    monkeypatch.setattr(config,'EXTRA_INVITES',('zcc-code',))
    visitor=TestClient(app,headers={'X-Requested-With':'studio'})
    assert visitor.post('/api/session',json={'invite':'zcc-code'}).status_code==200
    assert visitor.get('/api/session').status_code==200
    logged_out=visitor.delete('/api/session')
    assert logged_out.status_code==200 and logged_out.json()=={'ok':True}
    assert visitor.get('/api/session').status_code==401
    visitor.close()

def test_redaction_and_safe_traces(client):
    text=redact('身份证：110101199901011234\n订单号 AB123456789\n2026-09-12 展览\n姓名 张三\n手机号 13800138000')
    assert all(s not in text for s in ['110101199901011234','AB123456789','13800138000','张三'])
    assert '2026-09-12' in text
    result=create(client) if config.KIND=='card' else upload(client).json()
    db.trace(result['task_id'],'tool',tool='unknown',ok=False,prompt='secret',key='api-key',raw='ticket')
    assert 'secret' not in db.rows('SELECT detail FROM traces')[0]['detail']

def test_recovery_and_idempotency(client,renderer):
    if config.KIND=='card':
        result=create(client);m=Scripted(call('render_card',CARD))
    else:
        first=upload(client).json();drive(first);d=review(client,first['work_id']);result=client.post(f'/api/works/{first["work_id"]}/details',json=d).json();m=Scripted(call('update_album',album_for(d)),call('render_album',{}))
    db.run('UPDATE tasks SET status="running",attempts=1 WHERE id=?',(result['task_id'],))
    recover();assert task(result['task_id'])['status']=='queued'
    assert drive(result,m)['status']=='completed'
    assert drive(result,Scripted())['status']=='completed'
    assert len(db.rows('SELECT * FROM versions'))==1
    db.run('UPDATE tasks SET status="running",attempts=? WHERE id=?',(config.RETRIES+1,result['task_id']))
    recover();assert task(result['task_id'])['status']=='failed'

def test_provider_timeout_retry_and_protocol(monkeypatch):
    real=httpx.AsyncClient;counter=[]
    def handler(request):
        counter.append(request)
        if len(counter)<3:raise httpx.ReadTimeout('timeout')
        assert request.url.path=='/v1/chat/completions'
        assert request.headers['authorization']=='Bearer test-not-a-real-key'
        return httpx.Response(200,json={'choices':[{'message':call('get_style_context',{})}],'usage':{'prompt_tokens':4}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    result=asyncio.run(Provider().complete([{'role':'user','content':'hello'}],[]))
    assert len(counter)==3 and result[1]['prompt_tokens']==4
    monkeypatch.setattr(config,'MODEL_KEY','')
    with pytest.raises(ModelUnavailable):asyncio.run(Provider().complete([]))

def test_provider_failures_do_not_leak(monkeypatch):
    real=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(lambda request:httpx.Response(401,text='SECRET API KEY IN PROVIDER ERROR')),**kwargs))
    with pytest.raises(ModelFailure) as exc:asyncio.run(Provider().complete([]))
    assert 'SECRET' not in str(exc.value)

@pytest.mark.parametrize('case',range(20))
def test_twenty_synthetic_export_cases(client,renderer,case):
    # Contract/render regression only, explicitly NOT a real-model quality benchmark.
    if config.KIND=='card':
        states=[['困','想出门','不想社交'],['开心','有点烦','都可以'],['充满干劲','想躺平','饥饿'],['内向','外向','不知道']][case%4]
        c={**CARD,'style':sorted(styles.STYLE_IDS)[case%len(styles.STYLE_IDS)]}
        if case==19:c.update(title='今'*24,subtitle='中'*70,tags=['文'*12]*3)
        result=client.post('/api/cards',json={'states':states,'memory':'一个普通但值得记录的今天。','style':c['style']}).json()
        final=drive(result,Scripted(call('render_card',c)))
    else:
        result=upload(client,1+case%10).json();drive(result);d=review(client,result['work_id'])
        if case%3==0:d['assets'][0].update(date='2026-09-12',place='已核对展览馆',rotation=90)
        r=client.post(f'/api/works/{result["work_id"]}/details',json=d).json()
        final=drive(r,Scripted(call('update_album',album_for(d)),call('render_album',{})))
    assert final['status']=='completed',final['error']
    version=db.rows('SELECT * FROM versions')[0]
    for file in json.loads(version['files']):assert (config.DATA/result['work_id']/version['id']/file).is_file()

@pytest.mark.skipif(config.KIND!='card',reason='card project')
def test_revision_uses_selected_version_and_rejects_foreign_version(client,renderer):
    first=create(client);drive(first,Scripted(call('render_card',CARD)));wid=first['work_id']
    original=client.get('/api/works/'+wid).json()['versions'][0]
    newer={**CARD,'title':'新版标题'}
    changed=client.post(f'/api/works/{wid}/card-content',json=newer).json();drive(changed)
    revision=client.post(f'/api/works/{wid}/revise',json={'feedback':'基于最初版本改副标题','base_version_id':original['id']}).json()
    model=Scripted(call('render_card',CARD));assert drive(revision,model)['status']=='completed'
    request=json.loads(model.messages[0][1]['content'])
    assert request['current_version']['title']==CARD['title']
    assert client.post(f'/api/works/{wid}/revise',json={'feedback':'test','base_version_id':'a'*32}).status_code==404

@pytest.mark.skipif(config.KIND!='album',reason='album project')
def test_cloud_optin_is_explicit_and_output_stays_unconfirmed(client):
    response=client.post('/api/albums',files={'files':('sample.png',photo(),'image/png')},data={'cloud_vision':'true'})
    model=Scripted({'role':'assistant','content':'2026-09-12\n订单号：AB123456789\n城市艺术馆'})
    assert drive(response.json(),model)['status']=='awaiting_details'
    content=model.messages[0][1]['content']
    assert content[1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    meta=json.loads(db.rows('SELECT * FROM assets')[0]['meta'])
    assert meta['inspection']['source']=='cloud_unconfirmed' and not meta['reviewed']
    assert 'AB123456789' not in meta['inspection']['vision_text']
