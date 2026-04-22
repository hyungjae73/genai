# Session: 2026-04-09 (ocr-font-fix)

## Summary
OCRスクリーンショットの□□□（豆腐文字）問題を調査・修正。原因はDockerコンテナに日本語フォントが未インストールのため、Playwrightがスクリーンショット撮影時に日本語文字を□□□でレンダリングしていた。Dockerfileに fonts-noto-cjk を追加してリビルド・再デプロイ完了。

## Tasks Completed
- OCR文字化けの原因特定: Tesseract/OCRエンジン自体は正常（eng+jpn設定済み）、スクリーンショット画像の時点で既に文字化けしていた
- docker/Dockerfile に fonts-noto-cjk を追加
- api/celery-worker/celery-beat イメージリビルド・再デプロイ完了
- fc-list :lang=ja で Noto CJK フォントのインストール確認

## Decisions Made
- fonts-noto-cjk を採用: Noto CJK は Google 製の包括的な CJK フォントで、日本語・中国語・韓国語をカバー

## Open Items
- 再クロールして□□□が解消されたか確認が必要
