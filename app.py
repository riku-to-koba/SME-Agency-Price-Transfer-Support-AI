import asyncio
import json
import boto3
import nest_asyncio
import streamlit as st
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import current_time, calculator
import subprocess
import tempfile
import os
import re
import uuid
from pathlib import Path

# イベントループのネスト許可
nest_asyncio.apply()

# ============================================================================
# セッション管理
# ============================================================================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

SESSION_ID = st.session_state.session_id
print(f"[SESSION] Current session ID: {SESSION_ID}")

# ============================================================================
# 図生成ユーティリティ
# ============================================================================

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


@tool
def generate_diagram(diagram_type: str, title: str, description: str) -> str:
    """図を自動生成してダウンロード用に保存します。

    Args:
        diagram_type: 図の種類 ('flowchart', 'bar_chart', 'line_chart', 'network_diagram')
        title: 図のタイトル
        description: 図の説明や詳細情報

    Returns:
        str: 生成された図の場所またはエラーメッセージ
    """
    try:
        print(f"[TOOL] generate_diagram called: type={diagram_type}, title={title}")

        # 図の種類に応じたPythonコードを生成
        if diagram_type == 'flowchart':
            code = _generate_flowchart_code(title, description)
        elif diagram_type == 'bar_chart':
            code = _generate_bar_chart_code(title, description)
        elif diagram_type == 'line_chart':
            code = _generate_line_chart_code(title, description)
        elif diagram_type == 'network_diagram':
            code = _generate_network_diagram_code(title, description)
        else:
            return f"エラー: サポートされていない図の種類です: {diagram_type}"

        # 図を生成
        success, image_path, error = DiagramGenerator.generate(code, timeout=30)

        if success:
            print(f"[TOOL] Success! Image path: {image_path}")

            # ダウンロード用に diagrams フォルダに保存
            download_dir = os.path.join(os.getcwd(), "diagrams")
            os.makedirs(download_dir, exist_ok=True)

            # ファイル名を作成（タイトルをサニタイズ + セッションID）
            safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
            safe_title = safe_title[:50]  # 長さ制限
            download_path = os.path.join(download_dir, f"{SESSION_ID}_{safe_title}_{uuid.uuid4().hex[:8]}.png")

            # ファイルをコピー
            import shutil
            shutil.copy(image_path, download_path)
            print(f"[TOOL] Copied to download folder: {download_path}")

            # 成功メッセージを返す
            result = f"✅ 図を生成しました: {title}"
            print(f"[TOOL] Returning: {result}")
            return result
        else:
            error_result = f"❌ 図の生成に失敗しました: {error}"
            print(f"[TOOL] Failed: {error}")
            return error_result

    except Exception as e:
        error_msg = f"❌ エラーが発生しました: {str(e)}"
        print(f"[TOOL] Exception: {error_msg}")
        return error_msg


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


def _generate_bar_chart_code(title: str, description: str) -> str:
    """棒グラフのコードを生成"""
    title_escaped = title.replace("'", "\\'")
    code = f"""
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))

categories = ['カテゴリA', 'カテゴリB', 'カテゴリC', 'カテゴリD']
values = [85, 72, 91, 68]
colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']

ax.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
ax.set_ylabel('スコア', fontsize=12, fontweight='bold')
ax.set_title('{title_escaped}', fontsize=14, fontweight='bold')
ax.set_ylim(0, 100)
ax.grid(axis='y', alpha=0.3, linestyle='--')

for i, v in enumerate(values):
    ax.text(i, v + 2, str(v), ha='center', fontweight='bold')

plt.tight_layout()
"""
    return code


def _generate_line_chart_code(title: str, description: str) -> str:
    """折れ線グラフのコードを生成"""
    title_escaped = title.replace("'", "\\'")
    code = f"""
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))

months = ['1月', '2月', '3月', '4月', '5月', '6月']
values = [65, 75, 70, 85, 90, 95]

ax.plot(months, values, marker='o', linewidth=2, markersize=8, color='#45B7D1')
ax.fill_between(range(len(months)), values, alpha=0.3, color='#45B7D1')

ax.set_ylabel('値', fontsize=12, fontweight='bold')
ax.set_title('{title_escaped}', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, linestyle='--')

for i, v in enumerate(values):
    ax.text(i, v + 2, str(v), ha='center', fontweight='bold')

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
def web_search(query: str, max_results: int = 5) -> str:
    """Web検索を実行（Tavily API）"""
    try:
        from tavily import TavilyClient
        tavily_client = TavilyClient(api_key="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")
        response = tavily_client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
        )

        result_text = f"【検索クエリ】: {query}\n\n"
        if response.get("answer"):
            result_text += f"【AI回答】: {response['answer']}\n\n"

        result_text += "【検索結果】:\n"
        for i, result in enumerate(response.get("results", []), 1):
            result_text += f"\n{i}. {result['title']}\n"
            result_text += f"   URL: {result['url']}\n"
            result_text += f"   {result['content'][:200]}...\n"

        return result_text
    except Exception as e:
        return f"検索エラー: {str(e)}"


@tool
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Knowledge Baseから詳細情報を検索します。
    
    Args:
        query: 検索クエリ
        max_results: 最大検索結果数（デフォルト: 5）
    
    Returns:
        str: 検索結果のJSON文字列
    """
    try:
        print(f"Start search in Knowledge Base for query: {query}")
        knowledge_base_id = '7SM8UQNQFL'
        region = 'ap-northeast-1'

        # bedrock-agent-runtimeクライアントを使用
        bedrock_agent_client = boto3.client(
            service_name='bedrock-agent-runtime',
            region_name=region
        )

        # Retrieve API を使用してナレッジベースから関連文書を取得
        retrieve_params = {
            'knowledgeBaseId': knowledge_base_id,
            'retrievalQuery': {
                'text': query
            },
            'retrievalConfiguration': {
                'vectorSearchConfiguration': {
                    'numberOfResults': max_results,
                    'overrideSearchType': 'SEMANTIC'
                }
            }
        }
        
        response = bedrock_agent_client.retrieve(**retrieve_params)
        
        # 結果を整理
        results = []
        for idx, result in enumerate(response.get('retrievalResults', []), 1):
            content = result.get('content', {}).get('text', '')
            score = result.get('score', 0)
            location = result.get('location', {})
            metadata = result.get('metadata', {})
            
            # ファイル名を取得
            file_name = '不明'
            uri = ''
            
            if 's3Location' in location:
                s3_location = location.get('s3Location', {})
                uri = s3_location.get('uri', '')
                if uri:
                    file_name = uri.split('/')[-1]
            
            if location.get('type') == 'S3':
                uri = location.get('s3Location', {}).get('uri', '')
                if uri:
                    file_name = uri.split('/')[-1]
            
            if file_name == '不明' and metadata:
                for key in ['x-amz-bedrock-kb-source-uri', 'source', 'file', 'document']:
                    if key in metadata:
                        source_info = metadata[key]
                        if isinstance(source_info, str) and source_info:
                            file_name = source_info.split('/')[-1]
                            uri = source_info
                            break
            
            result_info = {
                'index': idx,
                'content': content,
                'score': round(score, 4),
                'source': {
                    'file_name': file_name,
                    'uri': uri
                }
            }
            results.append(result_info)
        
        print(f"finish search in Knowledge Base, found {len(results)} results.")
        
        # フォーマット済みテキストとして返す
        formatted_text = f"【Knowledge Base検索結果】\n"
        formatted_text += f"検索クエリ: {query}\n"
        formatted_text += f"結果件数: {len(results)}件\n\n"
        
        for result in results:
            formatted_text += f"--- 結果 {result['index']} ---\n"
            formatted_text += f"【出典】ファイル名: {result['source']['file_name']}\n"
            formatted_text += f"スコア: {result['score']}\n"
            formatted_text += f"【内容】\n{result['content'][:500]}...\n"
            if result['source']['uri']:
                formatted_text += f"URI: {result['source']['uri']}\n"
            formatted_text += "\n"
        
        return formatted_text
        
    except Exception as e:
        return json.dumps({
            'success': False,
            'query': query,
            'error': str(e),
            'results': []
        }, ensure_ascii=False)

# エージェントの初期化（キャッシュ）
@st.cache_resource
def initialize_agent():
    bedrock_model = BedrockModel(
        model_id="jp.anthropic.claude-haiku-4-5-20251001-v1:0",
        region_name="ap-northeast-1",
        temperature=0.7,
        max_tokens=50000,
        streaming=True,
    )

    system_prompt = """あなたは親切で知識豊富なAIアシスタントです。

簡潔で分かりやすい回答を心がけてください。
質問に対して、あなたの知識範囲内で即座に回答してください。

もし最新情報や特定の社内情報が必要な場合は、
「より詳しい情報を検索します」と明示してください。"""

    agent = Agent(
        model=bedrock_model,
        tools=[current_time, calculator, web_search, search_knowledge_base, generate_diagram],
        system_prompt=system_prompt,
        callback_handler=None
    )
    return agent


# ページ設定
st.set_page_config(
    page_title="AIアシスタント",
    layout="centered"
)

col1, col2 = st.columns([4, 1])
with col1:
    st.title("AIアシスタント")
with col2:
    if st.button("履歴クリア", type="secondary"):
        st.session_state.messages = []
        st.session_state.agent = initialize_agent()
        st.rerun()

st.markdown("---")

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = initialize_agent()

# チャット履歴の表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        content = message["content"]

        # 画像パスを抽出して表示
        image_paths = re.findall(r'\[IMAGE_PATH:(.+?)\]', content)

        # 画像パスを除いたテキストを表示
        display_text = re.sub(r'\[IMAGE_PATH:.+?\]', '', content).strip()
        if display_text:
            st.markdown(display_text)

        # 画像があればここに表示
        for image_path in image_paths:
            if os.path.exists(image_path):
                st.image(image_path)

# ユーザー入力
if prompt := st.chat_input("メッセージを入力してください"):
    # ユーザーメッセージを追加
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # アシスタントの応答
    with st.chat_message("assistant"):
        response_placeholder = st.empty()

        # 考え中の表示
        response_placeholder.markdown("考え中...")

        # ストリーミング処理
        async def stream_response():
            full_response = ""
            has_content = False
            current_tool = None  # 現在使用中のツールを追跡
            try:
                agent_stream = st.session_state.agent.stream_async(prompt)
                async for event in agent_stream:
                    if "data" in event:
                        # 最初のコンテンツが来たら「考え中」を消す
                        if not has_content:
                            has_content = True
                        # 生成されたテキストチャンクを追加
                        full_response += event["data"]

                        # ストリーミング表示用：[IMAGE_PATH:...] を除いたテキストを表示
                        display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                        response_placeholder.markdown(display_response + "▌")
                    elif "current_tool_use" in event and event["current_tool_use"].get("name"):
                        # ツール使用情報の表示（同じツールの場合は1回だけ）
                        tool_name = event["current_tool_use"]["name"]
                        if tool_name != current_tool:
                            current_tool = tool_name
                            tool_msg = f"\n\n*[{tool_name} を使用中]*\n\n"
                            if not has_content:
                                has_content = True
                            full_response += tool_msg
                            display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                            response_placeholder.markdown(display_response + "▌")

                # 最終表示（[IMAGE_PATH:...] を除いたテキストを表示）
                display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                response_placeholder.markdown(display_response)
                return full_response

            except Exception as e:
                error_msg = f"エラーが発生しました: {str(e)}"
                response_placeholder.error(error_msg)
                return error_msg

        # 非同期処理を実行
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        full_response = loop.run_until_complete(stream_response())

        # 応答テキストから画像タグを除去
        import re as regex_module
        display_response = regex_module.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', full_response).strip()

        # アシスタントメッセージを履歴に追加
        st.session_state.messages.append({"role": "assistant", "content": display_response})

        # diagrams フォルダから現在のセッションの図を取得して表示・ダウンロード
        diagrams_dir = os.path.join(os.getcwd(), "diagrams")
        if os.path.exists(diagrams_dir):
            # セッションIDが含まれたファイルのみを取得
            diagram_files = sorted(
                [f for f in os.listdir(diagrams_dir) if f.startswith(SESSION_ID) and f.endswith('.png')],
                key=lambda x: os.path.getmtime(os.path.join(diagrams_dir, x)),
                reverse=True
            )

            # 直近 10 分以内に作成されたファイルのみ表示
            import time
            now = time.time()
            recent_diagrams = []
            for filename in diagram_files:
                filepath = os.path.join(diagrams_dir, filename)
                mtime = os.path.getmtime(filepath)
                if now - mtime < 600:  # 10分以内
                    recent_diagrams.append((filename, filepath))

            if recent_diagrams:
                st.markdown("---")
                st.subheader("📊 生成された図")
                for filename, filepath in recent_diagrams:
                    # 図を表示
                    st.image(filepath, caption=filename)
