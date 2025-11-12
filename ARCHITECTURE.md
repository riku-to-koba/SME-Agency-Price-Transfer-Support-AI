# システムアーキテクチャ図

## 全体フロー

```mermaid
graph TB
    User[ユーザー<br/>中小企業担当者] -->|質問入力| UI[Streamlit UI<br/>app.py]
    UI -->|質問を送信| Agent[PriceTransferAgent<br/>agent/core.py]

    Agent -->|質問分析| Detect{ステップ判定<br/>必要に応じてヒアリング}
    Detect -->|判定結果| Update[セッション状態更新<br/>current_step設定]
    Update -->|プロンプト再構成| Reload[エージェント再初期化<br/>ステップ別プロンプト追加]

    Reload --> Tools[ツール実行]

    Tools --> KB[search_knowledge_base<br/>ナレッジベース検索]
    Tools --> Web[web_search<br/>Web検索]
    Tools --> Calc[calculator<br/>計算]
    Tools --> Diagram[generate_diagram<br/>図生成]

    KB --> Response[回答生成]
    Web --> Response
    Calc --> Response
    Diagram --> Response

    Response -->|ストリーミング応答| UI
    UI -->|表示| User

    style User fill:#FFE4B5
    style UI fill:#E0F7FA
    style Agent fill:#C8E6C9
    style Detect fill:#FFECB3
    style Update fill:#FFECB3
    style Reload fill:#FFECB3
    style Tools fill:#B3E5FC
    style Response fill:#C8E6C9
```

## ステップ判定と動的プロンプト切り替え

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant UI as Streamlit UI
    participant Agent as PriceTransferAgent
    participant Prompt as システムプロンプト
    participant Tools as ツール群

    User->>UI: 「原価計算のやり方を教えて」
    UI->>Agent: 質問を送信

    Agent->>Agent: 質問内容を分析<br/>「原価計算」→ STEP 0 - CHECK 3

    alt ステップ不明確
        Agent->>User: ヒアリング
        User->>Agent: 回答
    end

    Agent->>Agent: detect_current_step<br/>ステップ判定

    Agent->>UI: セッション状態更新<br/>current_step = "STEP_0_CHECK_3"

    UI->>Agent: エージェント再初期化

    Agent->>Prompt: ステップ別プロンプト取得<br/>基本 + CHECK 3用追加

    Agent->>Tools: 推奨ツールを実行<br/>search_knowledge_base<br/>calculator<br/>generate_diagram

    Tools-->>Agent: ツール結果

    Agent->>UI: CHECK 3に特化した<br/>詳しい回答

    UI->>User: 表示（ストリーミング）
```

## プロンプト構成

```mermaid
graph LR
    Base[基本プロンプト<br/>MAIN_SYSTEM_PROMPT] --> Final[最終プロンプト]

    Step{判定されたステップ} -->|STEP 0 - CHECK 1| C1[CHECK 1用<br/>取引条件確認]
    Step -->|STEP 0 - CHECK 2| C2[CHECK 2用<br/>データ収集]
    Step -->|STEP 0 - CHECK 3| C3[CHECK 3用<br/>原価計算]
    Step -->|STEP 1| S1[STEP 1用<br/>業界動向]
    Step -->|STEP 2-5| S2[STEP 2-5用<br/>実践編]

    C1 --> Final
    C2 --> Final
    C3 --> Final
    S1 --> Final
    S2 --> Final

    Final --> Agent[PriceTransferAgent]

    style Base fill:#FFF9C4
    style C3 fill:#FF6B6B
    style Final fill:#C8E6C9
```

## データフロー

```mermaid
graph TD
    Session[st.session_state] -->|保持| SID[session_id]
    Session -->|保持| MSG[messages<br/>会話履歴]
    Session -->|保持| AGT[agent<br/>エージェントインスタンス]
    Session -->|保持| STEP[current_step<br/>判定されたステップ]

    STEP -->|例| E1["STEP_0_CHECK_3"]
    STEP -->|例| E2["STEP_1"]
    STEP -->|例| E3["None (未判定)"]

    STEP --> Update{ステップ更新?}
    Update -->|Yes| Reinit[エージェント再初期化<br/>新しいプロンプトで]
    Update -->|No| Keep[現状維持]

    style Session fill:#FFFDE7
    style STEP fill:#FFECB3
    style E1 fill:#FF6B6B
```

## ファイル構成と責務

```mermaid
graph TB
    subgraph UI層
        APP[app.py<br/>Streamlit UI<br/>・チャット画面<br/>・ストリーミング表示<br/>・図の表示]
    end

    subgraph エージェント層
        CORE[agent/core.py<br/>PriceTransferAgent<br/>・初期化<br/>・ステップ更新<br/>・プロンプト構成]
        PROMPT[agent/prompts.py<br/>システムプロンプト<br/>・基本プロンプト<br/>・ステップ別追加]
    end

    subgraph ツール層
        DIAGRAM[tools/diagram_generator.py<br/>図生成ツール<br/>・matplotlib実行<br/>・データ抽出]
        SEARCH[tools/search_tools.py<br/>検索ツール<br/>・Web検索<br/>・KB検索]
    end

    APP --> CORE
    CORE --> PROMPT
    CORE --> DIAGRAM
    CORE --> SEARCH

    style APP fill:#E0F7FA
    style CORE fill:#C8E6C9
    style PROMPT fill:#FFF9C4
    style DIAGRAM fill:#B3E5FC
    style SEARCH fill:#B3E5FC
```

## ステップ判定の柔軟性

```mermaid
graph TD
    Question[ユーザーの質問] --> Type{質問タイプ}

    Type -->|ステップ特化| Specific[現在のステップ<br/>コンテキストで回答]
    Type -->|全般的な質問| General[ステップに関係なく<br/>一般的に回答]
    Type -->|別のステップ| Other[その質問に回答<br/>+ ステップ変更提案]

    Specific --> Keep1[ステップ維持]
    General --> Keep2[ステップ維持]
    Other --> Suggest{ステップ変更?}

    Suggest -->|Yes| Change[新しいステップで<br/>エージェント再初期化]
    Suggest -->|No| Keep3[ステップ維持]

    style Type fill:#FFECB3
    style Specific fill:#C8E6C9
    style General fill:#B3E5FC
    style Other fill:#FFE4B5
```

---

## 重要なポイント

### 1. ステップ判定は「推奨」であって「制約」ではない
- ステップが判定されても、全般的な質問や他のステップの質問にも柔軟に対応
- ステップは「フォーカス」を設定するだけ

### 2. プロンプトの動的切り替え
- 基本プロンプト + ステップ別追加プロンプトで構成
- ステップ判定後、エージェントを再初期化して最適化

### 3. ツールの推奨使用
- 各ステップに応じて推奨ツールを自動的に使用
- 例: CHECK 3 では `search_knowledge_base` + `calculator` + `generate_diagram`

### 4. セッション状態の活用
- `current_step` でステップを管理
- 会話中にステップが変わっても対応可能
