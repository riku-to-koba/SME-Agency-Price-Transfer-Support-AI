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
    │  - Web検索標準   │  - ステップ判定   │
    │  - 傾聴・相談    │  - 進捗管理       │
    │  - ステートレス  │  - ステートフル   │
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
3. **ステートフルな進捗管理**: Mode 2 Agentは会話履歴と進捗状態を保持し、セッション継続を実現
4. **ステップ自動判定**: Mode 2 Agentが会話内容から現在のステップ(CHECK 1-9 / STEP 1-5)を自動判定
5. **ツール自動選択・実行**: 判定されたステップに応じて、最適な専門ツールを自動選択・起動
6. **シームレスな実行**: ユーザーは対話を続けるだけで、裏側でツールが連携動作

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
価格交渉に特化した専門家エージェント。14ステップのプレイブックに沿って徹底サポート。

#### 責務
- **ステップ判定**: 会話履歴全体から現在のステップ（CHECK 1-9 / STEP 1-5）を自動判定
- **進捗管理**: 完了したステップをセッションに記録し、継続的な支援を実現
- **ツール自動選択**: 判定したステップに応じて、最適なツール（6つの専門ツール）を自動選択・実行
- **依存関係チェック**: ステップ間の前提条件を考慮（例: CHECK 9にはCHECK 3が必要）
- **成果物管理**: 生成されたグラフ、文書、試算表などをセッションに紐付けて保存

#### ステップ判定方式
- **入力情報**:
  - 会話履歴全体（LLMコンテキスト）
  - 直近のユーザー発言
  - ユーザー属性データ（業種、企業規模等）
  - これまでに実行したツールの履歴
- **判定ロジック**:
  - LLMに対して「現在のステップを特定せよ」という推論タスクを実行
  - 14ステップ（CHECK 1-9, STEP 1-5）のいずれかを出力
  - 複数ステップが該当する場合は優先度を判定
- **出力**: ステップID（例: `CHECK_3`, `STEP_4`）

#### 進捗管理構造
```python
session.mode2_progress = {
    "completed_steps": ["CHECK_2", "CHECK_3"],
    "current_step": "CHECK_6",
    "data": {
        "CHECK_2": {
            "graph_url": "s3://bucket/session123/market_graph.png",
            "increase_rate": 35
        },
        "CHECK_3": {
            "cost_breakdown": {...},
            "excel_url": "s3://bucket/session123/cost_analysis.xlsx"
        }
    }
}
```

#### 技術構成
- **LLM**: Claude 4.5 Haiku
- **プロンプト戦略**: ステップ特化型プロンプトを動的にロード
- **専門ツール**: 6つの高度なツール（後述）
- **外部API**: Web Search API, RAG Service, S3 Storage
- **メモリ管理**:
  - 会話履歴をLLMコンテキストで保持
  - 構造化データ（原価情報、取引先リスト等）をJSON形式でプロンプトに埋め込み
  - セッションが長くなった場合は自動要約でコンテキスト圧縮

#### 特性
- **ステートフル（状態を保持）**: 進捗データをセッションに保存し、モード切り替え後も復元可能
- **体系的な支援**: 14ステップのプレイブックに沿った段階的サポート
- **証拠ベース**: 全ての提案に出典・根拠を明示

#### 実装イメージ
```python
class Mode2Agent:
    async def execute(self, user_input: str, session: Session) -> Response:
        # ステップ判定
        step = await self._detect_step(user_input, session)

        # ツール実行
        result = await self._execute_tool_for_step(step, user_input, session)

        # 進捗更新
        session.mode2_progress["current_step"] = step
        if self._is_step_completed(result):
            session.mode2_progress["completed_steps"].append(step)
            session.mode2_progress["data"][step] = result.data

        return Response(result.message, attachments=result.files)

    async def _detect_step(self, user_input: str, session: Session) -> str:
        prompt = f"""
        会話履歴: {session.history}
        ユーザー発言: {user_input}
        完了済みステップ: {session.mode2_progress["completed_steps"]}

        現在のステップをCHECK_1〜CHECK_9, STEP_1〜STEP_5の中から選択せよ。
        """
        return await self.llm.infer(prompt)
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
    mode2_progress: Dict  # Mode 2の進捗データ
    user_attributes: Dict  # 業種、企業規模等
    created_at: datetime
    updated_at: datetime
```

#### メモリ継続性の実現
- **Orchestratorを毎回通過**: 全リクエストがOrchestratorを経由するため、セッション状態を常に更新
- **Mode 2進捗の永続化**: `mode2_progress`はセッションに保存され、Mode 1に切り替わっても保持
- **モード切り替え後の復元**: Mode 2に戻った際、以前の進捗状態から継続可能

#### 実装パターン（段階的アプローチ）
1. **プロトタイプ段階**: LLMコンテキストのみで会話履歴を保持
2. **初期リリース**: In-Memoryストア（Python辞書 `SESSIONS = {}`）でセッション管理
3. **本番運用**: Redis / DynamoDB等の永続ストアに移行

---

## 🛠️ 3. 6つの専門ツール（Mode 2専用）

### 3.1 ツール一覧と役割

| ツール名 | 役割 | 使用タイミング | 主要技術 |
|---------|------|--------------|---------|
| `market_analysis` | 市場データ分析・グラフ生成 | CHECK 2, STEP 1 | Web Search API, Pandas, Matplotlib |
| `company_research` | 取引先調査・財務分析 | CHECK 6, STEP 2 | Web Search API, LLM (情報抽出) |
| `analyze_cost_impact` | コスト試算・松竹梅プラン生成 | CHECK 3, CHECK 9 | NumPy, Pandas, RAG, Excel出力 |
| `scenario_generator` | 交渉シナリオ作成・ロールプレイ | CHECK 7, STEP 4 | LLM (Multi-Agent), RP評価エンジン |
| `document_generator` | 文書自動生成 | 全ステップ | Jinja2, python-docx, openpyxl, PDF生成 |
| `search_knowledge_base` | 法務知識検索 | CHECK 8, 随時 | RAG (S3 + Vector Search), LLM |

### 3.2 ツール連携の実例

**CHECK 9（最終試算）での自動連携フロー:**
1. `market_analysis` → 原材料費の上昇率データ取得（例: +20%）
2. `analyze_cost_impact` → 上昇率を元にコスト試算・松竹梅プラン生成
3. `search_knowledge_base` → 計算式の法的根拠を確認（労務費転嫁指針）
4. `document_generator` → 試算表をExcelで出力、グラフを資料に統合
5. `scenario_generator` → 試算結果を元に交渉シナリオ作成
6. `company_research` → 相手の支払い能力を確認（増収増益なら強気交渉）

→ これら全てが自動的に連携し、ユーザーは対話するだけで完璧な交渉準備が整う。

---

## 🔄 4. 実行フロー

### 4.1 リクエスト処理の全体フロー

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

### 4.2 モード判定の詳細

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

### 4.3 ステップ判定の詳細（Mode 2 Agent内）

#### Mode 2 Agentのステップ判定ロジック

```python
async def _detect_step(self, user_input: str, session: Session) -> str:
    prompt = f"""
    あなたは価格転嫁支援エージェントです。以下の情報から、ユーザーが現在取り組んでいるステップを特定してください。

    【会話履歴】
    {session.history}

    【ユーザーの最新発言】
    {user_input}

    【完了済みステップ】
    {session.mode2_progress["completed_steps"]}

    【ステップ一覧】
    準備編:
    - CHECK_1: 取引条件・業務内容の確認
    - CHECK_2: データの証拠化
    - CHECK_3: 精緻な原価計算
    - CHECK_4: 戦略的単価表の作成
    - CHECK_5: 見積書フォーマット刷新
    - CHECK_6: 取引先の経営分析
    - CHECK_7: 代替不可能性の言語化
    - CHECK_8: 法令違反リスクチェック
    - CHECK_9: 必達目標額の決定

    実践編:
    - STEP_1: 外堀を埋める
    - STEP_2: ターゲット選定
    - STEP_3: 交渉の申し入れ
    - STEP_4: 交渉本番
    - STEP_5: アフターフォロー

    現在のステップを上記から1つ選んで、そのIDのみを出力してください（例: CHECK_3）。
    """

    step_id = await self.llm.infer(prompt)
    return step_id.strip()
```

#### ツール自動選択

```python
STEP_TOOL_MAPPING = {
    "CHECK_1": ["document_generator"],
    "CHECK_2": ["market_analysis"],
    "CHECK_3": ["analyze_cost_impact", "search_knowledge_base"],
    "CHECK_4": ["document_generator"],
    "CHECK_5": ["document_generator"],
    "CHECK_6": ["company_research"],
    "CHECK_7": ["scenario_generator"],
    "CHECK_8": ["search_knowledge_base"],
    "CHECK_9": ["analyze_cost_impact"],
    "STEP_1": ["market_analysis"],
    "STEP_2": ["company_research"],
    "STEP_3": ["document_generator"],
    "STEP_4": ["scenario_generator", "document_generator"],
    "STEP_5": ["document_generator"],
}

async def _execute_tool_for_step(self, step: str, user_input: str, session: Session):
    tools = STEP_TOOL_MAPPING.get(step, [])
    results = []
    for tool_name in tools:
        tool = self.tools[tool_name]
        result = await tool.execute(user_input, session)
        results.append(result)
    return results
```

### 4.4 ユーザー体験フロー例

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
4. Mode 2 Agent: ステップ判定
    - 会話履歴: すでにCHECK 1-3が完了
    - ユーザー発言: 「取引先の財務状況」→ CHECK 6
    - 判定: CHECK_6
    ↓
5. Mode 2 Agent: ツール自動選択
    - CHECK_6 → company_research
    ↓
6. company_researchツール実行:
    - Web Search APIでA社の決算短信を検索
    - IR情報、パートナーシップ構築宣言を取得
    - 財務分析: 増収増益、内部留保潤沢
    - ランク判定: S（最優先）
    ↓
7. Mode 2 Agent: 進捗更新
    - session.mode2_progress["current_step"] = "CHECK_6"
    - session.mode2_progress["completed_steps"].append("CHECK_6")
    - session.mode2_progress["data"]["CHECK_6"] = {...}
    ↓
8. AI応答:
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
   強気の交渉が可能です。次は必達目標額の決定（CHECK 9）に進みますか？」
    ↓
9. ユーザーはツール名を意識せず、対話を続けるだけで適切な支援を受けられる
```

---

## 🌐 5. 外部連携 & データレイヤー

### 5.1 Web Search API

#### 用途
全ての外部データ取得に使用。Mode 1でも標準搭載。

#### 検索対象
- **市場データ**: 企業物価指数、最低賃金、e-Stat（政府統計）
- **企業情報**: 決算短信、パートナーシップ構築宣言、IR情報
- **ニュース**: 業界動向、値上げニュース、経営者インタビュー
- **統計データ**: 厚労省賃金統計、経産省エネルギー価格統計

#### 使用ツール
- `market_analysis`: 市場データ、統計データ検索
- `company_research`: 企業情報、ニュース検索

---

### 5.2 RAG Service (Knowledge Base)

#### 技術構成
- **ストレージ**: S3
- **検索方式**: Vector Search（セマンティック検索）+ キーワード検索（ハイブリッド）
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
- `search_knowledge_base`: 法務知識検索、違法性判定
- `analyze_cost_impact`: 計算式参照（原価計算モデル）

---

### 5.3 S3 Storage

#### 用途
セッション単位で生成物を一時保存。

#### 保存データ
- 生成されたグラフ画像（PNG/SVG）
- 生成された文書（PDF/Word/Excel）
- 会話履歴（セッション終了後24時間で自動削除）
- ユーザーアップロードファイル（見積書、契約書等）

#### 使用ツール
- `document_generator`: 文書出力先
- `market_analysis`: グラフ保存先

---

### 5.4 セッション管理（詳細は2.4節を参照）

#### セッション構造
```python
class Session:
    session_id: str           # セッション識別子
    user_id: str              # ユーザー識別子
    mode: str                 # 現在のモード ("mode1" or "mode2")
    history: List[Message]    # 会話履歴
    mode2_progress: Dict      # Mode 2の進捗データ（完了ステップ、成果物等）
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
- **Mode 2進捗の永続化**: `mode2_progress`はセッションに保存され、Mode 1に切り替わっても保持
- **モード切り替え後の復元**: Mode 2に戻った際、以前の進捗状態から継続可能

#### 実装パターン（段階的アプローチ）
1. **プロトタイプ段階**: LLMコンテキストのみで会話履歴を保持
2. **初期リリース**: In-Memoryストア（Python辞書 `SESSIONS = {}`）でセッション管理
3. **本番運用**: Redis / DynamoDB等の永続ストアに移行

---

## 💻 6. 技術スタック

### 6.1 フロントエンド
- **フレームワーク**: React
- **UI**: チャットインターフェース
- **状態管理**: React Hooks
- **通信**: REST API / WebSocket（リアルタイム対話）

### 6.2 バックエンド

#### LLM
- **モデル**: Claude 4.5 Haiku（全モード共通）
- **プロンプト戦略**: モード別・ステップ別に動的にプロンプトを構築

#### 言語・フレームワーク
- **言語**: Python 3.11+
- **フレームワーク**: FastAPI（非同期処理対応）

#### 主要ライブラリ
- **Web検索**: Web Search API SDK
- **データ分析**: Pandas, NumPy
- **可視化**: Matplotlib, Seaborn
- **文書生成**: Jinja2, python-docx, openpyxl, ReportLab (PDF)
- **RAG**: LangChain, FAISS / Pinecone (Vector Search)
- **LLM連携**: Anthropic SDK

### 6.3 インフラ
- **クラウド**: AWS
- **ストレージ**: S3
- **知識ベース**: S3 + Vector Search (FAISS / Pinecone)
- **コンピュート**: ECS / Lambda（サーバーレス）
- **API Gateway**: AWS API Gateway
- **認証**: AWS Cognito

### 6.4 データフロー（3層エージェント・アーキテクチャ）

```
ユーザー入力
    ↓
[React UI] → REST API
    ↓
[FastAPI Backend]
    ↓
┌─────────────────────────────────────────┐
│ Orchestrator Agent (親エージェント)      │
│ - 全リクエストの受け口                   │
│ - モード判定（キーワード + LLM推論）     │
│ - モード切り替え処理                     │
│ - セッション状態更新                     │
│ - LLM: Claude 4.5 Haiku                 │
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
│ - 傾聴・アドバイス    │ - ステップ判定       │
│ - Web検索           │ - ツール自動選択      │
│ - LLM応答生成       │ - 進捗管理           │
│ - Haiku             │ - Haiku              │
└──────────────────────┴──────────────────────┘
    ↓                        ↓
[Web Search API]         ┌─────────────────────┐
                         │ 6つの専門ツール      │
                         │ - market_analysis   │
                         │ - company_research  │
                         │ - analyze_cost_...  │
                         │ - scenario_gen...   │
                         │ - document_gen...   │
                         │ - search_knowl...   │
                         └─────────────────────┘
                                ↓
                         [外部連携]
                         - Web Search API
                         - RAG Service
                         - S3 Storage
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

## 🔐 7. セキュリティ設計

### 7.1 データ保護
- **会話履歴の自動削除**: セッション終了後24時間で自動削除
- **個人情報の匿名化**: 企業名、担当者名等を匿名化してRAGに保存
- **アクセス制御**: AWS IAMで厳格なアクセス権限管理

### 7.2 API保護
- **認証**: JWTトークンベース認証
- **レート制限**: API Gateway でリクエスト数制限
- **HTTPS通信**: 全ての通信をTLS 1.3で暗号化

### 7.3 コンプライアンス
- **下請法遵守**: 法的判断は必ず「専門家への相談を推奨」を併記
- **個人情報保護**: GDPR/個人情報保護法に準拠
- **データ保持ポリシー**: 最低限の期間のみ保持

---

## 📊 8. スケーラビリティ設計

### 8.1 水平スケーリング
- **コンピュート**: ECS Auto Scalingでトラフィックに応じて自動スケール
- **データベース**: DynamoDB（フルマネージド NoSQL）でスケーラブルなセッション管理
- **ストレージ**: S3は無制限スケール

### 8.2 パフォーマンス最適化
- **キャッシング**:
  - Web検索結果を15分間キャッシュ（同一クエリの重複検索を回避）
  - RAG検索結果をRedisでキャッシュ
- **非同期処理**:
  - 重いツール（market_analysis, company_research）は非同期実行
  - ユーザーには「分析中...」のストリーミング表示
- **バッチ処理**:
  - 複数ツールの並列実行（例: CHECK 9で6つのツールを並列起動）

---

## 🧪 9. テスト戦略

### 9.1 単体テスト
- **対象**: 各ツールの機能単位（pytest使用）
- **カバレッジ目標**: 80%以上

### 9.2 統合テスト
- **対象**: ツール連携フロー（例: CHECK 9の6ツール連携）
- **シナリオテスト**: 14ステップ全てをシミュレーション

### 9.3 E2Eテスト
- **対象**: ユーザーフロー全体（Mode 1 → Mode 2 → 交渉成功）
- **ツール**: Playwright（ブラウザ自動化）

### 9.4 LLM品質テスト
- **プロンプトテスト**: 各ステップのプロンプトが意図通りに動作するか検証
- **評価指標**: 正答率、適切なツール選択率、ユーザー満足度

---

## 🚀 10. デプロイメント戦略

### 10.1 CI/CD
- **ツール**: GitHub Actions
- **フロー**:
  1. コミット → 自動テスト実行
  2. テスト成功 → Dockerイメージビルド
  3. ECRにプッシュ
  4. ECSにデプロイ（Blue-Green Deployment）

### 10.2 環境分離
- **開発環境 (Dev)**: 開発者用、自由にテスト可能
- **ステージング環境 (Staging)**: 本番同等の環境でQA
- **本番環境 (Production)**: エンドユーザー向け、高可用性・高信頼性

### 10.3 監視・ログ
- **監視**: AWS CloudWatch でメトリクス監視
- **ログ**: CloudWatch Logs で集約管理
- **アラート**: エラー率・レスポンス時間の異常を検知して通知

---

## 📈 11. KPI & モニタリング

### 11.1 ビジネスKPI
- **モード移行率**: Mode 1からMode 2への移行率（目標: 30%以上）
- **ステップ完了率**: CHECK 1-9を完了したユーザーの割合（目標: 70%以上）
- **交渉成功報告率**: STEP 4（交渉本番）後の成功報告率（目標: 60%以上）
- **ツール利用率**: 各専門ツールの起動回数・利用率
- **ユーザー満足度**: NPS（Net Promoter Score）（目標: 50以上）

### 11.2 技術KPI
- **レスポンス時間**: API応答時間（目標: p95 < 2秒）
- **ツール実行時間**: 各ツールの実行時間（目標: p95 < 5秒）
- **エラー率**: API・ツールのエラー率（目標: < 0.1%）
- **可用性**: システム稼働率（目標: 99.9%以上）

### 11.3 コスト管理
- **LLM API費用**: Claudeトークン使用量の監視
- **Web Search API費用**: 検索クエリ数の監視
- **インフラ費用**: AWS各サービスの利用料監視

---

## 🔮 12. 今後の拡張可能性

### 12.1 新モードの追加
- **Mode 3: 資金繰り支援モード**: キャッシュフロー改善、融資支援
- **Mode 4: 人材採用支援モード**: 求人票作成、面接サポート
- **Mode 5: 販路拡大支援モード**: マーケティング戦略、営業支援

### 12.2 機能拡張
- **多言語対応の強化**: 中国語、英語での完全サポート
- **業種特化モデル**: 製造業、建設業、IT業界等の専門版
- **音声対応**: 音声入力・音声出力でハンズフリー対話
- **モバイルアプリ**: iOS/Android ネイティブアプリ開発

### 12.3 AI機能の高度化
- **マルチモーダル対応**: 画像（見積書、契約書）の読み取り・分析
- **予測分析**: 過去データから交渉成功率を予測
- **パーソナライゼーション**: ユーザーごとに最適化された支援

---

## 📝 13. 補足事項

### 設計思想
- **ユーザーファースト**: 専門知識不要で、対話だけで最適な支援を提供
- **証拠ベース**: 全ての提案に出典・根拠を明示し、信頼性を担保
- **実行支援**: 「参考になった」で終わらせず、即座に使える成果物を出力

### 技術選定の理由
- **Claude 4.5 Haiku**: 高速・低コストで、複雑な推論タスクに対応
- **React**: モダンなUI開発で、拡張性・保守性が高い
- **FastAPI**: 非同期処理に強く、高パフォーマンスなAPI開発が可能
- **AWS**: スケーラビリティ・可用性・セキュリティに優れたクラウド基盤

### 関連ドキュメント
- **要件定義書**: [REQUIREMENTS.md](./REQUIREMENTS.md)
- **システムマップ**: [system-map.html](./system-map.html)

---

**最終更新日**: 2025-11-25
