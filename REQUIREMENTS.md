# 価格転嫁支援AIアシスタント - 要件定義書

## 📋 プロジェクト概要

### 目的
中小企業向けの価格転嫁支援AIアシスタントを開発する。
価格転嫁を検討している事業者に対して、的確なアドバイスを提供するチャットボット。

### 最終形（ビジョン）
- 単なる質問応答型チャットボットではなく、ある程度フロー的に使えるもの
- ユーザーの状況をヒアリングし、価格転嫁プロセスのどこにいるのかを特定
- 特定したステップに応じたアドバイスを提供

### 現在の方針
- 一つのシステムプロンプトで全部やるのではなく、**ステップ判定後に追加プロンプトを動的に追加**
- ステップ判定は**エージェントが自動で行う**（手動選択ではない）
- UIのサイドバーは不要
- 判定されたステップに応じて、特定のツールを推奨・使用する

---

## 🎯 対象となる価格転嫁プロセス

中小企業庁が定義する価格転嫁プロセスに沿って支援を行う。

### STEP 0: 価格交渉準備編

価格交渉を行う前の準備段階。以下の8つのCHECKポイントを確認する。

| CHECK | 内容 | Good Practice |
|-------|------|--------------|
| **CHECK 1** | 取引条件・業務内容の確認 | 自社の業務フローと見積チェックリストを作成し、仕様の不確定要素の事前確認に活用 |
| **CHECK 2** | 原材料費・労務費データの定期収集 | 原材料費や労務費のデータは業界誌や公的サイトで定期的にチェック |
| **CHECK 3** | 原価計算の実施 | 支援機関やインターネットなどを活用して学習し、自社の主な事業の製品・サービスの原価計算を実施 |
| **CHECK 4** | 単価表の作成 | 自社の主な事業の製品・サービスの単価表を作成しておくと、価格交渉に役立つ |
| **CHECK 5** | 見積書フォーマットの整備 | 自社の特徴をふまえた見積書を用いて、見積チェックリストの不確定要素の明記等を行い価格交渉に活用 |
| **CHECK 6** | 取引先の経営方針・業績把握 | 取引先の動向把握は交渉スピードに影響。直接把握できない場合、業界団体などを活用し情報収集 |
| **CHECK 7** | 自社の付加価値の明確化 | 差別化が原価把握、取引先との交渉では重要。自社付加価値の見直しが必要 |
| **CHECK 8** | 適正な取引慣行の確認 | 適用対象が拡大され、一方的な代金決定の禁止等の禁止行為が追加。取引内容の確認が必要 |

### STEP 1〜5: 価格交渉実践編

準備が整った後の実際の価格交渉プロセス。

| STEP | 内容 | Good Practice |
|------|------|--------------|
| **STEP 1** | 業界動向の情報収集 | 自社の所属する業界団体などを通じ、業界動向を把握 |
| **STEP 2** | 取引先情報収集と交渉方針検討 | 発注側企業の事業形態や業種、規模などの動向と、自社との取引実績をふまえ交渉方針を検討 |
| **STEP 3** | 書面での申し入れ | 必要に応じて、書面での申し入れを行う |
| **STEP 4** | 説明資料の準備 | ①交渉に迅速・的確に対応できるよう、原材料費や労務費のデータは定期収集し備える<br>②現行商品・サービスの価格交渉だけでなく、自社の付加価値を活かした代替案提示が取引継続のポイント |
| **STEP 5** | 発注後の価格交渉 | ①アウトプットイメージの共有が困難か短期業務ほどプロセス管理を重視し、随時顧客等に進行確認を<br>②受注後に問題が生じ、価格交渉が必要な場合はスピード重視で顧客相談を |

---

## 🏗️ システムアーキテクチャ

### ファイル構成

```
SME-Agency-Price-Transfer-Support-AI/
├── app.py                          # Streamlit UI（エントリポイント）
├── requirements.txt                # 依存パッケージ
│
├── agent/
│   ├── __init__.py
│   ├── core.py                     # エージェント初期化・実行ロジック
│   └── prompts.py                  # システムプロンプト定義
│
├── tools/
│   ├── __init__.py
│   ├── diagram_generator.py        # 図生成ツール
│   └── search_tools.py             # Web検索・KB検索ツール
│
└── utils/
    └── __init__.py
```

### 技術スタック

- **UI**: Streamlit
- **フレームワーク**: Strands Agents
- **LLM**: AWS Bedrock - Claude Haiku 4.5 (`jp.anthropic.claude-haiku-4-5-20251001-v1:0`)
  - Region: ap-northeast-1
  - Temperature: 0.7
  - Max tokens: 50000
  - Streaming: 有効
- **検索**:
  - Tavily API (Web検索)
  - AWS Bedrock Knowledge Base (ナレッジベースID: `7SM8UQNQFL`)
- **図生成**: matplotlib (Pythonサブプロセスで実行)

---

## 🔧 実装済み機能

### 1. チャット機能
- Streamlitを使用した基本的なチャットUI
- ストリーミング応答（リアルタイムでテキストが生成される）
- チャット履歴の保存・表示
- 履歴クリア機能

### 2. ツール機能

#### `web_search` (Tavily API)
- Web検索を実行
- 最大5件の検索結果を取得
- AI要約機能付き

#### `search_knowledge_base` (AWS Bedrock KB)
- ナレッジベースから価格転嫁関連情報を検索
- セマンティック検索
- 最大5件の結果を取得
- 出典ファイル名とスコアを表示

#### `generate_diagram`
- 棒グラフ、折れ線グラフ、フローチャート、ネットワーク図を生成
- description からデータを自動抽出（JSON形式、テーブル形式、リスト形式に対応）
- 生成された図は `diagrams/` フォルダに保存
- UI上で最新の図を自動表示
- 日本語フォント対応（Windows/macOS/Linux）

#### `calculator`
- 基本的な計算機能（Strands標準ツール）

#### `current_time`
- 現在時刻を取得（Strands標準ツール）

### 3. セッション管理
- UUID-based のセッションID生成
- セッション状態の管理（会話履歴、エージェントインスタンス）

### 4. エージェントの分離
- UI部分（`app.py`）とエージェントロジック（`agent/core.py`）を分離
- システムプロンプトは `agent/prompts.py` で管理
- ツールは `tools/` 配下で管理

---

## 🚀 実装予定の機能

### Phase 1: ステップ自動判定機能

**目的:**
- ユーザーの質問内容から、価格転嫁プロセスのどのステップにいるかを自動判定
- 判定後、そのステップに特化したアドバイスを提供

**実装方針:**
1. エージェントがユーザーの質問を分析
2. 必要に応じて1〜2個の簡単な質問でヒアリング
3. `detect_current_step` ツールを使用してステップを判定
4. セッション状態 (`st.session_state.current_step`) を更新
5. エージェントを新しいステップ用のプロンプトで再初期化

**期待される動作:**
```
ユーザー: 「原価計算のやり方を教えて」
↓
エージェント: [内部でSTEP_3と判定]
↓
[detect_current_step ツール使用]
↓
[システムプロンプトにSTEP_3用の追加プロンプトが追加される]
↓
エージェント: 「STEP_3（原価計算）について、詳しくご説明します...」
```

### Phase 2: ステップ別のツール推奨

**目的:**
- 判定されたステップに応じて、特定のツールを積極的に使用するよう推奨

**実装方針:**
- `agent/prompts.py` にステップ別の追加プロンプトを定義
- 各ステップごとに「推奨ツール」と「使用指示」を記載
- エージェントはこの指示に従って自動的にツールを使用

**例:**
```
STEP_3の場合:
「このステップでは以下のツールを積極的に使用してください:
 - search_knowledge_base: 原価計算の手順を検索
 - calculator: 原価計算のシミュレーション
 - generate_diagram: 原価構造の可視化」
```

---

## 🔄 想定されるユーザーフロー

### 基本フロー

```
1. ユーザーが質問を入力
   例: 「原価計算のやり方を教えて」

2. エージェントが質問内容を分析
   - 「原価計算」というキーワードからSTEP_3と判断

3. ステップ判定（必要に応じてヒアリング）
   - 明確な場合: 即座に判定
   - 不明確な場合: 1〜2個の質問で確認

4. detect_current_step ツールを使用
   - {"step": "STEP_3", "reasoning": "原価計算について質問"}

5. セッション状態を更新 & エージェント再初期化
   - st.session_state.current_step = "STEP_3"
   - エージェントに追加プロンプトを注入

6. ステップに特化したアドバイスを提供
   - STEP_3の文脈を理解した詳しい回答
   - 推奨ツールを使用（検索、計算、可視化など）
```

---

## 📊 データフロー

### セッション管理

```python
st.session_state = {
    "session_id": str,           # ランダムなUUID（8文字）
    "messages": list,            # 会話履歴
    "agent": PriceTransferAgent, # エージェントインスタンス
    "current_step": str | None   # 判定されたステップ (例: "STEP_3")
}
```

### エージェントの初期化・更新

```python
# 初期化
agent = PriceTransferAgent(current_step=None)

# ステップ判定後に更新
agent.update_step("STEP_3")
# → 内部でシステムプロンプトが再構成され、エージェントが再初期化される
```

---

## 🎨 UI要件

### 現在のUI
- タイトル: 「価格転嫁支援AIアシスタント」
- 履歴クリアボタン
- チャットエリア（会話履歴表示）
- テキスト入力欄
- 生成された図の自動表示（最新1件）

### 表示要素
- ストリーミング応答（リアルタイムテキスト生成）
- ツール使用中の表示（例: `*[search_knowledge_base を使用中]*`）
- 生成された図の自動表示

### 今後の検討事項
- ステップ判定結果の表示方法（ユーザーに明示するか？）
- サイドバーの必要性（現時点では不要）

---

## 🔒 制約・考慮事項

### 技術的制約
- 図生成はPythonサブプロセスで実行（タイムアウト30秒）
- セッション状態はStreamlitのメモリ上のみ（永続化なし）
- 複数ユーザー同時利用時はセッションIDで分離

### UX考慮事項
- 価格転嫁は長期プロセスのため、すぐに最初から最後まで進めるものではない
- ユーザーは途中のステップから開始することもある
- ステップを強制せず、自由な質問も可能にする柔軟性が必要

---

## 📝 未確定の検討事項

- 各ステップで具体的にどのツールを使うべきか
- ステップ判定の精度をどう担保するか
- ステップ遷移（次のステップへの誘導）は必要か
- 会話履歴の永続化は必要か
- 業種別のカスタマイズは必要か

---

## ✅ 現在の実装状況

### 完了済みの機能

| 機能 | 実装場所 | 説明 |
|-----|---------|------|
| **基本チャットUI** | `app.py` | Streamlitベースのチャット画面 |
| **ストリーミング応答** | `app.py:95-127` | リアルタイムでテキストが生成される |
| **ウェルカムメッセージ** | `app.py:57-76` | 初回アクセス時に自己紹介と使い方を表示 |
| **履歴クリア** | `app.py:42-47` | セッション状態とキャッシュを完全にクリア |
| **Web検索** | `tools/search_tools.py:web_search` | Tavily APIを使用 |
| **KB検索** | `tools/search_tools.py:search_knowledge_base` | AWS Bedrock Knowledge Base |
| **図生成** | `tools/diagram_generator.py:generate_diagram` | matplotlib、棒/線/フロー/ネットワーク図 |
| **計算機** | Strands標準ツール | 基本的な計算 |
| **エージェント分離** | `agent/core.py` | UI層とロジック層を分離 |
| **プロンプト管理** | `agent/prompts.py` | システムプロンプトを一元管理 |

### 未実装の機能

| 機能 | 優先度 | 実装予定場所 | 説明 |
|-----|-------|------------|------|
| **ステップ判定ツール** | 🔴 高 | `tools/step_detector.py` | ユーザーの質問からステップを自動判定 |
| **ステップ別プロンプト** | 🔴 高 | `agent/prompts.py` | STEP 0〜5、CHECK 1〜8ごとの追加プロンプト |
| **プロンプト動的切り替え** | 🔴 高 | `agent/core.py:update_step()` | ステップ判定後にエージェントを再初期化 |
| **ステップ状態管理** | 🔴 高 | `app.py` | `st.session_state.current_step` の管理 |
| **ステップ別ツール推奨** | 🟡 中 | `agent/prompts.py` | 各ステップで推奨ツールの指定 |

---

## 🎯 次のアクション（優先順位順）

### Phase 1: ステップ自動判定機能の実装

**実装内容:**

#### 1. ステップ判定ツールの作成
```bash
# 新規ファイル作成
touch tools/step_detector.py
```

**実装すべき内容:**
- `detect_current_step(user_question: str, context: str = "") -> str` ツール
- LLMにステップ判定させる（STEP 0〜5、CHECK 1〜8）
- 返り値: `{"step": "STEP_0_CHECK_3", "reasoning": "原価計算について質問"}`

**参考実装:**
```python
@tool
def detect_current_step(user_question: str, conversation_context: str = "") -> str:
    """ユーザーの質問から価格転嫁プロセスのステップを判定

    Args:
        user_question: ユーザーの質問内容
        conversation_context: これまでの会話の文脈（オプション）

    Returns:
        str: 判定結果（JSON形式）
    """
    # このツールはLLMに判定させる
    # システムプロンプトに判定ロジックを記述
    return json.dumps({
        "step": "UNKNOWN",
        "confidence": "low",
        "reasoning": "このツールを使用後、エージェントが判定します"
    }, ensure_ascii=False)
```

#### 2. ステップ別プロンプトの定義

**編集ファイル:** `agent/prompts.py`

**追加すべき内容:**
```python
# ステップ別の追加プロンプト
STEP_CONTEXT = {
    "STEP_0_CHECK_1": """
【現在のフォーカス】STEP 0 - CHECK 1: 取引条件・業務内容の確認
ユーザーはこの段階にいます。以下を重点的にサポート：
- 取引先からの引合段階での確認事項
- 業務フローと見積チェックリストの作成方法
- 仕様の不確定要素の事前確認テクニック
""",
    "STEP_0_CHECK_3": """
【現在のフォーカス】STEP 0 - CHECK 3: 原価計算
ユーザーはこの段階にいます。以下を重点的にサポート：
- 製品・サービス単位での原価計算の具体的方法
- 支援機関やインターネットを活用した学習方法
- 主な事業の原価計算の実践例
""",
    # ... 他のステップも同様に定義
}

def get_step_prompt(step: str) -> str:
    """ステップに応じた追加プロンプトを取得"""
    if step and step in STEP_CONTEXT:
        return STEP_CONTEXT[step]
    return ""
```

#### 3. エージェントのステップ更新機能

**編集ファイル:** `agent/core.py`

**追加すべき内容:**
```python
class PriceTransferAgent:
    def __init__(self, current_step: str = None):
        self.current_step = current_step
        self.model = self._initialize_model()
        self.agent = self._initialize_agent()

    def get_system_prompt(self):
        """現在のステップに応じたシステムプロンプトを生成"""
        from .prompts import MAIN_SYSTEM_PROMPT, get_step_prompt

        prompt = MAIN_SYSTEM_PROMPT

        # ステップが特定されている場合は追加
        if self.current_step:
            prompt += "\n\n" + get_step_prompt(self.current_step)

        return prompt

    def update_step(self, new_step: str):
        """ステップを更新してエージェントを再初期化"""
        if self.current_step != new_step:
            self.current_step = new_step
            # エージェントを再初期化（新しいプロンプトで）
            self.agent = self._initialize_agent()
            return True
        return False
```

#### 4. UI側でステップ状態を管理

**編集ファイル:** `app.py`

**追加すべき内容:**
```python
# セッション状態の初期化に追加
if "current_step" not in st.session_state:
    st.session_state.current_step = None

# ストリーミング処理内でツール結果を検知
async def stream_response():
    # ...
    elif "tool_result" in event:
        # ツールの結果を取得
        if event.get("tool_name") == "detect_current_step":
            import json
            result = json.loads(event["tool_result"])
            detected_step = result.get("step")

            # セッション状態を更新
            if detected_step and detected_step != "UNKNOWN":
                st.session_state.current_step = detected_step
                # エージェントを再初期化
                st.session_state.agent.update_step(detected_step)
```

#### 5. メインプロンプトにステップ判定の指示を追加

**編集ファイル:** `agent/prompts.py`

**MAIN_SYSTEM_PROMPT に追加:**
```python
MAIN_SYSTEM_PROMPT = """あなたは中小企業向けの価格転嫁支援専門AIアシスタントです。

## 重要: ステップ判定プロセス

ユーザーが質問してきたとき、以下の手順で対応してください：

1. **質問内容を分析**
   - どのステップ（STEP 0 CHECK 1〜8、STEP 1〜5）に関連しているか判断

2. **簡単なヒアリング（必要に応じて）**
   - ステップが不明確な場合のみ、1〜2個の質問で状況を確認
   - 明確な場合はスキップ

3. **ステップが特定できたら `detect_current_step` ツールを使用**
   - 例: {"step": "STEP_0_CHECK_3", "reasoning": "原価計算について質問"}
   - このツールを使うと、そのステップに最適化されたアドバイスができるようになります

4. **ステップ特定後の対応**
   - ステップ特化の質問: そのステップのコンテキストで詳しく回答
   - 全般的な質問: ステップに関係なく普通に回答
   - 他のステップの質問: 回答 + 必要に応じてステップ変更を提案

## 価格転嫁プロセスの全体像
...（既存の内容）
"""
```

---

### Phase 2: ステップ別ツール推奨（Phase 1完了後）

**実装内容:**
- 各ステップごとに推奨ツールと使用指示を定義
- 例: STEP 0 - CHECK 3 では `search_knowledge_base` → `calculator` → `generate_diagram` の順で使用

**実装場所:**
- `agent/prompts.py` の `STEP_CONTEXT` に追加

---

## 🔧 開発環境セットアップ（新規セッション用）

```bash
# リポジトリ確認
cd c:\Users\rikuto.kobayashi\SME-Agency-Price-Transfer-Support-AI

# 依存パッケージインストール（必要に応じて）
pip install -r requirements.txt

# Streamlit起動
streamlit run app.py
```

**重要なファイル:**
- `REQUIREMENTS.md` - 本ドキュメント
- `ARCHITECTURE.md` - システムアーキテクチャ図（Mermaid）
- `app.py` - メインUI
- `agent/core.py` - エージェントロジック
- `agent/prompts.py` - システムプロンプト
- `tools/` - カスタムツール群

---

## 📊 実装完了の判断基準

### Phase 1完了の条件
- [ ] `tools/step_detector.py` が作成され、ツールとして登録されている
- [ ] `agent/prompts.py` にステップ別プロンプトが定義されている
- [ ] `agent/core.py` に `update_step()` メソッドが実装されている
- [ ] `app.py` でステップ状態が管理され、ツール結果を検知している
- [ ] ユーザーが「原価計算について教えて」と質問すると、エージェントが自動で STEP 0 - CHECK 3 と判定し、そのステップに特化した回答をする

### 動作確認方法
1. Streamlitを起動
2. 「原価計算のやり方を教えて」と質問
3. エージェントが `detect_current_step` ツールを使用
4. `st.session_state.current_step` が `"STEP_0_CHECK_3"` に更新される
5. 以降の質問に対して、CHECK 3のコンテキストを考慮した回答が返る
6. 「価格転嫁とは？」のような全般的な質問にも柔軟に回答できる
