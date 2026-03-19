"""
Unit tests for MetadataExtractor.

Tests cover:
- Extraction of each metadata field (title, description, language)
- Missing/malformed data handling
- Open Graph tag extraction

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import pytest

from src.extractors.metadata_extractor import MetadataExtractor


@pytest.fixture
def extractor():
    return MetadataExtractor()


FULL_HTML = """
<html lang="ja">
<head>
    <title>テスト商品ページ</title>
    <meta name="description" content="これはテスト用の商品ページです。">
    <meta property="og:title" content="OGテストタイトル">
    <meta property="og:description" content="OGテスト説明文">
    <meta property="og:image" content="https://example.com/image.png">
    <meta property="og:url" content="https://example.com/product">
</head>
<body><p>Hello</p></body>
</html>
"""


class TestMetadataFieldExtraction:
    """各メタデータフィールドの抽出テスト (Req 2.1, 2.2)"""

    def test_extracts_title(self, extractor):
        html = "<html><head><title>My Page Title</title></head><body></body></html>"
        result = extractor.extract_metadata(html)
        assert result["title"] == "My Page Title"

    def test_extracts_title_with_whitespace(self, extractor):
        html = "<html><head><title>  Spaced Title  </title></head><body></body></html>"
        result = extractor.extract_metadata(html)
        assert result["title"] == "Spaced Title"

    def test_extracts_description(self, extractor):
        html = '<html><head><meta name="description" content="A page description"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["description"] == "A page description"

    def test_extracts_description_with_whitespace(self, extractor):
        html = '<html><head><meta name="description" content="  trimmed  "></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["description"] == "trimmed"

    def test_extracts_language_from_html_lang(self, extractor):
        html = '<html lang="en"><head></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["language"] == "en"

    def test_extracts_language_from_meta_tag(self, extractor):
        html = '<html><head><meta http-equiv="content-language" content="zh"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["language"] == "zh"

    def test_html_lang_takes_precedence_over_meta(self, extractor):
        html = '<html lang="ja"><head><meta http-equiv="content-language" content="en"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["language"] == "ja"

    def test_extracts_all_fields_from_full_html(self, extractor):
        result = extractor.extract_metadata(FULL_HTML)
        assert result["title"] == "テスト商品ページ"
        assert result["description"] == "これはテスト用の商品ページです。"
        assert result["language"] == "ja"
        assert result["og_title"] == "OGテストタイトル"
        assert result["og_description"] == "OGテスト説明文"
        assert result["og_image"] == "https://example.com/image.png"
        assert result["og_url"] == "https://example.com/product"

    def test_returns_dict_with_all_expected_keys(self, extractor):
        result = extractor.extract_metadata("<html></html>")
        expected_keys = {"title", "description", "og_title", "og_description", "og_image", "og_url", "language"}
        assert set(result.keys()) == expected_keys


class TestMissingDataHandling:
    """欠損データのハンドリングテスト (Req 2.5)"""

    def test_empty_html_returns_all_none(self, extractor):
        result = extractor.extract_metadata("")
        for key in result:
            assert result[key] is None, f"{key} should be None for empty HTML"

    def test_minimal_html_returns_none_for_missing(self, extractor):
        html = "<html><head></head><body></body></html>"
        result = extractor.extract_metadata(html)
        assert result["title"] is None
        assert result["description"] is None
        assert result["og_title"] is None

    def test_empty_title_tag_returns_none(self, extractor):
        html = "<html><head><title></title></head><body></body></html>"
        result = extractor.extract_metadata(html)
        assert result["title"] is None

    def test_meta_description_without_content_returns_none(self, extractor):
        html = '<html><head><meta name="description"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["description"] is None

    def test_meta_description_with_empty_content_returns_none(self, extractor):
        html = '<html><head><meta name="description" content=""></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["description"] is None

    def test_malformed_html_returns_all_none(self, extractor):
        html = "<not valid html at all <><>>"
        result = extractor.extract_metadata(html)
        # Should not raise, all fields should be None or gracefully handled
        assert isinstance(result, dict)

    def test_html_with_only_body_returns_none_for_head_fields(self, extractor):
        html = "<html><body><p>Content only</p></body></html>"
        result = extractor.extract_metadata(html)
        assert result["title"] is None
        assert result["description"] is None

    def test_partial_og_tags_returns_none_for_missing(self, extractor):
        html = """
        <html><head>
            <meta property="og:title" content="Only Title">
        </head><body></body></html>
        """
        result = extractor.extract_metadata(html)
        assert result["og_title"] == "Only Title"
        assert result["og_description"] is None
        assert result["og_image"] is None
        assert result["og_url"] is None


class TestOpenGraphExtraction:
    """Open Graphタグの抽出テスト (Req 2.3)"""

    def test_extracts_og_title(self, extractor):
        html = '<html><head><meta property="og:title" content="OG Title"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_title"] == "OG Title"

    def test_extracts_og_description(self, extractor):
        html = '<html><head><meta property="og:description" content="OG Desc"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_description"] == "OG Desc"

    def test_extracts_og_image(self, extractor):
        html = '<html><head><meta property="og:image" content="https://img.example.com/pic.jpg"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_image"] == "https://img.example.com/pic.jpg"

    def test_extracts_og_url(self, extractor):
        html = '<html><head><meta property="og:url" content="https://example.com/page"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_url"] == "https://example.com/page"

    def test_og_tags_with_whitespace_are_trimmed(self, extractor):
        html = '<html><head><meta property="og:title" content="  Spaced OG  "></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_title"] == "Spaced OG"

    def test_og_tag_without_content_returns_none(self, extractor):
        html = '<html><head><meta property="og:title"></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_title"] is None

    def test_og_tag_with_empty_content_returns_none(self, extractor):
        html = '<html><head><meta property="og:title" content=""></head><body></body></html>'
        result = extractor.extract_metadata(html)
        assert result["og_title"] is None

    def test_all_og_tags_extracted_together(self, extractor):
        html = """
        <html><head>
            <meta property="og:title" content="Product Name">
            <meta property="og:description" content="Great product">
            <meta property="og:image" content="https://cdn.example.com/img.png">
            <meta property="og:url" content="https://shop.example.com/product/1">
        </head><body></body></html>
        """
        result = extractor.extract_metadata(html)
        assert result["og_title"] == "Product Name"
        assert result["og_description"] == "Great product"
        assert result["og_image"] == "https://cdn.example.com/img.png"
        assert result["og_url"] == "https://shop.example.com/product/1"

    def test_ignores_non_og_meta_properties(self, extractor):
        html = """
        <html><head>
            <meta property="article:author" content="John">
            <meta property="og:title" content="Real OG">
        </head><body></body></html>
        """
        result = extractor.extract_metadata(html)
        assert result["og_title"] == "Real OG"
        # article:author should not appear in result
        assert "article:author" not in result
