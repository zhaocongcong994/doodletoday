#!/usr/bin/env python3
"""An explicit, tiny real-model check. Never prints credentials or provider bodies."""
import asyncio
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.provider import Provider,ModelFailure,ModelUnavailable

async def main():
    schema={'type':'function','function':{'name':'connection_ok','description':'确认连接成功','parameters':{'type':'object','properties':{},'additionalProperties':False}}}
    message,usage=await Provider().complete([{'role':'user','content':'请调用 connection_ok 工具确认连接。'}],[schema])
    calls=message.get('tool_calls') or []
    if not any(c.get('function',{}).get('name')=='connection_ok' for c in calls):
        raise ModelFailure('服务可响应，但未返回工具调用。请使用支持工具调用的模型。')
    print('真实模型工具调用成功。用量：', {k:usage.get(k,0) for k in ['prompt_tokens','completion_tokens']})

try:asyncio.run(main())
except (ModelFailure,ModelUnavailable) as e:raise SystemExit(str(e))
