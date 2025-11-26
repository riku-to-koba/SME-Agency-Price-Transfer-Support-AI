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
    """理想の原価計算リクエスト"""
    material_cost: float
    labor_cost: float
    energy_cost: float
    overhead: float
    material_cost_change: float  # %
    labor_cost_change: float     # %
    energy_cost_change: float    # %
    current_sales: Optional[float] = None


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


def extract_pdf_documents(text: str) -> tuple[str, list[str]]:
    """テキストからPDFドキュメントのBase64データを抽出する。

    Returns:
        (PDFタグを除去したテキスト, Base64 PDFデータのリスト)
    """
    pattern = r'\[PDF_DOCUMENT\](.*?)\[/PDF_DOCUMENT\]'
    pdfs = re.findall(pattern, text, re.DOTALL)
    clean_text = re.sub(pattern, '', text, flags=re.DOTALL).strip()
    return clean_text, pdfs


def extract_pdf_files(text: str) -> tuple[str, list[str]]:
    """テキストからPDFファイル名を抽出し、Base64エンコードしたデータを返す。

    Returns:
        (PDFタグを除去したテキスト, Base64 PDFデータのリスト)
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
                    pdfs.append(pdf_base64)
            except Exception:
                pass
    
    return clean_text, pdfs


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
        sent_images = []  # 送信済み画像を追跡

        # initial thinking signal
        yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': '思考中...'}, ensure_ascii=False)}\n\n"

        try:
            async for event in orchestrator.stream(session, request.message):
                # 任意のイベントから画像とPDFを抽出
                event_str = str(event)
                _, event_images = extract_chart_images(event_str)
                for img in event_images:
                    if img not in sent_images:
                        sent_images.append(img)
                        yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                # PDFも抽出
                _, event_pdfs = extract_pdf_documents(event_str)
                for pdf in event_pdfs:
                    if pdf not in sent_images:  # 送信済みリストを共用
                        sent_images.append(pdf)
                        yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"
                
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
                    else:
                        yield f"data: {json.dumps({'type': 'status', 'status': 'tool_use', 'tool': tool_name, 'message': status_message}, ensure_ascii=False)}\n\n"
                    continue

                # tool result
                if "tool_result" in event:
                    tool_result_str = str(event.get("tool_result", ""))
                    
                    # ツール結果からPDFファイルを抽出（generate_document用）
                    _, tool_pdf_files = extract_pdf_files(tool_result_str)
                    for pdf in tool_pdf_files:
                        if pdf not in sent_images:
                            sent_images.append(pdf)
                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"
                    
                    # 古いBase64形式のPDFも抽出（互換性のため）
                    _, tool_pdfs = extract_pdf_documents(tool_result_str)
                    for pdf in tool_pdfs:
                        if pdf not in sent_images:
                            sent_images.append(pdf)
                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"
                    
                    # ツール結果から画像も抽出
                    _, tool_images = extract_chart_images(tool_result_str)
                    for img in tool_images:
                        if img not in sent_images:
                            sent_images.append(img)
                            yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': '思考中...'}, ensure_ascii=False)}\n\n"
                    continue

                # content chunk
                if "data" in event:
                    full_response += event["data"]

                    # 画像データを抽出
                    clean_text, images = extract_chart_images(full_response)

                    # 新しい画像があれば送信
                    for img in images:
                        if img not in sent_images:
                            sent_images.append(img)
                            yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                    # PDFファイルを抽出（ファイル名からBase64エンコード）
                    # 注意: タグは除去せず、フロントエンドで表示用に処理する
                    _, pdf_files = extract_pdf_files(clean_text)
                    for pdf in pdf_files:
                        if pdf not in sent_images:
                            sent_images.append(pdf)
                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"

                    # 古いBase64形式のPDFも抽出（互換性のため）
                    # 注意: タグは除去せず、フロントエンドで表示用に処理する
                    _, pdfs = extract_pdf_documents(clean_text)
                    for pdf in pdfs:
                        if pdf not in sent_images:
                            sent_images.append(pdf)
                            yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"

                    # 古いパターンのみ除去（PDF_FILEタグは保持）
                    display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', clean_text).strip()
                    display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
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

                # グローバル変数から生成されたPDFを取得して送信
                try:
                    from tools.document_generator import LAST_GENERATED_PDFS
                    import base64 as b64
                    
                    while LAST_GENERATED_PDFS:
                        pdf_path = LAST_GENERATED_PDFS.pop(0)
                        if os.path.exists(pdf_path):
                            with open(pdf_path, 'rb') as f:
                                pdf_bytes = f.read()
                                pdf_base64 = b64.b64encode(pdf_bytes).decode('utf-8')
                                yield f"data: {json.dumps({'type': 'pdf', 'data': pdf_base64}, ensure_ascii=False)}\n\n"
                except Exception:
                    pass

                # 最終的なテキストから画像を抽出（タグは保持）
                clean_text, images = extract_chart_images(full_response)
                
                # PDFファイルを抽出（ファイル名からBase64エンコード）
                # 注意: タグは除去せず、フロントエンドで表示用に処理する
                _, pdf_files = extract_pdf_files(clean_text)
                for pdf in pdf_files:
                    if pdf not in sent_images:
                        sent_images.append(pdf)
                        yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"
                
                # 古いBase64形式のPDFも抽出（互換性のため）
                _, pdfs = extract_pdf_documents(clean_text)
                
                # PDF_FILEタグは保持してフロントエンドで処理
                display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', clean_text).strip()
                display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()

                # 残りの画像があれば送信
                for img in images:
                    if img not in sent_images:
                        sent_images.append(img)
                        yield f"data: {json.dumps({'type': 'image', 'data': img}, ensure_ascii=False)}\n\n"

                # 残りのPDFがあれば送信
                for pdf in pdfs:
                    if pdf not in sent_images:
                        sent_images.append(pdf)
                        yield f"data: {json.dumps({'type': 'pdf', 'data': pdf}, ensure_ascii=False)}\n\n"

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


@app.post("/api/ideal-pricing", response_model=IdealPricingResponse)
async def ideal_pricing_endpoint(request: IdealPricingRequest):
    """理想の原価計算 - 松竹梅プランを算出"""
    try:
        # 現在の総コスト
        current_total_cost = (
            request.material_cost +
            request.labor_cost +
            request.energy_cost +
            request.overhead
        )

        if current_total_cost <= 0:
            return IdealPricingResponse(
                success=False,
                message="コスト構造が正しく入力されていません"
            )

        # 価格上昇後の各コスト
        new_material = request.material_cost * (1 + request.material_cost_change / 100)
        new_labor = request.labor_cost * (1 + request.labor_cost_change / 100)
        new_energy = request.energy_cost * (1 + request.energy_cost_change / 100)
        new_overhead = request.overhead  # 経費は変動なしと仮定

        new_total_cost = new_material + new_labor + new_energy + new_overhead
        total_cost_increase = new_total_cost - current_total_cost
        cost_increase_rate = (total_cost_increase / current_total_cost) * 100

        # 売上高の推計（未指定の場合）
        if request.current_sales and request.current_sales > 0:
            current_sales = request.current_sales
        else:
            # 利益率8%を仮定
            current_sales = current_total_cost / (1 - 0.08)

        # 現在の利益率
        current_profit = current_sales - current_total_cost
        before_profit_rate = (current_profit / current_sales) * 100 if current_sales > 0 else 0

        # 価格据え置き時の利益率
        new_profit = current_sales - new_total_cost
        new_profit_rate = (new_profit / current_sales) * 100 if current_sales > 0 else 0

        # 松竹梅シナリオを計算
        def calc_price(target_margin: float) -> float:
            if target_margin >= 100:
                return new_total_cost * 1.2
            return new_total_cost / (1 - target_margin / 100)

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

        result = {
            "cost_structure": {
                "before": {
                    "material_cost": request.material_cost,
                    "labor_cost": request.labor_cost,
                    "energy_cost": request.energy_cost,
                    "overhead": request.overhead,
                    "total": current_total_cost,
                },
                "after": {
                    "material_cost": new_material,
                    "labor_cost": new_labor,
                    "energy_cost": new_energy,
                    "overhead": new_overhead,
                    "total": new_total_cost,
                },
                "changes": {
                    "material_cost": request.material_cost_change,
                    "labor_cost": request.labor_cost_change,
                    "energy_cost": request.energy_cost_change,
                    "overhead": 0,
                },
                "total_increase": total_cost_increase,
                "total_increase_rate": cost_increase_rate,
            },
            "profit_analysis": {
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
