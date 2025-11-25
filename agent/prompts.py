"""システムプロンプト定義（後方互換性用）

新しい設計では、各エージェント（Mode1Agent, Mode2Agent）が
独自のシステムプロンプトを持っています。

このファイルは後方互換性のために残されています。
"""

# 後方互換性のため、空のプロンプトを定義
MAIN_SYSTEM_PROMPT = ""
SYSTEM_PROMPT = ""

# ステップコンテキストは使用されなくなりました
STEP_CONTEXT = {}


def get_step_prompt(step: str) -> str:
    """後方互換性のためのダミー関数"""
    return ""
