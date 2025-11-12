"""価格転嫁支援エージェントのコア実装"""
from strands import Agent
from strands.models import BedrockModel
from strands_tools import current_time, calculator
from tools.diagram_generator import generate_diagram
from tools.web_search import web_search
from tools.knowledge_base import search_knowledge_base
from tools.step_detector import detect_current_step
from .prompts import MAIN_SYSTEM_PROMPT, get_step_prompt


class PriceTransferAgent:
    """価格転嫁支援エージェント"""

    def __init__(self, model_config: dict = None, current_step: str = None, user_info: dict = None):
        """エージェントを初期化

        Args:
            model_config: モデル設定の辞書（オプション）
            current_step: 現在のステップID（オプション）
            user_info: ユーザー基本情報の辞書（オプション）
        """
        print("=" * 80)
        print("[DEBUG] ========== PriceTransferAgent 初期化 ==========")
        print(f"[DEBUG] user_info引数: {user_info}")
        print(f"[DEBUG] user_infoの型: {type(user_info)}")
        
        self.current_step = current_step
        self.user_info = user_info or {}
        print(f"[DEBUG] self.user_infoに設定: {self.user_info}")
        
        self.model = self._initialize_model(model_config)
        self.agent = self._initialize_agent()
        print("=" * 80)

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

    def get_system_prompt(self) -> str:
        """現在のステップに応じたシステムプロンプトを生成

        Returns:
            str: システムプロンプト
        """
        prompt = MAIN_SYSTEM_PROMPT

        # ユーザー情報がある場合は追加プロンプトを結合
        # 空の辞書でないか、実際に値があるかチェック
        has_user_info = self.user_info and any(
            self.user_info.get(key) for key in 
            ["industry", "products", "companySize", "region", "clientIndustry", "priceTransferStatus"]
        )
        
        if has_user_info:
            print(f"[DEBUG] ユーザー情報を検出: {self.user_info}")
            user_info_prompt = self._build_user_info_prompt()
            if user_info_prompt:
                prompt += "\n\n" + user_info_prompt
                print("[DEBUG] ユーザー情報プロンプトをシステムプロンプトに追加しました")
        else:
            print(f"[DEBUG] ユーザー情報がありません。user_info={self.user_info}")

        # ステップが特定されている場合は追加プロンプトを結合
        if self.current_step:
            step_prompt = get_step_prompt(self.current_step)
            if step_prompt:
                prompt += "\n\n" + step_prompt

        return prompt

    def _build_user_info_prompt(self) -> str:
        """ユーザー情報からプロンプトを構築

        Returns:
            str: ユーザー情報プロンプト
        """
        info_parts = []
        
        if self.user_info.get("industry"):
            info_parts.append(f"- **業種**: {self.user_info['industry']}")
        if self.user_info.get("products"):
            info_parts.append(f"- **主な製品・サービス**: {self.user_info['products']}")
        if self.user_info.get("companySize"):
            info_parts.append(f"- **従業員規模**: {self.user_info['companySize']}")
        if self.user_info.get("region"):
            info_parts.append(f"- **地域**: {self.user_info['region']}")
        if self.user_info.get("clientIndustry"):
            info_parts.append(f"- **取引先の主な業種**: {self.user_info['clientIndustry']}")
        if self.user_info.get("priceTransferStatus"):
            info_parts.append(f"- **現在の価格転嫁の状況**: {self.user_info['priceTransferStatus']}")

        if not info_parts:
            print("[DEBUG] ユーザー情報が空のため、プロンプトに追加しません")
            return ""

        user_info_text = "## ユーザー企業の基本情報\n\n"
        user_info_text += "\n".join(info_parts)
        user_info_text += "\n\n**重要**: 上記のユーザー企業の情報を踏まえて、より具体的で実践的なアドバイスを提供してください。"
        user_info_text += "\n- 業種や規模に応じた具体的な事例や手法を提示"
        user_info_text += "\n- 地域の特性を考慮した情報提供"
        user_info_text += "\n- 現在の価格転嫁の状況に応じた適切なステップの提案"

        print(f"[DEBUG] ユーザー情報プロンプトを生成しました:")
        print(f"{user_info_text}")
        return user_info_text

    def _initialize_agent(self) -> Agent:
        """Strandsエージェントを初期化

        Returns:
            Agent: 初期化されたエージェント
        """
        system_prompt = self.get_system_prompt()
        
        # デバッグ: システムプロンプトの一部をログ出力（ユーザー情報が含まれているか確認）
        if "ユーザー企業の基本情報" in system_prompt:
            print("[DEBUG] ✅ システムプロンプトにユーザー情報が含まれています")
            # ユーザー情報部分を抽出して表示
            import re
            match = re.search(r'## ユーザー企業の基本情報.*?(?=\n\n##|$)', system_prompt, re.DOTALL)
            if match:
                print(f"[DEBUG] ユーザー情報部分:\n{match.group()}")
        else:
            print("[DEBUG] ⚠️ システムプロンプトにユーザー情報が含まれていません")
            print(f"[DEBUG] 現在のuser_info: {self.user_info}")
        
        return Agent(
            model=self.model,
            tools=[
                current_time,
                calculator,
                web_search,
                search_knowledge_base,
                generate_diagram,
                detect_current_step
            ],
            system_prompt=system_prompt,
            callback_handler=None
        )

    def update_step(self, new_step: str) -> bool:
        """ステップを更新してエージェントを再初期化

        Args:
            new_step: 新しいステップID

        Returns:
            bool: ステップが変更された場合True、変更なしの場合False
        """
        if self.current_step != new_step:
            print(f"[DEBUG] ステップ更新: {self.current_step} -> {new_step}")
            print(f"[DEBUG] ステップ更新時のuser_info: {self.user_info}")
            self.current_step = new_step
            # エージェントを再初期化（新しいプロンプトで）
            # ユーザー情報はself.user_infoに保持されているので、再初期化時にも含まれる
            self.agent = self._initialize_agent()
            return True
        return False

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
