---
inclusion: auto
---

# Debugging & Error Resolution Constitution

このドキュメントは、テスト実行・エラー修復時にKiroが従うべき絶対的な思考プロセスを定義する。

## 1. Zero Warning Policy（警告の完全エラー化）と例外ハンドリング

- **基本原則:** `pytest` 実行時の Warning は全て Error として扱う（`genai/pytest.ini` に `filterwarnings = error` を設定済み）。
- テスト実行時やリンター実行時に発生した `DeprecationWarning`, `RuntimeWarning`（特にFastAPIやCeleryにおける `coroutine was never awaited` のような非同期関連の警告）、および ESLint/mypy の警告を絶対に無視してはならない。
- Kiroは、エラーだけでなく「全てのWarningがゼロになるまで」修正を完了したとみなしてはならない。

### サードパーティライブラリの例外ハンドリング

- もし `urllib3` や `botocore` など、外部ライブラリの内部から発生する避けられない Warning が原因でテストがクラッシュした場合、**絶対に `pytest.ini` の `error` 設定を削除・無効化してはならない。**
- **正しい対処法:** その Warning の「メッセージ」と「発生源のモジュール」を特定し、`pytest.ini` の `filterwarnings` に **ピンポイントの除外ルール（ホワイトリスト）を追加** することで解決せよ。
- 除外ルールの書式: `ignore:<メッセージパターン>:<Warningクラス>` （例: `ignore:urllib3 v2 only supports OpenSSL:Warning`）
- **現在のホワイトリスト** (`genai/pytest.ini`):
  - `urllib3` — LibreSSL環境でのNotOpenSSLWarning（import時発火のためメッセージパターンで除外）
  - `testcontainers` — `@wait_container_is_ready` デコレータの非推奨警告
  - `pydantic` — class-based config の非推奨警告（Celery等が使用）

## 2. テスト改ざんの禁止 (No Test Degradation)

- 実装コードのバグでテストが落ちた際、**「テストコード側のアサーションを削除する」「PBT（プロパティベーステスト）の条件を緩める」「モックを乱用して無理やりパスさせる」ことを固く禁ずる。**
- テストを修正して良いのは、「要件（Spec）そのものが変更された場合」のみである。

## 3. RCA (Root Cause Analysis) プロセスの強制

- テストエラー、ランタイムエラー、または重大なWarningに遭遇した場合、**いきなり修正コードを出力してはならない。**
- 修正コードを書く前に、必ず以下のフォーマット（思考プロセス）を出力し、根本原因を特定すること：

### 🔍 Root Cause Analysis (RCA)

- **発生したエラー/Warningの正確な内容:** (スタックトレースの核となる部分)
- **表面的な事象:** (例: 「Pydanticのバリデーションエラーが出た」)
- **根本原因 (Root Cause):** (例: 「DBから抽出した時点でタイムゾーン情報が欠落しており、UTCとして扱われていないため」)
- **要件（Spec）との照合:** この修正は要件定義を満たしているか？副作用はないか？
- **修正方針:** (具体的な修正アプローチ)

## 4. コンテキストの再確認（Regression Prevention）

- バグを修正する際、「目の前のエラーを消すこと」に集中しすぎて、別の機能やアーキテクチャを破壊してはならない。
- 修正案が固まったら、必ず一度立ち止まり「この修正によって、他のCeleryキューやフロントエンドの型定義に影響が出ないか？」を自己レビューせよ。
