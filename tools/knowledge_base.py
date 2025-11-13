"""Knowledge Base検索ツール（AWS Bedrock Knowledge Base）"""
import json
import boto3
import time
from botocore.exceptions import ClientError
from strands import tool


@tool
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Knowledge Baseから詳細情報を検索します。

    Args:
        query: 検索クエリ
        max_results: 最大検索結果数（デフォルト: 5）

    Returns:
        str: 検索結果のフォーマット済みテキスト
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

        # Retrieve API を使用してナレッジベースから関連文書を取得 - リトライロジック付き
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

        max_retries = 5
        retry_delay = 2  # 初期待機時間（秒）
        
        response = None
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = bedrock_agent_client.retrieve(**retrieve_params)
                break  # 成功したらループを抜ける
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                last_error = e
                
                if error_code == 'ThrottlingException':
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # 指数バックオフ
                        print(f"⚠️  [Knowledge Base] レート制限エラー (試行 {attempt + 1}/{max_retries})")
                        print(f"⏳ {wait_time}秒待機してから再試行します...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ [Knowledge Base] 最大リトライ回数に達しました")
                        raise
                else:
                    # ThrottlingException以外のエラーは即座に再スロー
                    raise
                    
        if response is None:
            raise last_error if last_error else Exception("API呼び出しに失敗しました")

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
