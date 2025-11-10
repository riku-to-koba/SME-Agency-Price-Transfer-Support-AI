import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import platform
import base64
import os
from io import BytesIO
from pathlib import Path
import tempfile

# ページ設定
st.set_page_config(page_title="画像表示テスト", layout="wide")

st.title("🎨 Streamlit 画像表示テスト")
st.markdown("---")

# ============================================================================
# ヘルパー関数：日本語フォント設定
# ============================================================================
def setup_japanese_font():
    """matplotlib の日本語フォント設定"""
    try:
        if platform.system() == 'Windows':
            font_candidates = ['Yu Gothic', 'MS Gothic', 'Meiryo', 'MS UI Gothic']
        elif platform.system() == 'Darwin':  # macOS
            font_candidates = ['Hiragino Sans', 'Hiragino Kaku Gothic Pro']
        else:  # Linux
            font_candidates = ['Noto Sans CJK JP', 'IPAGothic', 'TakaoGothic']

        available_fonts = [f.name for f in fm.fontManager.ttflist]
        for font_name in font_candidates:
            if font_name in available_fonts:
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['font.family'] = 'sans-serif'
                plt.rcParams['axes.unicode_minus'] = False
                return
    except Exception as e:
        st.warning(f"フォント設定エラー: {e}")

# ============================================================================
# テスト1: シンプルなグラフを生成
# ============================================================================
def create_simple_chart():
    """シンプルな棒グラフを生成"""
    setup_japanese_font()

    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ['営業', '企画', '技術', 'サポート']
    values = [85, 72, 91, 68]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']

    ax.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('スコア', fontsize=12, fontweight='bold')
    ax.set_title('部門別パフォーマンス評価', fontsize=14, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    for i, v in enumerate(values):
        ax.text(i, v + 2, str(v), ha='center', fontweight='bold')

    plt.tight_layout()
    return fig

# ============================================================================
# テスト2: フローチャート（Graphviz 代わりに matplotlib で実装）
# ============================================================================
def create_flowchart():
    """シンプルなフローチャート"""
    setup_japanese_font()

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # ボックスと矢印を描画
    def draw_box(ax, x, y, width, height, text, color='lightblue'):
        from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
        box = FancyBboxPatch((x - width/2, y - height/2), width, height,
                            boxstyle="round,pad=0.1",
                            edgecolor='black', facecolor=color, linewidth=2)
        ax.add_patch(box)
        ax.text(x, y, text, ha='center', va='center', fontsize=11, fontweight='bold')

    def draw_arrow(ax, x1, y1, x2, y2):
        from matplotlib.patches import FancyArrowPatch
        arrow = FancyArrowPatch((x1, y1), (x2, y2),
                              arrowstyle='->', mutation_scale=25,
                              linewidth=2, color='black')
        ax.add_patch(arrow)

    # フロー描画
    draw_box(ax, 5, 9, 2, 0.8, '開始', 'lightgreen')
    draw_arrow(ax, 5, 8.6, 5, 8)

    draw_box(ax, 5, 7.5, 2.5, 0.8, '見積もり作成', 'lightblue')
    draw_arrow(ax, 5, 7.1, 5, 6.5)

    draw_box(ax, 5, 6, 2.5, 0.8, '顧客確認', 'lightyellow')
    draw_arrow(ax, 5, 5.6, 5, 5)

    draw_box(ax, 5, 4.5, 2.5, 0.8, '承認済み?', 'lightcoral')
    draw_arrow(ax, 6.25, 4.5, 7.5, 4.5)
    draw_arrow(ax, 3.75, 4.5, 2.5, 4.5)

    draw_box(ax, 7.5, 4.5, 1.5, 0.6, 'Yes', 'lightgreen')
    draw_box(ax, 2.5, 4.5, 1.5, 0.6, 'No', 'lightcoral')

    draw_arrow(ax, 7.5, 4.2, 7.5, 3.5)
    draw_box(ax, 7.5, 3, 2, 0.8, '納品処理', 'lightblue')
    draw_arrow(ax, 7.5, 2.6, 7.5, 2)

    draw_box(ax, 7.5, 1.5, 2, 0.8, '終了', 'lightgreen')

    draw_arrow(ax, 2.5, 4.2, 2.5, 3.5)
    draw_box(ax, 2.5, 3, 2, 0.8, '修正依頼', 'lightyellow')
    draw_arrow(ax, 2.5, 2.6, 2.5, 2)
    draw_box(ax, 2.5, 1.5, 1.5, 0.8, '見積修正', 'lightblue')
    draw_arrow(ax, 3.4, 1.5, 4, 1.5)

    ax.text(5, 9.5, 'SME見積プロセス', ha='center', fontsize=14, fontweight='bold')

    plt.tight_layout()
    return fig

# ============================================================================
# セッション状態の初期化
# ============================================================================
if "test_results" not in st.session_state:
    st.session_state.test_results = {}

# ============================================================================
# タブで3つのテストを実装
# ============================================================================
tab1, tab2, tab3 = st.tabs(["パターン1: ファイル保存", "パターン2: Base64", "パターン3: BytesIO"])

# ============================================================================
# パターン1: ファイル保存 + ローカルパス参照
# ============================================================================
with tab1:
    st.header("パターン1: ファイル保存 → パス参照")
    st.markdown("""
    **方式:** Python で生成 → PNG ファイルに保存 → ファイルパスで参照

    **メリット:**
    - 最も安定している
    - ストリーミングと組み合わせやすい
    - ファイルとして管理可能

    **デメリット:**
    - 一時ファイル管理が必要
    """)

    if st.button("グラフを生成（パターン1）", key="btn1"):
        with st.spinner("グラフを生成中..."):
            # 一時ファイルに保存
            temp_dir = tempfile.gettempdir()
            image_path = os.path.join(temp_dir, "test_chart_1.png")

            fig = create_simple_chart()
            fig.savefig(image_path, dpi=150, bbox_inches='tight')
            plt.close(fig)

            # ファイルパスで参照
            if os.path.exists(image_path):
                st.success(f"✅ ファイル保存成功: {image_path}")
                st.image(image_path)
                st.session_state.test_results['pattern1'] = '成功'
            else:
                st.error("❌ ファイルが保存されませんでした")
                st.session_state.test_results['pattern1'] = '失敗'

# ============================================================================
# パターン2: Base64 エンコード
# ============================================================================
with tab2:
    st.header("パターン2: Base64 エンコード")
    st.markdown("""
    **方式:** Python で生成 → bytes → Base64 → 直接表示

    **メリット:**
    - ファイル管理が不要
    - メモリベース

    **デメリット:**
    - Base64 は large なデータ
    - Streamlit が完全対応しているか不明
    """)

    if st.button("グラフを生成（パターン2）", key="btn2"):
        with st.spinner("グラフを生成中..."):
            fig = create_simple_chart()

            # BytesIO に保存
            img_buffer = BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)

            # Base64 エンコード
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

            st.success(f"✅ Base64 エンコード成功 (サイズ: {len(img_base64)} bytes)")

            # Base64 直接表示
            st.image(f"data:image/png;base64,{img_base64}")
            st.session_state.test_results['pattern2'] = '成功'

# ============================================================================
# パターン3: BytesIO 直接
# ============================================================================
with tab3:
    st.header("パターン3: BytesIO オブジェクト直接")
    st.markdown("""
    **方式:** Python で生成 → BytesIO → Streamlit に直接渡す

    **メリット:**
    - シンプルで明確
    - ファイル・エンコーディング不要

    **デメリット:**
    - 方式が直感的でない可能性
    """)

    if st.button("グラフを生成（パターン3）", key="btn3"):
        with st.spinner("グラフを生成中..."):
            fig = create_simple_chart()

            img_buffer = BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)

            st.success("✅ BytesIO 生成成功")
            st.image(img_buffer)
            st.session_state.test_results['pattern3'] = '成功'

# ============================================================================
# フローチャートテスト
# ============================================================================
st.markdown("---")
st.header("🔄 フローチャートテスト")

if st.button("フローチャートを生成", key="btn_flowchart"):
    with st.spinner("フローチャートを生成中..."):
        fig = create_flowchart()

        # パターン1: ファイル保存
        temp_dir = tempfile.gettempdir()
        flowchart_path = os.path.join(temp_dir, "test_flowchart.png")
        fig.savefig(flowchart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

        if os.path.exists(flowchart_path):
            st.success("✅ フローチャート生成成功")
            st.image(flowchart_path, caption="SME見積プロセス")
        else:
            st.error("❌ フローチャートが生成されませんでした")

# ============================================================================
# テスト結果のサマリー
# ============================================================================
st.markdown("---")
st.header("📊 テスト結果サマリー")

if st.session_state.test_results:
    for pattern, result in st.session_state.test_results.items():
        status = "✅" if result == "成功" else "❌"
        st.write(f"{status} {pattern}: {result}")
else:
    st.info("上記のボタンをクリックしてテストを実行してください")

# ============================================================================
# 推奨事項
# ============================================================================
st.markdown("---")
st.header("💡 推奨事項")
st.markdown("""
### テスト実装での発見：
1. **ファイル保存（パターン1）** が最も安定していることが期待される
2. **BytesIO（パターン3）** がシンプルで実装しやすい
3. **Base64（パターン2）** は Streamlit の対応状況に依存

### 次のステップ：
1. どのパターンが安定して動作するか確認
2. エージェント統合時の処理フローを設計
3. python-executor.txt の手法を参考に実装
""")
