# Requirements Document

## Introduction

偽サイト検知の完全なフロー実装とアラートシステムの統合改善を行う。現在、`FakeSiteDetector`のドメイン類似度チェックは実装済みだが、コンテンツ比較フロー（`verify_fake_site()`）がタスクから呼ばれておらず、偽サイト確定判定が動作しない。また、バックエンドの`AlertResponse`スキーマとフロントエンドの`Alert`型に不整合があり、偽サイトアラートのUI表示・ダッシュボード統計・ナビゲーション統合が未実装である。本機能では、検知フローの接続、アラートスキーマの統一、偽サイト専用UIの追加、TakeDown対応を見据えたアラート表示を実現する。

## Glossary

- **FakeSiteDetector**: 偽サイト検知ロジックを提供するクラス。ドメイン類似度（Damerau-Levenshtein距離＋ビジュアル類似文字正規化）とコンテンツ類似度（TF-IDFコサイン類似度＋重要フィールド重み付け）を計算する
- **Damerau-Levenshtein距離**: レーベンシュタイン距離に隣接文字の転置操作を追加した編集距離。タイポスクワッティングの検出精度が向上する
- **ビジュアル類似文字**: 視覚的に紛らわしい文字の組み合わせ（`rn↔m`, `vv↔w`, `cl↔d`等）。事前正規化により検出可能にする
- **複合TLD**: `.co.jp`, `.com.au`等の複数パートからなるトップレベルドメイン
- **SuspiciousDomain**: 疑わしいドメインを表すデータクラス。ドメイン名、類似度スコア、コンテンツ類似度、確定フラグ、正規ドメインを保持する
- **AlertResponse**: バックエンドAPIがアラート情報を返す際のPydanticスキーマ
- **Alert_Model**: SQLAlchemyのAlertテーブルモデル。アラートの永続化を担当する
- **MonitoringSite**: 監視対象サイトのSQLAlchemyモデル。`url`フィールドを持つが`domain`フィールドは持たない
- **scan_fake_sites**: 単一ドメインの偽サイトスキャンを行うCeleryタスク
- **scan_all_fake_sites**: 全監視サイトの偽サイトスキャンを一括実行するCeleryタスク
- **verify_fake_site**: SuspiciousDomainのコンテンツ比較を行い、偽サイト確定判定を返すFakeSiteDetectorのメソッド
- **TakeDown_Action**: 偽サイト確定後に行うドメイン停止要請等の対応アクション
- **Dashboard**: 統計情報を表示するフロントエンドページ
- **AlertTab**: 階層型ビュー内のサイト詳細パネルに表示されるアラートタブコンポーネント
- **CrawlerEngine**: サイトのHTMLコンテンツを取得する非同期クローラー

## Requirements

### Requirement 1: MonitoringSiteモデルからドメイン抽出

**User Story:** As a システム管理者, I want MonitoringSiteのURLからドメインを正しく抽出できるようにしたい, so that 偽サイトスキャンで`site.domain`のAttributeErrorが発生しなくなる

#### Acceptance Criteria

1. THE MonitoringSite SHALL provide a `domain` property that extracts the domain name from the `url` field using URL parsing
2. WHEN the `url` field contains a valid URL with protocol, THE MonitoringSite.domain property SHALL return the hostname without protocol, port, or path
3. WHEN the `url` field contains a URL with `www.` prefix, THE MonitoringSite.domain property SHALL return the domain with `www.` removed
4. IF the `url` field is empty or malformed, THEN THE MonitoringSite.domain property SHALL return an empty string

### Requirement 2: 偽サイト検知フローの完全接続

**User Story:** As a コンプライアンス担当者, I want 類似ドメインの検知からコンテンツ比較・確定判定までの一連のフローが自動実行されるようにしたい, so that 偽サイトが自動的に検知・確定される

#### Acceptance Criteria

1. WHEN scan_fake_sites タスクが類似ドメインを検出した場合, THE scan_fake_sites タスク SHALL 各類似ドメインに対してHTTPリクエストでコンテンツを取得する
2. WHEN 類似ドメインのコンテンツ取得に成功した場合, THE scan_fake_sites タスク SHALL FakeSiteDetector.verify_fake_site()を呼び出してコンテンツ類似度を計算する
3. WHEN 類似ドメインのコンテンツ取得に失敗した場合（DNS解決失敗、タイムアウト、HTTP エラー）, THE scan_fake_sites タスク SHALL 該当ドメインをスキップしてログに記録する
4. WHEN verify_fake_site()がis_confirmed_fake=Trueを返した場合, THE scan_fake_sites タスク SHALL Alert_Modelにalert_type='fake_site'、severity='critical'のアラートレコードを作成する
5. THE scan_all_fake_sites タスク SHALL MonitoringSite.domain プロパティを使用してドメイン名を取得する（`site.domain`属性の直接参照ではなく）

### Requirement 3: AlertResponseスキーマとAlert型の統一

**User Story:** As a フロントエンド開発者, I want バックエンドのAlertResponseスキーマにsite_nameとviolation_typeフィールドが含まれるようにしたい, so that フロントエンドのAlert型と整合性が取れる

#### Acceptance Criteria

1. THE AlertResponse スキーマ SHALL `site_name` フィールド（文字列型、Optional）を含む
2. THE AlertResponse スキーマ SHALL `violation_type` フィールド（文字列型、Optional）を含む
3. THE AlertResponse スキーマ SHALL `is_resolved` フィールド（ブール型）を含む
4. THE AlertResponse スキーマ SHALL `site_id` フィールド（整数型、Optional）を含む
5. WHEN アラートにsite_idが設定されている場合, THE alerts API SHALL 対応するMonitoringSiteのnameをsite_nameとして返す
6. WHEN アラートにviolation_idが設定されている場合, THE alerts API SHALL 対応するViolationのviolation_typeを返す
7. WHEN アラートのalert_typeが'fake_site'の場合, THE alerts API SHALL violation_typeとして'fake_site'を返す

### Requirement 4: 偽サイトアラートのダッシュボード統計表示

**User Story:** As a 管理者, I want ダッシュボードで偽サイト検知の統計情報を確認したい, so that 偽サイトの脅威状況を一目で把握できる

#### Acceptance Criteria

1. THE Dashboard SHALL 偽サイト検知数（alert_type='fake_site'のアラート件数）を統計カードとして表示する
2. THE Dashboard SHALL 未解決の偽サイトアラート件数を統計カードに表示する
3. THE statistics API SHALL `fake_site_alerts` フィールド（偽サイトアラート総数）を返す
4. THE statistics API SHALL `unresolved_fake_site_alerts` フィールド（未解決偽サイトアラート数）を返す

### Requirement 5: アラート一覧のアラート種別フィルタリングと視覚的区別

**User Story:** As a オペレーター, I want アラート一覧で契約違反アラートと偽サイトアラートを視覚的に区別し、種別でフィルタリングしたい, so that 対応が必要なアラートを素早く特定できる

#### Acceptance Criteria

1. THE Alerts ページ SHALL アラート種別フィルター（すべて、契約違反、偽サイト）のセレクトボックスを表示する
2. WHEN アラート種別フィルターで「偽サイト」が選択された場合, THE Alerts ページ SHALL alert_typeが'fake_site'のアラートのみを表示する
3. WHEN アラート種別フィルターで「契約違反」が選択された場合, THE Alerts ページ SHALL alert_typeが'fake_site'以外のアラートのみを表示する
4. THE Alerts ページ SHALL 偽サイトアラートカードに赤色の「偽サイト」バッジを表示する
5. THE Alerts ページ SHALL 契約違反アラートカードに黄色の「契約違反」バッジを表示する
6. THE AlertTab コンポーネント SHALL アラート種別バッジ（偽サイト/契約違反）を各アラートアイテムに表示する

### Requirement 6: グローバルナビゲーションへの偽サイト検知メニュー追加

**User Story:** As a ユーザー, I want グローバルナビゲーションから偽サイト検知ページに直接アクセスしたい, so that 偽サイト関連の情報に素早くアクセスできる

#### Acceptance Criteria

1. THE App コンポーネント SHALL グローバルナビゲーションに「偽サイト検知」リンクを含む
2. THE App コンポーネント SHALL `/fake-sites` ルートに偽サイト検知ページを登録する
3. THE 偽サイト検知ページ SHALL 検知された偽サイトの一覧を表示する（alert_type='fake_site'のアラートをフィルタリング）
4. THE 偽サイト検知ページ SHALL 各偽サイトアラートに対して、検知ドメイン、類似度スコア、検知日時、対応ステータスを表示する

### Requirement 7: TakeDown対応を見据えたアラート表示

**User Story:** As a コンプライアンス担当者, I want 偽サイト検知時にTakeDown対応が必要であることを明確に表示したい, so that 迅速にTakeDown手続きを開始できる

#### Acceptance Criteria

1. WHEN アラートのalert_typeが'fake_site'かつis_resolvedがFalseの場合, THE アラートカード SHALL 「TakeDown対応が必要」の警告バナーを表示する
2. THE 偽サイトアラートカード SHALL 検知された偽ドメイン名を目立つ位置に表示する
3. THE 偽サイトアラートカード SHALL 正規ドメインとの類似度スコアを表示する
4. WHEN 偽サイトアラートのis_resolvedがTrueに変更された場合, THE アラートカード SHALL 「TakeDown対応が必要」バナーを非表示にする

### Requirement 8: Alert_Modelへの偽サイト関連フィールド追加

**User Story:** As a バックエンド開発者, I want Alert_Modelに偽サイト検知に必要な情報を保存できるようにしたい, so that 偽サイトアラートの詳細情報をDBに永続化できる

#### Acceptance Criteria

1. THE Alert_Model SHALL `fake_domain` フィールド（文字列型、nullable）を持つ。偽サイトとして検知されたドメイン名を格納する
2. THE Alert_Model SHALL `legitimate_domain` フィールド（文字列型、nullable）を持つ。正規ドメイン名を格納する
3. THE Alert_Model SHALL `domain_similarity_score` フィールド（浮動小数点型、nullable）を持つ。ドメイン類似度スコアを格納する
4. THE Alert_Model SHALL `content_similarity_score` フィールド（浮動小数点型、nullable）を持つ。コンテンツ類似度スコアを格納する
5. THE AlertResponse スキーマ SHALL 上記4フィールドをレスポンスに含む

### Requirement 9: ドメイン類似度アルゴリズムの改善

**User Story:** As a セキュリティ担当者, I want ドメイン類似度の検出精度を向上させたい, so that ビジュアル類似文字や文字転置を使った巧妙なタイポスクワッティングも検知できる

#### Acceptance Criteria

1. THE FakeSiteDetector SHALL レーベンシュタイン距離の代わりにDamerau-Levenshtein距離を使用する（隣接文字の転置を1操作として扱う）
2. THE FakeSiteDetector SHALL ドメイン比較前にビジュアル類似文字の正規化を行う（`rn→m`, `vv→w`, `cl→d`, `nn→m`等のマッピングを適用）
3. THE FakeSiteDetector SHALL ドメイン比較時にハイフンを除去した文字列でも追加比較を行い、高い方の類似度スコアを採用する
4. THE _generate_candidate_domains 関数 SHALL ハイフン追加・削除パターンの候補を生成に含める
5. THE _normalize_domain メソッド SHALL 複合TLD（`.co.jp`, `.com.au`等）を正しく処理する（`rsplit('.', 1)`ではなく既知TLDリストまたはパターンマッチで分割する）

### Requirement 10: コンテンツ類似度アルゴリズムの改善

**User Story:** As a セキュリティ担当者, I want コンテンツ類似度の判定精度を向上させたい, so that 偽サイトの確定判定がより正確になる

#### Acceptance Criteria

1. THE FakeSiteDetector SHALL コンテンツ比較時にIDF（逆文書頻度）の重み付けを適用する（現行は単語頻度のみでIDFなし）
2. THE FakeSiteDetector SHALL 商品名・価格・ブランド名等の重要フィールドが一致する場合、コンテンツ類似度スコアにボーナス重みを加算する
3. THE FakeSiteDetector SHALL HTMLのDOM構造（タグ階層、主要CSSクラス名）の類似度を補助指標として計算する
4. THE FakeSiteDetector SHALL スクリーンショット画像のパーセプチュアルハッシュ（pHash）比較による視覚的類似度を補助指標として計算する
5. THE FakeSiteDetector SHALL 最終的なコンテンツ類似度スコアを、テキスト類似度（重み0.4）、フィールド一致度（重み0.3）、構造類似度（重み0.15）、視覚類似度（重み0.15）の加重平均で算出する
