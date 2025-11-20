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
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.core import PriceTransferAgent
from tools.cost_analysis import calculate_cost_impact
from tools.step_detector import detect_current_step

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


def get_or_create_session(session_id: Optional[str] = None, user_info: Optional[dict] = None) -> str:
    """セッションを取得または作成"""
    if session_id and session_id in sessions:
        # 既存セッションの場合、created_atがなければ設定
        if "created_at" not in sessions[session_id]:
            sessions[session_id]["created_at"] = datetime.now().timestamp()
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
        "user_info": user_info_dict,
        "created_at": datetime.now().timestamp()  # セッション作成時刻を記録
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
    # セッション開始時刻をリセット（図もクリアされる）
    sessions[session_id]["created_at"] = datetime.now().timestamp()
    
    return {"message": "Session cleared"}


@app.post("/api/chat")
async def chat_endpoint(request: ChatMessage):
    """チャットエンドポイント（ストリーミング対応）"""
    # セッションを取得または作成
    session_id = get_or_create_session(request.session_id)
    session = sessions[session_id]
    
    # 既存セッションの場合、created_atがなければ設定（リロード時の対策）
    if "created_at" not in session:
        session["created_at"] = datetime.now().timestamp()
    
    # ユーザーメッセージを履歴に追加
    user_message = {"role": "user", "content": request.message}
    session["messages"].append(user_message)
    
    # ステップ更新情報を保存（ストリーミング内で実行するため）
    step_update_info = {
        "step": None,
        "confidence": "不明",
        "reasoning": "理由なし",
        "updated": False
    }
    
    async def stream_response():
        """ストリーミング応答を生成"""
        full_response = ""
        has_content = False
        current_tool = None
        is_cancelled = False
        is_thinking = True  # 最初は思考中
        
        # ツール名から日本語メッセージへのマッピング
        tool_status_messages = {
            "web_search": "検索中...",
            "search_knowledge_base": "検索中...",
            "generate_diagram": "図を生成中...",
            "calculator": "計算中...",
            "detect_current_step": "ステップを判定中...",
            "analyze_cost_impact": "コスト分析中...",
            "current_time": "時刻を取得中...",
        }
        
        # 最初に「思考中」を送信
        yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': '思考中...'}, ensure_ascii=False)}\n\n"
        
        # ============================================================================
        # ステップ判定を最初に実行（質問の最初にステップ判定を行う）
        # ============================================================================
        print(f"\n{'='*80}")
        print(f"[DEBUG] ========== 質問の最初にステップ判定を実行 ==========")
        print(f"[DEBUG] ユーザーの質問: {request.message}")
        print(f"{'='*80}\n")
        
        # 会話履歴から文脈を構築（直近5件のメッセージ）
        conversation_context = ""
        recent_messages = session["messages"][-5:]  # 直近5件
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                conversation_context += f"ユーザー: {content}\n"
            elif role == "assistant":
                conversation_context += f"アシスタント: {content[:200]}...\n"  # 長い場合は省略
        
        # ステップ判定を実行（非同期で実行してブロックしないようにする）
        step_updated = False  # 初期化
        try:
            # 同期関数を非同期で実行
            import concurrent.futures
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                step_result_json = await loop.run_in_executor(
                    executor,
                    detect_current_step,
                    request.message,
                    conversation_context
                )
            
            # JSON結果をパース
            step_result = json.loads(step_result_json)
            detected_step = step_result.get("step")
            confidence = step_result.get("confidence", "不明")
            reasoning = step_result.get("reasoning", "理由なし")
            
            print(f"[DEBUG] ステップ判定結果:")
            print(f"  - ステップ: {detected_step}")
            print(f"  - 信頼度: {confidence}")
            print(f"  - 理由: {reasoning}\n")
            
            # ステップが有効で、現在のステップと異なる場合のみ更新
            if detected_step and detected_step != "UNKNOWN":
                current_step = session.get("current_step")
                if current_step != detected_step:
                    print(f"[DEBUG] ✅ ステップを更新: {current_step} -> {detected_step}")
                    session["current_step"] = detected_step
                    # エージェントを新しいステップで再初期化
                    session["agent"].update_step(detected_step)
                    print(f"[DEBUG] ✅ エージェント再初期化完了（新しいプロンプトで）\n")
                    step_updated = True
                else:
                    print(f"[DEBUG] ℹ️ ステップは既に設定済み: {detected_step}\n")
            else:
                print(f"[DEBUG] ⚠️ ステップが判定できませんでした（UNKNOWN）\n")
            
            # ステップ更新情報を保存
            step_update_info["step"] = detected_step
            step_update_info["confidence"] = confidence
            step_update_info["reasoning"] = reasoning
            step_update_info["updated"] = step_updated
            
        except Exception as e:
            print(f"[DEBUG] ❌ ステップ判定エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            print(f"[DEBUG] ⚠️ エラーが発生しましたが、処理を続行します\n")
        
        # ステップ更新情報があれば、送信
        if step_update_info.get("updated") and step_update_info.get("step"):
            yield f"data: {json.dumps({'type': 'step_update', 'step': step_update_info['step'], 'confidence': step_update_info['confidence'], 'reasoning': step_update_info['reasoning']}, ensure_ascii=False)}\n\n"
        
        try:
            agent = session["agent"]
            agent_stream = agent.stream_async(request.message)
            
            async for event in agent_stream:
                # クライアント切断をチェック（非同期ジェネレータの中断を検知）
                try:
                    if "data" in event:
                        # テキストチャンクが来たら思考中を解除
                        if is_thinking:
                            is_thinking = False
                            yield f"data: {json.dumps({'type': 'status', 'status': 'none', 'message': ''}, ensure_ascii=False)}\n\n"
                        
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
                            is_thinking = False  # ツール使用中は思考中ではない
                            print(f"[DEBUG] ツール使用中: {tool_name}")
                            
                            # ツール使用中のステータスメッセージを送信
                            status_message = tool_status_messages.get(tool_name, f"{tool_name}を実行中...")
                            yield f"data: {json.dumps({'type': 'status', 'status': 'tool_use', 'tool': tool_name, 'message': status_message}, ensure_ascii=False)}\n\n"
                            
                            # analyze_cost_impactツールの場合は、フロントエンドにモーダル表示イベントを送信
                            if tool_name == "analyze_cost_impact":
                                yield f"data: {json.dumps({'type': 'tool_use', 'tool': tool_name, 'show_modal': True}, ensure_ascii=False)}\n\n"
                    
                    elif "tool_result" in event:
                        # ツール結果が来たら、ステータスをクリアして思考中に戻す
                        if current_tool:
                            current_tool = None
                            is_thinking = True
                            yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'message': '思考中...'}, ensure_ascii=False)}\n\n"
                        
                        # ツール結果を検知（detect_current_stepは既に質問の最初で実行済み）
                        tool_use = event.get("tool_use", {})
                        if tool_use.get("name") == "detect_current_step":
                            # 既に質問の最初でステップ判定を行っているため、ここではログのみ
                            tool_result = event.get("tool_result", "")
                            print(f"[DEBUG] ℹ️ エージェントがdetect_current_stepを再度呼び出しました（既に実行済み）")
                            # ステップ更新イベントは送信しない（既に質問の最初で処理済み）
                except (GeneratorExit, asyncio.CancelledError) as e:
                    # クライアント切断を検知
                    is_cancelled = True
                    print(f"[DEBUG] クライアントが切断されました: {str(e)}")
                    break
                except Exception as e:
                    # その他のエラーはログに記録して続行
                    print(f"[DEBUG] ストリーミング中のエラー: {str(e)}")
                    continue
            
            # クライアントが切断されていない場合のみ最終処理
            if not is_cancelled:
                # ステータスをクリア
                yield f"data: {json.dumps({'type': 'status', 'status': 'none', 'message': ''}, ensure_ascii=False)}\n\n"
                
                # 最終応答を処理
                display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
                
                # アシスタントメッセージを履歴に追加（空でない場合のみ）
                if display_response:
                    session["messages"].append({"role": "assistant", "content": display_response})
                
                # 完了イベント
                yield f"data: {json.dumps({'type': 'done', 'content': display_response}, ensure_ascii=False)}\n\n"
            else:
                # 停止された場合、部分的な応答を履歴に追加（空でない場合のみ）
                if full_response:
                    display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                    display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
                    if display_response:
                        session["messages"].append({"role": "assistant", "content": display_response})
            
        except (GeneratorExit, asyncio.CancelledError) as e:
            # クライアント切断を検知
            print(f"[DEBUG] ストリーミングがキャンセルされました: {str(e)}")
            # 部分的な応答を履歴に追加（空でない場合のみ）
            if full_response:
                display_response = re.sub(r'\[IMAGE_PATH:[^\]]*\]', '', full_response).strip()
                display_response = re.sub(r'\[DIAGRAM_IMAGE\].+?\[/DIAGRAM_IMAGE\]', '', display_response).strip()
                if display_response:
                    session["messages"].append({"role": "assistant", "content": display_response})
        except Exception as e:
            error_msg = f"エラーが発生しました: {str(e)}"
            print(f"[DEBUG] ストリーミングエラー: {error_msg}")
            try:
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg}, ensure_ascii=False)}\n\n"
            except:
                # クライアントが既に切断されている場合は無視
                pass
    
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
async def get_latest_diagram(session_id: Optional[str] = None):
    """最新の図の情報を取得（セッションに紐づく）"""
    diagrams_dir = os.path.join(os.getcwd(), "diagrams")
    if not os.path.exists(diagrams_dir):
        return {"diagram": None}
    
    # セッションIDが必須（セッションIDがない場合は図を返さない）
    if not session_id or session_id not in sessions:
        return {"diagram": None}
    
    # セッション開始時刻を取得
    session_start_time = sessions[session_id].get("created_at")
    
    # created_atが設定されていない場合は、現在時刻を設定（既存セッション対策）
    if not session_start_time:
        session_start_time = datetime.now().timestamp()
        sessions[session_id]["created_at"] = session_start_time
    
    # すべての図ファイルを取得
    all_diagram_files = [
        f for f in os.listdir(diagrams_dir) if f.endswith('.png')
    ]
    
    # セッション開始時刻以降に作成された図のみをフィルタリング
    filtered_files = []
    for filename in all_diagram_files:
        filepath = os.path.join(diagrams_dir, filename)
        file_mtime = os.path.getmtime(filepath)
        if file_mtime >= session_start_time:
            filtered_files.append((filename, file_mtime))
    
    if filtered_files:
        # 最新の図を取得
        filtered_files.sort(key=lambda x: x[1], reverse=True)
        filename = filtered_files[0][0]
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


@app.post("/api/cost-analysis", response_model=CostAnalysisResponse)
async def cost_analysis_endpoint(request: CostAnalysisRequest):
    """価格転嫁検討ツール - コスト高騰影響分析
    
    このエンドポイントはSTEP_0_CHECK_9（価格転嫁の必要性判定）で使用します。
    価格転嫁の必要性を判定するためのツールで、営業利益が赤字になっているかを調査します。
    """
    try:
        # セッションのcurrent_stepをチェック（オプション）
        # 今回はツールとして直接呼び出せるようにする
        
        # 計算実行
        result = calculate_cost_impact(
            before_sales=request.before_sales,
            before_cost=request.before_cost,
            before_expenses=request.before_expenses,
            current_sales=request.current_sales,
            current_cost=request.current_cost,
            current_expenses=request.current_expenses
        )
        
        return CostAnalysisResponse(
            success=True,
            result=result,
            message="分析が完了しました"
        )
        
    except Exception as e:
        print(f"[DEBUG] コスト分析エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return CostAnalysisResponse(
            success=False,
            result=None,
            message=f"分析エラー: {str(e)}"
        )


if __name__ == "__main__":
    import sys
    import uvicorn

    # バッファリングを無効化（ログが即座に表示されるように）
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    print("=" * 80, flush=True)
    print("[DEBUG] FastAPIサーバーを起動します", flush=True)
    print("[DEBUG] ポート: 8765", flush=True)
    print("=" * 80, flush=True)
    uvicorn.run(app, host="0.0.0.0", port=8765)

