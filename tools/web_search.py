"""Web検索ツール（Tavily API + AI信頼性判定）"""
import json
import boto3
import time
import re
from botocore.exceptions import ClientError
from strands import tool


def is_trusted_source_ai(url: str, title: str, content: str) -> dict:
    """AIを使ってURLとコンテンツの信頼性を動的に判定

    Args:
        url: 判定対象のURL
        title: ページタイトル
        content: ページ内容の一部

    Returns:
        dict: {
            "is_trusted": bool,
            "reasoning": str,
            "source_type": str  # "government", "public_org", "academic", "media", "unknown"
        }
    """
    try:
        print(f"\n🔍 [AI信頼性判定] URL: {url}")

        # AWSプロファイルを使用してセッションを作成
        session = boto3.Session(profile_name='bedrock_use_only')

        # LLMを使って信頼性を判定
        bedrock_runtime = session.client(
            service_name='bedrock-runtime',
            region_name='ap-northeast-1'
        )

        prompt = f"""以下のWeb検索結果が、中小企業の価格転嫁に関する情報源として信頼できるかどうかを判定してください。

【URL】
{url}

【タイトル】
{title}

【コンテンツ抜粋】
{content[:300]}

【判定基準】
基本的に、明らかに怪しいサイト以外は信頼できるとみなしてください。

信頼できないソース（untrusted）とみなす条件（これらに該当する場合のみ除外）：
1. 個人ブログ、アフィリエイトサイト
2. まとめサイト、キュレーションサイト
3. 広告目的のサイト（明らかに広告のみのサイト）
4. 情報源が不明確で、明らかに信頼性の低いサイト
5. スパムサイト、詐欺サイト

それ以外のサイト（政府機関、公的機関、企業サイト、メディア、業界団体、データ提供サイトなど）は基本的に信頼できるとみなしてください。

【回答形式】
以下のJSON形式で回答してください：
```json
{{
  "is_trusted": true,
  "reasoning": "経済産業省の公式サイトであり、価格転嫁に関する公的な情報源",
  "source_type": "government"
}}
```

source_type は以下から選択：
- "government": 政府機関
- "public_org": 公的機関・支援機関
- "academic": 大学・研究機関
- "industry_media": 業界メディア・専門誌
- "news_media": ニュースメディア
- "data_site": データ提供サイト・統計サイト
- "industry_group": 業界団体
- "company": 企業サイト
- "media": その他のメディア
- "unknown": 判定不能・信頼性低い
"""

        # Bedrock APIを呼び出し（Claude Haiku - 高速判定用）- リトライロジック付き
        max_retries = 5
        retry_delay = 2  # 初期待機時間（秒）
        
        response = None
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = bedrock_runtime.invoke_model(
                    modelId="jp.anthropic.claude-haiku-4-5-20251001-v1:0",
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 300,
                        "temperature": 0.1,  # 判定タスクなので低めに設定
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    })
                )
                break  # 成功したらループを抜ける
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                last_error = e
                
                if error_code == 'ThrottlingException':
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # 指数バックオフ
                        print(f"⚠️  [AI信頼性判定] レート制限エラー (試行 {attempt + 1}/{max_retries})")
                        print(f"⏳ {wait_time}秒待機してから再試行します...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ [AI信頼性判定] 最大リトライ回数に達しました")
                        raise
                else:
                    # ThrottlingException以外のエラーは即座に再スロー
                    raise
                    
        if response is None:
            raise last_error if last_error else Exception("API呼び出しに失敗しました")

        # レスポンスを解析
        response_body = json.loads(response['body'].read())
        assistant_message = response_body['content'][0]['text']

        # JSONブロックを抽出
        json_match = re.search(r'```json\s*(.*?)\s*```', assistant_message, re.DOTALL)
        if json_match:
            result_json = json_match.group(1)
        else:
            result_json = assistant_message

        result = json.loads(result_json.strip())

        print(f"✅ 判定結果: {'信頼できる' if result.get('is_trusted') else '信頼できない'}")
        print(f"   理由: {result.get('reasoning', '不明')}")
        print(f"   種類: {result.get('source_type', 'unknown')}\n")

        return result

    except Exception as e:
        print(f"❌ [AI信頼性判定エラー] {str(e)}")
        # エラー時は安全側（信頼できない）に倒す
        return {
            "is_trusted": False,
            "reasoning": f"判定エラー: {str(e)}",
            "source_type": "unknown"
        }


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Web検索を実行（Tavily API）- AIが信頼性を動的に判定

    Args:
        query: 検索クエリ
        max_results: 最大検索結果数（デフォルト: 5）

    Returns:
        str: 検索結果のテキスト（AIが信頼できると判定したソースのみ）
    """
    try:
        import os
        from tavily import TavilyClient

        print(f"\n{'='*80}")
        print(f"🔍 [Web検索] 検索クエリ: {query}")
        print(f"{'='*80}\n")

        # 環境変数からAPIキーを取得（デプロイ時に設定）
        api_key = os.environ.get("TAVILY_API_KEY", "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")
        tavily_client = TavilyClient(api_key=api_key)

        # より多めに検索して、フィルタリング後に十分な結果を確保
        print(f"🌐 Tavily APIで検索中...")
        response = tavily_client.search(
            query=query,
            max_results=max_results * 2,  # AI判定するため多めに取得
            search_depth="advanced",
            include_answer=True,
        )
        print(f"✅ {len(response.get('results', []))}件の検索結果を取得\n")

        # AIを使って各結果の信頼性を判定
        filtered_results = []
        trusted_count = 0
        untrusted_count = 0

        print(f"🔍 フィルタリング中...")
        for result in response.get("results", []):
            url = result.get('url', '')
            title = result.get('title', '')
            content = result.get('content', '')

            # AI判定を実行
            trust_result = is_trusted_source_ai(url, title, content)

            if trust_result.get("is_trusted"):
                # 信頼性情報を結果に追加
                result['trust_info'] = trust_result
                filtered_results.append(result)
                trusted_count += 1

                if len(filtered_results) >= max_results:
                    break
            else:
                untrusted_count += 1
                print(f"⚠️  除外: {url}")
                print(f"   理由: {trust_result.get('reasoning', '不明')}\n")

        print(f"\n📊 フィルタリング結果: 信頼できる {trusted_count}件 / 除外 {untrusted_count}件\n")

        # 結果テキストを構築
        result_text = f"【検索クエリ】: {query}\n\n"

        # 信頼できるソースの検索結果がある場合のみAI回答を表示
        if filtered_results and response.get("answer"):
            result_text += f"【AI回答】: {response['answer']}\n\n"

        result_text += f"【検索結果】（AIが信頼できると判定したソースのみ）:\n"

        if not filtered_results:
            result_text += "\n※ 信頼できる情報源からの検索結果が見つかりませんでした。\n"
            result_text += "※ 中小企業庁（meti.go.jp）などの政府機関サイトを直接ご参照ください。\n"
            return result_text

        for i, result in enumerate(filtered_results, 1):
            trust_info = result.get('trust_info', {})
            source_type = trust_info.get('source_type', 'unknown')

            # ソース種別の日本語表示
            source_type_ja = {
                'government': '政府機関',
                'public_org': '公的機関',
                'academic': '学術機関',
                'industry_media': '業界メディア',
                'news_media': 'ニュースメディア',
                'data_site': 'データ提供サイト',
                'industry_group': '業界団体',
                'company': '企業サイト',
                'media': 'メディア',
                'unknown': '不明'
            }.get(source_type, '不明')

            result_text += f"\n{i}. {result['title']}\n"
            result_text += f"   URL: {result['url']}\n"
            result_text += f"   種別: {source_type_ja}\n"
            result_text += f"   {result['content'][:200]}...\n"

        result_text += f"\n※ 全{len(response.get('results', []))}件中、AIが信頼できると判定した{len(filtered_results)}件を表示\n"

        return result_text
    except Exception as e:
        print(f"❌ [Web検索エラー] {str(e)}")
        return f"検索エラー: {str(e)}"
