"""グラフ生成ツール（generate_chart）

データを可視化し、交渉の場で即座に使える高品質グラフを生成。
ローカルにファイル保存し、パスをUI側に返す。
"""
import io
import base64
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from strands import tool

# グローバル変数: 生成されたグラフファイルのパスを追跡
# api/main.py がストリーミング終了時にこれを読み込んで確実に送信する
LAST_GENERATED_CHARTS: List[str] = []


def _generate_chart_file(
    data: Dict[str, Any],
    chart_type: str,
    title: str,
    x_label: str = "",
    y_label: str = "",
    output_dir: str = "outputs/charts"
) -> tuple[str, str]:
    """グラフを生成してファイルに保存し、ファイルパスとBase64データを返す"""
    import matplotlib
    matplotlib.use('Agg')
    
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import platform
    
    # 日本語フォント設定
    jp_fonts = []
    if platform.system() == 'Windows':
        font_candidates = ['Yu Gothic', 'MS Gothic', 'Meiryo', 'MS UI Gothic']
    elif platform.system() == 'Darwin':
        font_candidates = ['Hiragino Sans', 'Hiragino Kaku Gothic Pro']
    else:
        font_candidates = ['Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic']

    available_fonts = [f.name for f in fm.fontManager.ttflist]
    for font_name in font_candidates:
        if font_name in available_fonts:
            jp_fonts.append(font_name)
            break

    if jp_fonts:
        matplotlib.rcParams['font.sans-serif'] = jp_fonts + matplotlib.rcParams['font.sans-serif']
        matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    
    # グラフ作成
    if chart_type == "line":
        # 折れ線グラフ
        time_series = data.get('time_series', [])
        
        if time_series:
            dates = [item.get('date', str(i)) for i, item in enumerate(time_series)]
            values = [item.get('value', 0) for item in time_series]
        else:
            dates = data.get('labels', ['1', '2', '3', '4', '5'])
            values = data.get('values', [100, 110, 120, 130, 140])

        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.plot(dates, values, marker='o', linewidth=2.5, markersize=8, color='#2563eb')
        ax.fill_between(range(len(dates)), values, alpha=0.2, color='#2563eb')
        
        ax.set_xlabel(x_label, fontsize=12, fontweight='bold')
        ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 値ラベル
        for i, v in enumerate(values):
            label = f'{v:.1f}' if isinstance(v, float) else str(v)
            ax.annotate(label, (i, v), textcoords="offset points", xytext=(0, 10),
                        ha='center', fontsize=9, fontweight='bold')
        
        plt.xticks(rotation=45, ha='right')
        
    elif chart_type == "bar":
        # 棒グラフ
        labels = data.get('labels', ['項目1', '項目2', '項目3'])
        values = data.get('values', [100, 200, 150])

        # 複数系列対応
        if 'series' in data:
            series = data['series']
            fig, ax = plt.subplots(figsize=(12, 6))
            x = range(len(labels))
            width = 0.8 / len(series)
            colors = ['#2563eb', '#dc2626', '#16a34a', '#f59e0b', '#8b5cf6']

            for i, (name, vals) in enumerate(series.items()):
                offset = (i - len(series)/2 + 0.5) * width
                bars = ax.bar([xi + offset for xi in x], vals, width, label=name, color=colors[i % len(colors)])

                for bar, val in zip(bars, vals):
                    label = f'{val:,.0f}' if isinstance(val, (int, float)) else str(val)
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.01,
                            label, ha='center', va='bottom', fontsize=8, fontweight='bold')

            ax.set_xticks(list(x))
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.legend()
        else:
            fig, ax = plt.subplots(figsize=(10, 6))
            main_color = '#2563eb'

            bars = ax.bar(labels, values, color=main_color, edgecolor='white', linewidth=1.5)

            for bar, val in zip(bars, values):
                label = f'{val:,.0f}' if isinstance(val, (int, float)) else str(val)
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                        label, ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax.set_xlabel(x_label, fontsize=12, fontweight='bold')
        ax.set_ylabel(y_label, fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.xticks(rotation=45, ha='right')
    else:
        # デフォルト（折れ線グラフ）
        return _generate_chart_file(data, "line", title, x_label, y_label, output_dir)

    plt.tight_layout()

    # 出力ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)

    # ファイル名を生成（タイムスタンプ付き）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in title)
    filename = f"chart_{safe_title}_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)

    # ファイルに保存
    plt.savefig(filepath, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')

    # Base64エンコード（UI表示用）
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return filepath, image_base64


@tool
def generate_chart(
    data: dict,
    chart_type: str,
    title: str,
    x_label: str = "",
    y_label: str = ""
) -> str:
    """データを可視化したグラフ画像を生成します。

    Args:
        data: グラフ用データ
        chart_type: グラフタイプ（"line" または "bar"）
        title: グラフタイトル
        x_label: X軸ラベル（オプション）
        y_label: Y軸ラベル（オプション）

    ## グラフタイプの選び方

    ### line（折れ線グラフ）
    時間の経過に伴う変化・推移を見せる時に使用。
    - 例: 価格推移、売上推移、倒産件数の年次推移、指数の変化
    - data形式: {"time_series": [{"date": "2021", "value": 100}, {"date": "2022", "value": 115}, ...]}

    ### bar（棒グラフ）
    カテゴリ間の大小比較を見せる時に使用。時系列データには使わない。
    - 例: 業種別売上、部門別コスト、地域別シェア、項目別内訳
    - data形式: {"labels": ["製造業", "小売業", "建設業"], "values": [100, 200, 150]}

    Returns:
        str: 生成結果のメッセージ（ファイルパスとBase64画像データを含む特殊フォーマット）
    """
    try:
        # グラフを生成してファイル保存 + Base64エンコード
        filepath, image_base64 = _generate_chart_file(
            data=data,
            chart_type=chart_type,
            title=title,
            x_label=x_label,
            y_label=y_label
        )

        # ファイル名を抽出（URLとして使用）
        filename = os.path.basename(filepath)
        chart_url = f"/charts/{filename}"

        # 特殊フォーマットで返す（URLタグを使用）
        return f"""✅ グラフを生成しました

**タイトル**: {title}
**グラフタイプ**: {chart_type}

[CHART_URL]{chart_url}[/CHART_URL]"""

    except Exception as e:
        return f"❌ グラフ生成中にエラーが発生しました: {str(e)}"
