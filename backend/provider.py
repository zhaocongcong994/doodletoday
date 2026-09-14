import asyncio
import httpx
from . import config

class ModelUnavailable(Exception):
    pass

class ModelFailure(Exception):
    pass

class Provider:
    async def complete(self, messages, tools=None):
        if not config.model_ready():
            raise ModelUnavailable('模型未配置，请在 .env 中设置服务地址、模型和凭据。')
        body = {'model':config.MODEL_ID, 'messages':messages, 'max_tokens':2400}
        if tools:
            body.update(tools=tools, tool_choice='auto')
        for attempt in range(config.RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=config.MODEL_TIMEOUT) as c:
                    r=await c.post(config.MODEL_URL+'/chat/completions', headers={'Authorization':'Bearer '+config.MODEL_KEY}, json=body)
                    if r.status_code in (408,429) or r.status_code>=500:
                        raise httpx.TimeoutException('retryable provider response')
                    if r.status_code>=400:
                        raise ModelFailure('模型服务拒绝请求，请检查模型配置或额度。')
                    data=r.json()
                    message=data['choices'][0]['message']
                    if not isinstance(message,dict) or not isinstance(message.get('tool_calls',[]),list):
                        raise ValueError('invalid message')
                    return message, data.get('usage',{})
            except (httpx.TransportError, ValueError, KeyError, IndexError):
                if attempt>=config.RETRIES:
                    raise ModelFailure('模型调用超时或返回格式无效，可以重试。') from None
                await asyncio.sleep(min(2**attempt,4))
