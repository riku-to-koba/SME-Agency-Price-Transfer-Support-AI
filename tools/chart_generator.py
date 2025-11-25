"""グラフ生成ツール（generate_chart）

データを可視化し、交渉の場で即座に使える高品質グラフを生成。
"""
import os
import uuid
import json
from typing import List, Optional, Dict, Any
from strands import tool


def _create_chart_code(
    data: Dict[str, Any],
    chart_type: str,
    title: str,
    x_label: str = "",
    y_label: str = "",
    annotations: Optional[List[Dict]] = None,
    output_path: str = ""
) -> str:
    """グラフ生成用のPythonコードを作成"""
    
    escaped_path = output_path.replace('\\', '\\\\')
    title_escaped = title.replace("'", "\\'")
    x_label_escaped = x_label.replace("'", "\\'") if x_label else ""
    y_label_escaped = y_label.replace("'", "\\'") if y_label else ""
    
    # ヘッダー部分（日本語フォント設定含む）
    header = f"""# -*- coding: utf-8 -*-
import sys
import platform
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

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

"""

    # データ部分
    data_json = json.dumps(data, ensure_ascii=False)
    
    if chart_type == "line":
        # 折れ線グラフ
        code = f"""
data = {data_json}
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

ax.set_xlabel('{x_label_escaped}', fontsize=12, fontweight='bold')
ax.set_ylabel('{y_label_escaped}', fontsize=12, fontweight='bold')
ax.set_title('{title_escaped}', fontsize=14, fontweight='bold', pad=15)
ax.grid(True, alpha=0.3, linestyle='--')

# 値ラベル
for i, v in enumerate(values):
    ax.annotate(f'{{v:.1f}}' if isinstance(v, float) else str(v), 
                (i, v), textcoords="offset points", xytext=(0, 10),
                ha='center', fontsize=9, fontweight='bold')

plt.xticks(rotation=45, ha='right')
plt.tight_layout()
"""

    elif chart_type == "bar":
        # 棒グラフ（単色で統一感のあるデザイン）
        code = f"""
data = {data_json}
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
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(vals)*0.01,
                    f'{{val:,.0f}}' if isinstance(val, (int, float)) else str(val),
                    ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.legend()
else:
    fig, ax = plt.subplots(figsize=(10, 6))
    # 単色で統一（青系のグラデーションまたは単色）
    main_color = '#2563eb'
    
    bars = ax.bar(labels, values, color=main_color, edgecolor='white', linewidth=1.5)
    
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                f'{{val:,.0f}}' if isinstance(val, (int, float)) else str(val),
                ha='center', va='bottom', fontsize=9, fontweight='bold')

ax.set_xlabel('{x_label_escaped}', fontsize=12, fontweight='bold')
ax.set_ylabel('{y_label_escaped}', fontsize=12, fontweight='bold')
ax.set_title('{title_escaped}', fontsize=14, fontweight='bold', pad=15)
ax.grid(axis='y', alpha=0.3, linestyle='--')

plt.xticks(rotation=45, ha='right')
plt.tight_layout()
"""

    else:
        # デフォルト（折れ線グラフ）
        return _create_chart_code(data, "line", title, x_label, y_label, annotations, output_path)

    # フッター（保存処理）
    footer = f"""
# グラフを保存
plt.savefig(r'{escaped_path}', dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
print("[CHART_SAVED]", file=sys.stderr)
"""

    return header + code + footer


def _execute_chart_code(code: str, timeout: int = 30) -> tuple:
    """Pythonコードを実行してグラフを生成"""
    import subprocess
    import tempfile
    import time as time_module
    
    timestamp = int(time_module.time() * 1000)
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"chart_{timestamp}.png")
    temp_py_path = os.path.join(temp_dir, f"chart_{timestamp}.py")
    
    try:
        with open(temp_py_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(
            ['python', temp_py_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        
        if os.path.exists(output_path):
            return True, output_path, ""
        elif result.returncode != 0:
            return False, "", result.stderr or "Unknown error"
        else:
            return False, "", "グラフが生成されませんでした"
            
    except subprocess.TimeoutExpired:
        return False, "", f"タイムアウト({timeout}秒)"
    except Exception as e:
        return False, "", str(e)
    finally:
        try:
            os.unlink(temp_py_path)
        except:
            pass


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
        str: 生成結果のメッセージ
    """
    try:
        
        print(f"\n{'='*60}")
        print(f"📊 [generate_chart] グラフ生成開始")
        print(f"   タイプ: {chart_type}")
        print(f"   タイトル: {title}")
        print(f"{'='*60}\n")
        
        # 出力パスを設定
        import time as time_module
        timestamp = int(time_module.time() * 1000)
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "diagrams")
        os.makedirs(temp_dir, exist_ok=True)
        
        # ファイル名をサニタイズ
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:30]
        output_path = os.path.join(temp_dir, f"chart_{safe_title}_{uuid.uuid4().hex[:8]}.png")
        
        # グラフコードを生成
        code = _create_chart_code(
            data=data,
            chart_type=chart_type,
            title=title,
            x_label=x_label,
            y_label=y_label,
            output_path=output_path
        )
        
        # コードを実行
        success, image_path, error = _execute_chart_code(code)
        
        if success and os.path.exists(output_path):
            # ファイルサイズを取得
            file_size = os.path.getsize(output_path)
            
            print(f"✅ グラフ生成成功: {output_path}")
            print(f"   ファイルサイズ: {file_size} bytes")
            
            return f"""✅ グラフを生成しました

**タイトル**: {title}
**グラフタイプ**: {chart_type}
**ファイル**: {os.path.basename(output_path)}

グラフが正常に生成されました。交渉資料や説明資料にご活用ください。"""
            
        else:
            print(f"❌ グラフ生成失敗: {error}")
            return f"❌ グラフの生成に失敗しました: {error}"
            
    except Exception as e:
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"❌ グラフ生成中にエラーが発生しました: {str(e)}"

