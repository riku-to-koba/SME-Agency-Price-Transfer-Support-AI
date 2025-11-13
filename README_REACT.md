# 価格転嫁支援AIアシスタント - React版

StreamlitからReact + TypeScriptフロントエンドに移行したバージョンです。

## 📁 プロジェクト構成

```
SME-Agency-Price-Transfer-Support-AI/
├── api/                    # FastAPIバックエンド
│   ├── main.py            # APIサーバー
│   └── requirements.txt   # バックエンド依存パッケージ
├── frontend/               # React + TypeScriptフロントエンド
│   ├── src/
│   │   ├── App.tsx        # メインコンポーネント
│   │   ├── App.css        # スタイル
│   │   └── main.tsx       # エントリーポイント
│   ├── package.json       # フロントエンド依存パッケージ
│   └── vite.config.ts     # Vite設定
├── agent/                 # エージェントロジック（既存）
├── tools/                 # ツール（既存）
└── app.py                 # Streamlit版（既存、参考用）
```

## 🚀 セットアップ

### 1. バックエンドのセットアップ

```bash
# 仮想環境を作成（推奨）
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt
pip install -r api/requirements.txt
```

### 2. フロントエンドのセットアップ

```bash
cd frontend

# 依存パッケージをインストール
npm install
```

## 🏃 起動方法

### 方法1: 統合起動スクリプト（最も簡単）⭐

**Windows:**
```bash
# ダブルクリックするか、コマンドプロンプトで実行
start_all.bat
```

または PowerShell:
```powershell
.\start_all.ps1
```

このスクリプトは以下を自動で行います：
- 依存パッケージの確認とインストール
- バックエンドサーバーの起動（別ウィンドウ）
- フロントエンドサーバーの起動（別ウィンドウ）
- ブラウザで `http://localhost:5173` を開く

### 方法2: 個別起動スクリプト

**Windows:**
```bash
# ターミナル1: バックエンド
start_backend.bat

# ターミナル2: フロントエンド
start_frontend.bat
```

**macOS/Linux:**
```bash
chmod +x start_backend.sh start_frontend.sh
./start_backend.sh  # ターミナル1
./start_frontend.sh # ターミナル2
```

### 方法3: 手動起動

**ターミナル1: バックエンド**
```bash
# 依存パッケージをインストール（初回のみ）
pip install -r api/requirements.txt

# バックエンドサーバーを起動（ポート8000）
python api/main.py
```

**ターミナル2: フロントエンド**
```bash
cd frontend

# 依存パッケージをインストール（初回のみ）
npm install

# フロントエンドサーバーを起動
npm run dev
```

ブラウザで `http://localhost:5173` を開いてください。

## 🔧 環境変数

以下の環境変数が必要です（既存のStreamlit版と同じ）：

- AWS認証情報（`~/.aws/credentials` または環境変数）
- `TAVILY_API_KEY`: Tavily APIキー（Web検索用）

## 📡 APIエンドポイント

### `POST /api/session`
新しいセッションを作成

**レスポンス:**
```json
{
  "session_id": "abc12345"
}
```

### `POST /api/chat`
チャットメッセージを送信（ストリーミング対応）

**リクエスト:**
```json
{
  "message": "原価計算のやり方を教えて",
  "session_id": "abc12345"
}
```

**レスポンス:** Server-Sent Events (SSE) ストリーム

### `GET /api/diagrams/latest`
最新の生成された図を取得

**レスポンス:**
```json
{
  "diagram": {
    "filename": "diagram.png",
    "data": "data:image/png;base64,..."
  }
}
```

### `POST /api/session/{session_id}/clear`
セッションをクリア

## 🎨 機能

- ✅ リアルタイムストリーミング応答
- ✅ セッション管理
- ✅ ステップ自動判定と表示
- ✅ ツール使用中の表示
- ✅ 生成された図の自動表示
- ✅ チャット履歴の管理
- ✅ レスポンシブデザイン

## 🔄 Streamlit版との違い

1. **フロントエンド**: Streamlit → React + TypeScript
2. **バックエンド**: Streamlit内蔵 → FastAPI（独立サーバー）
3. **ストリーミング**: Streamlit独自 → Server-Sent Events (SSE)
4. **セッション管理**: Streamlit session_state → FastAPIメモリ管理

## 🐛 トラブルシューティング

### バックエンドが起動しない
- Python仮想環境がアクティブか確認
- ポート8000が使用されていないか確認
- `requirements.txt`の依存パッケージがインストールされているか確認

### フロントエンドが起動しない
- Node.jsがインストールされているか確認（v18以上推奨）
- `npm install`が完了しているか確認
- ポート5173が使用されていないか確認

### CORSエラー
- `api/main.py`の`allow_origins`にフロントエンドのURLが含まれているか確認

### ストリーミングが動作しない
- ブラウザの開発者ツールでネットワークタブを確認
- EventSourceがサポートされているか確認（モダンブラウザは対応済み）

## 📝 開発メモ

- バックエンドは`uvicorn`で起動（開発モード）
- フロントエンドは`vite`で起動（HMR対応）
- セッション管理はメモリ上（再起動でリセット）
- 本番環境ではセッション管理をデータベースなどに移行推奨

