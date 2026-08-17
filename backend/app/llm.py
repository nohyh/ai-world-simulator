"""LLM 客户端：OpenAI 兼容协议（DeepSeek/GLM/Qwen/OpenAI 等通用）+ mock 演示模式。

只有两个原语：
  stream_chat()  —— 主叙事流式调用
  chat()         —— 辅助调用的非流式调用（NPC 解析/心智/结晶/世界推进）
"""
import asyncio
import json
import random
import re

import httpx

from . import config as C


class LLMError(Exception):
    pass


class LLMConfig:
    def __init__(self, d=None):
        d = d or {}
        self.provider = d.get("provider") or C.DEFAULT_PROVIDER
        self.base_url = (d.get("base_url") or C.DEFAULT_BASE_URL).rstrip("/")
        self.api_key = d.get("api_key") or ""
        self.model = d.get("model") or C.DEFAULT_MODEL
        self.aux_model = d.get("aux_model") or d.get("model") or C.DEFAULT_AUX_MODEL
        self.temperature = d.get("temperature") or C.DEFAULT_TEMPERATURE

    @property
    def is_mock(self):
        return self.provider == "mock"

    def public(self):
        return {"provider": self.provider, "base_url": self.base_url,
                "model": self.model, "aux_model": self.aux_model}


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        if not cfg.is_mock:
            self._http = httpx.AsyncClient(
                base_url=cfg.base_url,
                headers={"Authorization": f"Bearer {cfg.api_key}"},
                timeout=httpx.Timeout(connect=15, read=300, write=30, pool=15),
            )

    async def close(self):
        if not self.cfg.is_mock:
            await self._http.aclose()

    # ---------------- OpenAI 兼容 ----------------
    async def stream_chat(self, messages, temperature=None, max_tokens=3000):
        """流式对话，逐段 yield 文本 delta。"""
        if self.cfg.is_mock:
            async for delta in _mock_narrator_stream(messages):
                yield delta
            return
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.cfg.temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        got_any = False
        last_err = None
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(2 * attempt)
            try:
                async with self._http.stream("POST", "/chat/completions", json=payload) as resp:
                    if resp.status_code >= 400:
                        body = (await resp.aread()).decode("utf-8", "replace")[:300]
                        raise LLMError(f"LLM HTTP {resp.status_code}: {body}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if chunk == "[DONE]":
                            return
                        try:
                            obj = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        delta = (obj.get("choices") or [{}])[0].get("delta", {}).get("content")
                        if delta:
                            got_any = True
                            yield delta
                    if got_any:
                        return
            except (httpx.HTTPError, LLMError) as e:
                last_err = e
                if got_any:  # 已经吐过内容就不能安全重试
                    raise
        raise LLMError(f"流式调用失败: {last_err}")

    async def chat(self, messages, aux=False, temperature=None, max_tokens=1500):
        """非流式调用。aux=True 用辅助（便宜）模型。"""
        if self.cfg.is_mock:
            return _mock_aux_reply(messages)
        payload = {
            "model": self.cfg.aux_model if aux else self.cfg.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else (
                C.DEFAULT_AUX_TEMPERATURE if aux else self.cfg.temperature),
            "max_tokens": max_tokens,
        }
        last_err = None
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(2 * attempt)
            try:
                resp = await self._http.post("/chat/completions", json=payload)
                if resp.status_code >= 400:
                    raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
                data = resp.json()
                return data["choices"][0]["message"]["content"] or ""
            except httpx.HTTPError as e:
                last_err = e
        raise LLMError(f"调用失败: {last_err}")


# ---------------- mock 演示模式（无 API Key 也能跑通全流程） ----------------

_MOCK_TURN = """<beat type="narration">雨水敲打着铁皮屋顶，你{action_echo}之后，避难所里陷入短暂沉默。</beat>
<beat type="dialogue" speaker="陈医生">他们昨晚又往北移动了，至少二十人。</beat>
<beat type="dialogue" speaker="老周">粮最多撑五天。</beat>
<beat type="narration">你注意到队长一直没说话，只是盯着地图边缘的一行小字。</beat>
[[META]]
{"choices": ["追问地图边缘的小字", "质问队长为何沉默", "清点避难所的存粮", "提议连夜出发"], "minutes": 25, "place": "避难所·医务室", "present": ["陈医生", "老周", "队长"]}
[[END]]"""


async def _mock_narrator_stream(messages):
    text = _MOCK_TURN
    # 找到玩家行动做一点回声，让演示不那么死板
    user_txt = ""
    for m in reversed(messages):
        if m["role"] == "user":
            user_txt = m["content"][-60:]
            break
    echo = re.sub(r"\s+", "", user_txt)[:12] or "行动"
    text = text.replace("{action_echo}", f"「{echo}」")
    for i in range(0, len(text), 9):
        yield text[i:i + 9]
        await asyncio.sleep(0.02)


def _mock_aux_reply(messages):
    """根据调用方塞在 system 末尾的 mock 提示返回对应 JSON。"""
    joined = "\n".join(m["content"] for m in messages if m["role"] == "system")
    if "MOCK:npccards" in joined:
        return json.dumps({
            "npcs": [
                {"name": "陈医生", "identity": "避难所的医疗官", "personality": "冷静、惜字如金，背负着过去的错误",
                 "relationship": "信任的同伴", "goal": "找到失踪的医疗队", "secret_plan": "隐瞒自己已被感染"},
                {"name": "老周", "identity": "老猎人", "personality": "务实、嘴硬心软",
                 "relationship": "旧识", "goal": "保住避难所里的孩子们", "secret_plan": ""},
            ],
            "main_plot": "北方的武装集团正在逼近避难所，水源与粮食只够支撑五天。",
        }, ensure_ascii=False)
    if "MOCK:npcmind" in joined:
        return json.dumps({
            "npcs": {"陈医生": {"feeling": "焦虑而克制", "goal": "找到失踪的医疗队",
                              "opinion_of_player": "可靠的决策者", "secret_plan": "隐瞒感染"}},
            "plot_advanced": random.choice([True, False]),
            "player_attr_changes": {},
            "key_item_changes": {"add": [], "remove": []},
        }, ensure_ascii=False)
    if "MOCK:crystal" in joined:
        return json.dumps({
            "summary": "玩家在避难所与同伴商议北迁的武装集团威胁，粮食仅够五天。",
            "key_events": ["陈医生展示染血地图", "确认敌方北移动向"],
            "characters": [{"name": "陈医生", "state": "焦虑", "relationship": "信任"}],
            "world_facts": ["武装集团在北方活动", "存粮只够五天"],
        }, ensure_ascii=False)
    if "MOCK:tick" in joined:
        return json.dumps({
            "developments": ["北方的武装集团又前进了十公里，侦察兵回报他们似乎在寻找什么。"],
            "plot_pressure": "敌方逼近的速度在加快。",
        }, ensure_ascii=False)
    return "{}"
