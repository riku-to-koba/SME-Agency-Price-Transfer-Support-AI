"""交渉シミュレーションツール（simulate_negotiation）

本番で失敗しないためのロールプレイ訓練。AI相手の模擬戦で経験値を積む。
"""
import json
from typing import Optional, Dict, Any, List
import boto3
from strands import tool


# ペルソナ別の特徴と発言パターン
PERSONAS = {
    "aggressive": {
        "name": "高圧的な購買部長",
        "description": "コスト削減を最優先し、強気で交渉してくる",
        "traits": [
            "威圧的な態度で相手を動揺させようとする",
            "過去の取引実績を持ち出して値下げを要求",
            "「他社はもっと安い」と競合を引き合いに出す",
            "即答を迫り、考える時間を与えない",
        ],
        "typical_responses": [
            "それでは困りますね。他社さんはもっと安くしてくれますよ。",
            "御社との取引も長いですが、このご時世ですからね...",
            "今すぐ回答してもらえないと、他社に切り替えざるを得ません。",
            "コスト上昇？それは御社の経営努力で何とかしていただかないと。",
        ]
    },
    "logical": {
        "name": "論理武装した担当者",
        "description": "データや根拠を求め、論理的に反論してくる",
        "traits": [
            "具体的な数値やデータを求める",
            "論理の矛盾を指摘してくる",
            "業界平均や市場データを引用する",
            "感情よりも合理性を重視",
        ],
        "typical_responses": [
            "その数字の根拠を具体的に教えていただけますか？",
            "業界平均と比較して、御社の値上げ幅は妥当なのでしょうか？",
            "コスト上昇の内訳を詳しく見せていただけますか？",
            "他の仕入先からは、そこまでの値上げ要請は来ていないのですが...",
        ]
    },
    "collaborative": {
        "name": "協調的な担当者",
        "description": "Win-Winを目指し、建設的な対話を心がける",
        "traits": [
            "相手の状況を理解しようとする",
            "代替案を一緒に検討する姿勢",
            "長期的な関係を重視",
            "歩み寄りの余地を探る",
        ],
        "typical_responses": [
            "御社のお気持ちはよく分かります。一緒に解決策を考えましょう。",
            "段階的な値上げという形はいかがでしょうか？",
            "長いお付き合いですので、何とかお互いにとって良い形を見つけたいですね。",
            "他に削減できる部分がないか、一緒に検討してみましょうか？",
        ]
    },
    "cost_focused": {
        "name": "コスト重視の担当者",
        "description": "予算制約を理由に、粘り強く値下げを求める",
        "traits": [
            "予算の制約を強調する",
            "社内承認の難しさを訴える",
            "少しでも安くしようと粘る",
            "値上げ幅の縮小を求める",
        ],
        "typical_responses": [
            "正直なところ、今期の予算ではこの値上げは厳しいです...",
            "上には何て説明すればいいのか...社内で通らないと思います。",
            "もう少し何とかなりませんか？せめて半分の値上げ幅で...",
            "来期からということで、今期は据え置きにしていただけませんか？",
        ]
    }
}


def _evaluate_response(user_response: str, scenario: Dict, persona: str) -> Dict:
    """ユーザーの発言を評価"""
    
    # 評価基準
    scores = {
        "logic_score": 50,  # 論理性
        "tone_score": 50,   # 協調性
        "evidence_usage_score": 50,  # 証拠活用
    }
    
    strengths = []
    improvements = []
    
    response_lower = user_response.lower()
    
    # 論理性の評価
    logic_keywords = ["なぜなら", "データ", "根拠", "数字", "統計", "%", "円", "上昇", "増加"]
    logic_count = sum(1 for kw in logic_keywords if kw in user_response)
    scores["logic_score"] = min(100, 50 + logic_count * 10)
    
    if logic_count >= 3:
        strengths.append("論理的な説明ができている")
    elif logic_count == 0:
        improvements.append("具体的な数値やデータを示すと説得力が増します")
    
    # 協調性の評価
    collaborative_keywords = ["ご理解", "お願い", "一緒に", "ご検討", "ご協力", "長年", "関係"]
    aggressive_keywords = ["絶対", "無理", "できない", "当然"]
    
    collab_count = sum(1 for kw in collaborative_keywords if kw in user_response)
    aggr_count = sum(1 for kw in aggressive_keywords if kw in user_response)
    
    scores["tone_score"] = min(100, max(20, 50 + collab_count * 10 - aggr_count * 15))
    
    if collab_count >= 2:
        strengths.append("協調的なトーンで好印象")
    if aggr_count >= 2:
        improvements.append("もう少し協調的なトーンで伝えると良いでしょう")
    
    # 証拠活用の評価
    evidence_keywords = ["下請法", "法律", "指針", "ガイドライン", "企業物価指数", "最低賃金", "原材料"]
    evidence_count = sum(1 for kw in evidence_keywords if kw in user_response)
    scores["evidence_usage_score"] = min(100, 50 + evidence_count * 15)
    
    if evidence_count >= 2:
        strengths.append("法的根拠や公的データを効果的に活用")
    elif evidence_count == 0:
        improvements.append("公的データや法的根拠を示すと説得力が高まります")
    
    # 自社の強みに言及しているか
    strength_keywords = scenario.get("user_strengths", [])
    strength_mentioned = any(s.lower() in response_lower for s in strength_keywords)
    if strength_mentioned:
        strengths.append("自社の強みを効果的にアピール")
    else:
        improvements.append("自社の強み（品質、納期、技術力など）をアピールしましょう")
    
    # 総合スコア
    total_score = (scores["logic_score"] + scores["tone_score"] + scores["evidence_usage_score"]) // 3
    
    return {
        "score": total_score,
        **scores,
        "strengths": strengths if strengths else ["発言できています"],
        "improvements": improvements if improvements else ["このまま交渉を続けてください"],
    }


def _generate_opponent_response(scenario: Dict, persona_key: str, user_response: str, round_num: int) -> str:
    """相手役の発言を生成"""
    persona = PERSONAS.get(persona_key, PERSONAS["logical"])
    
    # ラウンドに応じた反応を選択
    if round_num == 1:
        # 最初は典型的な反応
        import random
        base_response = random.choice(persona["typical_responses"])
    elif round_num == 2:
        # 2回目は少し軟化
        if persona_key == "aggressive":
            base_response = "...そうですか。ただ、うちも予算の制約があるので、もう少し何とかなりませんか？"
        elif persona_key == "logical":
            base_response = "なるほど、データを見せていただきありがとうございます。ただ、この計算方法について確認させてください。"
        elif persona_key == "collaborative":
            base_response = "ありがとうございます。それでは、段階的な値上げという形で検討してみましょうか。"
        else:  # cost_focused
            base_response = "事情は理解しました。ただ、予算の関係で、せめて値上げ幅を抑えていただけないでしょうか。"
    else:
        # 3回目以降は収束
        if persona_key == "collaborative":
            base_response = "分かりました。御社の事情も理解できましたので、社内で前向きに検討させていただきます。"
        else:
            base_response = "...分かりました。持ち帰って検討させてください。1週間ほどお時間をいただけますか。"
    
    return base_response


@tool
def simulate_negotiation(
    scenario: dict,
    opponent_persona: str,
    user_response: str
) -> str:
    """交渉のロールプレイを行い、スコアリングとフィードバックを提供します。

    Args:
        scenario: 交渉シナリオ
            - client_name: 取引先名
            - negotiation_goal: 交渉目標（例: "10%値上げ"）
            - user_strengths: 自社の強み（リスト）
            - client_characteristics: 取引先の特徴
            - round: 現在のラウンド数（1から開始、省略時は1）
        opponent_persona: 相手役のペルソナ
            - "aggressive": 高圧的な購買部長
            - "logical": 論理武装した担当者
            - "collaborative": 協調的な担当者
            - "cost_focused": コスト重視の担当者
        user_response: ユーザーの発言（交渉での自分の発言）

    Returns:
        str: 相手の反応、スコア、フィードバック
    
    使用例:
    - 交渉練習: simulate_negotiation(
        scenario={"client_name": "A社", "negotiation_goal": "10%値上げ", "user_strengths": ["高品質", "短納期"]},
        opponent_persona="cost_focused",
        user_response="原材料費が20%上昇しており..."
      )
    """
    try:
        # ペルソナを検証
        if opponent_persona not in PERSONAS:
            return f"""❌ 無効なペルソナです: {opponent_persona}

対応ペルソナ:
- aggressive: 高圧的な購買部長
- logical: 論理武装した担当者
- collaborative: 協調的な担当者
- cost_focused: コスト重視の担当者"""
        
        persona = PERSONAS[opponent_persona]
        round_num = scenario.get("round", 1)
        
        # ユーザーの発言を評価
        evaluation = _evaluate_response(user_response, scenario, opponent_persona)
        
        # 相手役の反応を生成
        opponent_response = _generate_opponent_response(scenario, opponent_persona, user_response, round_num)
        
        # 次のアドバイス
        if evaluation["score"] >= 80:
            next_suggestion = "素晴らしい対応です！この調子で交渉を続けてください。"
        elif evaluation["score"] >= 60:
            next_suggestion = "良い流れです。さらに具体的なデータを示すと、より説得力が増します。"
        else:
            if evaluation["logic_score"] < 60:
                next_suggestion = "次は、具体的な数値データを示して論理的に説明してみましょう。"
            elif evaluation["tone_score"] < 60:
                next_suggestion = "次は、相手の立場にも配慮しつつ、協調的なトーンで伝えてみましょう。"
            else:
                next_suggestion = "次は、法的根拠や公的データを引用すると説得力が高まります。"
        
        # 結果をフォーマット
        result = f"""🎭 **交渉シミュレーション - ラウンド {round_num}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【相手役: {persona['name']}】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

「{opponent_response}」

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【あなたの発言の評価】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **総合スコア: {evaluation['score']}点**

| 評価項目 | スコア |
|----------|--------|
| 論理性 | {evaluation['logic_score']}点 |
| 協調性 | {evaluation['tone_score']}点 |
| 証拠活用 | {evaluation['evidence_usage_score']}点 |

**✅ 良かった点:**
{chr(10).join('- ' + s for s in evaluation['strengths'])}

**💡 改善ポイント:**
{chr(10).join('- ' + s for s in evaluation['improvements'])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【次のアドバイス】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{next_suggestion}

---
*シミュレーションを続ける場合は、相手の発言に対する返答を入力してください。*
*終了する場合は「終了」または「ありがとうございました」と入力してください。*"""
        
        return result
        
    except Exception as e:
        return f"❌ シミュレーション中にエラーが発生しました: {str(e)}"



