"""ステップ判定ツール"""
import json
import boto3
import re
from strands import tool


@tool
def detect_current_step(user_question: str, conversation_context: str = "") -> str:
    """ユーザーの質問から価格転嫁プロセスのステップを判定します。

    【デバッグログ機能】
    このツールは実行時に詳細なログを出力します。

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
    print("\n" + "="*80)
    print("🔍 [detect_current_step] ツールが呼び出されました")
    print(f"📝 ユーザーの質問: {user_question}")
    print(f"📚 会話文脈: {conversation_context[:100] if conversation_context else '(なし)'}...")
    print("="*80 + "\n")

    try:
        print("🔧 [STEP 1] Bedrockクライアントを初期化中...")
        # LLMを使ってステップを判定
        bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name='ap-northeast-1'
        )
        print("✅ [STEP 1] Bedrockクライアント初期化完了\n")

        # ステップ判定用のプロンプト
        prompt = f"""以下のユーザーの質問から、最も関連する価格転嫁プロセスのステップを判定してください。

【ユーザーの質問】
{user_question}

【判定可能なステップ】
- STEP_0_CHECK_1: 取引条件・業務内容の確認
- STEP_0_CHECK_2: 原材料費・労務費データの定期収集
- STEP_0_CHECK_3: 原価計算の実施
- STEP_0_CHECK_4: 単価表の作成
- STEP_0_CHECK_5: 見積書フォーマットの整備
- STEP_0_CHECK_6: 取引先の経営方針・業績把握
- STEP_0_CHECK_7: 自社の付加価値の明確化
- STEP_0_CHECK_8: 適正な取引慣行の確認
- STEP_1: 業界動向の情報収集
- STEP_2: 取引先情報収集と交渉方針検討
- STEP_3: 書面での申し入れ
- STEP_4: 説明資料の準備
- STEP_5: 発注後に発生する価格交渉

【判定ルール】
1. 質問内容から最も関連するステップを1つ選んでください
2. 複数のステップに関連する場合は、最も重要なものを選んでください
3. 明確に判定できない一般的な質問の場合は "UNKNOWN" を返してください

【出力形式】
以下のJSON形式で出力してください：
{{
    "step": "STEP_0_CHECK_3",
    "confidence": "high",
    "reasoning": "原価計算について質問しているため"
}}

confidence は "high", "medium", "low" のいずれかです。
"""

        print("🔧 [STEP 2] プロンプトを作成しました")
        print(f"📄 プロンプト長: {len(prompt)} 文字\n")

        print("🔧 [STEP 3] Bedrock APIを呼び出し中...")
        # Bedrock APIを呼び出し（Claude Haiku）
        response = bedrock_runtime.invoke_model(
            modelId="jp.anthropic.claude-haiku-4-5-20251001-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0.3,  # 判定タスクなので低めに設定
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        print("✅ [STEP 3] Bedrock API呼び出し成功\n")

        # レスポンスを解析
        print("🔧 [STEP 4] レスポンスを解析中...")
        response_body = json.loads(response['body'].read())
        assistant_message = response_body['content'][0]['text']

        print("📩 [LLMレスポンス]")
        print("-" * 80)
        print(assistant_message)
        print("-" * 80 + "\n")

        # JSONブロックを抽出（```json ... ``` の中身を取得）
        print("🔧 [STEP 5] JSON抽出中...")
        json_match = re.search(r'```json\s*(.*?)\s*```', assistant_message, re.DOTALL)
        if json_match:
            result_json = json_match.group(1)
            print("✅ コードブロック内のJSONを抽出")
        else:
            # コードブロックがない場合は全体をJSONとして解析
            result_json = assistant_message
            print("⚠️  コードブロックなし - 全体をJSONとして解析")

        print(f"📄 抽出されたJSON: {result_json[:200]}...\n")

        # JSONをパースして検証
        print("🔧 [STEP 6] JSONをパース中...")
        result = json.loads(result_json.strip())
        print("✅ JSONパース成功\n")

        # 必須フィールドの確認
        print("🔧 [STEP 7] フィールド検証中...")
        if "step" not in result:
            result["step"] = "UNKNOWN"
            print("⚠️  'step' フィールドが見つかりません - UNKNOWNを設定")
        if "confidence" not in result:
            result["confidence"] = "low"
            print("⚠️  'confidence' フィールドが見つかりません - lowを設定")
        if "reasoning" not in result:
            result["reasoning"] = "判定理由が取得できませんでした"
            print("⚠️  'reasoning' フィールドが見つかりません")

        final_result = json.dumps(result, ensure_ascii=False)
        print("\n" + "="*80)
        print("🎉 [判定完了]")
        print(f"📊 判定結果: {final_result}")
        print("="*80 + "\n")

        return final_result

    except Exception as e:
        # エラーが発生した場合はUNKNOWNを返す
        print("\n" + "="*80)
        print("❌ [エラー発生]")
        print(f"エラー種類: {type(e).__name__}")
        print(f"エラーメッセージ: {str(e)}")
        print("="*80 + "\n")

        import traceback
        print("📋 [詳細トレースバック]")
        print("-" * 80)
        traceback.print_exc()
        print("-" * 80 + "\n")

        error_result = json.dumps({
            "step": "UNKNOWN",
            "confidence": "low",
            "reasoning": f"判定エラー: {str(e)}"
        }, ensure_ascii=False)

        print(f"⚠️  エラー時の返却値: {error_result}\n")
        return error_result
