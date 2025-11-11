"""価格転嫁支援AIアシスタント - Streamlit UI"""
import asyncio
import nest_asyncio
import streamlit as st
import os
import re
import uuid
from agent.core import PriceTransferAgent

# イベントループのネスト許可
nest_asyncio.apply()

# ============================================================================
# セッション管理
# ============================================================================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

SESSION_ID = st.session_state.session_id

# ============================================================================
# エージェント初期化
# ============================================================================
@st.cache_resource
def initialize_agent():
    """エージェントを初期化（キャッシュ）"""
    return PriceTransferAgent()


# ============================================================================
# ページ設定
# ============================================================================
st.set_page_config(
    page_title="価格転嫁支援AIアシスタント",
    layout="centered"
)

col1, col2 = st.columns([4, 1])
with col1:
    st.title("価格転嫁支援AIアシスタント")
with col2:
    if st.button("履歴クリア", type="secondary"):
        st.session_state.messages = []
        st.session_state.agent = initialize_agent()
        del st.session_state.session_id
        st.rerun()

st.markdown("---")

# ============================================================================
# セッション状態の初期化
# ============================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = initialize_agent()

# ============================================================================
# チャット履歴の表示
# ============================================================================
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

# ============================================================================
# ユーザー入力
# ============================================================================
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
        display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', full_response).strip()

        # アシスタントメッセージを履歴に追加
        st.session_state.messages.append({"role": "assistant", "content": display_response})

        # diagrams フォルダから図を取得して表示
        diagrams_dir = os.path.join(os.getcwd(), "diagrams")
        if os.path.exists(diagrams_dir):
            # すべての図ファイルを取得（セッションID関係なく最新のものを表示）
            diagram_files = sorted(
                [f for f in os.listdir(diagrams_dir) if f.endswith('.png')],
                key=lambda x: os.path.getmtime(os.path.join(diagrams_dir, x)),
                reverse=True
            )

            # 最新の 1 個のファイルのみ表示
            recent_diagrams = []
            if diagram_files:
                filename = diagram_files[0]
                filepath = os.path.join(diagrams_dir, filename)
                recent_diagrams.append((filename, filepath))

            if recent_diagrams:
                st.markdown("---")
                st.subheader("📊 生成された図")
                for filename, filepath in recent_diagrams:
                    # 図を表示
                    st.image(filepath, caption=filename)
