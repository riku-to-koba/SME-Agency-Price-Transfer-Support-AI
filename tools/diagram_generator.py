"""図生成ツール"""
import subprocess
import tempfile
import os
import uuid
from strands import tool


class DiagramGenerator:
    """Python コードを実行して図を生成するユーティリティ"""

    @staticmethod
    def _create_python_code_wrapper(code: str, output_path: str) -> str:
        """Python コードをラップしてグラフ自動保存機能を追加"""
        escaped_path = output_path.replace('\\', '\\\\')

        # f-string の内側での置換問題を避けるため、別々に構築
        header = f"""# -*- coding: utf-8 -*-
import sys
import platform

# グラフ保存用の内部変数
_diagram_output_file = r'{escaped_path}'

# matplotlib の日本語フォント設定(自動)
try:
    import matplotlib
    matplotlib.use('Agg')  # GUI表示なし

    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    # 利用可能な日本語フォントを検索
    jp_fonts = []
    if platform.system() == 'Windows':
        font_candidates = ['Yu Gothic', 'MS Gothic', 'Meiryo', 'MS UI Gothic', 'MS PGothic']
    elif platform.system() == 'Darwin':  # macOS
        font_candidates = ['Hiragino Sans', 'Hiragino Kaku Gothic Pro', 'AppleGothic']
    else:  # Linux
        font_candidates = ['Noto Sans CJK JP', 'IPAGothic', 'IPAMincho', 'TakaoGothic']

    available_fonts = [f.name for f in fm.fontManager.ttflist]
    for font_name in font_candidates:
        if font_name in available_fonts:
            jp_fonts.append(font_name)
            break

    if jp_fonts:
        matplotlib.rcParams['font.sans-serif'] = jp_fonts + matplotlib.rcParams['font.sans-serif']
        matplotlib.rcParams['font.family'] = 'sans-serif'

    matplotlib.rcParams['axes.unicode_minus'] = False
except ImportError:
    pass

# ========== ユーザーコード ==========
"""

        footer = """
# ====================================

# matplotlib グラフの保存
try:
    import matplotlib.pyplot as plt
    if plt.get_fignums():
        plt.savefig(_diagram_output_file, dpi=150, bbox_inches='tight')
        print("[DIAGRAM_SAVED:" + _diagram_output_file + "]", file=sys.stderr)
except ImportError:
    pass
except Exception as e:
    print("[DIAGRAM_ERROR:" + str(e) + "]", file=sys.stderr)
"""

        return header + code + footer

    @staticmethod
    def generate(code: str, timeout: int = 30) -> tuple[bool, str, str]:
        """
        Python コードを実行して図を生成

        Args:
            code: 実行する Python コード（matplotlib で図を生成）
            timeout: タイムアウト時間（秒）

        Returns:
            (success: bool, image_path: str, error: str)
        """
        timestamp = int(__import__('time').time() * 1000)
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"diagram_{timestamp}.png")
        temp_py_path = os.path.join(temp_dir, f"diagram_{timestamp}.py")

        try:
            # Python コードをラップ
            wrapped_code = DiagramGenerator._create_python_code_wrapper(code, output_path)

            # 一時ファイルに書き込み
            with open(temp_py_path, 'w', encoding='utf-8') as f:
                f.write(wrapped_code)

            # Python を実行
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            env['PYTHONUNBUFFERED'] = '1'

            result = subprocess.run(
                ['python', temp_py_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

            # クリーンアップ
            try:
                os.unlink(temp_py_path)
            except:
                pass

            # 出力をチェック
            stderr = result.stderr or ''
            if '[DIAGRAM_SAVED:' in stderr and os.path.exists(output_path):
                return True, output_path, ''
            elif result.returncode != 0:
                error_msg = result.stderr or 'Unknown error'
                return False, '', error_msg
            else:
                return False, '', '図が生成されませんでした'

        except subprocess.TimeoutExpired:
            return False, '', f'タイムアウト({timeout}秒)'
        except Exception as e:
            return False, '', str(e)
        finally:
            try:
                os.unlink(temp_py_path)
            except:
                pass


def _extract_data_from_description(description: str):
    """description からデータを抽出"""
    import json
    import re

    # JSON形式を試す
    json_match = re.search(r'\{.*?"data".*?\}', description, re.DOTALL)
    if json_match:
        try:
            data_dict = json.loads(json_match.group())
            return data_dict.get("data", []), data_dict.get("labels", [])
        except:
            pass

    # テーブル形式またはリスト形式を試す
    labels = []
    data = []

    # パターン: "ラベル: 値" または "- ラベル: 値"
    lines = description.split('\n')
    for line in lines:
        # リスト形式 "- ラベル: 値" または "ラベル: 値"
        match = re.search(r'(?:-\s*)?([^:]+):\s*(\d+(?:\.\d+)?)', line)
        if match:
            label = match.group(1).strip()
            value = float(match.group(2))
            labels.append(label)
            data.append(value)

    if labels and data:
        return data, labels

    return [], []


def _generate_bar_chart_code_with_data(title: str, labels: list, data: list) -> str:
    """棒グラフのコードを生成（実データ使用）"""
    title_escaped = title.replace("'", "\\'")

    # Pythonリテラルに変換
    labels_str = str(labels)
    data_str = str(data)

    code = f"""
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))

labels = {labels_str}
values = {data_str}
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#95E1D3', '#F38181', '#AA96DA', '#FCBAD3'][:len(labels)]

ax.bar(labels, values, color=colors, edgecolor='black', linewidth=1.5)
ax.set_ylabel('値', fontsize=12, fontweight='bold')
ax.set_title('{title_escaped}', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3, linestyle='--')

for i, v in enumerate(values):
    ax.text(i, v + max(values)*0.02, str(v), ha='center', fontweight='bold')

plt.xticks(rotation=45, ha='right')
plt.tight_layout()
"""
    return code


def _generate_line_chart_code_with_data(title: str, labels: list, data: list) -> str:
    """折れ線グラフのコードを生成（実データ使用）"""
    title_escaped = title.replace("'", "\\'")

    labels_str = str(labels)
    data_str = str(data)

    code = f"""
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))

labels = {labels_str}
values = {data_str}

ax.plot(labels, values, marker='o', linewidth=2, markersize=8, color='#45B7D1')
ax.fill_between(range(len(labels)), values, alpha=0.3, color='#45B7D1')

ax.set_ylabel('値', fontsize=12, fontweight='bold')
ax.set_title('{title_escaped}', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, linestyle='--')

for i, v in enumerate(values):
    ax.text(i, v + max(values)*0.02, str(v), ha='center', fontweight='bold')

plt.xticks(rotation=45, ha='right')
plt.tight_layout()
"""
    return code


def _generate_flowchart_code(title: str, description: str) -> str:
    """フローチャートのコードを生成"""
    title_escaped = title.replace("'", "\\'")
    code = f"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(12, 8))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

def draw_box(ax, x, y, width, height, text, color='lightblue'):
    box = FancyBboxPatch((x - width/2, y - height/2), width, height,
                        boxstyle="round,pad=0.1",
                        edgecolor='black', facecolor=color, linewidth=2)
    ax.add_patch(box)
    ax.text(x, y, text, ha='center', va='center', fontsize=10, fontweight='bold', wrap=True)

def draw_arrow(ax, x1, y1, x2, y2):
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                          arrowstyle='->', mutation_scale=20,
                          linewidth=2, color='black')
    ax.add_patch(arrow)

# フローチャートの例
draw_box(ax, 5, 9, 2, 0.8, '開始', 'lightgreen')
draw_arrow(ax, 5, 8.6, 5, 8)

draw_box(ax, 5, 7.5, 2.5, 0.8, '処理1', 'lightblue')
draw_arrow(ax, 5, 7.1, 5, 6.5)

draw_box(ax, 5, 6, 2.5, 0.8, '判定', 'lightyellow')
draw_arrow(ax, 6.25, 6, 7.5, 6)
draw_arrow(ax, 3.75, 6, 2.5, 6)

draw_box(ax, 7.5, 6, 1.5, 0.6, 'Yes', 'lightgreen')
draw_box(ax, 2.5, 6, 1.5, 0.6, 'No', 'lightcoral')

draw_arrow(ax, 7.5, 5.7, 7.5, 5)
draw_box(ax, 7.5, 4.5, 2, 0.8, '処理2', 'lightblue')
draw_arrow(ax, 7.5, 4.1, 7.5, 3.5)

draw_box(ax, 7.5, 3, 2, 0.8, '終了', 'lightgreen')

draw_arrow(ax, 2.5, 5.7, 2.5, 5)
draw_box(ax, 2.5, 4.5, 2, 0.8, '処理3', 'lightyellow')
draw_arrow(ax, 2.5, 4.1, 2.5, 3.5)
draw_box(ax, 2.5, 3, 1.5, 0.8, '処理4', 'lightblue')

ax.text(5, 9.7, '{title_escaped}', ha='center', fontsize=14, fontweight='bold')
plt.tight_layout()
"""
    return code


def _generate_network_diagram_code(title: str, description: str) -> str:
    """ネットワーク図のコードを生成"""
    title_escaped = title.replace("'", "\\'")
    code = f"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

fig, ax = plt.subplots(figsize=(10, 8))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

def draw_node(ax, x, y, label, color='lightblue', size=0.5):
    circle = mpatches.Circle((x, y), size, color=color, ec='black', linewidth=2)
    ax.add_patch(circle)
    ax.text(x, y, label, ha='center', va='center', fontsize=9, fontweight='bold')

def draw_connection(ax, x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], 'k-', linewidth=2)

# ノード配置
draw_node(ax, 5, 8, 'Central', 'lightcoral', 0.6)
draw_node(ax, 2, 5, 'Node A', 'lightblue', 0.5)
draw_node(ax, 5, 5, 'Node B', 'lightblue', 0.5)
draw_node(ax, 8, 5, 'Node C', 'lightblue', 0.5)
draw_node(ax, 2, 2, 'Node D', 'lightgreen', 0.5)
draw_node(ax, 8, 2, 'Node E', 'lightgreen', 0.5)

# 接続
draw_connection(ax, 5, 7.4, 2, 5.5)
draw_connection(ax, 5, 7.4, 5, 5.5)
draw_connection(ax, 5, 7.4, 8, 5.5)
draw_connection(ax, 2, 4.5, 2, 2.5)
draw_connection(ax, 8, 4.5, 8, 2.5)
draw_connection(ax, 2, 2, 8, 2)

ax.text(5, 9.2, '{title_escaped}', ha='center', fontsize=14, fontweight='bold')
plt.tight_layout()
"""
    return code


@tool
def generate_diagram(diagram_type: str, title: str, description: str) -> str:
    """実データを使って図を自動生成します。

    description に以下のいずれかの形式で データを含めてください：
    1. JSON形式: {"data": [値1, 値2, ...], "labels": ["ラベル1", "ラベル2", ...]}
    2. テーブル形式:
       ラベル1: 値1
       ラベル2: 値2
    3. リスト形式:
       - ラベル1: 値1
       - ラベル2: 値2

    Args:
        diagram_type: 図の種類 ('bar_chart', 'line_chart', 'flowchart', 'network_diagram')
        title: 図のタイトル
        description: 図のデータと説明

    Returns:
        str: 生成された図の場所またはエラーメッセージ
    """
    try:
        # グローバル変数からセッションIDを取得（Streamlit連携用）
        # インポート時の循環参照を避けるため、必要な時だけインポート
        try:
            import streamlit as st
            session_id = st.session_state.get('session_id', 'default')
        except:
            session_id = 'default'

        # description からデータを抽出
        data, labels = _extract_data_from_description(description)

        if not data or not labels:
            return f"❌ データが見つかりません。description にデータを含めてください。"

        # 図の種類に応じたPythonコードを生成（実データを使用）
        if diagram_type == 'flowchart':
            code = _generate_flowchart_code(title, description)
        elif diagram_type == 'bar_chart':
            code = _generate_bar_chart_code_with_data(title, labels, data)
        elif diagram_type == 'line_chart':
            code = _generate_line_chart_code_with_data(title, labels, data)
        elif diagram_type == 'network_diagram':
            code = _generate_network_diagram_code(title, description)
        else:
            return f"エラー: サポートされていない図の種類です: {diagram_type}"

        # 図を生成
        success, image_path, error = DiagramGenerator.generate(code, timeout=30)

        if success:
            # ダウンロード用に diagrams フォルダに保存
            download_dir = os.path.join(os.getcwd(), "diagrams")
            os.makedirs(download_dir, exist_ok=True)

            # ファイル名を作成（タイトルをサニタイズ + セッションID）
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
            safe_title = safe_title[:50]  # 長さ制限
            download_path = os.path.join(download_dir, f"{session_id}_{safe_title}_{uuid.uuid4().hex[:8]}.png")

            # ファイルをコピー
            import shutil
            shutil.copy(image_path, download_path)

            # 成功メッセージを返す
            return f"✅ 図を生成しました: {title}"
        else:
            return f"❌ 図の生成に失敗しました: {error}"

    except Exception as e:
        return f"❌ エラーが発生しました: {str(e)}"
