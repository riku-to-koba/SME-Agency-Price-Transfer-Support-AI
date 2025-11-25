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
"""
from __future__ import annotations

import json
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
        """初回ウェルカムメッセージを生成"""
        return (
            "こんにちは、**中小企業サポートAI**です。\n\n"
            "あなたの経営課題について、何でもご相談ください。\n"
            "内容に応じて、最適なサポートモードで対応します。\n\n"
            "【相談できること】\n"
            "- 💰 価格転嫁・値上げ交渉（専門モードで徹底サポート）\n"
            "- 💼 よろず経営相談（人材、資金繰り、販路拡大、事業承継など）\n\n"
            "【教えていただきたいこと】\n"
            "- 今の課題や困りごと\n"
            "- 業種・主要な製品やサービス（わかる範囲で）\n"
            "- 相手先のタイプ（B2B/B2C など）\n\n"
            "まずは、お困りのことを自由にお話しください。\n\n"
            "例：\n"
            "「原材料が上がり、取引先に値上げを相談したい」\n"
            "「人材採用がうまくいかない」\n"
            "「資金繰りが厳しくなってきた」"
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

    def _is_consent(self, message: str) -> bool:
        """ユーザーの承諾判定"""
        consent_keywords = [
            "はい", "お願い", "それで", "大丈夫", "ok", "yes", "進め",
            "よろしく", "いいです", "了解", "承知", "問題ない", "構いません",
            "そうして", "そうしよう", "賛成", "go"
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in consent_keywords)

    def _is_rejection(self, message: str) -> bool:
        """ユーザーの拒否判定"""
        reject_keywords = [
            "いや", "違う", "ちがう", "いいえ", "no", "やめ",
            "遠慮", "結構", "不要", "いらない", "やめて", "stop",
            "別の", "ほか", "他"
        ]
        message_lower = message.lower()
        return any(kw in message_lower for kw in reject_keywords)

    def _generate_initial_clarification(self) -> str:
        """初回ヒアリング質問"""
        return (
            "状況をもう少し詳しく教えてください。\n\n"
            "【確認させてください】\n"
            "1. どのような課題で困っていますか？\n"
            "   （例：値上げ交渉、人材採用、資金繰り、販路拡大など）\n\n"
            "2. あなたの会社について:\n"
            "   - 業種は？（製造、小売、建設、IT など）\n"
            "   - 主な顧客は？（B2B の取引先、一般消費者など）\n\n"
            "3. 緊急度は？（すぐ対応が必要、数ヶ月後の準備など）"
        )

    def _generate_followup_clarification(self, session: dict) -> str:
        """2回目以降のヒアリング質問（会話履歴を考慮）"""
        return (
            "ありがとうございます。もう少しだけ確認させてください。\n\n"
            "具体的には:\n"
            "- この課題は「価格交渉・値上げ」に関連するものでしょうか？\n"
            "- それとも、それ以外の経営課題（人材・資金・販路など）でしょうか？\n\n"
            "一言で構いませんので、教えてください。"
        )

    def _request_mode_consent(self, mode: str, reason: str) -> str:
        """モード切り替えの承諾を求める"""
        if mode == "mode2":
            mode_name = "💰 価格転嫁専門モード"
            mode_desc = (
                "価格交渉・値上げに特化した専門サポートモードです。\n"
                "14ステップの体系的な準備・実行支援で、交渉を成功に導きます。\n\n"
                "【提供する支援】\n"
                "- 市場データ分析・グラフ生成\n"
                "- 精緻なコスト試算\n"
                "- 取引先調査・財務分析\n"
                "- 交渉シナリオ作成・ロールプレイ\n"
                "- 法務知識検索・文書自動生成"
            )
        else:
            mode_name = "💼 よろず経営相談モード"
            mode_desc = (
                "幅広い経営課題について、対話形式でサポートします。\n\n"
                "【相談できること】\n"
                "- 人材採用・育成\n"
                "- 資金繰り・融資\n"
                "- 販路拡大・マーケティング\n"
                "- 事業承継・組織改革\n"
                "- その他、経営全般の悩み"
            )

        return (
            f"お話の内容から、**{mode_name}**が最適と判断しました。\n"
            f"（理由: {reason}）\n\n"
            f"{mode_desc}\n\n"
            f"このモードで進めてよろしいでしょうか？\n"
            f"「はい」「お願いします」などとお答えください。"
        )

    async def stream(self, session: dict, message: str):
        """Route to appropriate agent and yield streaming events."""
        print(f"[DEBUG] Orchestrator.stream() called with message: {message[:50]}...")
        print(f"[DEBUG] Session mode: {session.get('mode')}")
        print(f"[DEBUG] Pending mode change: {session.get('pending_mode_change')}")

        # === ステップ1: モード承諾待ちの処理 ===
        if "pending_mode_change" in session:
            if self._is_consent(message):
                # ユーザーが承諾した
                pending = session["pending_mode_change"]
                session["mode"] = pending["mode"]
                session["mode_confirmed"] = True
                del session["pending_mode_change"]

                mode_name = "💰 価格転嫁専門モード" if pending["mode"] == "mode2" else "💼 よろず経営相談モード"
                confirm_msg = f"**{mode_name}**に切り替えました。\nそれでは、あなたの課題解決をサポートします！"

                session["messages"].append({"role": "user", "content": message})
                session["messages"].append({"role": "assistant", "content": confirm_msg})

                yield {
                    "type": "mode_update",
                    "mode": pending["mode"],
                    "reason": pending["reason"],
                    "confidence": 1.0,
                }
                yield {"data": confirm_msg}
                return

            elif self._is_rejection(message):
                # ユーザーが拒否した
                del session["pending_mode_change"]

                reject_msg = "承知しました。では改めて、どのようなご相談でしょうか？"
                session["messages"].append({"role": "user", "content": message})
                session["messages"].append({"role": "assistant", "content": reject_msg})

                yield {"data": reject_msg}
                return

            else:
                # 承諾でも拒否でもない場合（例: 「詳しく教えて」など）
                # もう一度承諾を促す
                pending = session["pending_mode_change"]
                mode_name = "💰 価格転嫁専門モード" if pending["mode"] == "mode2" else "💼 よろず経営相談モード"

                retry_msg = (
                    f"**{mode_name}**への切り替えについて、承諾をお願いします。\n\n"
                    f"・進める場合: 「はい」「お願いします」などとお答えください\n"
                    f"・やめる場合: 「いいえ」「違います」などとお答えください"
                )

                session["messages"].append({"role": "user", "content": message})
                session["messages"].append({"role": "assistant", "content": retry_msg})

                yield {"data": retry_msg}
                return

        # === ステップ2: 会話履歴を構築（ユーザー + アシスタント両方） ===
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

        # === ステップ5: モード切り替え判定とユーザー承諾 ===
        mode_changed = (session["mode"] != mode)

        # 初回モード確定、またはモード切り替えが発生した場合
        if mode_changed and not session.get("mode_confirmed"):
            # ユーザー承諾を求める
            consent_msg = self._request_mode_consent(mode, mode_reason)
            session["pending_mode_change"] = {"mode": mode, "reason": mode_reason}

            session["messages"].append({"role": "user", "content": message})
            session["messages"].append({"role": "assistant", "content": consent_msg})

            yield {"data": consent_msg}
            return

        # モードが確定済みで変更がある場合は通知のみ
        if mode_changed:
            self.update_mode(session, mode)
            yield {
                "type": "mode_update",
                "mode": mode,
                "reason": mode_reason,
                "confidence": mode_confidence,
            }

        # === ステップ6: ユーザーメッセージを履歴に追加 ===
        session["messages"].append({"role": "user", "content": message})

        # === ステップ7: 適切な子エージェントへ委譲 ===
        agent_response = ""

        if mode == "mode2":
            agent = self.ensure_mode2_agent(session)
            async for event in agent.stream_async(message):
                # データチャンクを収集
                if "data" in event:
                    agent_response += event["data"]
                yield event
        else:
            agent: Mode1Agent = session["agents"]["mode1"]
            turn_index = len([m for m in session.get("messages", []) if m.get("role") == "assistant"])
            async for event in agent.stream_async(
                message,
                user_info=session.get("user_info"),
                turn_index=turn_index,
            ):
                # データチャンクを収集
                if "data" in event:
                    agent_response += event["data"]
                yield event

        # エージェント応答を履歴に追加
        if agent_response:
            session["messages"].append({"role": "assistant", "content": agent_response})

    def append_assistant_message(self, session: dict, content: str):
        session["messages"].append({"role": "assistant", "content": content})
