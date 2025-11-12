"""FastAPIバックエンドサーバー"""
import asyncio
import json
import os
import re
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.core import PriceTransferAgent

app = FastAPI(title="価格転嫁支援AIアシスタント API")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite/Reactのデフォルトポート
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# セッション管理（メモリ上）
sessions: Dict[str, dict] = {}


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


def get_or_create_session(session_id: Optional[str] = None, user_info: Optional[dict] = None) -> str:
    """セッションを取得または作成"""
    if session_id and session_id in sessions:
        return session_id
    
    new_session_id = str(uuid.uuid4())[:8]
    
    # ユーザー情報を辞書形式に変換
    user_info_dict = None
    if user_info:
        user_info_dict = {
            "industry": user_info.get("industry"),
            "products": user_info.get("products"),
            "companySize": user_info.get("companySize"),
            "region": user_info.get("region"),
            "clientIndustry": user_info.get("clientIndustry"),
            "priceTransferStatus": user_info.get("priceTransferStatus"),
        }
        print(f"[DEBUG] エージェント初期化時にユーザー情報を渡します: {user_info_dict}")
    
    sessions[new_session_id] = {
        "session_id": new_session_id,
        "messages": [],
        "agent": PriceTransferAgent(user_info=user_info_dict),
        "current_step": None,
        "user_info": user_info_dict
    }
    print(f"[DEBUG] セッション作成: session_id={new_session_id}, user_info={user_info_dict}")
    return new_session_id


@app.get("/")
async def root():
    """ヘルスチェック"""
    return {"message": "価格転嫁支援AIアシスタント API", "status": "ok"}


@app.post("/api/session", response_model=SessionResponse)
async def create_session(request: SessionRequest = SessionRequest()):
    """新しいセッションを作成"""
    print("=" * 80)
    print("[DEBUG] ========== セッション作成APIが呼ばれました ==========")
    print(f"[DEBUG] リクエスト全体: {request}")
    print(f"[DEBUG] request.user_info: {request.user_info}")
    print(f"[DEBUG] request.user_infoの型: {type(request.user_info)}")
    
    user_info_dict = None
    if request.user_info:
        print(f"[DEBUG] ユーザー情報が存在します")
        user_info_dict = {
            "industry": request.user_info.industry,
            "products": request.user_info.products,
            "companySize": request.user_info.companySize,
            "region": request.user_info.region,
            "clientIndustry": request.user_info.clientIndustry,
            "priceTransferStatus": request.user_info.priceTransferStatus,
        }
        print(f"[DEBUG] ユーザー情報を辞書に変換: {user_info_dict}")
    else:
        print("[DEBUG] ユーザー情報がNoneまたは空です")
    
    session_id = get_or_create_session(user_info=user_info_dict)
    print(f"[DEBUG] セッション作成完了: session_id={session_id}")
    print("=" * 80)
    return SessionResponse(session_id=session_id)


@app.get("/api/session/{session_id}/messages")
async def get_messages(session_id: str):
    """セッションのメッセージ履歴を取得"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "messages": sessions[session_id]["messages"],
        "current_step": sessions[session_id]["current_step"]
    }


@app.post("/api/session/{session_id}/clear")
async def clear_session(session_id: str):
    """セッションをクリア"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    user_info = sessions[session_id].get("user_info")
    sessions[session_id]["messages"] = []
    sessions[session_id]["agent"] = PriceTransferAgent(user_info=user_info)
    sessions[session_id]["current_step"] = None
    
    return {"message": "Session cleared"}


@app.post("/api/chat")
async def chat_endpoint(request: ChatMessage):
    """チャットエンドポイント（ストリーミング対応）"""
    # セッションを取得または作成
    session_id = get_or_create_session(request.session_id)
    session = sessions[session_id]
    
    # ユーザーメッセージを履歴に追加
    user_message = {"role": "user", "content": request.message}
    session["messages"].append(user_message)
    
    async def stream_response():
        """ストリーミング応答を生成"""
        full_response = ""
        has_content = False
        current_tool = None
        
        try:
            agent = session["agent"]
            agent_stream = agent.stream_async(request.message)
            
            async for event in agent_stream:
                if "data" in event:
                    # テキストチャンク
                    if not has_content:
                        has_content = True
                    
                    full_response += event["data"]
                    
                    # [IMAGE_PATH:...] を除いたテキストを送信
                    display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                    
                    yield f"data: {json.dumps({'type': 'content', 'data': display_response}, ensure_ascii=False)}\n\n"
                
                elif "current_tool_use" in event and event["current_tool_use"].get("name"):
                    # ツール使用情報
                    tool_name = event["current_tool_use"]["name"]
                    if tool_name != current_tool:
                        current_tool = tool_name
                        tool_msg = f"\n\n*[{tool_name} を使用中]*\n\n"
                        full_response += tool_msg
                        
                        yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name}, ensure_ascii=False)}\n\n"
                
                elif "tool_result" in event:
                    # ツール結果を検知してステップ判定を処理
                    tool_use = event.get("tool_use", {})
                    if tool_use.get("name") == "detect_current_step":
                        tool_result = event.get("tool_result", "")
                        
                        try:
                            result_data = json.loads(tool_result)
                            detected_step = result_data.get("step")
                            confidence = result_data.get("confidence", "不明")
                            reasoning = result_data.get("reasoning", "理由なし")
                            
                            # ステップが有効な場合のみ更新
                            if detected_step and detected_step != "UNKNOWN":
                                session["current_step"] = detected_step
                                # エージェントを再初期化
                                update_result = session["agent"].update_step(detected_step)
                                
                                yield f"data: {json.dumps({'type': 'step_update', 'step': detected_step, 'confidence': confidence, 'reasoning': reasoning}, ensure_ascii=False)}\n\n"
                        except (json.JSONDecodeError, AttributeError) as e:
                            # JSONパースエラーは無視
                            pass
            
            # 最終応答を処理
            display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
            display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
            
            # アシスタントメッセージを履歴に追加
            session["messages"].append({"role": "assistant", "content": display_response})
            
            # 完了イベント
            yield f"data: {json.dumps({'type': 'done', 'content': display_response}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_msg = f"エラーが発生しました: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/diagrams/latest")
async def get_latest_diagram():
    """最新の図の情報を取得"""
    diagrams_dir = os.path.join(os.getcwd(), "diagrams")
    if not os.path.exists(diagrams_dir):
        return {"diagram": None}
    
    diagram_files = sorted(
        [f for f in os.listdir(diagrams_dir) if f.endswith('.png')],
        key=lambda x: os.path.getmtime(os.path.join(diagrams_dir, x)),
        reverse=True
    )
    
    if diagram_files:
        filename = diagram_files[0]
        return {
            "diagram": {
                "filename": filename,
                "url": f"/api/diagrams/{filename}"
            }
        }
    
    return {"diagram": None}


@app.get("/api/diagrams/{filename}")
async def get_diagram(filename: str):
    """図ファイルを取得"""
    diagrams_dir = os.path.join(os.getcwd(), "diagrams")
    filepath = os.path.join(diagrams_dir, filename)
    
    if not os.path.exists(filepath) or not filename.endswith('.png'):
        raise HTTPException(status_code=404, detail="Diagram not found")
    
    return FileResponse(filepath, media_type="image/png")


if __name__ == "__main__":
    import sys
    import uvicorn
    
    # バッファリングを無効化（ログが即座に表示されるように）
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    print("=" * 80, flush=True)
    print("[DEBUG] FastAPIサーバーを起動します", flush=True)
    print("[DEBUG] ポート: 8000", flush=True)
    print("=" * 80, flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)

