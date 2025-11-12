"""ステップ判定ツール"""
import json
from strands import tool


@tool
def detect_current_step(user_question: str, conversation_context: str = "") -> str:
    """ユーザーの質問から価格転嫁プロセスのステップを判定します。

    このツールを使用すると、ユーザーの質問内容に最も適したステップが判定され、
    システムがそのステップに特化したアドバイスを提供できるようになります。

    ## 判定可能なステップ

    ### 価格交渉準備編（STEP 0）
    - STEP_0_CHECK_1: 取引条件・業務内容の確認
    - STEP_0_CHECK_2: 原材料費・労務費データの定期収集
    - STEP_0_CHECK_3: 原価計算の実施
    - STEP_0_CHECK_4: 単価表の作成
    - STEP_0_CHECK_5: 見積書フォーマットの整備
    - STEP_0_CHECK_6: 取引先の経営方針・業績把握
    - STEP_0_CHECK_7: 自社の付加価値の明確化
    - STEP_0_CHECK_8: 適正な取引慣行の確認

    ### 価格交渉実践編（STEP 1-5）
    - STEP_1: 業界動向の情報収集
    - STEP_2: 取引先情報収集と交渉方針検討
    - STEP_3: 書面での申し入れ
    - STEP_4: 説明資料の準備
    - STEP_5: 発注後に発生する価格交渉

    Args:
        user_question: ユーザーの質問内容
        conversation_context: これまでの会話の文脈（オプション）

    Returns:
        str: 判定結果（JSON形式）
        {
            "step": "STEP_0_CHECK_3",
            "confidence": "high",
            "reasoning": "原価計算について質問しているため"
        }
    """
    # このツールはLLMに判定ロジックを委ねる
    # システムプロンプトに判定ロジックが記述されており、
    # エージェントがこのツールを呼び出すことで判定を実行する

    return json.dumps({
        "step": "UNKNOWN",
        "confidence": "low",
        "reasoning": "このツールを使用後、エージェントが質問内容を分析してステップを判定します"
    }, ensure_ascii=False)
