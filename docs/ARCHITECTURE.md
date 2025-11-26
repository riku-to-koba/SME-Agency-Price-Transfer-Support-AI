# アーキテクチャ設計書 (System Architecture)

## 🏗️ 1. システム概要

本システムは、**「3層エージェント・アーキテクチャ (3-Tier Agent Architecture)」**を採用する。
1つの親エージェント(Orchestrator)と2つの子エージェント(Mode 1 / Mode 2)で構成され、ユーザーの課題深度に応じてシステムプロンプト、ツールセット、振る舞いを動的に切り替え、単なるチャットボットを超えた「実行支援ソフトウェア」としての挙動を実現する。

### システム全体像

```
ユーザー（中小企業経営者）
        ↓
    チャットUI (React)
        ↓
    ┌─────────────────────────────────────┐
    │  Orchestrator Agent（親エージェント）  │
    │  - 全リクエストの入り口               │
    │  - モード判定のみを担当               │
    │  - ステートレス（状態を持たない）     │
    │  - LLM: Claude 4.5 Haiku            │
    └─────────────────────────────────────┘
        ↓（毎回判定）
    ┌─────────────────────────────────────┐
    │  適切な子エージェントへ振り分け       │
    └─────────────────────────────────────┘
        ↓
    ┌──────────────────┬──────────────────┐
    │  Mode 1 Agent    │  Mode 2 Agent    │
    │  よろず相談       │  価格転嫁専門     │
    │                  │                  │
    │  - Web検索標準   │  - ツール直接呼出 │
    │  - 傾聴・相談    │  - Function Call  │
    │  - ステートレス  │  - 成果物管理     │
    │  - Haiku        │  - Haiku         │
    └──────────────────┴──────────────────┘
        ↓
    外部連携・データレイヤー
    - Web Search API
    - RAG Service (S3 + Vector Search)
    - S3 Storage
    - Session Management (In-Memory / DB)
```

### アーキテクチャの特徴

1. **3層エージェント構造**: Orchestrator(親) → Mode 1/2 Agent(子)の明確な役割分担
2. **毎回のモード判定**: 全てのリクエストがOrchestratorを経由し、リアルタイムでモード判定
3. **6つの専門ツール直接使用**: Mode 2 AgentはLLMがFunction Callingで必要なツールを直接呼び出し
4. **柔軟なツール選択**: 会話内容に応じてLLMが最適なツールを判断・実行（ステップの強制なし）
5. **シームレスな実行**: ユーザーは対話を続けるだけで、裏側でツールが連携動作
6. **参考ガイドライン**: 14ステップ（CHECK 1-9, STEP 1-5）は参考情報として提供

**詳細なシステムマップは [system-map.html](./system-map.html) を参照してください。**

---

## 🧠 2. 3層エージェント・アーキテクチャ

### 2.1 Orchestrator Agent（親エージェント・司令塔）

#### 役割
全てのユーザーリクエストの入り口として、モード判定と適切なエージェントへの振り分けを担当。

#### 責務
- **ユーザー入力を毎回受け取る**: 全リクエストの入り口（フロントドア）
- **モード判定**: ユーザーの発言が「Mode 1: よろず相談」か「Mode 2: 価格転嫁専門」かを判定
- **モード切り替え処理**: モードが変わった場合、ユーザー承諾を取得してから切り替え
- **セッション状態の更新**: 現在のモード、会話履歴をセッションに保存
- **適切な子エージェントへの委譲**: Mode 1 AgentまたはMode 2 Agentに処理を委譲

#### 判定方式
- **キーワードベース判定**: 「値上げ」「価格転嫁」「コスト増」「買いたたき」「下請法」等のキーワードを検知
- **軽量LLM推論**: キーワードで判定できない場合のみ、LLMに問い合わせ（最小トークン使用）
- **判定頻度**: 毎回（全リクエスト）

#### 特性
- **ステートレス（状態を持たない）**: 判定だけを行い、ビジネスロジックは持たない
- **高速・軽量**: 最小限の推論で迅速にルーティング
- **LLM**: Claude 4.5 Haiku

#### 実装イメージ
```python
class OrchestratorAgent:
    async def handle(self, user_input: str, session: Session) -> Response:
        # 毎回モード判定
        mode = await self._detect_mode(user_input, session)

        # モード切り替え処理
        if mode != session.mode:
            if not await self._get_user_consent(mode):
                return Response("現在のモードを継続します")
            session.mode = mode

        # 適切な子エージェントへ委譲
        agent = self.agents[mode]  # Mode1Agent or Mode2Agent
        return await agent.execute(user_input, session)

    async def _detect_mode(self, user_input: str, session: Session) -> str:
        # キーワードマッチング
        keywords = ["値上げ", "価格転嫁", "コスト増", "買いたたき", "下請法"]
        if any(kw in user_input for kw in keywords):
            return "mode2"

        # 文脈分析（軽量LLM推論）
        confidence = await self.llm.classify(user_input, session.history)
        return "mode2" if confidence > 0.7 else "mode1"
```

---

### 2.2 Mode 1 Agent（よろず相談エージェント）

#### 役割
経営課題全般の相談に対応する汎用エージェント。

#### 責務
- **傾聴・状況整理**: ユーザーの悩みを丁寧に聞き出し、真の課題を特定
- **幅広い経営アドバイス**: 資金繰り、人材、販路拡大、事業承継など
- **Web検索機能**: 最新の市場動向、業界ニュース、統計データをリアルタイムで取得
- **メンタルケア**: 経営者の孤独感や不安に寄り添う

#### 技術構成
- **LLM**: Claude 4.5 Haiku
- **プロンプト戦略**: 傾聴・共感を重視した対話型
- **外部API**: Web Search API（市場動向、ニュース検索）
- **メモリ管理**: LLMのコンテキストウィンドウで会話履歴を保持

#### 特性
- **ステートレス（軽量）**: 複雑な状態管理は不要
- **柔軟な対応**: 特定のプロセスに縛られない自由な対話

---

### 2.3 Mode 2 Agent（価格転嫁専門エージェント）

#### 役割
価格交渉に特化した専門家エージェント。6つの専門ツールを直接使用して徹底サポート。

#### 責務
- **ツール直接実行**: LLMがFunction Callingで6つの専門ツールを直接呼び出し
- **柔軟な対応**: ユーザーの要望に応じて最適なツールを判断・実行
- **成果物管理**: 生成されたグラフ、文書、試算表などをセッションに紐付けて保存
- **ガイドライン提供**: 14ステップ（CHECK 1-9, STEP 1-5）を参考情報として提示

#### ツール使用方式
- **入力情報**:
  - ユーザーの発言
  - 会話履歴（LLMコンテキスト）
  - ユーザー属性データ（業種、企業規模等）
- **判断ロジック**:
  - LLMが会話内容から必要なツールを直接判断
  - Function Callingで該当ツールを呼び出し
- **柔軟性**: ユーザーは自由にツールを使用可能（順番の制約なし）

#### セッションデータ構造
```python
session.generated_files = [
    {
        "type": "graph",
        "url": "s3://bucket/session123/market_graph.png",
        "tool": "market_analysis",
        "created_at": "2025-01-01T10:00:00"
    },
    {
        "type": "excel",
        "url": "s3://bucket/session123/cost_analysis.xlsx",
        "tool": "analyze_cost_impact",
        "created_at": "2025-01-01T10:05:00"
    }
]
```

#### 技術構成
- **LLM**: Claude 4.5 Haiku
- **プロンプト戦略**: 価格転嫁専門家としてのシステムプロンプト
- **専門ツール**: 6つの高度なツール（後述）をFunction Callingで直接呼び出し
- **外部API**: Web Search API, RAG Service, S3 Storage
- **メモリ管理**:
  - 会話履歴をLLMコンテキストで保持
  - 構造化データ（原価情報、取引先リスト等）をJSON形式でプロンプトに埋め込み
  - セッションが長くなった場合は自動要約でコンテキスト圧縮

#### 特性
- **柔軟なツール使用**: ユーザーの要望に応じて適切なツールを直接呼び出し
- **参考ガイドライン**: 14ステップを参考情報として提供（強制ではない）
- **証拠ベース**: 全ての提案に出典・根拠を明示

#### 実装イメージ
```python
class Mode2Agent:
    # 6つの専門ツールをFunction Callingで定義
    tools = [
        market_analysis,
        company_research,
        analyze_cost_impact,
        scenario_generator,
        document_generator,
        search_knowledge_base,
    ]

    async def execute(self, user_input: str, session: Session) -> Response:
        # LLMがFunction Callingでツールを直接呼び出し
        response = await self.llm.chat(
            messages=session.history + [{"role": "user", "content": user_input}],
            tools=self.tools,
            system=PRICE_TRANSFER_SPECIALIST_PROMPT
        )

        # ツール呼び出しがあれば実行
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = await self._execute_tool(tool_call, session)
                session.generated_files.append(result.file_info)

        return Response(response.message, attachments=response.files)
```

---

### 2.4 セッション管理とメモリ継続性

#### セッション構造
```python
class Session:
    session_id: str
    user_id: str
    mode: str  # "mode1" or "mode2"
    history: List[Message]  # 会話履歴
    generated_files: List[Dict]  # 生成されたファイル（グラフ、文書等）
    user_attributes: Dict  # 業種、企業規模等
    created_at: datetime
    updated_at: datetime
```

#### メモリ継続性の実現
- **Orchestratorを毎回通過**: 全リクエストがOrchestratorを経由するため、セッション状態を常に更新
- **会話履歴の永続化**: 会話履歴は全モード共通で保持され、Mode 1に切り替わっても消えない
- **モード切り替え後の復元**: Mode 2に戻った際、以前の会話コンテキストから継続可能

#### 実装パターン（段階的アプローチ）
1. **プロトタイプ段階**: LLMコンテキストのみで会話履歴を保持
2. **初期リリース**: In-Memoryストア（Python辞書 `SESSIONS = {}`）でセッション管理
3. **本番運用**: Redis / DynamoDB等の永続ストアに移行

---

## 🛠️ 3. 6つの専門ツール（Mode 2専用）

### 3.1 ツール設計の原則

**最小公倍数のツール設計**
- 各ツールは単一の明確な責務を持つ
- LLMが判断・解釈を行い、ツールは実行のみを担当
- ツールを組み合わせて高度な機能を実現
- 過剰な抽象化を避け、必要な機能のみを実装

### 3.2 ツール一覧と役割

| ツール名 | 責務 | LLMの役割 | 主要技術 |
|---------|------|----------|---------|
| `web_search` | Web検索実行（AI信頼性判定付き） | 検索結果の解釈・分析 | Tavily API, Bedrock (Haiku) |
| `search_knowledge_base` | RAG検索実行 | 法的解釈・違法性判定・対抗話法生成 | AWS Bedrock Knowledge Base |
| `calculate_cost_impact` | コスト試算・シミュレーション | 計算結果の解釈・推奨シナリオ判断 | Python計算ロジック |
| `generate_chart` | グラフ画像生成（Base64形式） | データ抽出・グラフ種類選択・解釈 | Matplotlib |
| `generate_document` | 文書ファイル生成 | 文書内容作成・トーン判断・論理構成 | テンプレートエンジン, ReportLab (PDF) |
| `simulate_negotiation` | ロールプレイ・スコアリング | 相手役発言生成・戦略評価・改善提案 | ペルソナ別ロジック, スコアリング |

### 3.3 各ツールの詳細仕様

#### 3.3.1 `web_search`
**概要**: あらゆる外部情報取得の基盤ツール。AIが信頼性を動的に判定。

**責務**:
- Tavily APIでWeb検索を実行
- AIが各検索結果の信頼性を判定（政府機関、公的機関、企業サイト等を優先）
- 信頼できる情報源のみをフィルタリングして返却
- 結果の解釈・分析はLLMが担当

**入力パラメータ**:
```python
{
    "query": str,              # 検索クエリ
    "max_results": int         # 最大検索結果数（デフォルト: 5）
}
```

**出力**: フォーマット済みテキスト
```
【検索クエリ】: 企業物価指数 ステンレス 推移

【AI回答】: ...

【検索結果】（AIが信頼できると判定したソースのみ）:

1. 企業物価指数 2024年12月
   URL: https://...
   種別: 政府機関
   鉄鋼は前年比+15.3%...
```

**AI信頼性判定の基準**:
- 信頼できる: 政府機関、公的機関、大学・研究機関、業界メディア、企業サイト等
- 除外: 個人ブログ、アフィリエイトサイト、まとめサイト、スパムサイト

**LLMの役割**:
- 検索結果から数値データを抽出（価格指数、成長率、財務数値等）
- 企業情報を分析してランク付け（S/A/B/C）
- 業界動向を解釈して交渉戦略を提案

**使用タイミング**: CHECK 2（市場データ）, CHECK 6（取引先調査）, STEP 1（業界動向）

---

#### 3.3.2 `search_knowledge_base`
**概要**: AWS Bedrock Knowledge Baseを使用した法務知識検索ツール

**責務**:
- AWS Bedrock Knowledge Baseでセマンティック検索を実行
- 法的根拠、計算式、事例を取得
- 法的解釈・適用判断はLLMが担当

**入力パラメータ**:
```python
{
    "query": str,              # 検索クエリ
    "max_results": int         # 最大検索結果数（デフォルト: 5）
}
```

**出力**: フォーマット済みテキスト
```
【Knowledge Base検索結果】
検索クエリ: 買いたたき 判定基準
結果件数: 5件

--- 結果 1 ---
【出典】ファイル名: 下請法ガイドライン.pdf
スコア: 0.9523
【内容】
下請法第4条第1項第5号により、発注者が下請事業者の...
```

**登録データ**:
- 下請代金支払遅延等防止法（下請法）全文
- 独占禁止法 関連条文
- 価格転嫁円滑化施策ハンドブック（中小企業庁）
- 労務費の適切な転嫁のための価格交渉に関する指針
- 公正取引委員会 勧告事例集
- 原価計算の基礎（業種別モデル）

**LLMの役割**:
- 取得した条文をユーザーの状況に適用
- 違法性の判定と説明
- 対抗話法の生成（法的根拠付き）

**使用タイミング**: CHECK 3（計算式参照）, CHECK 8（法令違反チェック）, 随時

---

#### 3.3.3 `calculate_cost_impact`
**概要**: コスト影響試算・シミュレーションツール。松竹梅の3段階価格設定を自動生成。

**責務**:
- コスト上昇のインパクトを計算
- 松竹梅プラン（理想/妥当/最低防衛）を自動生成
- 計算結果の解釈・推奨はLLMが担当

**入力パラメータ**:
```python
{
    "current_cost_structure": {
        "material_cost": {"ratio": 0.40, "amount": 1000000},
        "labor_cost": {"ratio": 0.35, "amount": 875000},
        "energy_cost": {"ratio": 0.10, "amount": 250000},
        "overhead": {"ratio": 0.15, "amount": 375000}
    },
    "price_changes": {
        "material_cost": 0.20,  # +20%
        "labor_cost": 0.05,     # +5%
        "energy_cost": 0.30     # +30%
    },
    "current_sales": float,      # 現在の売上高（オプション）
    "target_profit_margin": float # 目標利益率（オプション）
}
```

**出力**: フォーマット済みテキスト
```
📊 **コスト影響分析結果**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【現状分析】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**現在のコスト構造:**
- 材料費: 1,000,000円 → 1,200,000円 (+20.0%)
- 労務費: 875,000円 → 918,750円 (+5.0%)
...

【価格改定シナリオ（松竹梅）】

🌟 **松（理想）**
   - 目標価格: 3,150,000円（+15.0%）
   - 利益率: 10.0%

✅ **竹（妥当）**
   - 目標価格: 2,950,000円（+10.0%）
   - 利益率: 8.0%

⚡ **梅（最低防衛）**
   - 目標価格: 2,800,000円（+5.0%）
   - 利益率: 3.0%
```

**LLMの役割**:
- 計算結果の解釈と説明
- どのシナリオを推奨すべきかの判断
- 計算ロジックをユーザーに分かりやすく説明

**使用タイミング**: CHECK 3, CHECK 9（最重要）

---

#### 3.3.4 `generate_chart`
**概要**: データ可視化ツール。Base64形式で画像データを返却。

**責務**:
- データを受け取りグラフ画像を生成
- Base64エンコードした画像データを返却（フロントエンドで直接表示可能）
- グラフ種類の選択・データ解釈はLLMが担当

**入力パラメータ**:
```python
{
    "data": {
        # 折れ線グラフの場合
        "time_series": [
            {"date": "2021", "value": 100},
            {"date": "2022", "value": 115},
            {"date": "2023", "value": 145}
        ]
        # または棒グラフの場合
        "labels": ["製造業", "小売業", "建設業"],
        "values": [100, 200, 150]
    },
    "chart_type": str,  # "line" | "bar"
    "title": str,
    "x_label": str,     # オプション
    "y_label": str      # オプション
}
```

**出力**: 特殊フォーマット（Base64画像データを含む）
```
✅ グラフを生成しました

**タイトル**: ステンレス価格指数の推移
**グラフタイプ**: line

[CHART_IMAGE]iVBORw0KGgoAAAANSU...[/CHART_IMAGE]
```

**グラフタイプの選び方**:
- `line`（折れ線グラフ）: 時間の経過に伴う変化・推移を見せる時
- `bar`（棒グラフ）: カテゴリ間の大小比較を見せる時

**LLMの役割**:
- `web_search`や`calculate_cost_impact`の結果からグラフ用データを抽出
- 適切なグラフタイプを選択
- グラフの解釈と説明文を生成

**使用タイミング**: CHECK 2（市場データ）, CHECK 9（コスト試算）, STEP 1（交渉資料）

---

#### 3.3.5 `generate_document`
**概要**: ビジネス文書生成ツール。テンプレートベースで高品質な文書を生成。

**責務**:
- テンプレートにデータを埋め込んで文書を生成
- テキストファイルとして保存
- 文書内容の作成はLLMが担当

**入力パラメータ**:
```python
{
    "document_type": str,  # "quotation" | "request_letter" | "negotiation_materials" | "agreement" | "cost_breakdown"
    "data": dict,          # 文書に埋め込むデータ
    "tone": str            # "formal" | "friendly" | "assertive" | "urgent"（request_letterのみ有効）
}
```

**データパラメータの例**:
```python
{
    "client_name": "株式会社A",
    "company_name": "自社名",
    "current_price": "10,000円",
    "new_price": "11,000円",
    "increase_rate": "10%",
    "reason": "原材料費の高騰により...",
    "effective_date": "2025年1月1日"
}
```

**出力**: フォーマット済みテキスト（プレビュー付き）
```
✅ 文書を生成しました

**文書タイプ**: 価格改定申入書
**トーン**: friendly
**保存先**: request_letter_価格改定申入書_abc12345.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【プレビュー】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
株式会社A様

いつも大変お世話になっております。
...
```

**対応文書タイプ**:
- `quotation`: コスト費目別見積書
- `request_letter`: 価格交渉申入書（トーン選択可能）
- `negotiation_materials`: 価格改定説明資料
- `agreement`: 合意書
- `cost_breakdown`: 原価内訳書

**トーン設定**（request_letterのみ）:
- `formal`: 正式な文書（初めての申入、大企業相手）
- `friendly`: 協調的な文体（長年の取引先向け）
- `assertive`: 毅然とした文体（理不尽な要求への対応）
- `urgent`: 切実な事情を訴える文体

**LLMの役割**:
- 文書の内容・論理構成を作成
- 適切なトーンを判断
- 法的根拠の引用箇所を指定

**使用タイミング**: CHECK 1, 4, 5, STEP 3, 4, 5など（全ステップで活用）

---

#### 3.3.6 `simulate_negotiation`
**概要**: 交渉ロールプレイ・訓練ツール。4種類のペルソナで模擬交渉を実施。

**責務**:
- 相手役のペルソナに応じた発言を生成
- ユーザーの発言を評価（論理性、協調性、証拠活用）
- スコアリングとフィードバックを提供

**入力パラメータ**:
```python
{
    "scenario": {
        "client_name": str,           # 取引先名
        "negotiation_goal": str,      # 交渉目標（例: "10%値上げ"）
        "user_strengths": list,       # 自社の強み（例: ["高品質", "短納期"]）
        "client_characteristics": str, # 取引先の特徴
        "round": int                  # 現在のラウンド数（省略時は1）
    },
    "opponent_persona": str,  # "aggressive" | "logical" | "collaborative" | "cost_focused"
    "user_response": str      # ユーザーの発言
}
```

**ペルソナ一覧**:
- `aggressive`: 高圧的な購買部長（威圧的、競合を引き合いに出す）
- `logical`: 論理武装した担当者（データや根拠を求める）
- `collaborative`: 協調的な担当者（Win-Winを目指す）
- `cost_focused`: コスト重視の担当者（予算制約を理由に粘る）

**出力**: フォーマット済みテキスト
```
🎭 **交渉シミュレーション - ラウンド 1**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【相手役: 高圧的な購買部長】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

「それでは困りますね。他社さんはもっと安くしてくれますよ。」

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【あなたの発言の評価】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **総合スコア: 75点**

| 評価項目 | スコア |
|----------|--------|
| 論理性 | 80点 |
| 協調性 | 70点 |
| 証拠活用 | 75点 |

**✅ 良かった点:**
- 論理的な説明ができている
- 証拠を効果的に提示

**💡 改善ポイント:**
- もう少し協調的なトーンで伝えると良いでしょう
```

**評価基準**:
- **論理性**: データ、数字、根拠の使用
- **協調性**: 協調的な言葉遣い、相手への配慮
- **証拠活用**: 法的根拠、公的データの引用

**使用タイミング**: CHECK 7（強みの言語化後）, STEP 4（交渉本番前）

---

### 3.4 ツール連携の実例

**ユースケース: 取引先A社への10%値上げ交渉準備**

1. **市場調査フェーズ**
   - LLM → `web_search("企業物価指数 ステンレス 推移")`
   - LLM: 検索結果から価格推移データを抽出・分析
   - LLM → `generate_chart(data, "line", "ステンレス価格指数の推移")`

2. **取引先分析フェーズ**
   - LLM → `web_search("A社 決算短信 2024")`
   - LLM: 財務状況を分析し、Sランク（強気交渉可能）と判定

3. **コスト試算フェーズ**
   - LLM: ユーザーから原価情報をヒアリング
   - LLM → `calculate_cost_impact({原価構造, 価格変動率})`
   - LLM: 試算結果を解釈し、「竹プラン（10%）が妥当」と判断

4. **法的根拠確認フェーズ**
   - LLM → `search_knowledge_base("労務費転嫁 計算式")`
   - LLM: 取得した指針を引用し、計算の正当性を説明

5. **交渉シナリオ作成フェーズ**
   - LLM: 市場データ、取引先情報、コスト試算を統合
   - LLM: 交渉シナリオ・想定問答集を生成

6. **文書生成フェーズ**
   - LLM: 申入書の内容を作成
   - LLM → `generate_document("request_letter", "friendly", {データ})`
   - LLM → `generate_document("quotation", "formal", {内訳データ})`

7. **ロールプレイ訓練フェーズ**
   - LLM → `simulate_negotiation({シナリオ, "cost_focused"})`
   - LLM: フィードバックを提供し、改善点を指導

→ **ユーザーは対話するだけで、完璧な交渉準備パッケージが完成**

---

## 🎨 4. ツールのテンプレート化

### 4.1 ツール定義（Strands SDK）

本システムでは **Strands SDK** の `@tool` デコレータを使用してツールを定義しています。
以下は各ツールの定義例です：

```python
from strands import tool

@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Web検索を実行（Tavily API）- AIが信頼性を動的に判定

    Args:
        query: 検索クエリ
        max_results: 最大検索結果数（デフォルト: 5）

    Returns:
        str: 検索結果のテキスト（AIが信頼できると判定したソースのみ）

【検索対象】
- 市場データ: 企業物価指数、最低賃金、統計データ
- 企業情報: 決算短信、IR情報、パートナーシップ宣言
- 業界ニュース: 値上げ動向、業界レポート

【使用例】
- 「企業物価指数 ステンレス 推移 過去3年」
- 「A社 決算短信 2024」
    """
    # Tavily APIで検索 → AIが信頼性を判定 → フィルタリング
    ...


@tool
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Knowledge Baseから詳細情報を検索します。

    Args:
        query: 検索クエリ
        max_results: 最大検索結果数（デフォルト: 5）

    Returns:
        str: 検索結果のフォーマット済みテキスト

【検索対象】
- 下請法・独占禁止法の条文
- 価格転嫁ガイドライン
- 公正取引委員会の事例
- 原価計算の計算式

【使用例】
- 「買いたたき 判定基準」
- 「労務費転嫁 計算式」
    """
    # AWS Bedrock Knowledge BaseでRAG検索
    ...


@tool
def calculate_cost_impact(
    current_cost_structure: dict,
    price_changes: dict,
    current_sales: float = 0,
    target_profit_margin: float = 0
) -> str:
    """コスト上昇のインパクトを試算し、松竹梅の価格改定案を生成します。

    Args:
        current_cost_structure: 現在の原価構造
            各費目に ratio（比率）と amount（金額）を指定
            例: {
                "material_cost": {"ratio": 0.40, "amount": 1000000},
                "labor_cost": {"ratio": 0.35, "amount": 875000},
                "energy_cost": {"ratio": 0.10, "amount": 250000},
                "overhead": {"ratio": 0.15, "amount": 375000}
            }
        price_changes: 各費目の価格変動率
            例: {
                "material_cost": 0.20,  # +20%
                "labor_cost": 0.05,     # +5%
                "energy_cost": 0.30     # +30%
            }
        current_sales: 現在の売上高（オプション）
        target_profit_margin: 目標利益率（オプション）

    Returns:
        str: 分析結果（コスト上昇額、シナリオ別価格案、推奨アクション）
    """
    # 松竹梅シナリオを計算して返却
    ...


@tool
def generate_chart(
    data: dict,
    chart_type: str,
    title: str,
    x_label: str = "",
    y_label: str = ""
) -> str:
    """データを可視化したグラフ画像を生成します。

    Args:
        data: グラフ用データ
        chart_type: グラフタイプ（"line" または "bar"）
        title: グラフタイトル
        x_label: X軸ラベル（オプション）
        y_label: Y軸ラベル（オプション）

    ## グラフタイプの選び方

    ### line（折れ線グラフ）
    時間の経過に伴う変化・推移を見せる時に使用。
    - data形式: {"time_series": [{"date": "2021", "value": 100}, ...]}

    ### bar（棒グラフ）
    カテゴリ間の大小比較を見せる時に使用。
    - data形式: {"labels": ["製造業", "小売業"], "values": [100, 200]}

    Returns:
        str: 生成結果のメッセージ（Base64画像データを含む特殊フォーマット）
    """
    # Matplotlibでグラフ生成 → Base64エンコードして返却
    ...


@tool
def generate_document(
    document_type: str,
    data: dict,
    tone: str = "formal"
) -> str:
    """ビジネス文書を自動生成します。

    Args:
        document_type: 文書タイプ
            - "quotation": コスト費目別見積書
            - "request_letter": 価格交渉申入書
            - "negotiation_materials": 価格改定説明資料
            - "agreement": 合意書
            - "cost_breakdown": 原価内訳書
        data: 文書に埋め込むデータ（会社名、金額、理由等）
        tone: 文書のトーン（request_letterのみ有効）
            - "formal": 正式な文書
            - "friendly": 協調的な文体
            - "assertive": 毅然とした文体
            - "urgent": 切実な文体

    Returns:
        str: 生成された文書のプレビューと保存先
    """
    # テンプレートにデータを埋め込んで文書生成
    ...


@tool
def simulate_negotiation(
    scenario: dict,
    opponent_persona: str,
    user_response: str
) -> str:
    """交渉のロールプレイを行い、スコアリングとフィードバックを提供します。

    Args:
        scenario: 交渉シナリオ
            - client_name: 取引先名
            - negotiation_goal: 交渉目標（例: "10%値上げ"）
            - user_strengths: 自社の強み（リスト）
            - client_characteristics: 取引先の特徴
            - round: 現在のラウンド数（1から開始、省略時は1）
        opponent_persona: 相手役のペルソナ
            - "aggressive": 高圧的な購買部長
            - "logical": 論理武装した担当者
            - "collaborative": 協調的な担当者
            - "cost_focused": コスト重視の担当者
        user_response: ユーザーの発言（交渉での自分の発言）

    Returns:
        str: 相手の反応、スコア、フィードバック
    """
    # ペルソナ別ロジックで相手役発言を生成、スコアリング
    ...
```

---

### 4.2 System Prompt例

Mode 2 Agentのシステムプロンプト実装例：

```python
MODE2_SYSTEM_PROMPT = """
あなたは価格転嫁交渉の専門家です。中小企業経営者が適正な利益を確保するため、データに基づいた戦略的な交渉支援を提供します。

## あなたの役割

1. **データ収集**: 市場データ、企業情報、法的根拠を収集
2. **分析**: コスト影響を試算し、最適な価格改定案を提案
3. **資料作成**: 交渉に必要な文書・グラフを自動生成
4. **戦略立案**: 交渉シナリオと想定問答集を作成
5. **訓練**: ロールプレイで本番に備える

## 利用可能なツール

### 1. web_search
市場データ、企業情報、業界ニュースを検索します。

**使用すべきタイミング:**
- ユーザーが「原材料の価格推移を調べて」と言った時
- 「取引先の財務状況を知りたい」と言った時
- 「業界の値上げ動向は？」と聞かれた時

**検索クエリの作り方:**
- 具体的に: ❌「原材料 価格」→ ⭕「企業物価指数 ステンレス 推移 過去3年」
- 公的データを優先: 日本銀行、厚労省、経産省、e-Stat
- 企業情報: 「[会社名] 決算短信 [年度]」「[会社名] パートナーシップ構築宣言」

---

### 2. search_knowledge_base
法務知識ベース（下請法、独禁法、ガイドライン）を検索します。

**使用すべきタイミング:**
- 「これって買いたたきですか？」と聞かれた時
- 「値上げの計算式を知りたい」と言われた時
- 「法的根拠を教えて」と求められた時

**重要:** 取得した条文は必ずユーザーの具体的な状況に適用して説明してください。

---

### 3. calculate_cost_impact
コスト上昇のインパクトを試算し、松竹梅の価格改定案を生成します。

**使用すべきタイミング:**
- 「いくら値上げすればいい？」と聞かれた時
- 「赤字にならないラインは？」と聞かれた時

**実行前に必ず確認すること:**
- 現在の原価構造（材料費、労務費、エネルギー費、経費の比率と金額）
- 各費目の上昇率

**ヒアリング例:**
「正確な試算のため、以下を教えてください：
1. 材料費: 月○○万円（売上の○%）
2. 労務費: 月○○万円（売上の○%）
3. エネルギー費: 月○○万円（売上の○%）
4. その他経費: 月○○万円（売上の○%）
5. 各費目の上昇率（分かる範囲で）」

---

### 4. generate_chart
データを可視化したグラフ画像を生成します。

**使用すべきタイミング:**
- `web_search`で取得した価格推移データをグラフ化する時
- `calculate_cost_impact`の結果を可視化する時

**データ抽出の責務:**
あなたが`web_search`の結果から数値データを抽出し、グラフ用のデータ構造に整形してください。

**例:**
```
検索結果「鉄鋼価格は2021年100、2022年115、2023年145」
→ あなたが抽出
→ generate_chart({time_series: [{date: "2021", value: 100}, ...], ...})
```

---

### 5. generate_document
ビジネス文書を自動生成します。

**使用すべきタイミング:**
- 「申入書を作成して」と言われた時
- 「見積書をコスト費目別にして」と言われた時
- 「交渉資料がほしい」と言われた時

**トーンの選び方:**
- **formal**: 初めての正式申入、大企業相手
- **friendly**: 長年の信頼関係がある取引先
- **assertive**: 理不尽な要求に対して毅然と対応
- **urgent**: 経営が危機的状況で切実さを伝える

**重要:** 文書の内容（reason、計算ロジック等）はあなたが作成し、`data`パラメータに渡してください。

---

### 6. simulate_negotiation
交渉のロールプレイを行い、スコアリングとフィードバックを提供します。

**使用すべきタイミング:**
- 「交渉の練習をしたい」と言われた時
- 「本番前にリハーサルしたい」と言われた時

**シナリオ設定:**
まずユーザーに以下を確認してください：
1. 交渉相手の特徴（高圧的、論理的、協調的、コスト重視）
2. 交渉目標（何%の値上げを目指すか）
3. 自社の強み（短納期、高品質、技術力等）

---

## ツール使用の判断基準（フローチャート）

| ユーザー発言 | 実行するツール | 備考 |
|------------|-------------|------|
| 「原材料の価格推移を調べて」 | web_search → generate_chart | まず検索、次にグラフ化 |
| 「取引先の財務状況を知りたい」 | web_search | 決算短信、IR情報を検索 |
| 「いくら値上げすればいい？」 | calculate_cost_impact | **必ず原価情報をヒアリング後に実行** |
| 「これって買いたたき？」 | search_knowledge_base | 法的根拠を提示 |
| 「申入書を作成して」 | generate_document (request_letter) | トーンは関係性から判断 |
| 「見積書をコスト費目別に」 | generate_document (quotation) | 内訳を整理してから生成 |
| 「交渉の練習をしたい」 | simulate_negotiation | ペルソナをユーザーに確認 |
| 「グラフを作って」 | generate_chart | **データはあなたが準備** |

---

## 重要な原則

### 1. ツールを使う前に必要な情報を確認
- ❌ 情報不足のままツールを実行
- ⭕ 必要な情報をヒアリングしてからツールを実行

### 2. ツールの結果は必ず解釈して説明
- ❌ ツールの出力をそのまま返す
- ⭕ 結果を分析し、ユーザーに分かりやすく説明

### 3. 複数ツールを組み合わせて高度な支援を実現
**例: 値上げ交渉パッケージの作成**
1. web_search → 市場データ取得
2. generate_chart → グラフ化
3. calculate_cost_impact → 試算
4. search_knowledge_base → 法的根拠確認
5. generate_document → 申入書・見積書生成

### 4. 証拠ベースの提案
- 全ての主張に出典を明示
- 計算には必ず根拠を付与
- 法的根拠を常に参照

### 5. ユーザーに寄り添う
- 経営者の不安や孤独感に共感
- 専門用語は分かりやすく説明
- 実行可能な具体的アドバイスを提供

---

## 参考: 14ステップ（CHECK 1-9, STEP 1-5）

以下のステップは参考ガイドラインです。ユーザーは自由にツールを使用でき、順番に従う必要はありません。

**CHECK 1-9（準備編）:**
1. 取引条件の可視化
2. 原材料費・労務費データの証拠化 → web_search, generate_chart
3. 原価計算の実施 → calculate_cost_impact
4. 単価表の作成
5. 見積書フォーマットの刷新 → generate_document
6. 取引先の経営分析 → web_search
7. 自社の強みの言語化
8. 法令違反リスクのチェック → search_knowledge_base
9. 必達目標額の決定 → calculate_cost_impact（最重要）

**STEP 1-5（実践編）:**
1. 外堀を埋める → web_search（業界動向）
2. ターゲット選定 → web_search（取引先分析）
3. 交渉の申し入れ → generate_document
4. 交渉本番 → simulate_negotiation（訓練）
5. アフターフォロー → generate_document

---

これで準備完了です。ユーザーの対話に応じて、適切なツールを選択・実行してください。
"""
```

---

### 4.3 実装イメージ

```python
class Mode2Agent:
    def __init__(self):
        self.llm = AnthropicClient(model="claude-4.5-haiku")
        self.tools = TOOLS_DEFINITION
        self.system_prompt = MODE2_SYSTEM_PROMPT

    async def execute(self, user_input: str, session: Session) -> Response:
        # LLMがFunction Callingでツールを直接呼び出し
        response = await self.llm.chat(
            messages=session.history + [{"role": "user", "content": user_input}],
            tools=self.tools,
            system=self.system_prompt
        )

        # ツール呼び出しがあれば実行
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = await self._execute_tool(tool_call, session)
                session.generated_files.append(result.file_info)
                # ツール結果を会話履歴に追加
                session.history.append({
                    "role": "tool",
                    "content": json.dumps(result.data)
                })

        return Response(response.message, attachments=response.files)

    async def _execute_tool(self, tool_call, session):
        tool_name = tool_call.name
        arguments = tool_call.arguments

        if tool_name == "web_search":
            return await web_search(**arguments)
        elif tool_name == "search_knowledge_base":
            return await search_knowledge_base(**arguments)
        elif tool_name == "calculate_cost_impact":
            return await calculate_cost_impact(**arguments)
        elif tool_name == "generate_chart":
            return await generate_chart(**arguments, session_id=session.session_id)
        elif tool_name == "generate_document":
            return await generate_document(**arguments, session_id=session.session_id)
        elif tool_name == "simulate_negotiation":
            return await simulate_negotiation(**arguments, session=session)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
```

---

## 🔄 5. 実行フロー

### 5.1 リクエスト処理の全体フロー

```
1. ユーザーがメッセージ送信
    ↓
2. Orchestrator Agentがリクエストを受信
    ↓
3. Orchestrator: モード判定を実行
    - キーワードマッチング: 「値上げ」「価格転嫁」「コスト増」等を検知
    - 文脈分析（LLM推論）: キーワードがない場合のみ実行
    - 出力: "mode1" or "mode2"
    ↓
4. Orchestrator: モード切り替え判定
    - IF 現在のモード ≠ 判定結果:
        → ユーザー承諾を取得
        → セッションのモードを更新
    ↓
5. Orchestrator: 適切な子エージェントへ委譲
    - Mode 1 Agent へ → または
    - Mode 2 Agent へ →
    ↓
6a. Mode 1 Agent（よろず相談）          6b. Mode 2 Agent（価格転嫁専門）
    - 傾聴・アドバイス                      - ステップ判定を実行
    - Web検索で情報収集                     - 会話履歴から現在のステップを特定
    - LLMで応答生成                         - ツール自動選択
    - レスポンス返却                        - 該当ツールを実行
                                            - 進捗データを更新
                                            - レスポンス返却
    ↓
7. ユーザーに応答を返却
    ↓
8. セッション状態を保存（会話履歴、モード、進捗等）
```

### 5.2 モード判定の詳細

#### Orchestrator Agentのモード判定ロジック

```python
async def _detect_mode(self, user_input: str, session: Session) -> str:
    # ステップ1: キーワードベース判定（高速）
    keywords_mode2 = [
        "値上げ", "価格転嫁", "コスト増", "買いたたき", "下請法",
        "原材料高騰", "人件費アップ", "赤字受注", "取引条件", "見積もり"
    ]
    if any(kw in user_input for kw in keywords_mode2):
        return "mode2"

    # ステップ2: 文脈分析（LLM推論、キーワードがない場合のみ）
    prompt = f"""
    ユーザー発言: {user_input}
    会話履歴: {session.history[-5:]}  # 直近5件

    この発言が「価格転嫁・値上げ交渉」に関連する内容か判定せよ。
    関連する場合は1、関連しない場合は0を出力。
    """
    result = await self.llm.classify(prompt)
    confidence = float(result)

    return "mode2" if confidence > 0.7 else "mode1"
```

### 5.3 ツール直接呼び出しの詳細（Mode 2 Agent内）

#### Mode 2 Agentのツール呼び出し方式

Strands SDKを使用し、`@tool`デコレータで定義されたツールをLLMが直接呼び出す。ステップ判定は行わず、会話内容からLLMが最適なツールを判断する。

```python
from strands import tool

# 6つの専門ツール（@toolデコレータで定義）
@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Web検索を実行（Tavily API）- AIが信頼性を動的に判定"""
    ...

@tool
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Knowledge Baseから詳細情報を検索"""
    ...

@tool
def calculate_cost_impact(current_cost_structure: dict, price_changes: dict, ...) -> str:
    """コスト上昇のインパクトを試算し、松竹梅の価格改定案を生成"""
    ...

@tool
def generate_chart(data: dict, chart_type: str, title: str, ...) -> str:
    """データを可視化したグラフ画像を生成（Base64形式）"""
    ...

@tool
def generate_document(document_type: str, data: dict, tone: str = "formal") -> str:
    """ビジネス文書を自動生成"""
    ...

@tool
def simulate_negotiation(scenario: dict, opponent_persona: str, user_response: str) -> str:
    """交渉のロールプレイを行い、スコアリングとフィードバックを提供"""
    ...

# ツールリストをエージェントに渡す
tools = [
    web_search,
    search_knowledge_base,
    calculate_cost_impact,
    generate_chart,
    generate_document,
    simulate_negotiation,
]
```

### 5.4 ユーザー体験フロー例

#### シナリオ: 取引先の財務状況を調べたい

```
1. ユーザー: 「取引先A社の財務状況を知りたいです」
    ↓
2. Orchestrator: モード判定
    - キーワード検知: 「取引先」（mode2のコンテキスト）
    - 会話履歴から価格転嫁の文脈を確認
    - 判定: mode2
    ↓
3. Orchestrator: Mode 2 Agentへ委譲
    ↓
4. Mode 2 Agent: LLMがツールを直接判断
    - ユーザー発言: 「取引先の財務状況」
    - LLM判断: web_searchツールが適切
    ↓
5. web_searchツール実行（Strands SDK）:
    - Tavily APIでA社の決算短信を検索
    - AI信頼性判定でフィルタリング
    - IR情報、パートナーシップ構築宣言を取得
    - LLMが財務分析: 増収増益、内部留保潤沢
    - LLMがランク判定: S（最優先）
    ↓
6. Mode 2 Agent: 結果をセッションに保存
    ↓
7. AI応答:
   「A社の財務状況を分析しました。

   【財務状況】
   - 売上高: 前年比+15% (増収)
   - 営業利益: 前年比+22% (増益)
   - 内部留保: 潤沢（自己資本比率 65%）

   【パートナーシップ構築宣言】
   2023年に宣言済み。「サプライヤーとの共存共栄」を明記。

   【総合評価】
   Sランク（最優先ターゲット）

   A社は支払い能力が十分にあり、かつ政府の価格転嫁推進方針に賛同しています。
   強気の交渉が可能です。他に調べたいことはありますか？」
    ↓
8. ユーザーはツール名を意識せず、対話を続けるだけで適切な支援を受けられる
```

---

## 🌐 6. 外部連携 & データレイヤー

### 6.1 Web Search API（Tavily）

#### 用途
全ての外部データ取得に使用。Mode 1でも標準搭載。

#### 技術構成
- **API**: Tavily API（advanced検索モード）
- **AI信頼性判定**: AWS Bedrock (Claude Haiku) で各検索結果の信頼性を動的に判定
- **フィルタリング**: 信頼できる情報源のみを返却

#### 検索対象
- **市場データ**: 企業物価指数、最低賃金、e-Stat（政府統計）
- **企業情報**: 決算短信、パートナーシップ構築宣言、IR情報
- **ニュース**: 業界動向、値上げニュース、経営者インタビュー
- **統計データ**: 厚労省賃金統計、経産省エネルギー価格統計

#### 使用ツール
- `web_search`: 市場データ、企業情報、業界ニュースの統合検索

---

### 6.2 RAG Service (AWS Bedrock Knowledge Base)

#### 技術構成
- **サービス**: AWS Bedrock Knowledge Base
- **ストレージ**: S3（ドキュメント格納）
- **検索方式**: セマンティック検索（SEMANTIC）
- **検索精度**: Top-K検索（関連度上位K件を取得）

#### 登録データ
- 下請代金支払遅延等防止法（下請法）全文
- 独占禁止法 関連条文
- 価格転嫁円滑化施策ハンドブック（中小企業庁）
- 労務費の適切な転嫁のための価格交渉に関する指針
- パートナーシップ構築宣言 制度概要
- 公正取引委員会 勧告事例集
- 下請取引適正化推進講習会 資料
- 原価計算の基礎（業種別モデル）

#### 使用ツール
- `search_knowledge_base`: 法務知識検索、違法性判定、計算式参照

---

### 6.3 S3 Storage

#### 用途
セッション単位で生成物を一時保存。

#### 保存データ
- 生成されたグラフ画像（PNG/SVG）
- 生成された文書（PDF/Word/Excel）
- 会話履歴（セッション終了後24時間で自動削除）
- ユーザーアップロードファイル（見積書、契約書等）

#### 使用ツール
- `generate_document`: 文書出力先
- `generate_chart`: グラフ保存先

---

### 6.4 セッション管理（詳細は2.4節を参照）

#### セッション構造
```python
class Session:
    session_id: str           # セッション識別子
    user_id: str              # ユーザー識別子
    mode: str                 # 現在のモード ("mode1" or "mode2")
    history: List[Message]    # 会話履歴
    generated_files: List[Dict]  # 生成されたファイル（グラフ、文書等）
    user_attributes: Dict     # 業種、企業規模、主要取引先等
    created_at: datetime
    updated_at: datetime
```

#### 会話履歴の保持
- **短期メモリ**: LLMのコンテキストウィンドウで直近の会話を保持
- **構造化データ**: 原価情報、取引先リスト等をJSON形式でプロンプトに埋め込み
- **自動要約**: セッションが長くなった場合、LLMが自動で要約を生成してコンテキストを圧縮

#### メモリ継続性
- **Orchestratorを毎回通過**: 全リクエストがOrchestratorを経由するため、セッション状態を常に更新
- **会話履歴の永続化**: 会話履歴は全モード共通で保持され、Mode 1に切り替わっても消えない
- **モード切り替え後の復元**: Mode 2に戻った際、以前の会話コンテキストから継続可能

#### 実装パターン（段階的アプローチ）
1. **プロトタイプ段階**: LLMコンテキストのみで会話履歴を保持
2. **初期リリース**: In-Memoryストア（Python辞書 `SESSIONS = {}`）でセッション管理
3. **本番運用**: Redis / DynamoDB等の永続ストアに移行

---

## 💻 7. 技術スタック

### 7.1 フロントエンド
- **フレームワーク**: React
- **UI**: チャットインターフェース
- **状態管理**: React Hooks
- **通信**: REST API / WebSocket（リアルタイム対話）

### 7.2 バックエンド

#### LLM
- **モデル**: Claude 4.5 Haiku（AWS Bedrock経由、全モード共通）
- **プロンプト戦略**: モード別・ステップ別に動的にプロンプトを構築

#### 言語・フレームワーク
- **言語**: Python 3.11+
- **エージェントフレームワーク**: Strands SDK（AWS製、@toolデコレータでツール定義）
- **Webフレームワーク**: FastAPI（非同期処理対応）

#### 主要ライブラリ
- **Web検索**: Tavily API（AI信頼性判定付き）
- **可視化**: Matplotlib
- **文書生成**: テンプレートエンジン, ReportLab (PDF)
- **RAG**: AWS Bedrock Knowledge Base
- **LLM連携**: AWS Bedrock (boto3)

### 7.3 インフラ
- **クラウド**: AWS
- **LLMサービス**: AWS Bedrock（Claude 4.5 Haiku）
- **知識ベース**: AWS Bedrock Knowledge Base（S3 + セマンティック検索）
- **ストレージ**: S3（文書・グラフ保存）
- **コンピュート**: ECS / Lambda（サーバーレス）
- **API Gateway**: AWS API Gateway

### 7.4 データフロー（3層エージェント・アーキテクチャ）

```
ユーザー入力
    ↓
[React UI] → REST API
    ↓
[FastAPI Backend + Strands SDK]
    ↓
┌─────────────────────────────────────────┐
│ Orchestrator Agent (親エージェント)      │
│ - 全リクエストの受け口                   │
│ - モード判定（キーワード + LLM推論）     │
│ - モード切り替え処理                     │
│ - セッション状態更新                     │
│ - LLM: Claude 4.5 Haiku (Bedrock)       │
└─────────────────────────────────────────┘
    ↓（毎回判定）
┌─────────────────────────────────────────┐
│ 適切な子エージェントへ振り分け           │
└─────────────────────────────────────────┘
    ↓
┌──────────────────────┬──────────────────────┐
│ Mode 1 Agent         │ Mode 2 Agent         │
│ (よろず相談)          │ (価格転嫁専門)        │
│                      │                      │
│ - 傾聴・アドバイス    │ - ツール直接呼出     │
│ - Web検索           │ - @tool デコレータ    │
│ - LLM応答生成       │ - 成果物管理         │
│ - Haiku (Bedrock)   │ - Haiku (Bedrock)    │
└──────────────────────┴──────────────────────┘
    ↓                        ↓
[Tavily API]            ┌─────────────────────┐
                         │ 6つの専門ツール      │
                        │ - web_search        │
                        │ - search_knowledge_ │
                        │   base              │
                        │ - calculate_cost_   │
                        │   impact            │
                        │ - generate_chart    │
                        │ - generate_document │
                        │ - simulate_         │
                        │   negotiation       │
                         └─────────────────────┘
                                ↓
                         [外部連携]
                        - Tavily API (Web検索)
                        - Bedrock KB (RAG)
                        - S3 (ファイル保存)
    ↓
[セッション永続化]
- In-Memory / Redis / DynamoDB
- 会話履歴、モード、進捗データ
    ↓
[FastAPI Backend] → 結果返却
    ↓
[React UI] → ユーザーに表示
```

---