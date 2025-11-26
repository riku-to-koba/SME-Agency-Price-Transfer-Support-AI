"""コスト影響試算ツール（calculate_cost_impact）

自社の経営を守るために「絶対に譲れないライン」を数学的に算出する。
このツールはモーダル表示をトリガーし、ユーザーに情報入力を促します。
実際の計算はフロントエンドからAPI経由で行われます。
"""
from typing import Dict, Any, Optional
from strands import tool


@tool
def calculate_cost_impact() -> str:
    """理想の原価計算を行い、松竹梅の価格改定案を生成します。

    ⚠️ 重要: このツールはモーダル入力方式です
    - 事前のヒアリングは不要です
    - 原価情報や価格上昇率の確認は不要です
    - すぐにこのツールを呼び出してください
    - ツールを呼び出すと、ユーザーに入力フォーム（モーダル）が自動表示されます
    - ⚠️ このツールを呼び出したら、追加の説明は一切不要です。出力を終了してください。

    このツールは以下の場合に使用してください：
    - 「いくら値上げすればいい？」と聞かれた時
    - 「適正価格を知りたい」と言われた時
    - 「コストが上がったらどうすればいい？」と聞かれた時
    - 「価格設定のシミュレーションをしたい」と言われた時
    - 「原価計算をしたい」と言われた時
    - 「赤字にならないラインは？」と聞かれた時

    【モーダルでユーザーが入力する項目】※「去年 vs 今年」方式
    各費目について「以前」と「現在」の金額を入力（上昇率は自動計算）
    
    - 月の売上: 以前 ○○万円 → 現在 ○○万円
    - 仕入れ・材料費: 以前 ○○万円 → 現在 ○○万円
    - 人件費（給与+社保）: 以前 ○○万円 → 現在 ○○万円
    - 光熱費（電気・ガス）: 以前 ○○万円 → 現在 ○○万円
    - その他経費: 以前 ○○万円 → 現在 ○○万円
    
    ※ 分からない項目は空欄でもOK（業界平均で試算）
    ※ だいたいの金額でOK

    【出力】
    - 🌟 松（理想）: コスト高騰前より高い利益率を確保
    - ✅ 竹（妥当）: コスト高騰前の利益率を維持
    - ⚡ 梅（最低防衛）: 事業継続のための最低ライン

    Returns:
        str: モーダル表示を促すメッセージ
    """
    
    # 短いメッセージのみ返す（モーダル表示後はAI出力を止める）
    # 戻り値に「出力終了」を明示して、LLMがこれ以上喋らないようにする
    return "[COST_MODAL_TRIGGER]\n\n【システム指示】入力フォームを表示しました。ユーザーの入力を待っています。これ以上の出力は不要です。"


# 詳細計算用の関数（APIから呼び出される）
def calculate_cost_impact_detailed(
    cost_data: dict,
    current_sales: float = 0,
    previous_sales: float = 0
) -> str:
    """詳細なコスト影響試算（内部API用）- 「去年 vs 今年」方式
    
    この関数はAPIエンドポイント（/api/ideal-pricing）から呼び出されます。
    
    Args:
        cost_data: 各費目の「以前」と「現在」の金額
            例: {
                "material_cost": {"previous": 500000, "current": 600000},
                "labor_cost": {"previous": 300000, "current": 315000},
                "energy_cost": {"previous": 100000, "current": 130000},
                "overhead": {"previous": 100000, "current": 105000}
            }
        current_sales: 現在の月間売上高（万円）
        previous_sales: 以前の月間売上高（万円）
    """
    try:
        # 業界平均の上昇率（空欄時のデフォルト値）
        DEFAULT_INCREASE_RATES = {
            "material_cost": 0.15,    # 材料費: +15%
            "labor_cost": 0.05,       # 人件費: +5%
            "energy_cost": 0.25,      # 光熱費: +25%
            "overhead": 0.03          # その他: +3%
        }
        
        # コストデータの処理（上昇率を自動計算）
        new_costs = {}
        previous_total_cost = 0
        current_total_cost = 0
        
        for cost_type, data in cost_data.items():
            if not isinstance(data, dict):
                continue
            
            previous = data.get("previous", 0) or 0
            current = data.get("current", 0) or 0
            
            # 両方空欄の場合はスキップ
            if previous == 0 and current == 0:
                continue
            
            # 片方だけ入力されている場合はデフォルト上昇率を適用
            if previous > 0 and current == 0:
                change_rate = DEFAULT_INCREASE_RATES.get(cost_type, 0.10)
                current = previous * (1 + change_rate)
            elif current > 0 and previous == 0:
                change_rate = DEFAULT_INCREASE_RATES.get(cost_type, 0.10)
                previous = current / (1 + change_rate)
            else:
                # 両方入力されている場合は上昇率を計算
                change_rate = (current - previous) / previous if previous > 0 else 0
            
            new_costs[cost_type] = {
                "original": previous,
                "new": current,
                "increase": current - previous,
                "change_rate": change_rate
            }
            previous_total_cost += previous
            current_total_cost += current
        
        if current_total_cost == 0:
            return "❌ コスト情報が入力されていません。少なくとも1つの費目を入力してください。"
        
        total_cost_increase = current_total_cost - previous_total_cost
        cost_increase_rate = (total_cost_increase / previous_total_cost) * 100 if previous_total_cost > 0 else 0
        
        # 売上高の処理
        if current_sales <= 0:
            # 売上高が未入力の場合、コストから推計（利益率8%と仮定）
            current_sales = current_total_cost / (1 - 0.08)
        
        if previous_sales <= 0:
            previous_sales = previous_total_cost / (1 - 0.08)
        
        # 利益率計算
        previous_profit = previous_sales - previous_total_cost
        before_profit_rate = (previous_profit / previous_sales) * 100 if previous_sales > 0 else 8.0
        
        current_profit = current_sales - current_total_cost
        new_profit_rate = (current_profit / current_sales) * 100 if current_sales > 0 else 0
        
        # 松竹梅シナリオ
        scenarios = _calculate_scenarios(current_total_cost, before_profit_rate, new_profit_rate)
        
        return _format_result(
            previous_total_cost, current_total_cost, new_costs,
            current_sales, before_profit_rate, new_profit_rate,
            cost_increase_rate, scenarios
        )
        
    except Exception as e:
        return f"❌ 計算エラー: {str(e)}"


def _calculate_scenarios(
    current_total_cost: float,
    before_profit_rate: float,
    current_profit_rate: float
) -> Dict[str, Dict[str, float]]:
    """松竹梅の3段階価格設定シナリオを生成"""
    
    # 松（理想）: コスト高騰前の利益率 + 2%
    premium_margin = before_profit_rate + 2
    premium_price = current_total_cost / (1 - premium_margin / 100) if premium_margin < 100 else current_total_cost * 1.2
    
    # 竹（妥当）: コスト高騰前の利益率を維持
    standard_margin = before_profit_rate
    standard_price = current_total_cost / (1 - standard_margin / 100) if standard_margin < 100 else current_total_cost * 1.1
    
    # 梅（最低防衛）: 利益率3%を確保
    minimum_margin = 3.0
    minimum_price = current_total_cost / (1 - minimum_margin / 100)
    
    return {
        "premium": {
            "name": "松（理想）",
            "price": round(premium_price, 0),
            "profit_margin": round(premium_margin, 2),
            "description": "コスト高騰前より高い利益率を確保"
        },
        "standard": {
            "name": "竹（妥当）",
            "price": round(standard_price, 0),
            "profit_margin": round(standard_margin, 2),
            "description": "コスト高騰前の利益率を維持"
        },
        "minimum": {
            "name": "梅（最低防衛）",
            "price": round(minimum_price, 0),
            "profit_margin": round(minimum_margin, 2),
            "description": "事業継続のための最低ライン"
        }
    }


def _format_result(
    current_total_cost, new_total_cost, new_costs,
    current_sales, before_profit_rate, new_profit_rate,
    cost_increase_rate, scenarios
) -> str:
    """結果をフォーマット"""
    result = f"""📊 **コスト影響分析結果**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【現状分析】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**現在のコスト構造:**
"""
    
    for cost_type, data in new_costs.items():
        type_name = {
            "material_cost": "材料費",
            "labor_cost": "労務費",
            "energy_cost": "エネルギー費",
            "overhead": "その他経費"
        }.get(cost_type, cost_type)
        
        change_pct = data["change_rate"] * 100
        result += f"- {type_name}: {data['original']:,.0f}円 → {data['new']:,.0f}円 ({'+' if change_pct >= 0 else ''}{change_pct:.1f}%)\n"
    
    total_cost_increase = new_total_cost - current_total_cost
    result += f"""
**総コスト:** {current_total_cost:,.0f}円 → {new_total_cost:,.0f}円
**コスト上昇額:** +{total_cost_increase:,.0f}円 (+{cost_increase_rate:.1f}%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【利益への影響】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 現在の売上高: {current_sales:,.0f}円
- コスト上昇前の利益率: {before_profit_rate:.1f}%
- **価格据え置き時の利益率: {new_profit_rate:.1f}%** {'⚠️ 赤字転落' if new_profit_rate < 0 else '⚠️ 利益圧迫' if new_profit_rate < 3 else ''}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【価格改定シナリオ（松竹梅）】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    for key, scenario in scenarios.items():
        price_increase = scenario["price"] - current_sales
        price_increase_rate = (price_increase / current_sales) * 100 if current_sales > 0 else 0
        
        emoji = "🌟" if key == "premium" else "✅" if key == "standard" else "⚡"
        result += f"""{emoji} **{scenario['name']}**
   - 目標価格: {scenario['price']:,.0f}円（+{price_increase_rate:.1f}%）
   - 利益率: {scenario['profit_margin']:.1f}%
   - {scenario['description']}

"""
    
    # 推奨アクション
    if new_profit_rate < 0:
        urgency = "🚨 **緊急度: 高** - 価格転嫁なしでは赤字です。早急な交渉が必要です。"
        recommended = "standard"
    elif new_profit_rate < 3:
        urgency = "⚠️ **緊急度: 中** - 利益率が大幅に低下します。価格転嫁を検討してください。"
        recommended = "standard"
    else:
        urgency = "📝 **緊急度: 低** - 利益率は維持できますが、将来に備えた交渉も検討可能です。"
        recommended = "minimum"
    
    result += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【推奨アクション】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{urgency}

**推奨シナリオ:** {scenarios[recommended]['name']}
- 交渉目標: {scenarios[recommended]['price']:,.0f}円（現行比 +{((scenarios[recommended]['price'] - current_sales) / current_sales * 100):.1f}%）
- 最低防衛ライン: {scenarios['minimum']['price']:,.0f}円
"""
    
    return result


# 後方互換性のため、旧関数名も維持
def analyze_cost_impact(*args, **kwargs):
    """後方互換性のためのラッパー"""
    return calculate_cost_impact()
