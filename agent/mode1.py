"""Mode1Agent: よろず相談エージェント（LLMベース + Web検索対応）

一般的な経営相談に対応する汎用エージェント。
- 傾聴・状況整理・メンタルケア
- 幅広い経営アドバイス（資金繰り、人材、販路拡大等）
- Web検索機能（標準搭載）
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
import boto3


# Mode1用システムプロンプト
MODE1_SYSTEM_PROMPT = """あなたは中小企業経営者のための「よろず相談」AIアシスタントです。

## あなたの役割

経営者の悩みを親身に聞き、真の課題を特定し、適切なアドバイスを提供します。

### 基本姿勢
- **傾聴**: まず経営者の話を丁寧に聞き、状況を整理する
- **共感**: 経営者の孤独感や不安に寄り添う
- **実践的**: 具体的で実行可能なアドバイスを提供する

### 対応できる相談内容
- 資金繰り・融資
- 人材採用・育成・労務管理
- 販路拡大・マーケティング
- 事業承継・組織改革
- 取引先との関係
- その他、経営全般の悩み

## 対話の進め方

1. **状況把握**: ユーザーの話を聞き、課題の背景を理解する
2. **課題整理**: 複数の課題がある場合は整理し、優先順位を確認する
3. **情報提供**: 必要に応じてWeb検索で最新情報を取得する
4. **アドバイス**: 具体的で実行可能な提案をする
5. **次のステップ**: 何から始めるべきか明確にする

## Web検索の活用

以下のような場合にWeb検索ツールを使用してください：
- 最新の市場動向・業界ニュースが必要な場合
- 補助金・助成金の情報を調べる場合
- 統計データや事例を探す場合
- 法改正や規制の最新情報を確認する場合

## 回答時の注意

- 専門用語は分かりやすく説明する
- 長すぎる回答は避け、要点を絞る
- 必要に応じて箇条書きを活用する
- 「次に何をすればいいか」を明確にする

## 価格転嫁の話題について

ユーザーが価格転嫁・値上げ交渉に関する相談を始めた場合、
専門モード（Mode 2）への切り替えを提案することがあります。
ただし、このモードでも基本的な相談対応は可能です。
"""


class Mode1Agent:
    """よろず相談エージェント - 一般経営相談に対応"""

    def __init__(self):
        """エージェントを初期化"""
        self.model = None
        self.agent = None
        self.init_error: Optional[str] = None
        self._initialize()

    def _initialize(self):
        """Strands AgentとBedrockモデルを初期化"""
        try:
            from strands import Agent
            from strands.models import BedrockModel

            # AWSセッション作成
            session = boto3.Session(
                profile_name='bedrock_use_only',
                region_name='ap-northeast-1'
            )

            # Bedrockモデル初期化
            self.model = BedrockModel(
                model_id="jp.anthropic.claude-haiku-4-5-20251001-v1:0",
                temperature=0.7,
                max_tokens=4096,
                streaming=True,
                boto_session=session,
            )

            # Web検索ツールをインポート
            from tools.web_search import web_search

            # エージェント初期化
            self.agent = Agent(
                model=self.model,
                tools=[web_search],  # Web検索を標準搭載
                system_prompt=MODE1_SYSTEM_PROMPT,
            )

        except Exception as e:
            self.init_error = f"Mode1Agent初期化エラー: {str(e)}"
            print(f"[ERROR] {self.init_error}")

    async def stream_async(
        self,
        prompt: str,
        user_info: Optional[dict] = None,
        turn_index: int = 0,
    ):
        """非同期ストリーミング応答

        Args:
            prompt: ユーザーからのプロンプト
            user_info: ユーザー情報（オプション）
            turn_index: 会話ターン数

        Yields:
            イベントストリーム
        """
        # 初期化エラーがある場合
        if self.init_error or not self.agent:
            yield {"data": f"申し訳ありません。システムの初期化でエラーが発生しました。\n\n{self.init_error or 'エージェントが初期化されていません'}"}
            return

        # ユーザー情報をプロンプトに追加
        enhanced_prompt = prompt
        if user_info:
            info_parts = []
            if user_info.get("industry"):
                info_parts.append(f"業種: {user_info['industry']}")
            if user_info.get("products"):
                info_parts.append(f"主要製品・サービス: {user_info['products']}")
            if user_info.get("companySize"):
                info_parts.append(f"従業員規模: {user_info['companySize']}")
            if user_info.get("region"):
                info_parts.append(f"地域: {user_info['region']}")

            if info_parts:
                context = "\n".join(info_parts)
                enhanced_prompt = f"【ユーザー企業情報】\n{context}\n\n【相談内容】\n{prompt}"

        try:
            async for event in self.agent.stream_async(enhanced_prompt):
                yield event
        except Exception as e:
            yield {"data": f"申し訳ありません。応答生成中にエラーが発生しました。\n\nエラー: {str(e)}"}

    def run(self, prompt: str, user_info: Optional[dict] = None, turn_index: int = 0) -> str:
        """同期実行（テスト用）

        Args:
            prompt: ユーザーからのプロンプト
            user_info: ユーザー情報（オプション）
            turn_index: 会話ターン数

        Returns:
            str: エージェントの応答
        """
        import asyncio

        async def collect():
            chunks = []
            async for evt in self.stream_async(prompt, user_info=user_info, turn_index=turn_index):
                if "data" in evt:
                    chunks.append(evt["data"])
            return "".join(chunks)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(collect())
        finally:
            loop.close()
