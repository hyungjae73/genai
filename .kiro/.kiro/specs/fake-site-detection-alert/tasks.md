# Implementation Plan: 偽サイト検知アラート

## Overview

偽サイト検知の完全なフロー実装とアラートシステムの統合改善を段階的に実装する。バックエンドのモデル拡張・アルゴリズム改善・検知フロー接続を先に行い、次にAPI層を整備し、最後にフロントエンドのUI統合を行う。

## Tasks

- [x] 1. MonitoringSiteモデルのdomainプロパティとAlert_Modelの偽サイトフィールド追加
  - [x] 1.1 MonitoringSite.domain プロパティを実装する
    - `genai/src/models.py` の `MonitoringSite` クラスに `@property def domain(self) -> str` を追加
    - `urllib.parse.urlparse` でホスト名を抽出し、`www.` プレフィックスを除去
    - 空文字列・不正URLの場合は空文字列を返す
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Property 1: ドメイン抽出の正確性のプロパティテストを書く
    - **Property 1: ドメイン抽出の正確性**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ランダムURL生成 → domain プロパティ → hostname一致検証
    - プロトコル・ポート・パス・www.プレフィックスの除去を検証
    - 空文字列・不正URLで空文字列を返すことを検証
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

  - [x] 1.3 Alert_Model に偽サイト関連フィールドを追加する
    - `genai/src/models.py` の `Alert` クラスに以下を追加:
      - `fake_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)`
      - `legitimate_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)`
      - `domain_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)`
      - `content_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)`
    - `ix_alerts_fake_domain` インデックスを `__table_args__` に追加
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.4 Alert_Model 新規フィールドのユニットテストを書く
    - `genai/tests/test_fake_site_properties.py` にフィールド存在確認テストを追加
    - 各フィールドの型・nullable設定を検証
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 2. ドメイン類似度アルゴリズムの改善
  - [x] 2.1 Damerau-Levenshtein距離を実装する
    - `genai/src/fake_detector.py` の `_levenshtein_distance` を `_damerau_levenshtein_distance` に置き換え
    - 隣接文字の転置を1操作として扱うアルゴリズムを実装
    - `calculate_domain_similarity` から新メソッドを呼び出すよう変更
    - _Requirements: 9.1_

  - [x] 2.2 Property 9: Damerau-Levenshtein距離の転置操作のプロパティテストを書く
    - **Property 9: Damerau-Levenshtein距離の転置操作**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ランダム文字列 → 隣接文字転置 → DL距離=1検証
    - **Validates: Requirements 9.1**

  - [x] 2.3 ビジュアル類似文字の正規化を実装する
    - `genai/src/fake_detector.py` に `VISUAL_SIMILAR_CHARS` マッピングと `_normalize_visual_chars` メソッドを追加
    - `calculate_domain_similarity` でドメイン比較前にビジュアル正規化を適用
    - _Requirements: 9.2_

  - [x] 2.4 Property 10: ビジュアル類似文字の正規化のプロパティテストを書く
    - **Property 10: ビジュアル類似文字の正規化**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ビジュアル類似文字含むランダムドメイン → 正規化 → 冪等性検証
    - **Validates: Requirements 9.2**

  - [x] 2.5 ハイフン除去による追加比較を実装する
    - `genai/src/fake_detector.py` の `calculate_domain_similarity` にハイフン除去比較ロジックを追加
    - ハイフンあり/なし両方で比較し、高い方のスコアを採用
    - _Requirements: 9.3_

  - [x] 2.6 Property 11: ハイフン除去による類似度最大化のプロパティテストを書く
    - **Property 11: ハイフン除去による類似度最大化**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ハイフン含むランダムドメインペア → 類似度比較 → max検証
    - **Validates: Requirements 9.3**

  - [x] 2.7 _generate_candidate_domains にハイフンパターンを追加する
    - `genai/src/tasks.py` の `_generate_candidate_domains` にハイフン追加・削除パターンを追加
    - ハイフン含むドメインはハイフン削除版を候補に追加
    - ハイフンなしドメイン（長さ>=4）はハイフン挿入版を候補に追加
    - _Requirements: 9.4_

  - [x] 2.8 Property 12: 候補ドメインのハイフンパターン生成のプロパティテストを書く
    - **Property 12: 候補ドメインのハイフンパターン生成**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ランダムドメイン → 候補生成 → ハイフンパターン含有検証
    - **Validates: Requirements 9.4**

  - [x] 2.9 複合TLDの正規化を実装する
    - `genai/src/fake_detector.py` に `COMPOUND_TLDS` リストを追加
    - `_normalize_domain` メソッドを複合TLD対応に改修（`rsplit('.', 1)` ではなくパターンマッチで分割）
    - `genai/src/tasks.py` の `_generate_candidate_domains` も複合TLD対応に改修
    - _Requirements: 9.5_

  - [x] 2.10 Property 13: 複合TLDの正規化のプロパティテストを書く
    - **Property 13: 複合TLDの正規化**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - 複合TLD付きランダムドメイン → 正規化 → TLD分離検証
    - **Validates: Requirements 9.5**

- [x] 3. Checkpoint - ドメイン類似度改善の検証
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. コンテンツ類似度アルゴリズムの改善
  - [x] 4.1 IDF重み付けを実装する
    - `genai/src/fake_detector.py` の `_calculate_word_frequency` を TF-IDF 方式に改修
    - 2文書間のIDF計算ロジックを追加
    - `calculate_content_similarity` から新ロジックを呼び出す
    - _Requirements: 10.1_

  - [x] 4.2 重要フィールド一致度の計算を実装する
    - `genai/src/fake_detector.py` に `calculate_field_similarity` メソッドを追加
    - 商品名・価格・ブランド名等の重要フィールドをHTMLから抽出して比較
    - _Requirements: 10.2_

  - [x] 4.3 Property 14: 重要フィールド一致によるボーナス加算のプロパティテストを書く
    - **Property 14: 重要フィールド一致によるボーナス加算**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - 重要フィールドが一致するHTML → コンテンツ類似度 >= フィールドなし類似度を検証
    - **Validates: Requirements 10.2**

  - [x] 4.4 DOM構造類似度の計算を実装する
    - `genai/src/fake_detector.py` に `calculate_structure_similarity` メソッドを追加
    - HTMLのタグ階層・主要CSSクラス名の類似度を計算
    - _Requirements: 10.3_

  - [x] 4.5 pHash視覚類似度の計算を実装する
    - `genai/src/fake_detector.py` に `calculate_visual_similarity` メソッドを追加
    - `imagehash` ライブラリを使用してパーセプチュアルハッシュ比較を実装
    - ImportErrorをキャッチし、ライブラリ未インストール時は0.0を返す
    - _Requirements: 10.4_

  - [x] 4.6 コンテンツ類似度の加重平均を実装する
    - `genai/src/fake_detector.py` の `calculate_content_similarity` を改修
    - テキスト類似度(0.4) + フィールド一致度(0.3) + 構造類似度(0.15) + 視覚類似度(0.15) の加重平均
    - スクリーンショット撮影失敗時の重み再配分ロジックを実装
    - _Requirements: 10.5_

  - [x] 4.7 Property 15: コンテンツ類似度の加重平均のプロパティテストを書く
    - **Property 15: コンテンツ類似度の加重平均**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ランダムサブスコア4つ → 加重平均 → 数値一致検証（0.4, 0.3, 0.15, 0.15）
    - 結果が [0.0, 1.0] の範囲内であることを検証
    - **Validates: Requirements 10.5**

- [x] 5. Checkpoint - コンテンツ類似度改善の検証
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 偽サイト検知フローの完全接続
  - [x] 6.1 scan_fake_sites タスクに verify_fake_site() 呼び出しを接続する
    - `genai/src/tasks.py` の `_scan_fake_sites_async` を改修
    - 各類似ドメインに対して `httpx` で GET リクエストしてコンテンツを取得
    - コンテンツ取得成功時: `FakeSiteDetector.verify_fake_site()` を呼び出し
    - コンテンツ取得失敗時（DNS解決失敗、タイムアウト、HTTPエラー）: スキップしてログ記録
    - Playwright でスクリーンショットを撮影し、視覚類似度計算に使用
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 6.2 確定偽サイトのアラートレコード作成を実装する
    - `_scan_fake_sites_async` 内で `is_confirmed_fake=True` の場合に `Alert` レコードを作成
    - `alert_type='fake_site'`, `severity='critical'` を設定
    - `fake_domain`, `legitimate_domain`, `domain_similarity_score`, `content_similarity_score` を設定
    - _Requirements: 2.4, 8.1, 8.2, 8.3, 8.4_

  - [x] 6.3 Property 2: 確定偽サイトのアラート生成のプロパティテストを書く
    - **Property 2: 確定偽サイトのアラート生成**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - is_confirmed_fake=True の SuspiciousDomain → Alert レコードの各フィールド検証
    - **Validates: Requirements 2.4, 8.1, 8.2, 8.3, 8.4**

  - [x] 6.4 scan_all_fake_sites で MonitoringSite.domain プロパティを使用するよう確認・修正する
    - `genai/src/tasks.py` の `scan_all_fake_sites` が `site.domain` プロパティを正しく使用していることを確認
    - 既に `site.domain` を参照しているが、プロパティ実装後に正常動作することを検証
    - _Requirements: 2.5_

  - [x] 6.5 検知フローのユニットテストを書く
    - `genai/tests/test_fake_site_properties.py` に verify_fake_site() 呼び出しフローのテストを追加
    - HTTPリクエスト失敗時のスキップ動作テスト
    - モック使用で httpx, Playwright の外部依存を分離
    - _Requirements: 2.1, 2.2, 2.3_

- [x] 7. AlertResponse スキーマとAlerts API の拡張
  - [x] 7.1 AlertResponse スキーマにフィールドを追加する
    - `genai/src/api/schemas.py` の `AlertResponse` に以下を追加:
      - `site_name: Optional[str] = None`
      - `violation_type: Optional[str] = None`
      - `is_resolved: bool`
      - `site_id: Optional[int] = None`
      - `fake_domain: Optional[str] = None`
      - `legitimate_domain: Optional[str] = None`
      - `domain_similarity_score: Optional[float] = None`
      - `content_similarity_score: Optional[float] = None`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 8.5_

  - [x] 7.2 Alerts API に site_name と violation_type の解決ロジックを追加する
    - `genai/src/api/alerts.py` の `list_alerts` と `get_alert` を改修
    - `site_id` が設定されている場合、MonitoringSite の name を `site_name` として返す
    - `alert_type='fake_site'` の場合、`violation_type='fake_site'` を返す
    - `violation_id` が設定されている場合、Violation の violation_type を返す
    - _Requirements: 3.5, 3.6, 3.7_

  - [x] 7.3 Alerts API に alert_type フィルターパラメータを追加する
    - `genai/src/api/alerts.py` の `list_alerts` に `alert_type` クエリパラメータを追加
    - フィルタリングロジックを実装
    - _Requirements: 5.2, 5.3_

  - [x] 7.4 Property 3 & 4: API site_name/violation_type 解決のプロパティテストを書く
    - **Property 3: API site_name解決**
    - **Property 4: API violation_type解決**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - site_id 設定時の site_name 解決を検証
    - alert_type='fake_site' 時の violation_type='fake_site' を検証
    - **Validates: Requirements 3.5, 3.6, 3.7**

- [x] 8. Statistics API の偽サイト統計拡張
  - [x] 8.1 MonitoringStatistics スキーマに偽サイト統計フィールドを追加する
    - `genai/src/api/schemas.py` の `MonitoringStatistics` に以下を追加:
      - `fake_site_alerts: int`
      - `unresolved_fake_site_alerts: int`
    - _Requirements: 4.3, 4.4_

  - [x] 8.2 Statistics API エンドポイントに偽サイト統計クエリを追加する
    - `genai/src/api/monitoring.py` の `get_statistics` に偽サイトアラートのカウントクエリを追加
    - `Alert` モデルをインポートし、`alert_type='fake_site'` でフィルタリング
    - `is_resolved=False` で未解決カウントを取得
    - _Requirements: 4.3, 4.4_

  - [x] 8.3 Property 5: 偽サイト統計カウントの正確性のプロパティテストを書く
    - **Property 5: 偽サイト統計カウントの正確性**
    - `genai/tests/test_fake_site_properties.py` に hypothesis を使用してテストを追加
    - ランダムなアラートデータ → 統計API → カウント一致検証
    - **Validates: Requirements 4.3, 4.4**

- [x] 9. Checkpoint - バックエンド全体の検証
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. フロントエンド Alert 型と API 関数の拡張
  - [x] 10.1 Alert インターフェースに偽サイト関連フィールドを追加する
    - `genai/frontend/src/services/api.ts` の `Alert` インターフェースに以下を追加:
      - `alert_type: string`
      - `fake_domain?: string`
      - `legitimate_domain?: string`
      - `domain_similarity_score?: number`
      - `content_similarity_score?: number`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 8.5_

  - [x] 10.2 Statistics インターフェースに偽サイト統計フィールドを追加する
    - `genai/frontend/src/services/api.ts` の `Statistics` インターフェースに以下を追加:
      - `fake_site_alerts: number`
      - `unresolved_fake_site_alerts: number`
    - _Requirements: 4.3, 4.4_

- [x] 11. Dashboard 偽サイト統計カード表示
  - [x] 11.1 Dashboard に偽サイト統計カードを追加する
    - `genai/frontend/src/pages/Dashboard.tsx` の `stats-grid` に偽サイト検知数カードと未解決偽サイトアラート数カードを追加
    - `statistics.fake_site_alerts` と `statistics.unresolved_fake_site_alerts` を表示
    - データが返らない場合は 0 として表示
    - _Requirements: 4.1, 4.2_

  - [x] 11.2 Dashboard 偽サイト統計カードのユニットテストを書く
    - `genai/frontend/src/pages/__tests__/Dashboard.test.tsx` にテストを追加
    - 偽サイト統計カードの表示を検証
    - _Requirements: 4.1, 4.2_

- [x] 12. Alerts ページのアラート種別フィルタリングとバッジ表示
  - [x] 12.1 Alerts ページにアラート種別フィルターを追加する
    - `genai/frontend/src/pages/Alerts.tsx` にアラート種別セレクトボックスを追加
    - フィルターオプション: すべて / 契約違反 / 偽サイト
    - フィルタリングロジック: 「偽サイト」→ `alert_type='fake_site'`、「契約違反」→ `alert_type!='fake_site'`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 12.2 Alerts ページにアラート種別バッジを追加する
    - `genai/frontend/src/pages/Alerts.tsx` のアラートカードにバッジを追加
    - 偽サイトアラート: 赤色「偽サイト」バッジ
    - 契約違反アラート: 黄色「契約違反」バッジ
    - _Requirements: 5.4, 5.5_

  - [x] 12.3 Alerts ページに TakeDown 対応バナーを追加する
    - `genai/frontend/src/pages/Alerts.tsx` のアラートカードに TakeDown 警告バナーを追加
    - `alert_type='fake_site'` かつ `is_resolved=False` の場合に「TakeDown対応が必要」バナーを表示
    - 偽ドメイン名と類似度スコアを表示
    - `is_resolved=True` の場合はバナー非表示
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 12.4 Property 6: アラート種別フィルタリングのプロパティテストを書く
    - **Property 6: アラート種別フィルタリング**
    - `genai/frontend/src/pages/__tests__/Alerts.test.tsx` に fast-check を使用してテストを追加
    - ランダムアラートリスト → フィルタリング → 結果検証
    - **Validates: Requirements 5.2, 5.3**

  - [x] 12.5 Property 7: TakeDownバナーの条件付き表示のプロパティテストを書く
    - **Property 7: TakeDownバナーの条件付き表示**
    - `genai/frontend/src/pages/__tests__/Alerts.test.tsx` に fast-check を使用してテストを追加
    - ランダム偽サイトアラート → TakeDownバナー表示条件検証
    - **Validates: Requirements 7.1, 7.4**

- [x] 13. 偽サイト検知ページの新規作成とナビゲーション統合
  - [x] 13.1 FakeSites ページを新規作成する
    - `genai/frontend/src/pages/FakeSites.tsx` を新規作成
    - `alert_type='fake_site'` のアラートをフィルタリングして一覧表示
    - 各アラートに検知ドメイン、類似度スコア、検知日時、対応ステータスを表示
    - _Requirements: 6.3, 6.4_

  - [x] 13.2 Property 8: 偽サイトアラート表示の完全性のプロパティテストを書く
    - **Property 8: 偽サイトアラート表示の完全性**
    - `genai/frontend/src/pages/__tests__/FakeSites.test.tsx` に fast-check を使用してテストを追加
    - ランダム偽サイトアラート → 表示項目の完全性検証（ドメイン、スコア、日時、ステータス）
    - **Validates: Requirements 6.4**

  - [x] 13.3 App.tsx にナビゲーションリンクとルートを追加する
    - `genai/frontend/src/App.tsx` のグローバルナビに「偽サイト検知」リンクを追加
    - `/fake-sites` ルートに `FakeSites` コンポーネントを登録
    - _Requirements: 6.1, 6.2_

  - [x] 13.4 ナビゲーションとルーティングのユニットテストを書く
    - `genai/frontend/src/pages/__tests__/FakeSites.test.tsx` にナビリンク存在確認テストを追加
    - `/fake-sites` ルートの動作確認テスト
    - _Requirements: 6.1, 6.2_

- [x] 14. AlertTab コンポーネントのアラート種別バッジ追加
  - [x] 14.1 AlertTab にアラート種別バッジを追加する
    - `genai/frontend/src/components/hierarchy/tabs/AlertTab.tsx` の各アラートアイテムにバッジを追加
    - 偽サイト: 赤色「偽サイト」バッジ、契約違反: 黄色「契約違反」バッジ
    - _Requirements: 5.6_

  - [x] 14.2 AlertTab バッジ表示のユニットテストを書く
    - `genai/frontend/src/components/hierarchy/tabs/AlertTab.test.tsx` にテストを追加
    - アラート種別バッジの表示を検証
    - _Requirements: 5.6_

- [x] 15. Final checkpoint - 全テスト実行と最終検証
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Backend property tests use `hypothesis` (Python), frontend property tests use `fast-check` (TypeScript)
- Checkpoints ensure incremental validation at key milestones
- 既存テストの失敗（CrawlResultComparison.test.tsx、Docker CI/CD関連の約20件）は本機能とは無関係のため無視してよい
