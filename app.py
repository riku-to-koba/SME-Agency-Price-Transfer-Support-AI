"""価格転嫁支援AIアシスタント - Streamlit UI（オーケストレーター連携版）"""
import asyncio
import os
import re
import uuid

import nest_asyncio
import streamlit as st

from agent.orchestrator import OrchestratorAgent

# イベントループのネストを許可
nest_asyncio.apply()

# オーケストレーターをセッション単位で保持
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = OrchestratorAgent()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

SESSION_ID = st.session_state.session_id
orchestrator: OrchestratorAgent = st.session_state.orchestrator

# セッションが未作成なら初期化
session_state = orchestrator.get_session(SESSION_ID)
if session_state is None:
    session_state = orchestrator.create_session(SESSION_ID, user_info=None)

# Streamlit ページ設定
st.set_page_config(
    page_title="価格転嫁支援AIアシスタント",
    layout="centered",
)

col1, col2 = st.columns([4, 1])
with col1:
    st.title("価格転嫁支援AIアシスタント")
with col2:
    if st.button("履歴クリア", type="secondary"):
        st.session_state.clear()
        st.experimental_rerun()

st.markdown("---")

# 初回ウェルカムメッセージ
if not session_state["messages"]:
    welcome_message = (
        "こんにちは、価格転嫁支援AIアシスタントです。\n"
        "中小企業の皆さまの価格転嫁をサポートします。\n\n"
        "**できること:**\n"
        "- 価格転嫁プロセス（準備編・実践編）についてのアドバイス\n"
        "- 原価計算や見積書作成など具体的な手順説明\n"
        "- 業界動向や事例の検索\n"
        "- データ可視化（グラフ生成）\n\n"
        "**使い方:**\n"
        "「原価計算のやり方」「見積書の作り方」「業界の価格転嫁動向を知りたい」など、聞きたいことを入力してください。"
    )
    session_state["messages"].append({"role": "assistant", "content": welcome_message})


# チャット履歴表示
for message in session_state["messages"]:
    with st.chat_message(message["role"]):
        content = message["content"]
        image_paths = re.findall(r"\[IMAGE_PATH:(.+?)\]", content)
        display_text = re.sub(r"\[IMAGE_PATH:.+?\]", "", content).strip()
        if display_text:
            st.markdown(display_text)
        for image_path in image_paths:
            if os.path.exists(image_path):
                st.image(image_path)


# ユーザー入力
if prompt := st.chat_input("メッセージを入力してください"):
    # ユーザーメッセージを保存
    session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # アシスタント応答
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.markdown("思考中...")

        async def stream_response():
            full_response = ""
            is_thinking = True

            try:
                agent_stream = orchestrator.stream(session_state, prompt)
                async for event in agent_stream:
                    # モード更新イベント
                    if event.get("type") == "mode_update":
                        mode_text = "Mode 2 (価格転嫁特化)" if event["mode"] == "mode2" else "Mode 1 (よろず相談)"
                        try:
                            st.toast(f"モード切替: {mode_text}")
                        except Exception:
                            pass
                        response_placeholder.markdown(f"現在モード: {mode_text}")
                        continue

                    # ツール使用ステータス
                    if "current_tool_use" in event and event["current_tool_use"].get("name"):
                        tool_name = event["current_tool_use"]["name"]
                        response_placeholder.markdown(f"{full_response}\n\n*[{tool_name} を使用中]*")
                        continue

                    # ツール結果はステータスのみリセット
                    if "tool_result" in event:
                        response_placeholder.markdown(full_response or "思考中...")
                        continue

                    # コンテンツ
                    if "data" in event:
                        if is_thinking:
                            is_thinking = False
                        full_response += event["data"]
                        display_response = re.sub(r"\[IMAGE_PATH:[^\]]*\]", "", full_response).strip()
                        display_response = re.sub(r"\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]", "", display_response).strip()
                        response_placeholder.markdown(display_response + "▁")

                # 最終表示
                display_response = re.sub(r"\[IMAGE_PATH:[^\]]*\]", "", full_response).strip()
                display_response = re.sub(r"\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]", "", display_response).strip()
                response_placeholder.markdown(display_response)
                return display_response

            except Exception as e:
                error_msg = f"エラーが発生しました: {str(e)}"
                response_placeholder.error(error_msg)
                return error_msg

        loop = asyncio.get_event_loop()
        full_response = loop.run_until_complete(stream_response())

        # アシスタントメッセージを履歴に追加
        session_state["messages"].append({"role": "assistant", "content": full_response})

        # 最新の図を表示（存在すれば）
        diagrams_dir = os.path.join(os.getcwd(), "diagrams")
        if os.path.exists(diagrams_dir):
            diagram_files = sorted(
                [f for f in os.listdir(diagrams_dir) if f.endswith(".png")],
                key=lambda x: os.path.getmtime(os.path.join(diagrams_dir, x)),
                reverse=True,
            )
            if diagram_files:
                filename = diagram_files[0]
                filepath = os.path.join(diagrams_dir, filename)
                st.markdown("---")
                st.subheader("📊 生成された図")
                st.image(filepath, caption=filename)
