"""
Metadata Extractor - HTMLからページメタデータを抽出するコンポーネント。

HTMLのtitleタグ、meta descriptionタグ、Open Graphタグからメタデータを抽出します。
抽出失敗時はnullを設定して処理を継続します。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import logging
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """HTMLからページメタデータを抽出するクラス。"""

    def extract_metadata(self, html: str) -> dict:
        """
        HTMLからメタデータを抽出する。

        Args:
            html: HTML文字列

        Returns:
            メタデータを含む辞書。抽出できなかったフィールドはNone。
            {
                "title": str | None,
                "description": str | None,
                "og_title": str | None,
                "og_description": str | None,
                "og_image": str | None,
                "og_url": str | None,
                "language": str | None,
            }
        """
        result = {
            "title": None,
            "description": None,
            "og_title": None,
            "og_description": None,
            "og_image": None,
            "og_url": None,
            "language": None,
        }

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.error("Failed to parse HTML: %s", e)
            return result

        result["title"] = self._extract_title(soup)
        result["description"] = self._extract_description(soup)
        result["language"] = self._extract_language(soup)

        og_tags = self._extract_og_tags(soup)
        result["og_title"] = og_tags.get("og_title")
        result["og_description"] = og_tags.get("og_description")
        result["og_image"] = og_tags.get("og_image")
        result["og_url"] = og_tags.get("og_url")

        return result

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """titleタグからページタイトルを抽出する。"""
        try:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                return title_tag.string.strip()
        except Exception as e:
            logger.warning("Failed to extract title: %s", e)
        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """meta descriptionタグから説明文を抽出する。"""
        try:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                return meta_desc["content"].strip()
        except Exception as e:
            logger.warning("Failed to extract description: %s", e)
        return None

    def _extract_og_tags(self, soup: BeautifulSoup) -> dict:
        """Open Graphタグを抽出する。"""
        og_mapping = {
            "og:title": "og_title",
            "og:description": "og_description",
            "og:image": "og_image",
            "og:url": "og_url",
        }
        result = {v: None for v in og_mapping.values()}

        for og_property, key in og_mapping.items():
            try:
                tag = soup.find("meta", attrs={"property": og_property})
                if tag and tag.get("content"):
                    result[key] = tag["content"].strip()
            except Exception as e:
                logger.warning("Failed to extract %s: %s", og_property, e)

        return result

    def _extract_language(self, soup: BeautifulSoup) -> Optional[str]:
        """html lang属性またはmetaタグから言語を検出する。"""
        try:
            html_tag = soup.find("html")
            if html_tag and html_tag.get("lang"):
                return html_tag["lang"].strip()
        except Exception as e:
            logger.warning("Failed to extract language from html tag: %s", e)

        try:
            meta_lang = soup.find("meta", attrs={"http-equiv": "content-language"})
            if meta_lang and meta_lang.get("content"):
                return meta_lang["content"].strip()
        except Exception as e:
            logger.warning("Failed to extract language from meta tag: %s", e)

        return None
