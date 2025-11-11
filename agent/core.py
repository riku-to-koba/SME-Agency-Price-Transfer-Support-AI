"""価格転嫁支援エージェントのコア実装"""
from strands import Agent
from strands.models import BedrockModel
from strands_tools import current_time, calculator
from tools.diagram_generator import generate_diagram
from tools.search_tools import web_search, search_knowledge_base
from .prompts import SYSTEM_PROMPT


class PriceTransferAgent:
    """価格転嫁支援エージェント"""

    def __init__(self, model_config: dict = None):
        """エージェントを初期化

        Args:
            model_config: モデル設定の辞書（オプション）
        """
        self.model = self._initialize_model(model_config)
        self.agent = self._initialize_agent()

    def _initialize_model(self, config: dict = None) -> BedrockModel:
        """Bedrockモデルを初期化

        Args:
            config: モデル設定の辞書（デフォルト設定を上書き）

        Returns:
            BedrockModel: 初期化されたモデル
        """
        default_config = {
            "model_id": "jp.anthropic.claude-haiku-4-5-20251001-v1:0",
            "region_name": "ap-northeast-1",
            "temperature": 0.7,
            "max_tokens": 50000,
            "streaming": True,
        }

        if config:
            default_config.update(config)

        return BedrockModel(**default_config)

    def _initialize_agent(self) -> Agent:
        """Strandsエージェントを初期化

        Returns:
            Agent: 初期化されたエージェント
        """
        return Agent(
            model=self.model,
            tools=[
                current_time,
                calculator,
                web_search,
                search_knowledge_base,
                generate_diagram
            ],
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None
        )

    async def stream_async(self, prompt: str):
        """非同期ストリーミング応答

        Args:
            prompt: ユーザーからのプロンプト

        Yields:
            イベントストリーム
        """
        async for event in self.agent.stream_async(prompt):
            yield event

    def run(self, prompt: str) -> str:
        """同期実行（テスト用）

        Args:
            prompt: ユーザーからのプロンプト

        Returns:
            str: エージェントの応答
        """
        return self.agent.run(prompt)
