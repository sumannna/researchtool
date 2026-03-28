# せどりリサーチツール 引き継ぎドキュメント

作成日: 2026-03-29

---

## プロジェクト概要

Windows デスクトップ向けせどり（転売）リサーチツール。
Python 3.11 + CustomTkinter GUI。
Keepa / Claude / Serper / 楽天 / Yahoo Shopping API を組み合わせて、Amazon で利益の出る商品を自動探索する。

- **リポジトリ**: `git@github.com:sumannna/researchtool.git`
- **作業ディレクトリ**: `C:\Users\suma\researchtool`
- **Python**: `C:/Users/suma/AppData/Local/Programs/Python/Python311/python.exe`
- **起動コマンド**: `python main.py`

---

## ディレクトリ構成

```
researchtool/
├── main.py                        # エントリポイント（ログ設定・DB初期化・App起動）
├── CLAUDE.md                      # 仕様書（必ず参照）
├── config.json                    # APIキー保存先（自動生成）
├── sedori.db                      # SQLite DB（自動生成）
├── backend/
│   ├── __init__.py                # ResearchResult / PriceItem dataclass, run_research()
│   ├── config_loader.py           # load_config / save_config / get_key / update_key
│   ├── db.py                      # SQLite CRUD（asin_cache / research_results / cache_fetch_log）
│   ├── keepa_client.py            # Keepa API ラッパー（シングルトン、非同期対応）
│   ├── asin_cache.py              # ASINキャッシュ更新（7日間隔）
│   ├── filter_engine.py           # Amazon出品チェック・禁止キーワードフィルター
│   ├── jan_resolver.py            # JANコード解決（Serper検索 → Claude抽出）
│   ├── price_fetcher.py           # 楽天・Yahoo価格取得
│   └── roi_calculator.py          # FBA手数料・利益率・ROI計算
├── frontend/
│   ├── app.py                     # メインウィンドウ
│   ├── styles.py                  # カラー・フォント定数
│   └── components/
│       ├── settings_dialog.py     # APIキー設定ダイアログ
│       ├── filter_panel.py        # ランク範囲・カテゴリ選択
│       ├── result_list.py         # 結果カード一覧
│       ├── discount_input.py      # 仕入れ値入力（金額/割引率）
│       ├── auto_mode_panel.py     # 自動実行モード（タイマー）
│       └── url_label.py           # クリッカブルURLラベル
└── tests/
    ├── test_roi_calculator.py     # 22テスト
    ├── test_filter_engine.py      # 20テスト
    ├── test_jan_resolver.py       # 25テスト
    ├── test_keepa_client.py       # 12テスト
    └── mock_responses/            # モックJSON（keepa_product / serper_result / rakuten_result / yahoo_result）
```

---

## 実装済み機能

### バックエンド

| モジュール | 主な関数 | 概要 |
|---|---|---|
| `config_loader` | `get_key(name)`, `save_config()` | APIキーを `config.json` に永続化 |
| `db` | `init_db()`, `bulk_upsert_asins()`, `pick_random_asin()`, `mark_excluded()`, `save_research_result()` | SQLite 3テーブル管理 |
| `keepa_client` | `get_product(asin)`, `best_sellers_query(category)`, `reset_api()` | Keepa シングルトン、トークン不足時60秒スリープ |
| `asin_cache` | `refresh_if_needed()`, `pick_asin()` | 7日間隔でキャッシュ更新 |
| `filter_engine` | `apply_filters(asin, product)` | Amazon直売除外・禁止キーワード除外 |
| `jan_resolver` | `resolve_jan(title)` | Serper検索→Claude(haiku)でJANコード抽出 |
| `price_fetcher` | `fetch_rakuten_prices()`, `fetch_yahoo_prices()` | 最大5件、単価順ソート |
| `roi_calculator` | `calculate_profit()`, `classify_fba_size()` | FBA手数料テーブル・紹介料率辞書 |

### フロントエンド

- asyncio ループを daemon スレッドで別途起動し、`run_coroutine_threadsafe` でバックエンドを非同期実行
- バッチ実行はキュー（`_research_queue`）で管理し、`_run_next()` / `_on_research_done()` で逐次実行

---

## 修正済みバグ

| # | 症状 | 原因 | 修正箇所 |
|---|---|---|---|
| 1 | 最初のカード追加時 TclError | `pack(before=None)` | `result_list.py` — `if self._cards` で条件分岐 |
| 2 | 自動モードのタイマーがUIクラッシュ | Timer スレッドから直接UI操作 | `auto_mode_panel.py` — `self.after(0, lambda: ...)` に変更 |
| 3 | バッチ2件目以降がスキップされる | `_is_researching` フラグが解除されない | `app.py` — `_research_queue` + `_run_next()` パターンに変更 |
| 4 | 設定ダイアログを×で閉じるとAPIキーがリセットされる | `WM_DELETE_WINDOW` 未バインド | `settings_dialog.py` — `self.protocol("WM_DELETE_WINDOW", self._save)` 追加 |

---

## テスト実行

```bash
cd C:/Users/suma/researchtool
C:/Users/suma/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/ -v
```

- 計84テスト（test_jan_resolver の関数名はASCIIのみ — Windowsでエンコードエラー回避のため）

---

## 設定方法

1. アプリ起動後、右上の「設定」ボタンをクリック
2. 各APIキーを入力
3. ×ボタンまたは「保存」ボタンで閉じると `config.json` に保存される

| キー名 | 用途 |
|---|---|
| `keepa_api_key` | Keepa API（ASIN取得・商品詳細） |
| `claude_api_key` | Claude API（JANコード抽出） |
| `serper_api_key` | Serper API（Google検索） |
| `rakuten_api_key` | 楽天 API（仕入れ価格取得） |
| `yahoo_client_id` | Yahoo ショッピング API（仕入れ価格取得） |

---

## Gitコミット履歴

```
d90823a Add backend/db.py      ← 全ファイル実装・バグ修正済みのコミット
d08c82c Delete README.md
d6fd978 Add files via upload
37aa827 Initial commit
```

---

## 既知の課題・今後の検討事項

- `config.json` のAPIキーは平文保存（暗号化は未実装）
- ログファイルの文字化け（Windowsのコードページ問題、動作には影響なし）
- PyInstaller による exe 化は未実施（CLAUDE.md に手順あり）
- `price_fetcher.py` の `detect_set_count()` は正規表現ベースで精度改善の余地あり

---

## 参照ファイル

- 仕様の詳細: `C:\Users\suma\researchtool\CLAUDE.md`
- 元の仕様書: `C:\Users\suma\Desktop\Claude\せどりツール\CLAUDE.md`
