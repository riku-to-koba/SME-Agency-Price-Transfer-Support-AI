import asyncio
import nest_asyncio
import streamlit as st
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import current_time, calculator

# イベントループのネスト許可
nest_asyncio.apply()


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
        tools=[current_time, calculator, web_search],
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
        st.markdown(message["content"])

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
            try:
                agent_stream = st.session_state.agent.stream_async(prompt)
                async for event in agent_stream:
                    if "data" in event:
                        # 最初のコンテンツが来たら「考え中」を消す
                        if not has_content:
                            has_content = True
                        # 生成されたテキストチャンクを追加
                        full_response += event["data"]
                        response_placeholder.markdown(full_response + "▌")
                    elif "current_tool_use" in event and event["current_tool_use"].get("name"):
                        # ツール使用情報の表示
                        tool_name = event["current_tool_use"]["name"]
                        tool_msg = f"\n\n*[{tool_name} を使用中]*\n\n"
                        if not has_content:
                            has_content = True
                        full_response += tool_msg
                        response_placeholder.markdown(full_response + "▌")

                # 最終表示（カーソルを削除）
                response_placeholder.markdown(full_response)
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

        # アシスタントメッセージを履歴に追加
        st.session_state.messages.append({"role": "assistant", "content": full_response})
