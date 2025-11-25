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
from fastapi.responses import FileResponse, StreamingResponse
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


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class UserInfo(BaseModel):
    industry: Optional[str] = None
    products: Optional[str] = None
    companySize: Optional[str] = None
    region: Optional[str] = None
    clientIndustry: Optional[str] = None
    priceTransferStatus: Optional[str] = None


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


def build_user_info_dict(user_info: Optional[UserInfo]) -> Optional[dict]:
    if not user_info:
        return None
    return {
        "industry": user_info.industry,
        "products": user_info.products,
        "companySize": user_info.companySize,
        "region": user_info.region,
        "clientIndustry": user_info.clientIndustry,
        "priceTransferStatus": user_info.priceTransferStatus,
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


@app.get("/")
async def root():
    """Health check."""
    return {"message": "Price Transfer Assistant API", "status": "ok"}


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

        # initial thinking signal
        yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': 'processing...'}, ensure_ascii=False)}\n\n"

        try:
            async for event in orchestrator.stream(session, request.message):
                # mode updates
                if event.get("type") == "mode_update":
                    yield f"data: {json.dumps({'type': 'mode_update', 'mode': event['mode']}, ensure_ascii=False)}\n\n"
                    continue

                # tool status
                if "current_tool_use" in event and event["current_tool_use"].get("name"):
                    tool_name = event["current_tool_use"]["name"]
                    status_message = f"{tool_name} running..."
                    yield f"data: {json.dumps({'type': 'status', 'status': 'tool_use', 'tool': tool_name, 'message': status_message}, ensure_ascii=False)}\n\n"
                    continue

                # tool result
                if "tool_result" in event:
                    yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': 'processing...'}, ensure_ascii=False)}\n\n"
                    continue

                # content chunk
                if "data" in event:
                    full_response += event["data"]
                    display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
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
                display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
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


@app.get("/api/diagrams/latest")
async def get_latest_diagram(session_id: Optional[str] = None):
    """Get latest diagram file info for a session."""
    diagrams_dir = os.path.join(os.getcwd(), "diagrams")
    if not os.path.exists(diagrams_dir):
        return {"diagram": None}

    if not session_id:
        return {"diagram": None}

    session = orchestrator.get_session(session_id)
    if session is None:
        return {"diagram": None}

    session_start_time = session.get("created_at") or datetime.now().timestamp()
    session["created_at"] = session_start_time

    all_diagram_files = [f for f in os.listdir(diagrams_dir) if f.endswith(".png")]
    filtered_files = []
    for filename in all_diagram_files:
        filepath = os.path.join(diagrams_dir, filename)
        file_mtime = os.path.getmtime(filepath)
        if file_mtime >= session_start_time:
            filtered_files.append((filename, file_mtime))

    if filtered_files:
        filtered_files.sort(key=lambda x: x[1], reverse=True)
        filename = filtered_files[0][0]
        return {
            "diagram": {
                "filename": filename,
                "url": f"/api/diagrams/{filename}",
            }
        }

    return {"diagram": None}


@app.get("/api/diagrams/{filename}")
async def get_diagram(filename: str):
    """Return diagram image file."""
    diagrams_dir = os.path.join(os.getcwd(), "diagrams")
    filepath = os.path.join(diagrams_dir, filename)

    if not os.path.exists(filepath) or not filename.endswith(".png"):
        raise HTTPException(status_code=404, detail="Diagram not found")

    return FileResponse(filepath, media_type="image/png")


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

    print("=" * 80, flush=True)
    print("[DEBUG] starting FastAPI server", flush=True)
    print("[DEBUG] port: 8765", flush=True)
    print("=" * 80, flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8765)
