# CLAUDE.md — Amazonせどり商材リサーチアプリ

## 1. プロジェクト概要

Amazonせどり向けの商材リサーチを自動化するWindowsデスクトップアプリケーション。
Keepa APIで商品データを取得し、Claude APIでJANコードを特定、楽天・Yahoo APIで仕入れ価格を調査してROI・利益率を表示する。

- **動作環境**: Windows 10/11（インストール不要・ポータブル実行形式）
- **配布形式**: PyInstallerによる単一exeファイル
- **言語**: Python 3.11+

---

## 2. 機能要件

### 2-1. ASINキャッシュ取得（バックグラウンド自動処理）

- 対象カテゴリのASINリストをKeepa APIから取得し、ローカルDBに保存する
- 取得頻度：週1回（前回取得日をDBに記録して自動判定）
- Keepaトークン制限：**1分間に最大60トークン消費まで**。超過しないようにウェイト制御を実装する
  - 各APIリクエストのトークン消費量をレスポンスから取得し、残量を監視すること
  - 残量が少ない場合は `time.sleep()` でウェイトを挟む

### 2-2. ランダムピックアップ

- キャッシュDBから「ランクの範囲（例：100位〜5000位）」をUIで指定し、その範囲内からランダムに1件取得する
- ピックアップ済みのASINは再度ピックアップされないようフラグ管理する

### 2-3. フィルター処理（順次適用）

#### フィルター1：Amazon直接出品チェック
- Keepaデータの出品者情報を参照し、「Amazon.co.jp」が出品中かどうかを判定する
- **Amazon出品中 → 除外**（Amazonがカートを独占するため販売不可）
- 除外されたASINは `excluded_asins` テーブルに記録し、以降のピックアップ対象から恒久除外する

#### フィルター2：禁止キーワードチェック
- UIで禁止キーワードリストを設定可能（例：「第2類医薬品」「劇物」「危険物」）
- 商品タイトルまたはカテゴリにキーワードが含まれる場合、除外する
- 除外されたASINは同様に恒久除外する

### 2-4. JANコード取得

フィルターを通過したASINに対してJANコードを特定する。

**取得フロー：**

```
Step1: Serper APIでWeb検索（KeepaのEANフィールドは誤情報が多いため使用しない）
  - 商品名を短縮して検索クエリを生成（後述のルール参照）
  - 上位5件のスニペットを取得する

Step2: Claude APIにスニペットを渡してJANコードを抽出させる
  - 入力トークン：title×5件＋link×5件＋snippet×5件＋構造オーバーヘッド ≒ 1,050トークン
  - 出力トークン：≒ 50トークン（1件あたり合計 約1,100トークン）
  - 取得できない場合は「JANコード不明」として処理継続
```

**商品名短縮ルール（必ず実装）：**
- Amazon商品名は長すぎるため、以下の処理で短縮してから検索する
  1. カッコ内の補足説明を除去 `(...)` `【...】` `[...]`
  2. 容量・個数表記（例：「500ml×24本」）は保持
  3. ブランド名＋製品名のみに絞る（目安：30文字以内）
  4. 短縮後の文字列 + `"JANコード"` or `"JAN"` で検索する

### 2-5. 仕入れ価格リサーチ（楽天・Yahoo）

JANコードが取得できた場合に実行する。

- 楽天API・Yahoo!ショッピングAPIで該当JANコードを検索する（**直列実行**、並列化しない）
- 各ECサイトから**最安値順に5件ずつ**取得してリスト表示する
- セット商品対応：商品名または個数フィールドに「12個セット」「×12」等の記述がある場合、価格を12で割って単価を算出して表示する
- **割引入力フィールド**：UIに割引額（円）または割引率（%）を入力するフォームを設置し、入力値に応じてリスト内の全価格をリアルタイム更新する

### 2-7. 自動リサーチモード

アプリ起動中に定期的にリサーチを自動実行するバックグラウンドモード。

**動作仕様：**
- アプリ起動中のみ動作する（アプリ終了で停止）
- デフォルト設定：**1時間に1回、1回あたり5件** を順次実行
- 実行間隔・1回あたりの件数はUIの設定パネルから変更可能
- 実行タイマーは `threading.Timer` または `schedule` ライブラリで実装する
- 自動実行中は手動ボタンを無効化せず、併用可能とする
- 次回自動実行までの残り時間をUIにカウントダウン表示する（例：「次回自動実行まで 47:23」）

**設定項目（config.jsonに保存）：**

```json
{
  "auto_research": {
    "enabled": false,
    "interval_minutes": 60,
    "batch_size": 5
  }
}
```

**UIコントロール（`frontend/components/auto_mode_panel.py` に実装）：**
- 自動モード ON/OFF トグルスイッチ
- 実行間隔入力フィールド（分単位）
- 1回あたりの件数入力フィールド（最大20件に制限）
- カウントダウン表示ラベル
- 「今すぐ実行」ボタン（スケジュールリセット）



以下の値をUIで表示する。

| 指標 | 計算式 |
|------|--------|
| 仕入れ単価 | 楽天/Yahoo取得価格（割引後） |
| Amazon販売価格 | Keepa取得の現在出品価格 |
| Amazon手数料 | 販売価格 × カテゴリ別手数料率（設定可能） |
| FBA手数料 | 商品サイズ区分に応じた固定値（設定可能） |
| 利益額 | 販売価格 − 仕入れ単価 − Amazon手数料 − FBA手数料 |
| 利益率 | 利益額 ÷ 販売価格 × 100（%） |
| ROI | 利益額 ÷ 仕入れ単価 × 100（%） |

---

## 3. 技術スタック

| 用途 | 採用技術 | 選定理由 |
|------|---------|---------|
| GUI | `tkinter` or `CustomTkinter` | インストール不要exeに向く、Pythonネイティブ |
| HTTPクライアント | `httpx` (async) | 非同期リクエストでUIスレッドをブロックしない |
| DB | `SQLite` (`sqlite3`) | 外部DBサーバー不要、ポータブル構成に適合 |
| exe化 | `PyInstaller` | 単一exeにバンドル可能 |
| 設定ファイル | `config.json`（暗号化推奨） | APIキー保存用 |
| ログ | `logging`（rotating file handler） | デバッグ用 |

---

## 4. 外部API一覧

| API | 用途 | 取得場所 |
|-----|------|---------|
| Keepa API | ASIN取得・商品詳細・出品者情報 | keepa.com |
| Claude API | JANコード抽出 | console.anthropic.com |
| Serper API | Webスニペット取得 | serper.dev |
| 楽天 商品検索API | 仕入れ価格取得 | webservice.rakuten.co.jp |
| Yahoo!ショッピングAPI | 仕入れ価格取得 | developer.yahoo.co.jp |

---

## 5. ディレクトリ構造

```
researchtool/
├── CLAUDE.md                  # 本ファイル
├── main.py                    # エントリーポイント（exe起動時）
├── config.json                # APIキー・設定保存（gitignore対象）
├── sedori.db                  # SQLiteデータベース
│
├── backend/                   # エージェントA担当
│   ├── __init__.py
│   ├── keepa_client.py        # Keepa API通信・トークン管理
│   ├── asin_cache.py          # ASINキャッシュ取得・DB保存・週次スケジューリング
│   ├── filter_engine.py       # フィルター1・2の判定ロジック
│   ├── jan_resolver.py        # JANコード取得フロー（Keepa→Serper→Claude）
│   ├── price_fetcher.py       # 楽天・Yahoo API価格取得
│   ├── roi_calculator.py      # ROI・利益率計算
│   └── db.py                  # SQLite CRUD・スキーマ定義
│
├── frontend/                  # エージェントB担当
│   ├── __init__.py
│   ├── app.py                 # メインウィンドウ・画面遷移
│   ├── components/
│   │   ├── result_list.py     # リサーチ結果リスト（スクロール対応）
│   │   ├── filter_panel.py    # フィルター設定パネル
│   │   ├── discount_input.py  # 割引入力フォーム
│   │   ├── auto_mode_panel.py # 自動リサーチモード設定・カウントダウン表示
│   │   ├── settings_dialog.py # APIキー入力ダイアログ
│   │   └── url_label.py       # クリックでブラウザ遷移するURLラベル
│   └── styles.py              # カラー・フォント定数
│
└── tests/                     # エージェントC担当
    ├── __init__.py
    ├── test_keepa_client.py
    ├── test_filter_engine.py
    ├── test_jan_resolver.py
    ├── test_roi_calculator.py
    └── mock_responses/        # APIモックデータ（JSON）
        ├── keepa_product.json
        ├── serper_result.json
        ├── rakuten_result.json
        └── yahoo_result.json
```

---

## 6. DBスキーマ

```sql
-- ASINキャッシュ
CREATE TABLE asin_cache (
    asin          TEXT PRIMARY KEY,
    category      TEXT,
    sales_rank    INTEGER,
    fetched_at    DATETIME,
    picked        BOOLEAN DEFAULT 0,
    excluded      BOOLEAN DEFAULT 0,
    exclude_reason TEXT    -- 'amazon_selling' | 'forbidden_keyword' | NULL
);

-- リサーチ結果
CREATE TABLE research_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asin          TEXT,
    title         TEXT,
    jan_code      TEXT,
    amazon_price  REAL,
    best_buy_url  TEXT,
    best_buy_price REAL,
    roi           REAL,
    profit_rate   REAL,
    researched_at DATETIME
);

-- キャッシュ取得履歴
CREATE TABLE cache_fetch_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category      TEXT,
    fetched_at    DATETIME,
    asin_count    INTEGER
);
```

---

## 7. エージェント構成と責任範囲

### エージェントA（バックエンド担当）

**担当ファイル**: `backend/` 配下の全ファイル

**実装責任**:
- Keepa APIラッパー（トークン消費監視・ウェイト制御を含む）
- ASINキャッシュの取得・DB保存・週次自動更新ロジック
- フィルター1・2の判定処理
- JANコード取得フロー（Serper API呼び出し→スニペット整形→Claude API呼び出し）
- 楽天・Yahoo!ショッピングAPI呼び出し・セット品単価計算
- ROI・利益率計算ロジック

**フロントエンドへのインターフェース（必ず守ること）**:

```python
# すべてのバックエンド関数は以下のシグネチャで非同期関数として実装する

async def run_research(rank_min: int, rank_max: int) -> ResearchResult:
    """1件のリサーチを実行して結果を返す"""
    ...

# ResearchResult は dataclass で定義
@dataclass
class ResearchResult:
    asin: str
    title: str
    jan_code: str | None
    amazon_price: float
    amazon_url: str
    rakuten_items: list[PriceItem]   # 最大5件
    yahoo_items: list[PriceItem]     # 最大5件
    roi: float
    profit_rate: float
    researched_at: datetime

@dataclass
class PriceItem:
    shop_name: str
    unit_price: float       # セット品は割り算済みの単価
    is_set: bool
    set_count: int
    url: str
```

---

### エージェントB（フロントエンド担当）

**担当ファイル**: `frontend/` 配下の全ファイル、`main.py`

**実装責任**:
- メインウィンドウのレイアウト
- リサーチ実行ボタン・ランク範囲入力フォーム
- 結果リスト（スクロール可・過去結果を上から積み上げ表示）
- URLラベル（クリックで `webbrowser.open()` によりデフォルトブラウザで開く）
- 割引入力フォーム（入力値変更時に表示価格をリアルタイム再計算）
- 設定ダイアログ（各APIキーの入力・保存・マスク表示）
- 処理中のプログレス表示（「フィルター1確認中...」等のステータステキスト）

**バックエンド呼び出し方法**:
- `asyncio` を使ってバックエンドの非同期関数を呼び出す
- UIスレッドをブロックしないよう `threading` または `asyncio.run_coroutine_threadsafe` を使うこと

---

### エージェントC（デバッグ担当）

**担当ファイル**: `tests/` 配下の全ファイル

**テスト方針**:
- 外部APIは `mock_responses/` 内のJSONファイルでモックする（実APIを叩かない）
- フィルター判定・ROI計算・JANコード短縮ロジックは必ずユニットテストを書く

**バグレポートフォーマット（A・Bへのフィードバック時）**:

```
## バグ報告 #[連番]

### 現象
[ユーザーが何をしたときに何が起きたか]

### 再現手順
1.
2.
3.

### 期待する動作
[こうなるべきだった]

### 対象ファイル・関数
`backend/filter_engine.py` の `check_amazon_seller()` 関数

### 修正担当
エージェント [A / B]
```

---

## 8. 実行フェーズ

```
フェーズ1（並列）:
  エージェントA → backend/ の全実装
  エージェントB → frontend/ の全実装（バックエンド関数はスタブで代替可）

フェーズ2（並列）:
  エージェントC → 全モジュールのテスト実行・バグ洗い出し

フェーズ3（逐次）:
  エージェントC → バグレポートを上記フォーマットで出力
  エージェントA / B → バグレポートを受けて修正（担当別）
  ※ フェーズ3は全バグが解消するまで繰り返す
```

---

## 9. KPI・完了基準

| 基準 | 詳細 |
|------|------|
| **情報の正常表示** | リサーチ結果（価格・ROI・利益率・URLリンク）が正しく画面に表示されること |
| **フィルター正確性** | Amazon出品・禁止キーワードの誤判定ゼロ |
| **JANコード取得率** | モックデータを使ったテストで80%以上の取得成功率 |
| **クラッシュなし** | APIキー未設定・API返却エラー・DB未初期化の各状態でクラッシュしないこと |
| **exe単体起動** | PyInstaller生成exeが外部Pythonなしで起動すること |

> ⚠️ **処理時間はKPIに含めない。** 情報が正確に表示されることを優先する。

---

## 10. 制約・禁止事項

- Amazon本体へのスクレイピングは**禁止**。データ取得はKeepa API経由に限定する
- APIキーは `config.json` に保存し、コードにハードコードしない
- `config.json` はGitに含めない（`.gitignore` に追記すること）
- Keepaトークンを1分間に60以上消費するコードは書かない
- Claude APIへ渡すテキストは最大2000トークン以内に収めること（コスト管理）

---

## 11. Keepa API 実装仕様（エージェントA必読）

### 使用ライブラリ

```
pip install keepa
```

公式Pythonラッパーを使う。直接HTTPリクエストは書かない。

### ドメイン指定

Amazon.co.jp は `domain='JP'`（内部値=5）を必ず指定する。

```python
import keepa
api = keepa.Keepa(KEEPA_API_KEY)
```

### ASINキャッシュ取得（Best Sellers API）

```python
# カテゴリIDを指定してASINリストを取得
asin_list = api.best_sellers_query(category=CATEGORY_NODE_ID, domain='JP')
# 戻り値: ['B0XXXXXXXX', 'B0YYYYYYYY', ...]
```

**主要カテゴリのnode ID（Amazon.co.jp）：**

| カテゴリ名 | node ID |
|-----------|---------|
| ドラッグストア | 2189494051 |
| ビューティー | 57035011 |
| ホーム＆キッチン | 3828871 |
| 食品・飲料・お酒 | 2189514051 |
| ペット用品 | 2201396051 |
| スポーツ＆アウトドア | 14304371 |
| おもちゃ | 13312011 |
| 文房具・オフィス用品 | 2189707051 |
| DIY・工具 | 2189641051 |
| カー用品 | 2151999051 |

> ⚠️ カテゴリIDはUIのチェックボックスに紐づける。DBの `category` カラムにはカテゴリ名（日本語）を保存する。

### 商品詳細取得（Product Query）

```python
products = api.query(
    asin,
    domain='JP',
    offers=20,          # 出品者情報を取得（Amazon出品チェックに必要）
    only_live_offers=True,  # 現在出品中のもののみ
    history=False,      # 価格履歴不要でトークン節約
    stats=30,           # 直近30日の統計
)
product = products[0]
```

**使用するフィールド一覧：**

| フィールド | 内容 | 使用箇所 |
|-----------|------|---------|
| `product['title']` | 商品名 | 表示・JANコード検索 |
| `product['csv'][0]` | Amazon価格履歴（最新値がAmazon出品価格） | フィルター1・販売価格 |
| `product['offers']` | 出品者リスト | フィルター1 |
| `product['salesRanks']` | カテゴリ別ランク履歴 | ランク確認 |
| `product['packageHeight']` | 梱包高さ(mm) | FBA手数料自動計算 |
| `product['packageLength']` | 梱包長さ(mm) | FBA手数料自動計算 |
| `product['packageWidth']` | 梱包幅(mm) | FBA手数料自動計算 |
| `product['packageWeight']` | 梱包重量(g) | FBA手数料自動計算 |
| `product['fbaFees']` | FBA手数料情報（あれば） | FBA手数料自動計算 |
| `product['rootCategory']` | ルートカテゴリID | カテゴリ手数料率の特定 |

### フィルター1（Amazon出品チェック）の実装方法

```python
def is_amazon_selling(product: dict) -> bool:
    """Amazon.co.jpが現在出品中かどうか判定する"""
    # 方法1: csv[0]（Amazon価格履歴）の最新値が -1 でなければ出品中
    csv_amazon = product.get('csv', [None])[0]
    if csv_amazon and len(csv_amazon) >= 2:
        latest_price = csv_amazon[-1]  # 最新価格
        if latest_price != -1:
            return True

    # 方法2: offers から isAmazon フラグを確認（より確実）
    live_order = product.get('liveOffersOrder', [])
    offers = product.get('offers', [])
    for idx in live_order:
        if offers[idx].get('isAmazon', False):
            return True

    return False
```

### FBA手数料自動計算の実装方法

```python
def calculate_fba_fee(product: dict) -> int:
    """
    KeepaデータからFBA手数料を自動計算する（円）
    fbaFeesフィールドがあればそれを優先、なければサイズ区分で算出
    """
    # keepaが手数料データを持っている場合はそれを使用
    fba_fees = product.get('fbaFees')
    if fba_fees and fba_fees.get('pickAndPackFee', -1) != -1:
        return fba_fees['pickAndPackFee']  # すでに円単位

    # ない場合はサイズ区分から算出（2024年4月改定後の料金）
    h = product.get('packageHeight', 0)  # mm
    l = product.get('packageLength', 0)  # mm
    w = product.get('packageWidth', 0)   # mm
    weight_g = product.get('packageWeight', 0)  # g

    # cm変換
    h_cm, l_cm, w_cm = h/10, l/10, w/10
    weight_kg = (weight_g + 150) / 1000  # 梱包資材150g加算

    # サイズ区分判定（2024年改定後）
    dims = sorted([l_cm, w_cm, h_cm], reverse=True)
    size = classify_fba_size(dims, weight_kg)

    # 手数料テーブル（2024年4月改定後・税込）
    FBA_FEE_TABLE = {
        '小型':       288,
        '標準1':      354,
        '標準2':      410,
        '標準3':      470,
        '標準4':      524,
        '大型1':      756,
        '大型2':      1040,
        '大型3':      1312,
        '大型4':      1640,
        '特大型1':    2117,
        '特大型2':    2700,
        '特大型3':    3700,
        '特大型4':    5625,
    }
    return FBA_FEE_TABLE.get(size, 500)  # 不明な場合は500円をデフォルト

def classify_fba_size(dims: list, weight_kg: float) -> str:
    """商品寸法・重量からFBAサイズ区分を返す"""
    l, w, h = dims[0], dims[1], dims[2]
    if l <= 25 and w <= 18 and h <= 2 and weight_kg <= 0.3:
        return '小型'
    elif l <= 35 and w <= 30 and h <= 3.3 and weight_kg <= 1.0:
        return '標準1'
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 2.0:
        return '標準2'
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 5.0:
        return '標準3'
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 9.0:
        return '標準4'
    elif l <= 80 and w <= 60 and h <= 60 and weight_kg <= 10.0:
        return '大型1'
    elif l <= 100 and w <= 60 and h <= 60 and weight_kg <= 15.0:
        return '大型2'
    elif l <= 120 and w <= 80 and h <= 80 and weight_kg <= 20.0:
        return '大型3'
    elif l <= 150 and w <= 100 and h <= 100 and weight_kg <= 25.0:
        return '大型4'
    else:
        return '特大型1'
```

### カテゴリ別販売手数料率（自動計算用）

```python
# rootCategoryIDから手数料率を引く辞書（代表的なカテゴリ）
REFERRAL_FEE_RATE = {
    2189494051: 0.08,   # ドラッグストア
    57035011:   0.08,   # ビューティー
    3828871:    0.10,   # ホーム＆キッチン
    2189514051: 0.08,   # 食品・飲料
    2201396051: 0.08,   # ペット用品
    14304371:   0.10,   # スポーツ
    13312011:   0.10,   # おもちゃ
    2189707051: 0.10,   # 文房具
    2189641051: 0.10,   # DIY・工具
    2151999051: 0.10,   # カー用品
}
DEFAULT_REFERRAL_FEE_RATE = 0.10  # 不明カテゴリのデフォルト

def get_referral_fee(product: dict, selling_price: int) -> int:
    rate = REFERRAL_FEE_RATE.get(
        product.get('rootCategory'), DEFAULT_REFERRAL_FEE_RATE
    )
    return int(selling_price * rate)
```

### トークン残量監視

```python
# api.tokens_left でトークン残量を確認できる
# keepaライブラリのwait=True（デフォルト）で自動ウェイト制御される
# 明示的に確認したい場合:
remaining = api.tokens_left
if remaining < 10:
    time.sleep(60)  # 1分待機してリフィルを待つ
```

### JANコード未取得時の表示仕様

楽天・Yahoo検索はスキップし、以下の項目のみUIに表示する：

- 商品タイトル
- Amazon販売価格
- AmazonページURL（`https://www.amazon.co.jp/dp/{ASIN}`）
- 「JANコード取得不可 - 仕入れ価格リサーチ不可」のメッセージ（警告色で表示）
- ROI・利益率は「-」で表示

---

## 12. Claude APIプロンプトテンプレート（JANコード抽出）

エージェントAは以下のプロンプトを `jan_resolver.py` にそのまま実装すること。

```python
SYSTEM_PROMPT = """あなたはAmazon商品のJANコードを特定する専門家です。
与えられた検索結果のスニペットから、商品のJANコード（13桁の数字）を抽出してください。
JANコードが見つかった場合は数字のみ（例: 4901234567890）を返してください。
見つからない場合は「NOT_FOUND」のみを返してください。
それ以外の文字は一切出力しないでください。"""

def build_user_prompt(product_title: str, serper_results: list[dict]) -> str:
    snippets = "\n".join([
        f"[{i+1}] タイトル: {r.get('title','')}\n    スニペット: {r.get('snippet','')}"
        for i, r in enumerate(serper_results[:5])
    ])
    return f"商品名: {product_title}\n\n検索結果:\n{snippets}\n\nこの商品のJANコードを教えてください。"
```

---

## 13. カテゴリ選択UI仕様（エージェントB）

UIにチェックボックスリストを設置し、複数カテゴリを同時選択可能にする。

```python
CATEGORY_LIST = [
    ("ドラッグストア",      2189494051),
    ("ビューティー",        57035011),
    ("ホーム＆キッチン",    3828871),
    ("食品・飲料・お酒",    2189514051),
    ("ペット用品",          2201396051),
    ("スポーツ＆アウトドア",14304371),
    ("おもちゃ",            13312011),
    ("文房具・オフィス用品",2189707051),
    ("DIY・工具",           2189641051),
    ("カー用品",            2151999051),
]
# 選択されたカテゴリのnode IDリストをバックエンドに渡す
```

---

## 14. 非機能要件

- **ログ**: `app.log` にローテーティングファイルハンドラで出力（最大5MB × 3世代）
- **エラーハンドリング**: 外部API呼び出しはすべて `try/except` で囲み、エラー時はUIにメッセージ表示してクラッシュしない
- **設定の永続化**: ウィンドウサイズ・APIキー・最後に使ったランク範囲は `config.json` に保存し、次回起動時に復元する
# CLAUDE.md — Amazonせどり商材リサーチアプリ

## 1. プロジェクト概要

Amazonせどり向けの商材リサーチを自動化するWindowsデスクトップアプリケーション。
Keepa APIで商品データを取得し、Claude APIでJANコードを特定、楽天・Yahoo APIで仕入れ価格を調査してROI・利益率を表示する。

- **動作環境**: Windows 10/11（インストール不要・ポータブル実行形式）
- **配布形式**: PyInstallerによる単一exeファイル
- **言語**: Python 3.11+

---

## 2. 機能要件

### 2-1. ASINキャッシュ取得（バックグラウンド自動処理）

- 対象カテゴリのASINリストをKeepa APIから取得し、ローカルDBに保存する
- 取得頻度：週1回（前回取得日をDBに記録して自動判定）
- Keepaトークン制限：**1分間に最大60トークン消費まで**。超過しないようにウェイト制御を実装する
  - 各APIリクエストのトークン消費量をレスポンスから取得し、残量を監視すること
  - 残量が少ない場合は `time.sleep()` でウェイトを挟む

### 2-2. ランダムピックアップ

- キャッシュDBから「ランクの範囲（例：100位〜5000位）」をUIで指定し、その範囲内からランダムに1件取得する
- ピックアップ済みのASINは再度ピックアップされないようフラグ管理する

### 2-3. フィルター処理（順次適用）

#### フィルター1：Amazon直接出品チェック
- Keepaデータの出品者情報を参照し、「Amazon.co.jp」が出品中かどうかを判定する
- **Amazon出品中 → 除外**（Amazonがカートを独占するため販売不可）
- 除外されたASINは `excluded_asins` テーブルに記録し、以降のピックアップ対象から恒久除外する

#### フィルター2：禁止キーワードチェック
- UIで禁止キーワードリストを設定可能（例：「第2類医薬品」「劇物」「危険物」）
- 商品タイトルまたはカテゴリにキーワードが含まれる場合、除外する
- 除外されたASINは同様に恒久除外する

### 2-4. JANコード取得

フィルターを通過したASINに対してJANコードを特定する。

**取得フロー：**

```
Step1: Serper APIでWeb検索（KeepaのEANフィールドは誤情報が多いため使用しない）
  - 商品名を短縮して検索クエリを生成（後述のルール参照）
  - 上位5件のスニペットを取得する

Step2: Claude APIにスニペットを渡してJANコードを抽出させる
  - 入力トークン：title×5件＋link×5件＋snippet×5件＋構造オーバーヘッド ≒ 1,050トークン
  - 出力トークン：≒ 50トークン（1件あたり合計 約1,100トークン）
  - 取得できない場合は「JANコード不明」として処理継続
```

**商品名短縮ルール（必ず実装）：**
- Amazon商品名は長すぎるため、以下の処理で短縮してから検索する
  1. カッコ内の補足説明を除去 `(...)` `【...】` `[...]`
  2. 容量・個数表記（例：「500ml×24本」）は保持
  3. ブランド名＋製品名のみに絞る（目安：30文字以内）
  4. 短縮後の文字列 + `"JANコード"` or `"JAN"` で検索する

### 2-5. 仕入れ価格リサーチ（楽天・Yahoo）

JANコードが取得できた場合に実行する。

- 楽天API・Yahoo!ショッピングAPIで該当JANコードを検索する（**直列実行**、並列化しない）
- 各ECサイトから**最安値順に5件ずつ**取得してリスト表示する
- セット商品対応：商品名または個数フィールドに「12個セット」「×12」等の記述がある場合、価格を12で割って単価を算出して表示する
- **割引入力フィールド**：UIに割引額（円）または割引率（%）を入力するフォームを設置し、入力値に応じてリスト内の全価格をリアルタイム更新する

### 2-7. 自動リサーチモード

アプリ起動中に定期的にリサーチを自動実行するバックグラウンドモード。

**動作仕様：**
- アプリ起動中のみ動作する（アプリ終了で停止）
- デフォルト設定：**1時間に1回、1回あたり5件** を順次実行
- 実行間隔・1回あたりの件数はUIの設定パネルから変更可能
- 実行タイマーは `threading.Timer` または `schedule` ライブラリで実装する
- 自動実行中は手動ボタンを無効化せず、併用可能とする
- 次回自動実行までの残り時間をUIにカウントダウン表示する（例：「次回自動実行まで 47:23」）

**設定項目（config.jsonに保存）：**

```json
{
  "auto_research": {
    "enabled": false,
    "interval_minutes": 60,
    "batch_size": 5
  }
}
```

**UIコントロール（`frontend/components/auto_mode_panel.py` に実装）：**
- 自動モード ON/OFF トグルスイッチ
- 実行間隔入力フィールド（分単位）
- 1回あたりの件数入力フィールド（最大20件に制限）
- カウントダウン表示ラベル
- 「今すぐ実行」ボタン（スケジュールリセット）



以下の値をUIで表示する。

| 指標 | 計算式 |
|------|--------|
| 仕入れ単価 | 楽天/Yahoo取得価格（割引後） |
| Amazon販売価格 | Keepa取得の現在出品価格 |
| Amazon手数料 | 販売価格 × カテゴリ別手数料率（設定可能） |
| FBA手数料 | 商品サイズ区分に応じた固定値（設定可能） |
| 利益額 | 販売価格 − 仕入れ単価 − Amazon手数料 − FBA手数料 |
| 利益率 | 利益額 ÷ 販売価格 × 100（%） |
| ROI | 利益額 ÷ 仕入れ単価 × 100（%） |

---

## 3. 技術スタック

| 用途 | 採用技術 | 選定理由 |
|------|---------|---------|
| GUI | `tkinter` or `CustomTkinter` | インストール不要exeに向く、Pythonネイティブ |
| HTTPクライアント | `httpx` (async) | 非同期リクエストでUIスレッドをブロックしない |
| DB | `SQLite` (`sqlite3`) | 外部DBサーバー不要、ポータブル構成に適合 |
| exe化 | `PyInstaller` | 単一exeにバンドル可能 |
| 設定ファイル | `config.json`（暗号化推奨） | APIキー保存用 |
| ログ | `logging`（rotating file handler） | デバッグ用 |

---

## 4. 外部API一覧

| API | 用途 | 取得場所 |
|-----|------|---------|
| Keepa API | ASIN取得・商品詳細・出品者情報 | keepa.com |
| Claude API | JANコード抽出 | console.anthropic.com |
| Serper API | Webスニペット取得 | serper.dev |
| 楽天 商品検索API | 仕入れ価格取得 | webservice.rakuten.co.jp |
| Yahoo!ショッピングAPI | 仕入れ価格取得 | developer.yahoo.co.jp |

---

## 5. ディレクトリ構造

```
research_app/
├── CLAUDE.md                  # 本ファイル
├── main.py                    # エントリーポイント（exe起動時）
├── config.json                # APIキー・設定保存（gitignore対象）
├── sedori.db                  # SQLiteデータベース
│
├── backend/                   # エージェントA担当
│   ├── __init__.py
│   ├── keepa_client.py        # Keepa API通信・トークン管理
│   ├── asin_cache.py          # ASINキャッシュ取得・DB保存・週次スケジューリング
│   ├── filter_engine.py       # フィルター1・2の判定ロジック
│   ├── jan_resolver.py        # JANコード取得フロー（Keepa→Serper→Claude）
│   ├── price_fetcher.py       # 楽天・Yahoo API価格取得
│   ├── roi_calculator.py      # ROI・利益率計算
│   └── db.py                  # SQLite CRUD・スキーマ定義
│
├── frontend/                  # エージェントB担当
│   ├── __init__.py
│   ├── app.py                 # メインウィンドウ・画面遷移
│   ├── components/
│   │   ├── result_list.py     # リサーチ結果リスト（スクロール対応）
│   │   ├── filter_panel.py    # フィルター設定パネル
│   │   ├── discount_input.py  # 割引入力フォーム
│   │   ├── auto_mode_panel.py # 自動リサーチモード設定・カウントダウン表示
│   │   ├── settings_dialog.py # APIキー入力ダイアログ
│   │   └── url_label.py       # クリックでブラウザ遷移するURLラベル
│   └── styles.py              # カラー・フォント定数
│
└── tests/                     # エージェントC担当
    ├── __init__.py
    ├── test_keepa_client.py
    ├── test_filter_engine.py
    ├── test_jan_resolver.py
    ├── test_roi_calculator.py
    └── mock_responses/        # APIモックデータ（JSON）
        ├── keepa_product.json
        ├── serper_result.json
        ├── rakuten_result.json
        └── yahoo_result.json
```

---

## 6. DBスキーマ

```sql
-- ASINキャッシュ
CREATE TABLE asin_cache (
    asin          TEXT PRIMARY KEY,
    category      TEXT,
    sales_rank    INTEGER,
    fetched_at    DATETIME,
    picked        BOOLEAN DEFAULT 0,
    excluded      BOOLEAN DEFAULT 0,
    exclude_reason TEXT    -- 'amazon_selling' | 'forbidden_keyword' | NULL
);

-- リサーチ結果
CREATE TABLE research_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asin          TEXT,
    title         TEXT,
    jan_code      TEXT,
    amazon_price  REAL,
    best_buy_url  TEXT,
    best_buy_price REAL,
    roi           REAL,
    profit_rate   REAL,
    researched_at DATETIME
);

-- キャッシュ取得履歴
CREATE TABLE cache_fetch_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category      TEXT,
    fetched_at    DATETIME,
    asin_count    INTEGER
);
```

---

## 7. エージェント構成と責任範囲

### エージェントA（バックエンド担当）

**担当ファイル**: `backend/` 配下の全ファイル

**実装責任**:
- Keepa APIラッパー（トークン消費監視・ウェイト制御を含む）
- ASINキャッシュの取得・DB保存・週次自動更新ロジック
- フィルター1・2の判定処理
- JANコード取得フロー（Serper API呼び出し→スニペット整形→Claude API呼び出し）
- 楽天・Yahoo!ショッピングAPI呼び出し・セット品単価計算
- ROI・利益率計算ロジック

**フロントエンドへのインターフェース（必ず守ること）**:

```python
# すべてのバックエンド関数は以下のシグネチャで非同期関数として実装する

async def run_research(rank_min: int, rank_max: int) -> ResearchResult:
    """1件のリサーチを実行して結果を返す"""
    ...

# ResearchResult は dataclass で定義
@dataclass
class ResearchResult:
    asin: str
    title: str
    jan_code: str | None
    amazon_price: float
    amazon_url: str
    rakuten_items: list[PriceItem]   # 最大5件
    yahoo_items: list[PriceItem]     # 最大5件
    roi: float
    profit_rate: float
    researched_at: datetime

@dataclass
class PriceItem:
    shop_name: str
    unit_price: float       # セット品は割り算済みの単価
    is_set: bool
    set_count: int
    url: str
```

---

### エージェントB（フロントエンド担当）

**担当ファイル**: `frontend/` 配下の全ファイル、`main.py`

**実装責任**:
- メインウィンドウのレイアウト
- リサーチ実行ボタン・ランク範囲入力フォーム
- 結果リスト（スクロール可・過去結果を上から積み上げ表示）
- URLラベル（クリックで `webbrowser.open()` によりデフォルトブラウザで開く）
- 割引入力フォーム（入力値変更時に表示価格をリアルタイム再計算）
- 設定ダイアログ（各APIキーの入力・保存・マスク表示）
- 処理中のプログレス表示（「フィルター1確認中...」等のステータステキスト）

**バックエンド呼び出し方法**:
- `asyncio` を使ってバックエンドの非同期関数を呼び出す
- UIスレッドをブロックしないよう `threading` または `asyncio.run_coroutine_threadsafe` を使うこと

---

### エージェントC（デバッグ担当）

**担当ファイル**: `tests/` 配下の全ファイル

**テスト方針**:
- 外部APIは `mock_responses/` 内のJSONファイルでモックする（実APIを叩かない）
- フィルター判定・ROI計算・JANコード短縮ロジックは必ずユニットテストを書く

**バグレポートフォーマット（A・Bへのフィードバック時）**:

```
## バグ報告 #[連番]

### 現象
[ユーザーが何をしたときに何が起きたか]

### 再現手順
1.
2.
3.

### 期待する動作
[こうなるべきだった]

### 対象ファイル・関数
`backend/filter_engine.py` の `check_amazon_seller()` 関数

### 修正担当
エージェント [A / B]
```

---

## 8. 実行フェーズ

```
フェーズ1（並列）:
  エージェントA → backend/ の全実装
  エージェントB → frontend/ の全実装（バックエンド関数はスタブで代替可）

フェーズ2（並列）:
  エージェントC → 全モジュールのテスト実行・バグ洗い出し

フェーズ3（逐次）:
  エージェントC → バグレポートを上記フォーマットで出力
  エージェントA / B → バグレポートを受けて修正（担当別）
  ※ フェーズ3は全バグが解消するまで繰り返す
```

---

## 9. KPI・完了基準

| 基準 | 詳細 |
|------|------|
| **情報の正常表示** | リサーチ結果（価格・ROI・利益率・URLリンク）が正しく画面に表示されること |
| **フィルター正確性** | Amazon出品・禁止キーワードの誤判定ゼロ |
| **JANコード取得率** | モックデータを使ったテストで80%以上の取得成功率 |
| **クラッシュなし** | APIキー未設定・API返却エラー・DB未初期化の各状態でクラッシュしないこと |
| **exe単体起動** | PyInstaller生成exeが外部Pythonなしで起動すること |

> ⚠️ **処理時間はKPIに含めない。** 情報が正確に表示されることを優先する。

---

## 10. 制約・禁止事項

- Amazon本体へのスクレイピングは**禁止**。データ取得はKeepa API経由に限定する
- APIキーは `config.json` に保存し、コードにハードコードしない
- `config.json` はGitに含めない（`.gitignore` に追記すること）
- Keepaトークンを1分間に60以上消費するコードは書かない
- Claude APIへ渡すテキストは最大2000トークン以内に収めること（コスト管理）

---

## 11. Keepa API 実装仕様（エージェントA必読）

### 使用ライブラリ

```
pip install keepa
```

公式Pythonラッパーを使う。直接HTTPリクエストは書かない。

### ドメイン指定

Amazon.co.jp は `domain='JP'`（内部値=5）を必ず指定する。

```python
import keepa
api = keepa.Keepa(KEEPA_API_KEY)
```

### ASINキャッシュ取得（Best Sellers API）

```python
# カテゴリIDを指定してASINリストを取得
asin_list = api.best_sellers_query(category=CATEGORY_NODE_ID, domain='JP')
# 戻り値: ['B0XXXXXXXX', 'B0YYYYYYYY', ...]
```

**主要カテゴリのnode ID（Amazon.co.jp）：**

| カテゴリ名 | node ID |
|-----------|---------|
| ドラッグストア | 2189494051 |
| ビューティー | 57035011 |
| ホーム＆キッチン | 3828871 |
| 食品・飲料・お酒 | 2189514051 |
| ペット用品 | 2201396051 |
| スポーツ＆アウトドア | 14304371 |
| おもちゃ | 13312011 |
| 文房具・オフィス用品 | 2189707051 |
| DIY・工具 | 2189641051 |
| カー用品 | 2151999051 |

> ⚠️ カテゴリIDはUIのチェックボックスに紐づける。DBの `category` カラムにはカテゴリ名（日本語）を保存する。

### 商品詳細取得（Product Query）

```python
products = api.query(
    asin,
    domain='JP',
    offers=20,          # 出品者情報を取得（Amazon出品チェックに必要）
    only_live_offers=True,  # 現在出品中のもののみ
    history=False,      # 価格履歴不要でトークン節約
    stats=30,           # 直近30日の統計
)
product = products[0]
```

**使用するフィールド一覧：**

| フィールド | 内容 | 使用箇所 |
|-----------|------|---------|
| `product['title']` | 商品名 | 表示・JANコード検索 |
| `product['csv'][0]` | Amazon価格履歴（最新値がAmazon出品価格） | フィルター1・販売価格 |
| `product['offers']` | 出品者リスト | フィルター1 |
| `product['salesRanks']` | カテゴリ別ランク履歴 | ランク確認 |
| `product['packageHeight']` | 梱包高さ(mm) | FBA手数料自動計算 |
| `product['packageLength']` | 梱包長さ(mm) | FBA手数料自動計算 |
| `product['packageWidth']` | 梱包幅(mm) | FBA手数料自動計算 |
| `product['packageWeight']` | 梱包重量(g) | FBA手数料自動計算 |
| `product['fbaFees']` | FBA手数料情報（あれば） | FBA手数料自動計算 |
| `product['rootCategory']` | ルートカテゴリID | カテゴリ手数料率の特定 |

### フィルター1（Amazon出品チェック）の実装方法

```python
def is_amazon_selling(product: dict) -> bool:
    """Amazon.co.jpが現在出品中かどうか判定する"""
    # 方法1: csv[0]（Amazon価格履歴）の最新値が -1 でなければ出品中
    csv_amazon = product.get('csv', [None])[0]
    if csv_amazon and len(csv_amazon) >= 2:
        latest_price = csv_amazon[-1]  # 最新価格
        if latest_price != -1:
            return True

    # 方法2: offers から isAmazon フラグを確認（より確実）
    live_order = product.get('liveOffersOrder', [])
    offers = product.get('offers', [])
    for idx in live_order:
        if offers[idx].get('isAmazon', False):
            return True

    return False
```

### FBA手数料自動計算の実装方法

```python
def calculate_fba_fee(product: dict) -> int:
    """
    KeepaデータからFBA手数料を自動計算する（円）
    fbaFeesフィールドがあればそれを優先、なければサイズ区分で算出
    """
    # keepaが手数料データを持っている場合はそれを使用
    fba_fees = product.get('fbaFees')
    if fba_fees and fba_fees.get('pickAndPackFee', -1) != -1:
        return fba_fees['pickAndPackFee']  # すでに円単位

    # ない場合はサイズ区分から算出（2024年4月改定後の料金）
    h = product.get('packageHeight', 0)  # mm
    l = product.get('packageLength', 0)  # mm
    w = product.get('packageWidth', 0)   # mm
    weight_g = product.get('packageWeight', 0)  # g

    # cm変換
    h_cm, l_cm, w_cm = h/10, l/10, w/10
    weight_kg = (weight_g + 150) / 1000  # 梱包資材150g加算

    # サイズ区分判定（2024年改定後）
    dims = sorted([l_cm, w_cm, h_cm], reverse=True)
    size = classify_fba_size(dims, weight_kg)

    # 手数料テーブル（2024年4月改定後・税込）
    FBA_FEE_TABLE = {
        '小型':       288,
        '標準1':      354,
        '標準2':      410,
        '標準3':      470,
        '標準4':      524,
        '大型1':      756,
        '大型2':      1040,
        '大型3':      1312,
        '大型4':      1640,
        '特大型1':    2117,
        '特大型2':    2700,
        '特大型3':    3700,
        '特大型4':    5625,
    }
    return FBA_FEE_TABLE.get(size, 500)  # 不明な場合は500円をデフォルト

def classify_fba_size(dims: list, weight_kg: float) -> str:
    """商品寸法・重量からFBAサイズ区分を返す"""
    l, w, h = dims[0], dims[1], dims[2]
    if l <= 25 and w <= 18 and h <= 2 and weight_kg <= 0.3:
        return '小型'
    elif l <= 35 and w <= 30 and h <= 3.3 and weight_kg <= 1.0:
        return '標準1'
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 2.0:
        return '標準2'
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 5.0:
        return '標準3'
    elif l <= 45 and w <= 35 and h <= 20 and weight_kg <= 9.0:
        return '標準4'
    elif l <= 80 and w <= 60 and h <= 60 and weight_kg <= 10.0:
        return '大型1'
    elif l <= 100 and w <= 60 and h <= 60 and weight_kg <= 15.0:
        return '大型2'
    elif l <= 120 and w <= 80 and h <= 80 and weight_kg <= 20.0:
        return '大型3'
    elif l <= 150 and w <= 100 and h <= 100 and weight_kg <= 25.0:
        return '大型4'
    else:
        return '特大型1'
```

### カテゴリ別販売手数料率（自動計算用）

```python
# rootCategoryIDから手数料率を引く辞書（代表的なカテゴリ）
REFERRAL_FEE_RATE = {
    2189494051: 0.08,   # ドラッグストア
    57035011:   0.08,   # ビューティー
    3828871:    0.10,   # ホーム＆キッチン
    2189514051: 0.08,   # 食品・飲料
    2201396051: 0.08,   # ペット用品
    14304371:   0.10,   # スポーツ
    13312011:   0.10,   # おもちゃ
    2189707051: 0.10,   # 文房具
    2189641051: 0.10,   # DIY・工具
    2151999051: 0.10,   # カー用品
}
DEFAULT_REFERRAL_FEE_RATE = 0.10  # 不明カテゴリのデフォルト

def get_referral_fee(product: dict, selling_price: int) -> int:
    rate = REFERRAL_FEE_RATE.get(
        product.get('rootCategory'), DEFAULT_REFERRAL_FEE_RATE
    )
    return int(selling_price * rate)
```

### トークン残量監視

```python
# api.tokens_left でトークン残量を確認できる
# keepaライブラリのwait=True（デフォルト）で自動ウェイト制御される
# 明示的に確認したい場合:
remaining = api.tokens_left
if remaining < 10:
    time.sleep(60)  # 1分待機してリフィルを待つ
```

### JANコード未取得時の表示仕様

楽天・Yahoo検索はスキップし、以下の項目のみUIに表示する：

- 商品タイトル
- Amazon販売価格
- AmazonページURL（`https://www.amazon.co.jp/dp/{ASIN}`）
- 「JANコード取得不可 - 仕入れ価格リサーチ不可」のメッセージ（警告色で表示）
- ROI・利益率は「-」で表示

---

## 12. Claude APIプロンプトテンプレート（JANコード抽出）

エージェントAは以下のプロンプトを `jan_resolver.py` にそのまま実装すること。

```python
SYSTEM_PROMPT = """あなたはAmazon商品のJANコードを特定する専門家です。
与えられた検索結果のスニペットから、商品のJANコード（13桁の数字）を抽出してください。
JANコードが見つかった場合は数字のみ（例: 4901234567890）を返してください。
見つからない場合は「NOT_FOUND」のみを返してください。
それ以外の文字は一切出力しないでください。"""

def build_user_prompt(product_title: str, serper_results: list[dict]) -> str:
    snippets = "\n".join([
        f"[{i+1}] タイトル: {r.get('title','')}\n    スニペット: {r.get('snippet','')}"
        for i, r in enumerate(serper_results[:5])
    ])
    return f"商品名: {product_title}\n\n検索結果:\n{snippets}\n\nこの商品のJANコードを教えてください。"
```

---

## 13. カテゴリ選択UI仕様（エージェントB）

UIにチェックボックスリストを設置し、複数カテゴリを同時選択可能にする。

```python
CATEGORY_LIST = [
    ("ドラッグストア",      2189494051),
    ("ビューティー",        57035011),
    ("ホーム＆キッチン",    3828871),
    ("食品・飲料・お酒",    2189514051),
    ("ペット用品",          2201396051),
    ("スポーツ＆アウトドア",14304371),
    ("おもちゃ",            13312011),
    ("文房具・オフィス用品",2189707051),
    ("DIY・工具",           2189641051),
    ("カー用品",            2151999051),
]
# 選択されたカテゴリのnode IDリストをバックエンドに渡す
```

---

## 14. 非機能要件

- **ログ**: `app.log` にローテーティングファイルハンドラで出力（最大5MB × 3世代）
- **エラーハンドリング**: 外部API呼び出しはすべて `try/except` で囲み、エラー時はUIにメッセージ表示してクラッシュしない
- **設定の永続化**: ウィンドウサイズ・APIキー・最後に使ったランク範囲は `config.json` に保存し、次回起動時に復元する
