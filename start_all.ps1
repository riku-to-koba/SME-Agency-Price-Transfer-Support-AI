# 価格転嫁支援AIアシスタント - 起動スクリプト (PowerShell版)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "価格転嫁支援AIアシスタント - 起動スクリプト" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# バックエンドの依存パッケージを確認
Write-Host "[1/3] バックエンドの依存パッケージを確認中..." -ForegroundColor Yellow
try {
    python -c "import fastapi" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "FastAPI not found"
    }
} catch {
    Write-Host "FastAPIが見つかりません。インストール中..." -ForegroundColor Yellow
    pip install -r api/requirements.txt
}

# フロントエンドの依存パッケージを確認
Write-Host "[2/3] フロントエンドの依存パッケージを確認中..." -ForegroundColor Yellow
Set-Location frontend
if (-not (Test-Path node_modules)) {
    Write-Host "node_modulesが見つかりません。インストール中..." -ForegroundColor Yellow
    npm install
}
Set-Location ..

Write-Host "[3/3] サーバーを起動中..." -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "バックエンド: http://localhost:8000" -ForegroundColor Green
Write-Host "フロントエンド: http://localhost:5173" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "ブラウザで http://localhost:5173 を開いてください" -ForegroundColor Yellow
Write-Host ""
Write-Host "注意: このウィンドウを閉じるとサーバーが停止します" -ForegroundColor Red
Write-Host "Ctrl+C で停止できます" -ForegroundColor Red
Write-Host ""

# バックエンドを新しいウィンドウで起動
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; python api/main.py" -WindowStyle Normal

# 少し待ってからフロントエンドを起動
Start-Sleep -Seconds 2

# フロントエンドを新しいウィンドウで起動
Set-Location frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; npm run dev" -WindowStyle Normal
Set-Location ..

Write-Host ""
Write-Host "両方のサーバーが起動しました！" -ForegroundColor Green
Write-Host "ブラウザを開いています..." -ForegroundColor Yellow
Write-Host ""

# 少し待ってからブラウザを開く
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"

Write-Host "サーバーを停止するには、各ウィンドウでCtrl+Cを押すか、ウィンドウを閉じてください" -ForegroundColor Red
Write-Host ""
Read-Host "Enterキーを押して終了"

