"""Mode1Agent: lightweight general consultation (stateless, offline)."""
from __future__ import annotations

import asyncio
from typing import Optional


class Mode1Agent:
    """Provides quick, generic guidance without external tools."""

    async def stream_async(
        self,
        prompt: str,
        user_info: Optional[dict] = None,
        turn_index: int = 0,
    ):
        """Yield a single deterministic chunk to mimic streaming."""
        summary_intro = "了解しました。まず状況を整理します。"
        if prompt:
            summary_intro += f" いまのお話は「{prompt[:80]}」ですね。"
        bullets = [
            "課題の背景・制約条件・期限を教えてください。",
            "現状わかっているデータ（数値・取引先・影響範囲）を共有してください。",
            "ゴール（達成したい姿）を簡潔に教えてください。",
        ]
        if user_info:
            enriched = []
            if user_info.get("industry"):
                enriched.append(f"業種: {user_info['industry']}")
            if user_info.get("products"):
                enriched.append(f"主要製品・サービス: {user_info['products']}")
            if user_info.get("region"):
                enriched.append(f"地域: {user_info['region']}")
            if enriched:
                summary_intro += " 共有プロフィール: " + "; ".join(enriched) + "。"

        bullet_text = "\n".join([f"- {b}" for b in bullets])
        next_hint = "次にこの3点を伺えれば、具体策を提案します。"
        if turn_index > 0:
            next_hint = "この3点を補足いただければ、さらに具体策を深掘りできます。"

        content = f"{summary_intro}\n\n{bullet_text}\n\n{next_hint}"
        yield {"data": content}

    def run(self, prompt: str, user_info: Optional[dict] = None, turn_index: int = 0) -> str:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._collect(prompt, user_info, turn_index))
        finally:
            loop.close()

    async def _collect(self, prompt: str, user_info: Optional[dict], turn_index: int):
        chunks = []
        async for evt in self.stream_async(prompt, user_info=user_info, turn_index=turn_index):
            if "data" in evt:
                chunks.append(evt["data"])
        return "".join(chunks)
