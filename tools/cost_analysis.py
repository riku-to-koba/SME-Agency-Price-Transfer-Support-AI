"""コスト影響試算ツール（calculate_cost_impact）

自社の経営を守るために「絶対に譲れないライン」を数学的に算出する。
"""
from typing import Dict, Any, Optional
from strands import tool


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


@tool
def calculate_cost_impact(
    current_cost_structure: dict,
    price_changes: dict,
    current_sales: float = 0,
    target_profit_margin: float = 0
) -> str:
    """コスト上昇のインパクトを試算し、松竹梅の価格改定案を生成します。

    Args:
        current_cost_structure: 現在の原価構造
            各費目に ratio（比率）と amount（金額）を指定
            例: {
                "material_cost": {"ratio": 0.40, "amount": 1000000},
                "labor_cost": {"ratio": 0.35, "amount": 875000},
                "energy_cost": {"ratio": 0.10, "amount": 250000},
                "overhead": {"ratio": 0.15, "amount": 375000}
            }
        price_changes: 各費目の価格変動率
            例: {
                "material_cost": 0.20,  # +20%
                "labor_cost": 0.05,     # +5%
                "energy_cost": 0.30     # +30%
            }
        current_sales: 現在の売上高（オプション、指定なしの場合はコストから推計）
        target_profit_margin: 目標利益率（オプション、%で指定）

    Returns:
        str: 分析結果（コスト上昇額、シナリオ別価格案、推奨アクション）

    使用例:
    - 「いくら値上げすればいい？」と聞かれた時に使用
    - 原価情報をヒアリング後、このツールで試算
    """
    try:
        print(f"\n{'='*60}")
        print(f"📊 [calculate_cost_impact] コスト影響試算開始")
        print(f"{'='*60}\n")
        
        # 現在の総コストを計算
        current_total_cost = sum(
            item.get("amount", 0) 
            for item in current_cost_structure.values()
            if isinstance(item, dict)
        )
        
        if current_total_cost == 0:
            return "❌ コスト構造が正しく入力されていません。各費目の金額（amount）を確認してください。"
        
        # コスト上昇後の新しいコストを計算
        new_costs = {}
        cost_increases = {}
        
        for cost_type, structure in current_cost_structure.items():
            if not isinstance(structure, dict):
                continue
                
            original_amount = structure.get("amount", 0)
            change_rate = price_changes.get(cost_type, 0)
            
            new_amount = original_amount * (1 + change_rate)
            increase = new_amount - original_amount
            
            new_costs[cost_type] = {
                "original": original_amount,
                "new": new_amount,
                "increase": increase,
                "change_rate": change_rate
            }
            cost_increases[cost_type] = increase
        
        new_total_cost = sum(c["new"] for c in new_costs.values())
        total_cost_increase = new_total_cost - current_total_cost
        cost_increase_rate = (total_cost_increase / current_total_cost) * 100 if current_total_cost > 0 else 0
        
        # 売上高を推計（指定がない場合）
        if current_sales <= 0:
            # 一般的な中小企業の利益率（5-10%）を仮定
            assumed_profit_margin = 8
            current_sales = current_total_cost / (1 - assumed_profit_margin / 100)
        
        # 現在の利益率
        current_profit = current_sales - current_total_cost
        before_profit_rate = (current_profit / current_sales) * 100 if current_sales > 0 else 0
        
        # コスト上昇後の利益率（価格据え置きの場合）
        new_profit = current_sales - new_total_cost
        new_profit_rate = (new_profit / current_sales) * 100 if current_sales > 0 else 0
        
        # 松竹梅シナリオを生成
        scenarios = _calculate_scenarios(new_total_cost, before_profit_rate, new_profit_rate)
        
        # 結果をフォーマット
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

**交渉のポイント:**
1. コスト上昇の具体的データ（{cost_increase_rate:.1f}%上昇）を提示
2. 公的指針（労務費転嫁指針等）を参照
3. 取引先の財務状況も考慮した提案を

---
*この試算結果をグラフ化する場合は「グラフを作成して」とお伝えください。*
*交渉用の文書を作成する場合は「申入書を作成して」とお伝えください。*"""
        
        print(f"✅ コスト影響試算完了")
        print(f"   コスト上昇率: {cost_increase_rate:.1f}%")
        print(f"   推奨シナリオ: {scenarios[recommended]['name']}")
        
        return result
        
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"❌ コスト影響試算中にエラーが発生しました: {str(e)}"


# 後方互換性のため、旧関数名も維持
def analyze_cost_impact(*args, **kwargs):
    """後方互換性のためのラッパー"""
    return calculate_cost_impact(*args, **kwargs)
