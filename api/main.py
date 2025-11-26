"""FastAPI backend server with 3-tier agent orchestrator."""
import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Make project root importable
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.orchestrator import OrchestratorAgent  # noqa: E402

app = FastAPI(title="Price Transfer Assistant API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Orchestrator (holds sessions)
orchestrator = OrchestratorAgent()

# 静的ファイル（生成されたグラフ）を提供
charts_dir = project_root / "outputs" / "charts"
charts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=str(charts_dir)), name="charts")

# ツール名の日本語マッピング
TOOL_NAME_JA = {
    "web_search": "Web検索",
    "search_knowledge_base": "知識ベース検索",
    "calculate_cost_impact": "コスト影響試算",
    "generate_chart": "グラフ生成",
    "generate_document": "文書生成",
    "simulate_negotiation": "交渉シミュレーション",
}


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class UserInfo(BaseModel):
    industry: Optional[str] = None
    products: Optional[str] = None
    companySize: Optional[str] = None
    region: Optional[str] = None
    clientIndustry: Optional[str] = None


class SessionRequest(BaseModel):
    user_info: Optional[UserInfo] = None


class SessionResponse(BaseModel):
    session_id: str


class CostAnalysisRequest(BaseModel):
    before_sales: float
    before_cost: float
    before_expenses: float
    current_sales: float
    current_cost: float
    current_expenses: float


class CostAnalysisResponse(BaseModel):
    success: bool
    result: Optional[dict] = None
    message: Optional[str] = None


class IdealPricingRequest(BaseModel):
    """理想の原価計算リクエスト（「去年 vs 今年」方式）
    
    各費目について「以前」と「現在」の金額を入力。
    上昇率は自動計算される。
    単位: 万円
    """
    # 売上
    previous_sales: Optional[float] = None
    current_sales: Optional[float] = None
    # 仕入れ・材料費
    material_cost_previous: Optional[float] = None
    material_cost_current: Optional[float] = None
    # 人件費
    labor_cost_previous: Optional[float] = None
    labor_cost_current: Optional[float] = None
    # 光熱費
    energy_cost_previous: Optional[float] = None
    energy_cost_current: Optional[float] = None
    # その他経費
    overhead_previous: Optional[float] = None
    overhead_current: Optional[float] = None


class IdealPricingResponse(BaseModel):
    """理想の原価計算レスポンス（松竹梅プラン）"""
    success: bool
    result: Optional[dict] = None
    message: Optional[str] = None


def build_user_info_dict(user_info: Optional[UserInfo]) -> Optional[dict]:
    if not user_info:
        return None
    return {
        "industry": user_info.industry,
        "products": user_info.products,
        "companySize": user_info.companySize,
        "region": user_info.region,
        "clientIndustry": user_info.clientIndustry,
    }


def get_or_create_session(session_id: Optional[str] = None, user_info: Optional[dict] = None) -> str:
    """Fetch existing session or create a new one."""
    if session_id:
        state = orchestrator.get_session(session_id)
        if state is not None:
            if "created_at" not in state:
                state["created_at"] = datetime.now().timestamp()
            return session_id

    new_session_id = session_id or str(uuid.uuid4())[:8]
    state = orchestrator.create_session(new_session_id, user_info=user_info)
    state["created_at"] = datetime.now().timestamp()
    return new_session_id


def get_session_or_404(session_id: str) -> dict:
    session = orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def extract_chart_images(text: str) -> tuple[str, list[str]]:
    """テキストからチャート画像のBase64データを抽出する。

    Returns:
        (画像タグを除去したテキスト, Base64画像データのリスト)
    """
    pattern = r'\[CHART_IMAGE\](.*?)\[/CHART_IMAGE\]'
    images = re.findall(pattern, text, re.DOTALL)
    clean_text = re.sub(pattern, '', text, flags=re.DOTALL).strip()
    return clean_text, images


def extract_images_from_event(event: dict) -> list[str]:
    """イベント辞書全体から画像データを再帰的に抽出する。
    
    Strands SDKのイベント構造はネストされている可能性があるため、
    全ての値を文字列化して検索する。
    """
    images = []
    
    def search_recursive(obj):
        if isinstance(obj, str):
            _, found_images = extract_chart_images(obj)
            images.extend(found_images)
        elif isinstance(obj, dict):
            for value in obj.values():
                search_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                search_recursive(item)
    
    search_recursive(event)
    return images


def extract_pdf_documents(text: str) -> tuple[str, list[str]]:
    """テキストからPDFドキュメントのBase64データを抽出する。

    Returns:
        (PDFタグを除去したテキスト, Base64 PDFデータのリスト)
    """
    pattern = r'\[PDF_DOCUMENT\](.*?)\[/PDF_DOCUMENT\]'
    pdfs = re.findall(pattern, text, re.DOTALL)
    clean_text = re.sub(pattern, '', text, flags=re.DOTALL).strip()
    return clean_text, pdfs


def extract_pdf_files(text: str) -> tuple[str, list[tuple[str, str]]]:
    """テキストからPDFファイル名を抽出し、Base64エンコードしたデータを返す。

    Returns:
        (PDFタグを除去したテキスト, [(ファイル名, Base64データ), ...] のリスト)
    """
    import base64
    
    pattern = r'\[PDF_FILE\](.*?)\[/PDF_FILE\]'
    filenames = re.findall(pattern, text, re.DOTALL)
    clean_text = re.sub(pattern, '', text, flags=re.DOTALL).strip()
    
    pdfs = []
    documents_dir = Path(__file__).parent.parent / "documents"
    
    for filename in filenames:
        filename = filename.strip()
        filepath = documents_dir / filename
        
        if filepath.exists():
            try:
                with open(filepath, 'rb') as f:
                    pdf_bytes = f.read()
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    pdfs.append((filename, pdf_base64))  # ファイル名とBase64のタプル
            except Exception:
                pass
    
    return clean_text, pdfs


def extract_chart_image_from_path(text: str) -> tuple[str, list[str]]:
    """テキストから保存先パスを抽出し、そのファイルをBase64エンコードして返す。
    
    generate_chart ツールは "**保存先**: outputs/charts/xxx.png" という形式で
    ファイルパスを出力するため、これを検出してファイルを読み込む。
    
    Returns:
        (テキスト, Base64画像データのリスト)
    """
    import base64
    
    images = []
    
    # "保存先: path/to/file.png" または "**保存先**: path/to/file.png" パターンを検出
    patterns = [
        r'\*\*保存先\*\*:\s*([^\s\n]+\.png)',
        r'保存先:\s*([^\s\n]+\.png)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for filepath in matches:
            # 相対パスの場合、プロジェクトルートからの相対パスとして解決
            full_path = Path(__file__).parent.parent / filepath
            if full_path.exists():
                try:
                    with open(full_path, 'rb') as f:
                        image_bytes = f.read()
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        images.append(image_base64)
                        print(f"[DEBUG] Loaded image from file: {full_path}, size: {len(image_base64)}")
                except Exception as e:
                    print(f"[DEBUG] Failed to load image from {full_path}: {e}")
    
    return text, images


def extract_chart_urls(text: str) -> list[str]:
    """テキストから[CHART_URL]タグを抽出してURLリストを返す。
    
    Returns:
        チャートURLのリスト
    """
    pattern = r'\[CHART_URL\](.*?)\[/CHART_URL\]'
    urls = re.findall(pattern, text, re.DOTALL)
    return [url.strip() for url in urls]


# モーダル表示が必要なツールの設定
# キー: ツール名, 値: モーダル種別
TOOLS_REQUIRING_MODAL: Dict[str, str] = {
    "calculate_cost_impact": "ideal_pricing",
    # 将来の拡張用
    # "analyze_cost_impact": "cost_comparison",
}


@app.get("/")
async def root():
    """Health check."""
    return {"message": "Price Transfer Assistant API", "status": "ok"}


@app.get("/api/documents")
async def list_documents():
    """生成されたドキュメント一覧を取得"""
    documents_dir = Path(__file__).parent.parent / "documents"
    if not documents_dir.exists():
        return {"documents": []}
    
    files = []
    for f in documents_dir.glob("*.pdf"):
        files.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "created": f.stat().st_mtime,
        })
    
    # 最新順にソート
    files.sort(key=lambda x: x["created"], reverse=True)
    return {"documents": files}


@app.get("/api/documents/{filename}")
async def download_document(filename: str):
    """ドキュメントをダウンロード"""
    from fastapi.responses import FileResponse
    
    documents_dir = Path(__file__).parent.parent / "documents"
    filepath = documents_dir / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # セキュリティチェック（パストラバーサル防止）
    if not filepath.resolve().parent == documents_dir.resolve():
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/pdf"
    )


@app.get("/api/documents/{filename}/preview")
async def preview_document(filename: str):
    """ドキュメントをブラウザで表示（プレビュー）"""
    from fastapi.responses import FileResponse
    
    documents_dir = Path(__file__).parent.parent / "documents"
    filepath = documents_dir / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # セキュリティチェック（パストラバーサル防止）
    if not filepath.resolve().parent == documents_dir.resolve():
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Content-Disposition: inline でブラウザ内表示
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"}
    )


@app.post("/api/session", response_model=SessionResponse)
async def create_session(request: SessionRequest = SessionRequest()):
    """Create a new session."""
    user_info_dict = build_user_info_dict(request.user_info) if request.user_info else None
    session_id = get_or_create_session(user_info=user_info_dict)
    return SessionResponse(session_id=session_id)


@app.get("/api/session/{session_id}/messages")
async def get_messages(session_id: str):
    """Get message history for a session."""
    session = get_session_or_404(session_id)
    return {
        "messages": session.get("messages", []),
        "current_step": session.get("current_step"),
        "mode": session.get("mode"),
    }


@app.post("/api/session/{session_id}/clear")
async def clear_session(session_id: str):
    """Clear a session."""
    session = get_session_or_404(session_id)
    user_info = session.get("user_info")
    orchestrator.create_session(session_id, user_info=user_info)
    orchestrator.get_session(session_id)["created_at"] = datetime.now().timestamp()
    return {"message": "Session cleared"}


@app.post("/api/chat")
async def chat_endpoint(request: ChatMessage):
    """Chat endpoint (SSE streaming)."""
    session_id = get_or_create_session(request.session_id)
    session = get_session_or_404(session_id)

    async def stream_response():
        full_response = ""
        is_cancelled = False
        sent_images = []  # 送信済み画像を追跡（Base64データ）
        sent_pdf_filenames = set()  # 送信済みPDFファイル名を追跡
        sent_chart_urls = set()  # 送信済みChart URLを追跡
        last_generate_document_result = None  # generate_documentの最後の結果を保存
        modal_triggered = False  # モーダル表示がトリガーされたかどうか

        # initial thinking signal
        yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': '思考中...'}, ensure_ascii=False)}\n\n"

        try:
            async for event in orchestrator.stream(session, request.message):
                # デバッグ: イベント構造を確認（本番では削除可能）
                print(f"[DEBUG] Event received: {list(event.keys()) if isinstance(event, dict) else type(event)}")
                
                # 任意のイベントから画像を再帰的に抽出
                event_images = extract_images_from_event(event)
                for img in event_images:
                    if img not in sent_images:
                        sent_images.append(img)
                        print(f"[DEBUG] Sending image event, size: {len(img)}")
                        yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                # PDFファイルを抽出（イベント全体を文字列化して検索）
                event_str = json.dumps(event, ensure_ascii=False, default=str) if isinstance(event, dict) else str(event)
                _, event_pdfs = extract_pdf_files(event_str)
                for filename, pdf_base64 in event_pdfs:
                    if filename not in sent_pdf_filenames:
                        sent_pdf_filenames.add(filename)
                        yield f"data: {json.dumps({'type': 'pdf', 'data': pdf_base64}, ensure_ascii=False)}\n\n"
                
                # mode updates
                if event.get("type") == "mode_update":
                    yield f"data: {json.dumps({'type': 'mode_update', 'mode': event['mode']}, ensure_ascii=False)}\n\n"
                    continue

                # tool status
                if "current_tool_use" in event and event["current_tool_use"].get("name"):
                    tool_name = event["current_tool_use"]["name"]
                    tool_name_ja = TOOL_NAME_JA.get(tool_name, tool_name)
                    status_message = f"{tool_name_ja}を実行中..."
                    
                    # モーダル表示が必要なツールかチェック
                    if tool_name in TOOLS_REQUIRING_MODAL:
                        modal_type = TOOLS_REQUIRING_MODAL[tool_name]
                        yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name, 'show_modal': True, 'modal_type': modal_type, 'message': status_message}, ensure_ascii=False)}\n\n"
                        modal_triggered = True  # モーダルがトリガーされた
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'tool_use', 'tool': tool_name, 'message': status_message}, ensure_ascii=False)}\n\n"
                    continue

                # tool result
                if "tool_result" in event:
                    tool_result = event.get("tool_result", "")
                    # tool_result が辞書の場合は文字列化
                    if isinstance(tool_result, dict):
                        tool_result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
                    else:
                        tool_result_str = str(tool_result)
                    
                    print(f"[DEBUG] Tool result received, length: {len(tool_result_str)}")
                    print(f"[DEBUG] Contains CHART_IMAGE: {'[CHART_IMAGE]' in tool_result_str}")
                    print(f"[DEBUG] Contains CHART_URL: {'[CHART_URL]' in tool_result_str}")

                    # モーダルトリガーを検出した場合、フラグを立てる
                    if "[COST_MODAL_TRIGGER]" in tool_result_str:
                        modal_triggered = True
                        # モーダル用のdoneイベントを送信して終了
                        yield f"data: {json.dumps({'type': 'status', 'status': 'none', 'message': ''}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'content': ''}, ensure_ascii=False)}\n\n"
                        return  # ストリーミングを終了

                    # generate_documentの結果を保存（LLMが削除した場合に備えて）
                    if "[PDF_FILE]" in tool_result_str:
                        last_generate_document_result = tool_result_str

                    # ツール結果からPDFファイルを抽出（generate_document用）
                    _, tool_pdf_files = extract_pdf_files(tool_result_str)
                    for filename, pdf_base64 in tool_pdf_files:
                        if filename not in sent_pdf_filenames:
                            sent_pdf_filenames.add(filename)
                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf_base64}, ensure_ascii=False)}\n\n"

                    # ツール結果から[CHART_URL]タグを抽出（generate_chart用）
                    # LLMがタグを削除しても画像が表示されるよう、直接送信
                    chart_urls = extract_chart_urls(tool_result_str)
                    for chart_url in chart_urls:
                        if chart_url not in sent_chart_urls:
                            sent_chart_urls.add(chart_url)
                            print(f"[DEBUG] 📊 Found CHART_URL in tool_result: {chart_url}")
                            # [CHART_URL]タグを含むコンテンツを直接送信
                            # これによりフロントエンドが画像を表示できる
                            chart_tag = f"\n\n[CHART_URL]{chart_url}[/CHART_URL]"
                            # full_responseに追加しておく（LLMが削除した場合のバックアップ）
                            full_response += chart_tag
                            yield f"data: {json.dumps({'type': 'content', 'data': chart_tag}, ensure_ascii=False)}\n\n"

                    # ツール結果から画像も抽出（[CHART_IMAGE]タグから）
                    _, tool_images = extract_chart_images(tool_result_str)
                    for img in tool_images:
                        if img not in sent_images:
                            sent_images.append(img)
                            print(f"[DEBUG] Sending image from tool_result (CHART_IMAGE tag), size: {len(img)}")
                            yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"
                    
                    # ファイルパスから画像を読み込む（フォールバック）
                    _, file_images = extract_chart_image_from_path(tool_result_str)
                    for img in file_images:
                        if img not in sent_images:
                            sent_images.append(img)
                            print(f"[DEBUG] Sending image from file path, size: {len(img)}")
                            yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                    yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': '思考中...'}, ensure_ascii=False)}\n\n"
                    continue

                # content chunk
                if "data" in event:
                    # モーダルがトリガーされた場合は、以降のLLM出力をスキップ
                    if modal_triggered:
                        continue
                    full_response += event["data"]

                    # 画像データを抽出（[CHART_IMAGE]タグから）
                    clean_text, images = extract_chart_images(full_response)

                    # 新しい画像があれば送信
                    for img in images:
                        if img not in sent_images:
                            sent_images.append(img)
                            yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"
                    
                    # ファイルパスからも画像を読み込む（フォールバック）
                    _, file_images = extract_chart_image_from_path(full_response)
                    for img in file_images:
                        if img not in sent_images:
                            sent_images.append(img)
                            print(f"[DEBUG] Sending image from file path in content, size: {len(img)}")
                            yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                    # PDFファイルを抽出（ファイル名で重複チェック）
                    _, pdf_files = extract_pdf_files(clean_text)
                    for filename, pdf_base64 in pdf_files:
                        if filename not in sent_pdf_filenames:
                            sent_pdf_filenames.add(filename)
                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf_base64}, ensure_ascii=False)}\n\n"

                    # 古いパターンのみ除去（PDF_FILEタグは保持）
                    display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', clean_text).strip()
                    display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
                    # モーダルトリガーを除去（モーダル表示後はAI出力を止める）
                    display_response = re.sub(r'\[COST_MODAL_TRIGGER\]', '', display_response).strip()
                    # 空でなければ送信
                    if display_response:
                        yield f"data: {json.dumps({'type': 'content', 'data': display_response}, ensure_ascii=False)}\n\n"
                    continue
        except (GeneratorExit, asyncio.CancelledError):
            is_cancelled = True
        except Exception as e:
            error_msg = f"Error occurred: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
        finally:
            if not is_cancelled:
                yield f"data: {json.dumps({'type': 'status', 'status': 'none', 'message': ''}, ensure_ascii=False)}\n\n"

                # LLMが[PDF_FILE]タグを削除していた場合、元のツール結果を追加
                if last_generate_document_result and "[PDF_FILE]" not in full_response:
                    pdf_tags = re.findall(r'\[PDF_FILE\](.*?)\[/PDF_FILE\]', last_generate_document_result)
                    if pdf_tags:
                        # タグを最後に追加
                        tag_text = "\n\n" + "\n".join([f"[PDF_FILE]{tag}[/PDF_FILE]" for tag in pdf_tags])
                        full_response += tag_text
                        yield f"data: {json.dumps({'type': 'content', 'data': tag_text}, ensure_ascii=False)}\n\n"

                # ========== 確実にグラフ画像を送信 ==========
                # グローバル変数からファイルパスを取得して確実に送信
                try:
                    from tools.chart_generator import LAST_GENERATED_CHARTS
                    if LAST_GENERATED_CHARTS:
                        print(f"[DEBUG] 🖼️ LAST_GENERATED_CHARTS から {len(LAST_GENERATED_CHARTS)} 件の画像を送信")
                        for chart_path in LAST_GENERATED_CHARTS:
                            chart_file = Path(project_root) / chart_path
                            if chart_file.exists():
                                try:
                                    import base64
                                    with open(chart_file, 'rb') as f:
                                        image_bytes = f.read()
                                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                                        if image_base64 not in sent_images:
                                            sent_images.append(image_base64)
                                            print(f"[DEBUG] ✅ グラフ画像を送信: {chart_path}, size: {len(image_base64)}")
                                            yield f"data: {json.dumps({'type': 'image', 'data': image_base64}, ensure_ascii=False)}\n\n"
                                except Exception as e:
                                    print(f"[DEBUG] ❌ 画像読み込みエラー: {e}")
                            else:
                                print(f"[DEBUG] ⚠️ ファイルが存在しません: {chart_file}")
                        # クリア
                        LAST_GENERATED_CHARTS.clear()
                except Exception as e:
                    print(f"[DEBUG] グラフ送信エラー: {e}")

                # ========== 確実にPDFを送信 ==========
                # グローバル変数からPDFファイルパスを取得して確実に送信
                try:
                    from tools.document_generator import LAST_GENERATED_PDFS
                    if LAST_GENERATED_PDFS:
                        print(f"[DEBUG] 📄 LAST_GENERATED_PDFS から {len(LAST_GENERATED_PDFS)} 件のPDFを送信")
                        for pdf_path in LAST_GENERATED_PDFS:
                            # 絶対パスか相対パスかを判定
                            pdf_file = Path(pdf_path)
                            if not pdf_file.is_absolute():
                                pdf_file = Path(project_root) / pdf_path
                            
                            if pdf_file.exists():
                                try:
                                    import base64
                                    with open(pdf_file, 'rb') as f:
                                        pdf_bytes = f.read()
                                        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                                        filename = pdf_file.name
                                        if filename not in sent_pdf_filenames:
                                            sent_pdf_filenames.add(filename)
                                            print(f"[DEBUG] ✅ PDFを送信: {pdf_path}")
                                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf_base64}, ensure_ascii=False)}\n\n"
                                except Exception as e:
                                    print(f"[DEBUG] ❌ PDF読み込みエラー: {e}")
                            else:
                                print(f"[DEBUG] ⚠️ PDFファイルが存在しません: {pdf_file}")
                        # クリア
                        LAST_GENERATED_PDFS.clear()
                except Exception as e:
                    print(f"[DEBUG] PDF送信エラー: {e}")

                # 最終的なテキストから画像を抽出（タグは保持）
                clean_text, images = extract_chart_images(full_response)
                
                # PDFファイルを抽出（ファイル名で重複チェック）
                _, pdf_files = extract_pdf_files(clean_text)
                for filename, pdf_base64 in pdf_files:
                    if filename not in sent_pdf_filenames:
                        sent_pdf_filenames.add(filename)
                        yield f"data: {json.dumps({'type': 'pdf', 'data': pdf_base64}, ensure_ascii=False)}\n\n"
                
                # PDF_FILEタグは保持してフロントエンドで処理
                display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', clean_text).strip()
                display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
                # モーダルトリガーを除去
                display_response = re.sub(r'\[COST_MODAL_TRIGGER\]', '', display_response).strip()

                # 残りの画像があれば送信
                for img in images:
                    if img not in sent_images:
                        sent_images.append(img)
                        yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"
                
                # ファイルパスからも画像を読み込む（最終フォールバック）
                _, final_file_images = extract_chart_image_from_path(full_response)
                for img in final_file_images:
                    if img not in sent_images:
                        sent_images.append(img)
                        print(f"[DEBUG] Sending image from file path (final), size: {len(img)}")
                        yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                if display_response:
                    orchestrator.append_assistant_message(session, display_response)
                yield f"data: {json.dumps({'type': 'done', 'content': display_response}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ideal-pricing-debug")
async def ideal_pricing_debug(request: dict):
    """デバッグ用：リクエストボディを確認"""
    print(f"[DEBUG] Raw request body: {request}")
    return {"received": request}


@app.post("/api/ideal-pricing", response_model=IdealPricingResponse)
async def ideal_pricing_endpoint(request: IdealPricingRequest):
    """理想の原価計算 - 「去年 vs 今年」方式で松竹梅プランを算出
    
    上昇率は「以前」と「現在」の金額から自動計算される。
    空欄の項目は業界平均で補完される。
    """
    # デバッグログ
    print(f"[DEBUG] Received request: {request}")
    try:
        # 業界平均の上昇率（空欄時のデフォルト値）
        DEFAULT_INCREASE_RATES = {
            "material_cost": 0.15,    # 材料費: +15%
            "labor_cost": 0.05,       # 人件費: +5%
            "energy_cost": 0.25,      # 光熱費: +25%
            "overhead": 0.03          # その他: +3%
        }
        
        # 万円 → 円に変換（入力は万円単位）
        def to_yen(value: Optional[float]) -> float:
            return (value or 0) * 10000
        
        # 各費目の処理（上昇率を自動計算）
        def process_cost(previous: Optional[float], current: Optional[float], cost_type: str):
            prev = to_yen(previous)
            curr = to_yen(current)
            
            # 両方空欄の場合はスキップ
            if prev == 0 and curr == 0:
                return None
            
            # 片方だけ入力されている場合はデフォルト上昇率を適用
            if prev > 0 and curr == 0:
                change_rate = DEFAULT_INCREASE_RATES.get(cost_type, 0.10)
                curr = prev * (1 + change_rate)
            elif curr > 0 and prev == 0:
                change_rate = DEFAULT_INCREASE_RATES.get(cost_type, 0.10)
                prev = curr / (1 + change_rate)
            else:
                # 両方入力されている場合は上昇率を計算
                change_rate = (curr - prev) / prev if prev > 0 else 0
            
            return {
                "previous": prev,
                "current": curr,
                "change_rate": change_rate
            }
        
        # 各費目を処理
        costs = {}
        cost_items = [
            ("material_cost", request.material_cost_previous, request.material_cost_current),
            ("labor_cost", request.labor_cost_previous, request.labor_cost_current),
            ("energy_cost", request.energy_cost_previous, request.energy_cost_current),
            ("overhead", request.overhead_previous, request.overhead_current),
        ]
        
        for cost_type, prev, curr in cost_items:
            result = process_cost(prev, curr, cost_type)
            if result:
                costs[cost_type] = result
        
        if not costs:
            return IdealPricingResponse(
                success=False,
                message="コスト情報が入力されていません。少なくとも1つの費目を入力してください。"
            )
        
        # 総コストの計算
        previous_total_cost = sum(c["previous"] for c in costs.values())
        current_total_cost = sum(c["current"] for c in costs.values())
        total_cost_increase = current_total_cost - previous_total_cost
        cost_increase_rate = (total_cost_increase / previous_total_cost) * 100 if previous_total_cost > 0 else 0
        
        # 売上高の処理
        current_sales = to_yen(request.current_sales)
        previous_sales = to_yen(request.previous_sales)
        
        if current_sales <= 0:
            # 売上高が未入力の場合、コストから推計（利益率8%と仮定）
            current_sales = current_total_cost / (1 - 0.08)
        
        if previous_sales <= 0:
            previous_sales = previous_total_cost / (1 - 0.08)
        
        # 利益率計算
        previous_profit = previous_sales - previous_total_cost
        before_profit_rate = (previous_profit / previous_sales) * 100 if previous_sales > 0 else 8.0
        
        current_profit = current_sales - current_total_cost
        new_profit_rate = (current_profit / current_sales) * 100 if current_sales > 0 else 0

        # 松竹梅シナリオを計算
        def calc_price(target_margin: float) -> float:
            if target_margin >= 100:
                return current_total_cost * 1.2
            return current_total_cost / (1 - target_margin / 100)

        # 松（理想）: 元の利益率 + 2%
        premium_margin = before_profit_rate + 2
        premium_price = calc_price(premium_margin)
        premium_increase_rate = ((premium_price - current_sales) / current_sales) * 100 if current_sales > 0 else 0

        # 竹（妥当）: 元の利益率を維持
        standard_margin = before_profit_rate
        standard_price = calc_price(standard_margin)
        standard_increase_rate = ((standard_price - current_sales) / current_sales) * 100 if current_sales > 0 else 0

        # 梅（最低防衛）: 利益率3%
        minimum_margin = 3.0
        minimum_price = calc_price(minimum_margin)
        minimum_increase_rate = ((minimum_price - current_sales) / current_sales) * 100 if current_sales > 0 else 0

        # 緊急度判定
        if new_profit_rate < 0:
            urgency = "high"
            urgency_message = "価格転嫁なしでは赤字です。早急な交渉が必要です。"
            recommended = "standard"
        elif new_profit_rate < 3:
            urgency = "medium"
            urgency_message = "利益率が大幅に低下します。価格転嫁を検討してください。"
            recommended = "standard"
        else:
            urgency = "low"
            urgency_message = "利益率は維持できますが、将来に備えた交渉も検討可能です。"
            recommended = "minimum"

        # コスト構造の詳細（各費目）
        cost_structure_before = {}
        cost_structure_after = {}
        cost_changes = {}
        
        for cost_type, data in costs.items():
            cost_structure_before[cost_type] = data["previous"]
            cost_structure_after[cost_type] = data["current"]
            cost_changes[cost_type] = data["change_rate"] * 100  # パーセント表示

        result = {
            "cost_structure": {
                "before": {
                    **cost_structure_before,
                    "total": previous_total_cost,
                },
                "after": {
                    **cost_structure_after,
                    "total": current_total_cost,
                },
                "changes": cost_changes,
                "total_increase": total_cost_increase,
                "total_increase_rate": cost_increase_rate,
            },
            "profit_analysis": {
                "previous_sales": previous_sales,
                "current_sales": current_sales,
                "before_profit_rate": before_profit_rate,
                "after_profit_rate_if_unchanged": new_profit_rate,
            },
            "scenarios": {
                "premium": {
                    "name": "松（理想）",
                    "description": "コスト高騰前より高い利益率を確保",
                    "target_price": premium_price,
                    "price_increase_rate": premium_increase_rate,
                    "profit_margin": premium_margin,
                },
                "standard": {
                    "name": "竹（妥当）",
                    "description": "コスト高騰前の利益率を維持",
                    "target_price": standard_price,
                    "price_increase_rate": standard_increase_rate,
                    "profit_margin": standard_margin,
                },
                "minimum": {
                    "name": "梅（最低防衛）",
                    "description": "事業継続のための最低ライン",
                    "target_price": minimum_price,
                    "price_increase_rate": minimum_increase_rate,
                    "profit_margin": minimum_margin,
                },
            },
            "recommendation": {
                "urgency": urgency,
                "urgency_message": urgency_message,
                "recommended_scenario": recommended,
            },
        }

        return IdealPricingResponse(success=True, result=result, message="計算完了")

    except Exception as e:
        return IdealPricingResponse(success=False, result=None, message=f"計算エラー: {str(e)}")


@app.post("/api/cost-analysis", response_model=CostAnalysisResponse)
async def cost_analysis_endpoint(request: CostAnalysisRequest):
    """Cost impact helper - calculates cost changes."""
    try:
        # コスト高騰前の計算
        before_total_cost = request.before_cost + request.before_expenses
        before_profit = request.before_sales - before_total_cost
        before_profit_rate = (before_profit / request.before_sales * 100) if request.before_sales > 0 else 0
        
        # 現在の計算
        current_total_cost = request.current_cost + request.current_expenses
        current_profit = request.current_sales - current_total_cost
        current_profit_rate = (current_profit / request.current_sales * 100) if request.current_sales > 0 else 0
        
        # 増減率の計算
        sales_change_rate = ((request.current_sales - request.before_sales) / request.before_sales * 100) if request.before_sales > 0 else 0
        cost_change_rate = ((request.current_cost - request.before_cost) / request.before_cost * 100) if request.before_cost > 0 else 0
        expenses_change_rate = ((request.current_expenses - request.before_expenses) / request.before_expenses * 100) if request.before_expenses > 0 else 0
        total_cost_change_rate = ((current_total_cost - before_total_cost) / before_total_cost * 100) if before_total_cost > 0 else 0
        profit_change_rate = ((current_profit - before_profit) / abs(before_profit) * 100) if before_profit != 0 else 0
        
        # 増減額の計算
        sales_change = request.current_sales - request.before_sales
        cost_change = request.current_cost - request.before_cost
        expenses_change = request.current_expenses - request.before_expenses
        total_cost_change = current_total_cost - before_total_cost
        profit_change = current_profit - before_profit
        
        # 参考価格の算出
        if before_profit_rate < 100 and before_profit_rate > 0:
            reference_price = current_total_cost / (1 - before_profit_rate / 100)
        else:
            reference_price = current_total_cost * 1.1
        
        price_gap = reference_price - request.current_sales
        price_gap_rate = (price_gap / request.current_sales * 100) if request.current_sales > 0 else 0
        
        result = {
            "before": {
                "sales": request.before_sales,
                "cost": request.before_cost,
                "expenses": request.before_expenses,
                "total_cost": before_total_cost,
                "profit": before_profit,
                "profit_rate": before_profit_rate
            },
            "current": {
                "sales": request.current_sales,
                "cost": request.current_cost,
                "expenses": request.current_expenses,
                "total_cost": current_total_cost,
                "profit": current_profit,
                "profit_rate": current_profit_rate
            },
            "changes": {
                "sales": {"amount": sales_change, "rate": sales_change_rate},
                "cost": {"amount": cost_change, "rate": cost_change_rate},
                "expenses": {"amount": expenses_change, "rate": expenses_change_rate},
                "total_cost": {"amount": total_cost_change, "rate": total_cost_change_rate},
                "profit": {"amount": profit_change, "rate": profit_change_rate}
            },
            "reference_price": reference_price,
            "price_gap": price_gap,
            "price_gap_rate": price_gap_rate
        }

        return CostAnalysisResponse(success=True, result=result, message="calculation succeeded")

    except Exception as e:
        return CostAnalysisResponse(success=False, result=None, message=f"calculation error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
