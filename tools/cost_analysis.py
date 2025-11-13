"""価格転嫁検討ツール（CHECK 9専用）"""
from strands import tool


def calculate_cost_impact(
    before_sales: float,
    before_cost: float,
    before_expenses: float,
    current_sales: float,
    current_cost: float,
    current_expenses: float
) -> dict:
    """コスト高騰の影響を計算
    
    Args:
        before_sales: コスト高騰前の売上高
        before_cost: コスト高騰前の売上原価
        before_expenses: コスト高騰前の販管費・その他経費
        current_sales: 現在の売上高
        current_cost: 現在の売上原価
        current_expenses: 現在の販管費・その他経費
    
    Returns:
        dict: 計算結果
    """
    # コスト高騰前の計算
    before_total_cost = before_cost + before_expenses
    before_profit = before_sales - before_total_cost
    before_profit_rate = (before_profit / before_sales * 100) if before_sales > 0 else 0
    
    # 現在の計算
    current_total_cost = current_cost + current_expenses
    current_profit = current_sales - current_total_cost
    current_profit_rate = (current_profit / current_sales * 100) if current_sales > 0 else 0
    
    # 増減率の計算
    sales_change_rate = ((current_sales - before_sales) / before_sales * 100) if before_sales > 0 else 0
    cost_change_rate = ((current_cost - before_cost) / before_cost * 100) if before_cost > 0 else 0
    expenses_change_rate = ((current_expenses - before_expenses) / before_expenses * 100) if before_expenses > 0 else 0
    total_cost_change_rate = ((current_total_cost - before_total_cost) / before_total_cost * 100) if before_total_cost > 0 else 0
    profit_change_rate = ((current_profit - before_profit) / before_profit * 100) if before_profit > 0 else 0
    
    # 増減額の計算
    sales_change = current_sales - before_sales
    cost_change = current_cost - before_cost
    expenses_change = current_expenses - before_expenses
    total_cost_change = current_total_cost - before_total_cost
    profit_change = current_profit - before_profit
    
    # 参考価格の算出（コスト高騰前の利益率を維持するための価格）
    # 参考価格 = 現在の総コスト / (1 - コスト高騰前の利益率)
    if before_profit_rate < 100:
        reference_price = current_total_cost / (1 - before_profit_rate / 100) if before_profit_rate < 100 else current_total_cost
    else:
        reference_price = current_total_cost
    
    # 現在価格との差額
    price_gap = reference_price - current_sales
    price_gap_rate = (price_gap / current_sales * 100) if current_sales > 0 else 0
    
    return {
        "before": {
            "sales": before_sales,
            "cost": before_cost,
            "expenses": before_expenses,
            "total_cost": before_total_cost,
            "profit": before_profit,
            "profit_rate": before_profit_rate
        },
        "current": {
            "sales": current_sales,
            "cost": current_cost,
            "expenses": current_expenses,
            "total_cost": current_total_cost,
            "profit": current_profit,
            "profit_rate": current_profit_rate
        },
        "changes": {
            "sales": {
                "amount": sales_change,
                "rate": sales_change_rate
            },
            "cost": {
                "amount": cost_change,
                "rate": cost_change_rate
            },
            "expenses": {
                "amount": expenses_change,
                "rate": expenses_change_rate
            },
            "total_cost": {
                "amount": total_cost_change,
                "rate": total_cost_change_rate
            },
            "profit": {
                "amount": profit_change,
                "rate": profit_change_rate
            }
        },
        "reference_price": reference_price,
        "price_gap": price_gap,
        "price_gap_rate": price_gap_rate
    }


@tool
def analyze_cost_impact(
    before_sales: float,
    before_cost: float,
    before_expenses: float,
    current_sales: float,
    current_cost: float,
    current_expenses: float
) -> str:
    """コスト高騰の影響を分析し、参考価格を算出します。
    
    このツールはSTEP_0_CHECK_9（価格転嫁の必要性判定）で使用します。
    中小企業庁の価格転嫁検討ツール（kakakutenka.smrj.go.jp）のロジックを実装しています。
    
    価格転嫁の必要性を判定するためのツールで、営業利益が赤字になっているかを調査します。
    原価計算ができている前提で、コスト高騰の影響を分析し、価格転嫁が必要かどうかを判断します。
    
    【使用タイミング】
    - ユーザーがコスト高騰前と現在の数値（売上高、売上原価、販管費など）を提供した場合
    - ユーザーが「コストが上がった」「利益率が下がった」「価格転嫁が必要か判断したい」などと言った場合
    - ユーザーが「コスト高騰の影響を分析したい」「価格転嫁の必要性を知りたい」と希望した場合
    
    【機能】
    - コスト高騰前と現在のデータを比較
    - 各コスト項目の増減率・増減額を計算
    - 利益率の変化を分析
    - コスト高騰前の利益率を維持するための参考価格を算出
    - 価格転嫁の必要性を判定
    
    Args:
        before_sales: コスト高騰前の売上高（円）
        before_cost: コスト高騰前の売上原価（円）
        before_expenses: コスト高騰前の販管費・その他経費（円）
        current_sales: 現在の売上高（円）
        current_cost: 現在の売上原価（円）
        current_expenses: 現在の販管費・その他経費（円）
    
    Returns:
        str: 分析結果のフォーマット済みテキスト（コスト高騰前の状況、現在の状況、増減分析、参考価格、価格転嫁の必要性判定を含む）
    
    【例】
    ユーザーが「コスト高騰前は売上1000万円、原価600万円、経費200万円で、現在は売上1000万円、原価700万円、経費200万円です。価格転嫁が必要か判断したい」と言った場合、このツールを使用してください。
    """
    try:
        print(f"\n{'='*80}")
        print(f"📊 [価格転嫁検討ツール] ツールが呼び出されました")
        print(f"{'='*80}\n")
        
        # パラメータが0または未入力の場合は、モーダルでの入力を待つ
        # この場合、ツールはモーダル表示のトリガーとして機能し、実際の計算はモーダルから実行される
        if (before_sales == 0 and before_cost == 0 and before_expenses == 0 and 
            current_sales == 0 and current_cost == 0 and current_expenses == 0):
            print("⚠️  パラメータが未入力です。モーダルでの入力を待ちます。")
            return "【価格転嫁検討ツール】\n\n数値入力用のモーダルが表示されました。\nモーダルに必要な数値を入力して「分析実行」をクリックしてください。\n\n必要な数値:\n- コスト高騰前: 売上高、売上原価、販管費・その他経費\n- 現在: 売上高、売上原価、販管費・その他経費"
        
        print(f"📊 [価格転嫁検討ツール] 分析開始")
        
        # 計算実行
        result = calculate_cost_impact(
            before_sales, before_cost, before_expenses,
            current_sales, current_cost, current_expenses
        )
        
        # 結果をフォーマット
        result_text = "【コスト高騰影響分析結果】\n\n"
        
        # コスト高騰前の状況
        result_text += "【コスト高騰前の状況】\n"
        result_text += f"売上高: {result['before']['sales']:,.0f}円\n"
        result_text += f"売上原価: {result['before']['cost']:,.0f}円\n"
        result_text += f"販管費・その他経費: {result['before']['expenses']:,.0f}円\n"
        result_text += f"総コスト: {result['before']['total_cost']:,.0f}円\n"
        result_text += f"利益: {result['before']['profit']:,.0f}円\n"
        result_text += f"利益率: {result['before']['profit_rate']:.2f}%\n\n"
        
        # 現在の状況
        result_text += "【現在の状況】\n"
        result_text += f"売上高: {result['current']['sales']:,.0f}円\n"
        result_text += f"売上原価: {result['current']['cost']:,.0f}円\n"
        result_text += f"販管費・その他経費: {result['current']['expenses']:,.0f}円\n"
        result_text += f"総コスト: {result['current']['total_cost']:,.0f}円\n"
        result_text += f"利益: {result['current']['profit']:,.0f}円\n"
        result_text += f"利益率: {result['current']['profit_rate']:.2f}%\n\n"
        
        # 増減分析
        result_text += "【コスト高騰の影響】\n"
        result_text += f"売上高: {result['changes']['sales']['amount']:+,.0f}円 ({result['changes']['sales']['rate']:+.2f}%)\n"
        result_text += f"売上原価: {result['changes']['cost']['amount']:+,.0f}円 ({result['changes']['cost']['rate']:+.2f}%)\n"
        result_text += f"販管費・その他経費: {result['changes']['expenses']['amount']:+,.0f}円 ({result['changes']['expenses']['rate']:+.2f}%)\n"
        result_text += f"総コスト: {result['changes']['total_cost']['amount']:+,.0f}円 ({result['changes']['total_cost']['rate']:+.2f}%)\n"
        result_text += f"利益: {result['changes']['profit']['amount']:+,.0f}円 ({result['changes']['profit']['rate']:+.2f}%)\n\n"
        
        # 価格転嫁の必要性判定
        if result['changes']['total_cost']['rate'] > result['changes']['sales']['rate']:
            result_text += "⚠️ **価格転嫁の必要性**: 総コストの増加率が売上高の増加率を上回っています。\n"
            result_text += "価格転嫁を検討することをお勧めします。\n\n"
        elif result['current']['profit_rate'] < result['before']['profit_rate']:
            result_text += "⚠️ **価格転嫁の必要性**: 利益率が低下しています。\n"
            result_text += "価格転嫁を検討することをお勧めします。\n\n"
        else:
            result_text += "✅ **現状**: コスト高騰の影響は比較的軽微です。\n\n"
        
        # 参考価格の算出
        result_text += "【参考価格の算出】\n"
        result_text += f"コスト高騰前の利益率を維持するための参考価格: {result['reference_price']:,.0f}円\n"
        result_text += f"現在の価格との差額: {result['price_gap']:+,.0f}円 ({result['price_gap_rate']:+.2f}%)\n\n"
        
        if result['price_gap'] > 0:
            result_text += f"💡 **推奨**: 価格を {result['price_gap']:,.0f}円 引き上げることで、\n"
            result_text += f"コスト高騰前の利益率（{result['before']['profit_rate']:.2f}%）を維持できます。\n"
        else:
            result_text += "💡 **現状**: 現在の価格でコスト高騰前の利益率を維持できています。\n"
        
        # 図生成の指示を追加（エージェントがgenerate_diagramツールを呼び出すように）
        import json
        
        # 百万円単位に変換したデータを準備
        data_values = [
            result['before']['sales'] / 1000000,
            result['before']['cost'] / 1000000,
            result['before']['expenses'] / 1000000,
            result['before']['total_cost'] / 1000000,
            result['before']['profit'] / 1000000,
            result['current']['sales'] / 1000000,
            result['current']['cost'] / 1000000,
            result['current']['expenses'] / 1000000,
            result['current']['total_cost'] / 1000000,
            result['current']['profit'] / 1000000,
        ]
        
        labels_list = [
            "売上高(前)",
            "売上原価(前)",
            "販管費(前)",
            "総コスト(前)",
            "利益(前)",
            "売上高(現在)",
            "売上原価(現在)",
            "販管費(現在)",
            "総コスト(現在)",
            "利益(現在)"
        ]
        
        # JSON形式でデータを準備
        comparison_data_json = json.dumps({
            "data": data_values,
            "labels": labels_list
        }, ensure_ascii=False)
        
        result_text += "\n\n"
        result_text += "【図示の指示 - 必須実行】\n"
        result_text += "この分析結果を視覚化するため、以下のデータを使って `generate_diagram` ツールで棒グラフを生成してください。\n\n"
        result_text += f"**図のタイトル**: コスト高騰前と現在の比較\n"
        result_text += f"**図の種類**: bar_chart\n"
        result_text += f"**データ**: {comparison_data_json}\n\n"
        result_text += "**重要**: この指示を見たら、すぐに `generate_diagram` ツールを呼び出してください。\n"
        result_text += "パラメータ: diagram_type='bar_chart', title='コスト高騰前と現在の比較', descriptionに上記のJSONデータを含めてください。\n"
        
        print(f"✅ [価格転嫁検討ツール] 分析完了（図生成指示を含む）\n")
        
        return result_text
        
    except Exception as e:
        print(f"❌ [価格転嫁検討ツールエラー] {str(e)}")
        import traceback
        traceback.print_exc()
        return f"分析エラーが発生しました: {str(e)}"

