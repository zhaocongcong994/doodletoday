import asyncio
import json
import re
import sys
from . import config

# Strip recognisable identifiers before ANY text leaves the local process.
def redact(text):
    text=re.sub(r'(?i)(身份证|证件号|订单号|订单编号|票号|取票码|检票码|手机号|电话|姓名|乘车人|乘客|座位|座号)\s*[:：]?\s*[^\n]+', '[已隐藏个人字段]', text)
    text=re.sub(r'(?<!\d)\d{6,}[\dXx]*(?!\d)', '[已隐藏编号]', text)
    text=re.sub(r'(?i)\b[A-Z0-9]{8,}\b', '[已隐藏编号]', text)
    return text[:4000]

async def recognize(path):
    if not config.OCR_ENABLED:
        return {'text':'','candidate_dates':[],'warning':'本地 OCR 未启用，请手动核对或留白。','source':'ocr_unavailable'}
    process=await asyncio.create_subprocess_exec(sys.executable, str(config.ROOT/'backend/ocr_runner.py'), str(path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        stdout,_=await asyncio.wait_for(process.communicate(), timeout=config.OCR_TIMEOUT)
        if process.returncode: raise ValueError('OCR failed')
        blocks=json.loads(stdout)
        text=redact('\n'.join(b['text'] for b in blocks))
        dates=list(dict.fromkeys(f'{y}-{int(m):02d}-{int(d):02d}' for y,m,d in re.findall(r'(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})',text)))
        uncertain=not blocks or any(b['confidence']<.85 for b in blocks)
        return {'text':text,'candidate_dates':dates,'warning':'识别有疑点，请核对。' if uncertain or len(dates)!=1 else '请确认票面日期和地点。','source':'ocr_unconfirmed'}
    except (asyncio.TimeoutError, ValueError, KeyError):
        return {'text':'','candidate_dates':[],'warning':'OCR 失败或超时，请手动核对或留白。','source':'ocr_failed'}
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
