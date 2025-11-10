from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import current_time, calculator

def strands_agent_chat():

    # LLMの初期化
    bedrock_model = BedrockModel(
        model_id="jp.anthropic.claude-haiku-4-5-20251001-v1:0",
        region_name="ap-northeast-1",
        temperature=0.7,
        max_tokens=2048,
        streaming=False,
    )

    system_prompt=\
"""あなたは親切で知識豊富なAIアシスタントです。

簡潔で分かりやすい回答を心がけてください。
質問に対して、あなたの知識範囲内で即座に回答してください。

もし最新情報や特定の社内情報が必要な場合は、
「より詳しい情報を検索します」と明示してください。"""

    # エージェントの初期化
    agent = Agent(
        model=bedrock_model,
        tools=[current_time, calculator, web_search],
        system_prompt=system_prompt
    )

    while True:
        # Get user input
        user_input = input("\nメッセージを入力してください (終了する場合は 'quit' と入力):\n")

        if user_input.lower() == 'quit':
            print("会話を終了します。")
            break

        try:
            response = agent(user_input)
            print("\nアシスタント:", response)
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            print("もう一度お試しください。")

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

if __name__ == "__main__":
    strands_agent_chat()

