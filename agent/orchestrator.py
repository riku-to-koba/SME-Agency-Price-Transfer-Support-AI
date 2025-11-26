"""Orchestrator + mode agents for 3-tier architecture.

- Mode detection: LLM first (Bedrock Haiku). LLMが使えない場合はエラーを返す。
- 低信頼ならヒアリング質問を返し、それ以外はMode1/Mode2へ委譲。
- Mode1Agent: lightweight general consultation (stateless).
- Mode2Agent: price-transfer specialist (wraps existing PriceTransferAgent).

【修正内容】
- 初回ウェルカムメッセージをOrchestrator管理に
- 会話履歴構築を改善（ユーザー+アシスタント両方）
- モード承諾フローの実装
- ヒアリングの多段階対応
- 自然な会話調のヒアリング
- LLMベースの承諾/拒否判定
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from agent.mode1 import Mode1Agent
from agent.mode2 import Mode2Agent


class ModeClassifier:
    """LLM-based mode classifier. LLM必須。"""

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

    async def classify(self, user_input: str, history: str) -> Tuple[str, str, float, Optional[str]]:
        """Return (mode, reason, confidence, clarification)."""
        if not self.model:
            raise RuntimeError(self.init_error or "LLMが利用できません。認証情報やリージョン設定を確認してください。")

        system_prompt = (
            "あなたは価格転嫁支援システムのモード判定担当です。"
            "ユーザーの最新発話と直近のユーザー発話履歴から、以下をJSONで返してください。"
            "- mode: 'mode1' (よろず経営相談) または 'mode2' (価格転嫁・値上げ交渉系)"
            "- reason: 判定理由を簡潔に"
            "- confidence: 0.0〜1.0 の確信度"
            "- clarification: confidenceが0.6未満のときのみ、モードを決めるための具体的な質問を2〜3行で返す。高い場合は空文字で可"
            "判定の指針:"
            " 価格交渉/値上げ/単価/原価計算/見積/コスト/下請法/買いたたき/取引条件/支払条件/交渉準備は mode2。"
            " 資金繰り/人材/販路/事業承継/組織/マーケなど交渉に直結しない相談は mode1。"
            " 出力は必ずJSONのみ。"
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
            # BedrockModelをAgentでラップして非同期ストリーミングで実行
            from strands import Agent
            temp_agent = Agent(model=self.model, tools=[], system_prompt=system_prompt)

            # stream_asyncでレスポンスを収集
            resp_chunks = []
            async for event in temp_agent.stream_async(user_prompt):
                if "data" in event:
                    resp_chunks.append(event["data"])

            resp = "".join(resp_chunks)
            
            # JSONブロックを抽出（```json ... ``` 形式に対応）
            json_match = re.search(r'```json\s*(.*?)\s*```', resp, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # ```なしの純粋なJSONを試す
                json_str = resp.strip()
            
            data = json.loads(json_str)
            return (
                data.get("mode", "mode1"),
                data.get("reason", "llm_reason"),
                max(0.0, min(1.0, float(data.get("confidence", 0.7)))),
                data.get("clarification") or None,
            )
        except json.JSONDecodeError as e:
            # JSONパースエラーの場合、デフォルトでmode1を返す
            print(f"[WARN] JSONパースエラー、mode1にフォールバック: {str(e)}")
            return ("mode1", "JSONパースエラー", 0.5, None)
        except Exception as e:
            raise RuntimeError(f"LLMモード判定に失敗しました: {str(e)}") from e

    async def judge_consent(self, user_input: str, context: str) -> Tuple[str, str]:
        """LLMでユーザーの承諾/拒否を判定する。
        
        Returns:
            (判定結果, 理由)
            判定結果: "consent" | "rejection" | "unclear"
        """
        if not self.model:
            raise RuntimeError(self.init_error or "LLMが利用できません。")

        system_prompt = (
            "あなたはユーザーの意図を判定するアシスタントです。\n"
            "ユーザーの発言が、提案されたモード切り替えに対して「承諾」「拒否」「不明確」のいずれかを判定してください。\n\n"
            "【判定基準】\n"
            "- consent（承諾）: 肯定的な返答、同意、進めてほしいという意思表示\n"
            "  例: 「はい」「お願いします」「それでいい」「大丈夫」「進めて」「OK」「いいですよ」「そうしてください」\n"
            "- rejection（拒否）: 否定的な返答、断り、別のことを希望\n"
            "  例: 「いいえ」「違います」「やめて」「それは違う」「別の相談がしたい」「今はいい」\n"
            "- unclear（不明確）: 質問、確認、または承諾/拒否が判断できない発言\n"
            "  例: 「詳しく教えて」「どういうこと？」「もう少し説明して」「ちょっと待って」\n\n"
            "出力は必ずJSONのみで返してください。"
        )
        user_prompt = f"""
直前のAIの提案:
{context}

ユーザーの返答:
{user_input}

出力フォーマット（必ずJSONのみ）:
{{
  "judgment": "consent",
  "reason": "判定理由を簡潔に"
}}
"""
        try:
            from strands import Agent
            temp_agent = Agent(model=self.model, tools=[], system_prompt=system_prompt)

            resp_chunks = []
            async for event in temp_agent.stream_async(user_prompt):
                if "data" in event:
                    resp_chunks.append(event["data"])

            resp = "".join(resp_chunks)
            
            # JSONブロックを抽出
            json_match = re.search(r'```json\s*(.*?)\s*```', resp, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = resp.strip()
            
            data = json.loads(json_str)
            judgment = data.get("judgment", "unclear")
            reason = data.get("reason", "")
            
            # 有効な値かチェック
            if judgment not in ("consent", "rejection", "unclear"):
                judgment = "unclear"
            
            return (judgment, reason)
        except Exception as e:
            print(f"[WARN] 承諾判定エラー、unclearにフォールバック: {str(e)}")
            return ("unclear", "判定エラー")


class OrchestratorAgent:
    """3-tier orchestrator coordinating Mode1 and Mode2 agents."""

    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self.mode_classifier = ModeClassifier()

    def create_session(self, session_id: str, user_info: Optional[dict] = None):
        """セッションを作成し、初回ウェルカムメッセージを設定"""
        session = {
            "session_id": session_id,
            "mode": None,  # 初回はモード未確定
            "mode_confirmed": False,  # モード承諾フラグ
            "messages": [],
            "current_step": None,
            "mode2_progress": {"completed_steps": [], "current_step": None, "data": {}},
            "user_info": user_info or {},
            "agents": {
                "mode1": Mode1Agent(),
                "mode2": None,  # lazy init
            },
        }

        # 初回ウェルカムメッセージをOrchestratorが管理
        welcome_message = self._generate_welcome_message()
        session["messages"].append({"role": "assistant", "content": welcome_message})

        self.sessions[session_id] = session
        return session

    def _generate_welcome_message(self) -> str:
        """初回ウェルカムメッセージを生成（自然な会話調）"""
        return (
            "こんにちは！中小企業価格転嫁サポートAIです。\n\n"
            "資金繰り、人材、販路拡大、価格交渉、事業承継…\n"
            "経営のお悩み、どんなことでも気軽にご相談ください。\n\n"
            "今日はどんなことでお困りですか？"
        )

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

    def _build_history_context(self, session: dict, max_turns: int = 5) -> str:
        """会話履歴を構築（ユーザー + アシスタント両方）

        Args:
            session: セッション情報
            max_turns: 取得する最大ターン数（1ターン = ユーザー発言 + AI応答）

        Returns:
            フォーマットされた会話履歴テキスト
        """
        messages = session.get("messages", [])

        # 直近のターン分を取得（max_turns * 2 メッセージ）
        recent_messages = messages[-(max_turns * 2):] if messages else []

        history_parts = []
        for msg in recent_messages:
            role_label = "ユーザー" if msg["role"] == "user" else "AI"
            content = msg.get("content", "")
            # 長すぎる場合は切る（1メッセージ最大300文字）
            if len(content) > 300:
                content = content[:300] + "..."
            history_parts.append(f"{role_label}: {content}")

        return "\n".join(history_parts)


    def _generate_initial_clarification(self) -> str:
        """初回ヒアリング質問（自然な会話調）"""
        return "なるほど。もう少し詳しく教えていただけますか？どんな状況で、何に困っているのか聞かせてください。"

    def _generate_followup_clarification(self, session: dict) -> str:
        """2回目以降のヒアリング質問（自然な会話調）"""
        return "ありがとうございます。具体的にどんなことでお手伝いできそうですか？"

    def _request_mode_consent(self, mode: str, reason: str) -> str:
        """モード切り替えの承諾を求める（自然な会話調）"""
        if mode == "mode2":
            return (
                f"なるほど、{reason}ということですね。\n\n"
                "価格交渉・値上げの相談でしたら、専門モードで詳しくサポートできます。\n"
                "市場データの分析、コスト試算、交渉シナリオの作成など、本格的な準備をお手伝いしますよ。\n\n"
                "専門モードに切り替えて進めてもいいですか？"
            )
        else:
            return (
                f"なるほど、{reason}ということですね。\n\n"
                "経営全般のご相談として、一緒に考えていきましょう。\n"
                "このまま進めてよろしいですか？"
            )

    async def stream(self, session: dict, message: str):
        """Route to appropriate agent and yield streaming events."""
        print(f"[DEBUG] Orchestrator.stream() called with message: {message[:50]}...")
        print(f"[DEBUG] Session mode: {session.get('mode')}")

        # === ステップ1: 会話履歴を構築（ユーザー + アシスタント両方） ===
        history_text = self._build_history_context(session)

        # === ステップ3: LLMでモード判定 ===
        print(f"[DEBUG] Starting mode classification...")
        print(f"[DEBUG] History text length: {len(history_text)}")
        try:
            mode, mode_reason, mode_confidence, clarification = await self.mode_classifier.classify(
                message, history_text
            )
            print(f"[DEBUG] Classification result: mode={mode}, confidence={mode_confidence}")
        except Exception as e:
            print(f"[DEBUG] Classification ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            yield {"type": "error", "error": str(e)}
            return

        # === ステップ4: ヒアリング処理（confidence が低い場合） ===
        if mode_confidence < 0.35:
            # ユーザー発言数をカウント（初回か2回目以降か）
            user_message_count = len([m for m in session.get("messages", []) if m.get("role") == "user"])

            if user_message_count == 0:
                # 初回ヒアリング
                clarify_msg = clarification or self._generate_initial_clarification()
            else:
                # 2回目以降のヒアリング
                clarify_msg = clarification or self._generate_followup_clarification(session)

            session["messages"].append({"role": "user", "content": message})
            session["messages"].append({"role": "assistant", "content": clarify_msg})
            yield {"data": clarify_msg}
            return

        # === ステップ5: モード確定（許可なしで移行） ===
        mode_changed = (session["mode"] != mode)

        if mode_changed:
            # モードを更新
            self.update_mode(session, mode)
            session["mode_confirmed"] = True
            
            # モード変更を通知
            yield {
                "type": "mode_update",
                "mode": mode,
                "reason": mode_reason,
                "confidence": mode_confidence,
            }
            
            # 短い確認メッセージを表示
            if mode == "mode2":
                confirm_msg = (
                    "価格転嫁の専門モードで対応します。\n\n"
                    "📊 市場データの調査・分析\n"
                    "💰 コスト試算と適正価格の算出\n"
                    "📄 申入書・見積書などの文書作成\n"
                    "🎭 交渉シミュレーション\n\n"
                    "などのサポートができます。\n\n"
                )
            else:
                confirm_msg = "経営全般のご相談として対応します。\n\n"
            
            yield {"data": confirm_msg}
            session["messages"].append({"role": "assistant", "content": confirm_msg.strip()})

        # === ステップ6: ユーザーメッセージを履歴に追加 ===
        session["messages"].append({"role": "user", "content": message})

        # === ステップ7: 適切な子エージェントへ委譲 ===
        # 注意: 会話履歴への追加はapi/main.pyのappend_assistant_messageで行う
        # ここでは追加しない（画像タグ等を除去したクリーンなテキストを保存するため）

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

        # 注意: エージェント応答の履歴追加は api/main.py の append_assistant_message で行う
        # 理由: ツール結果（[CHART_IMAGE]タグ等）を除去したクリーンなテキストを保存するため

    def append_assistant_message(self, session: dict, content: str):
        session["messages"].append({"role": "assistant", "content": content})

