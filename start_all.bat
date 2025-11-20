@echo off
chcp 65001 >nul
echo ========================================
echo 価格転嫁支援AIアシスタント - 起動スクリプト
echo ========================================
echo.

REM バックエンドの依存パッケージを確認
echo [1/3] バックエンドの依存パッケージを確認中...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo FastAPIが見つかりません。インストール中...
    pip install -r requirements.txt
)

REM フロントエンドの依存パッケージを確認
echo [2/3] フロントエンドの依存パッケージを確認中...
cd frontend
if not exist node_modules (
    echo node_modulesが見つかりません。インストール中...
    call npm install
)
cd ..

echo [3/3] サーバーを起動中...
echo.

echo.
echo ========================================
echo バックエンド: http://localhost:8765
echo フロントエンド: http://localhost:5173
echo ========================================
echo.
echo ブラウザで http://localhost:5173 を開いてください
echo.
echo 注意: このウィンドウを閉じるとサーバーが停止します
echo Ctrl+C で停止できます
echo.

REM バックエンドをバックグラウンドで起動
start "Backend Server" cmd /k "python api/main.py"

REM 少し待ってからフロントエンドを起動
timeout /t 2 /nobreak >nul

REM フロントエンドを起動
cd frontend
start "Frontend Server" cmd /k "npm run dev"
cd ..

REM 少し待ってからブラウザを開く
timeout /t 5 /nobreak >nul
start http://localhost:5173

echo.
echo 両方のサーバーが起動しました！
echo ブラウザが自動で開きます...
echo もし開かない場合は、手動で http://localhost:5173 を開いてください
echo.
pause

