"""後方互換性用のスタブ

新しい設計では、Mode2Agentが価格転嫁専門エージェントとして機能します。
このファイルは後方互換性のために残されています。
"""

from agent.mode2 import Mode2Agent


# 後方互換性のためのエイリアス
class PriceTransferAgent(Mode2Agent):
    """後方互換性のためのエイリアスクラス"""
    pass
