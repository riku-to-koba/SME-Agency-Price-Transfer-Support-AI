"""Orchestrator + mode agents for 3-tier architecture.

- Mode detection: LLM first (Bedrock Haiku). LLMが使えない場合はエラーを返す。
- If confidence is low, it asks clarifying questions before delegating.
- Mode1Agent: lightweight general consultation (stateless).
- Mode2Agent: price-transfer specialist (wraps existing PriceTransferAgent).
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from agent.mode1 import Mode1Agent
from agent.mode2 import Mode2Agent


class ModeClassifier:
    """LLM-based mode classifier with graceful fallback."""

    def __init__(self):
        self.model = None
        self.init_error: Optional[str] = None
        try:
            from strands.models import BedrockModel
            import boto3

            session = boto3.Session(profile_name="bedrock_use_only", region_name="ap-northeast-1")
            self.model = BedrockModel(
                model_id="jp.anthropic.claude-haiku-4-5-20251001-v1:0",
                temperature=0.2,
                max_tokens=1024,
                streaming=False,
                boto_session=session,
            )
        except Exception as e:
            self.model = None
            self.init_error = f"Bedrockモデルの初期化に失敗しました: {str(e)}"

    def classify(self, user_input: str, history: str) -> Tuple[str, str, float, Optional[str]]:
        """Return (mode, reason, confidence, clarification)."""
        if not self.model:
            raise RuntimeError(self.init_error or "LLMが利用できません。認証情報やリージョン設定を確認してください。")

        system_prompt = (
            "あなたは価格転嫁支援システムのモード判定係です。"
            "ユーザー発話と直近履歴から、以下をJSONで出力してください。"
            "- mode: 'mode1' (よろず経営相談) か 'mode2' (価格転嫁・値上げ交渉支援)。"
            "- reason: 判定理由を簡潔に。"
            "- confidence: 0.0〜1.0。"
            "- clarification: confidenceが0.6未満のとき、モードを決めるための具体的な質問を2〜3行で返す。高いときは空文字。"
            "判定の指針: "
            "価格交渉/値上げ/単価/原価計算/見積/コスト/下請法/買いたたき/取引条件/支払条件などの交渉文脈はmode2。"
            "資金繰り/人材/販路/事業承継/組織/マーケ等、価格交渉に直結しない一般相談はmode1。"
            "履歴には過去のユーザー発話のみを与える。出力は必ずJSONのみ。"
        )
        user_prompt = f"""
ユーザー入力:
{user_input}

直近履歴（ユーザー発話のみ抜粋、最大800文字）:
{history[-800:] if history else "なし"}

出力フォーマット（必ずJSONのみ）:
{{
  "mode": "mode1",
  "reason": "短い説明",
  "confidence": 0.5,
  "clarification": "確信が低い場合だけ質問。高いときは空文字または省略可"
}}
"""
        try:
            resp = self.model.run(prompt=user_prompt, system=system_prompt)
            data = json.loads(resp)
            return (
                data.get("mode", "mode1"),
                data.get("reason", "llm_reason"),
                max(0.0, min(1.0, float(data.get("confidence", 0.7)))),
                data.get("clarification") or None,
            )
        except Exception as e:
            raise RuntimeError(f"LLMモード判定に失敗しました: {str(e)}") from e


class OrchestratorAgent:
    """3-tier orchestrator coordinating Mode1 and Mode2 agents."""

    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self.mode_classifier = ModeClassifier()

    def create_session(self, session_id: str, user_info: Optional[dict] = None):
        self.sessions[session_id] = {
            "session_id": session_id,
            "mode": "mode1",
            "messages": [],
            "current_step": None,
            "mode2_progress": {"completed_steps": [], "current_step": None, "data": {}},
            "user_info": user_info or {},
            "agents": {
                "mode1": Mode1Agent(),
                "mode2": None,  # lazy init
            },
        }
        return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    def ensure_mode2_agent(self, session: dict):
        if session["agents"]["mode2"] is None:
            session["agents"]["mode2"] = Mode2Agent(
                current_step=session.get("current_step"),
                user_info=session.get("user_info"),
            )
        return session["agents"]["mode2"]

    def update_mode(self, session: dict, new_mode: str) -> bool:
        if session["mode"] != new_mode:
            session["mode"] = new_mode
            return True
        return False

    async def stream(self, session: dict, message: str):
        """Route to appropriate agent and yield streaming events."""
        history_text = " ".join(
            msg.get("content", "")
            for msg in (session.get("messages") or [])
            if msg.get("role") == "user"
        )

        # LLM-based detection only
        try:
            mode, mode_reason, mode_confidence, clarification = self.mode_classifier.classify(message, history_text)
        except Exception as e:
            yield {"type": "error", "error": str(e)}
            return

        mode_changed = self.update_mode(session, mode)
        if mode_changed:
            yield {
                "type": "mode_update",
                "mode": mode,
                "reason": mode_reason,
                "confidence": mode_confidence,
            }

        session["messages"].append({"role": "user", "content": message})

        # Clarify first if confidence is low
        if mode_confidence < 0.35:
            clarify = clarification or (
                "状況をもう少し教えてください：\n"
                "- 価格転嫁（値上げ交渉）か一般経営相談か\n"
                "- 業種・主要製品/サービス・取引先のタイプ（B2B/B2C）\n"
                "- いつまでに何を達成したいか（交渉日・期限など）"
            )
            yield {"data": clarify}
            return

        if mode == "mode2":
            agent = self.ensure_mode2_agent(session)
            async for event in agent.stream_async(message):
                yield event
        else:
            agent: Mode1Agent = session["agents"]["mode1"]
            turn_index = len([m for m in session.get("messages", []) if m.get("role") == "assistant"])
            async for event in agent.stream_async(
                message,
                user_info=session.get("user_info"),
                turn_index=turn_index,
            ):
                yield event

    def append_assistant_message(self, session: dict, content: str):
        session["messages"].append({"role": "assistant", "content": content})
