# 価格転嫁支援AIアシスタント - セットアップ・起動手順書

## 目次
1. [前提条件](#前提条件)
2. [AWS認証情報の設定](#aws認証情報の設定)
3. [アプリケーションの起動](#アプリケーションの起動)
4. [動作確認](#動作確認)
5. [トラブルシューティング](#トラブルシューティング)

---

## 前提条件

以下のソフトウェアがインストールされていることを確認してください：

- **Python 3.12以上**
  ```bash
  python --version
  ```

- **Node.js 18以上 & npm**
  ```bash
  node --version
  npm --version
  ```

- **AWS CLI v2**
  ```bash
  aws --version
  ```

  インストールされていない場合：
  - Windows: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
  - または `winget install Amazon.AWSCLI`

---

## AWS認証情報の設定

このアプリケーションはAWS Bedrockを使用するため、専用のAWSプロファイルを設定する必要があります。

### Step 1: アクセスキーの取得

1. `bedrock_use_only_accessKeys.csv` ファイルを開きます
2. 以下の情報を確認します：
   - **Access Key ID**: `AKIA...`で始まる文字列
   - **Secret Access Key**: 秘密キー文字列

### Step 2: AWS CLIでプロファイルを設定

コマンドプロンプトまたはPowerShellを開き、以下を実行：

```bash
aws configure --profile bedrock_use_only
```

プロンプトに従って入力：

```
AWS Access Key ID [None]: <CSVファイルのAccess Key IDを入力>
AWS Secret Access Key [None]: <CSVファイルのSecret Access Keyを入力>
Default region name [None]: ap-northeast-1
Default output format [None]: json
```

### Step 3: 設定の確認

設定が正しく保存されたか確認します：

**方法1: ファイルを直接確認**

```bash
# Windows
type %USERPROFILE%\.aws\credentials
# または
notepad %USERPROFILE%\.aws\credentials
```

以下のような内容が表示されれば成功：

```ini
[bedrock_use_only]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

**方法2: AWS CLIコマンドで確認**

```bash
aws configure list --profile bedrock_use_only
```

以下のような出力が表示されれば成功：

```
      Name                    Value             Type    Location
      ----                    -----             ----    --------
   profile         bedrock_use_only           manual    --profile
access_key     ****************XXXX shared-credentials-file
secret_key     ****************XXXX shared-credentials-file
    region           ap-northeast-1      config-file    ~/.aws/config
```

---

## アプリケーションの起動

### 一括起動（推奨）

1. プロジェクトのルートディレクトリで `start_all.bat` をダブルクリック

2. 自動的に以下が実行されます：
   - Python依存パッケージの確認・インストール
   - Node.js依存パッケージの確認・インストール
   - バックエンドサーバーの起動（ポート8765）
   - フロントエンドサーバーの起動（ポート5173）
   - ブラウザの自動起動

3. ブラウザが自動で開きます：http://localhost:5173

### サーバーの停止

- 各サーバーウィンドウで `Ctrl+C` を押す
- またはウィンドウを閉じる

---