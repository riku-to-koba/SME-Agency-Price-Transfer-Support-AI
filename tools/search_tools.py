"""検索ツール（Web検索とKnowledge Base検索）"""
import json
import boto3
from strands import tool


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Web検索を実行（Tavily API）

    Args:
        query: 検索クエリ
        max_results: 最大検索結果数（デフォルト: 5）

    Returns:
        str: 検索結果のテキスト
    """
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
