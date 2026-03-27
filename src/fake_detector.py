"""
Fake Site Detector for Payment Compliance Monitor.

This module detects similar domains and fake sites that may be impersonating
legitimate monitoring targets.
"""

import math
from dataclasses import dataclass
from typing import Optional
import re
from urllib.parse import urlparse


# Mapping of visually similar character sequences to their canonical forms.
# Used to normalize domains before similarity comparison so that tricks
# like "rn" → "m" or "vv" → "w" are detected.
VISUAL_SIMILAR_CHARS = {
    'rn': 'm', 'vv': 'w', 'cl': 'd', 'nn': 'm',
    'ri': 'n', 'lI': 'd', 'cI': 'd',
}

# Known compound (multi-part) TLDs.  When splitting a domain into its
# name and TLD parts we must check for these *before* falling back to
# a simple ``rsplit('.', 1)`` so that e.g. ``example.co.jp`` is split
# as ``("example", "co.jp")`` rather than ``("example.co", "jp")``.
COMPOUND_TLDS = [
    'co.jp', 'or.jp', 'ne.jp', 'ac.jp', 'go.jp',
    'com.au', 'co.uk', 'co.kr', 'com.br', 'com.cn',
    'co.nz', 'co.in', 'com.tw', 'com.hk',
]


@dataclass
class SuspiciousDomain:
    """
    Represents a suspicious domain that may be a fake site.
    
    Attributes:
        domain: The suspicious domain name
        similarity_score: Similarity score to legitimate domain (0.0-1.0)
        content_similarity: Content similarity score (0.0-1.0, None if not crawled)
        is_confirmed_fake: Whether this is confirmed as a fake site
        legitimate_domain: The legitimate domain this resembles
    """
    domain: str
    similarity_score: float
    content_similarity: Optional[float]
    is_confirmed_fake: bool
    legitimate_domain: str


class FakeSiteDetector:
    """
    Detects fake sites and similar domains.
    
    Uses Damerau-Levenshtein distance for domain similarity and TF-IDF for content similarity.
    """
    
    def __init__(
        self,
        domain_similarity_threshold: float = 0.8,
        content_similarity_threshold: float = 0.7
    ):
        """
        Initialize FakeSiteDetector.
        
        Args:
            domain_similarity_threshold: Minimum similarity score to flag as suspicious (0.0-1.0)
            content_similarity_threshold: Minimum content similarity to confirm as fake (0.0-1.0)
        """
        self.domain_similarity_threshold = domain_similarity_threshold
        self.content_similarity_threshold = content_similarity_threshold
    
    def calculate_domain_similarity(self, domain1: str, domain2: str) -> float:
        """
        Calculate similarity between two domain names using Damerau-Levenshtein distance.

        Compares domains both with and without hyphens, returning the higher score.

        Args:
            domain1: First domain name
            domain2: Second domain name

        Returns:
            Similarity score between 0.0 and 1.0 (1.0 = identical)
        """
        # Normalize domains (remove www, convert to lowercase)
        d1 = self._normalize_domain(domain1)
        d2 = self._normalize_domain(domain2)

        # Apply visual similar character normalization before comparison
        d1 = self._normalize_visual_chars(d1)
        d2 = self._normalize_visual_chars(d2)

        # Calculate similarity with original normalized domains
        score_with_hyphens = self._calculate_similarity_score(d1, d2)

        # Calculate similarity with hyphens removed from both domains
        d1_no_hyphen = d1.replace('-', '')
        d2_no_hyphen = d2.replace('-', '')
        score_without_hyphens = self._calculate_similarity_score(d1_no_hyphen, d2_no_hyphen)

        # Return the maximum of the two scores
        return max(score_with_hyphens, score_without_hyphens)
    
    def _calculate_similarity_score(self, d1: str, d2: str) -> float:
        """
        Calculate similarity score between two already-normalized domain strings.
        
        Args:
            d1: First normalized domain string
            d2: Second normalized domain string
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        distance = self._damerau_levenshtein_distance(d1, d2)
        max_length = max(len(d1), len(d2))
        if max_length == 0:
            return 1.0
        similarity = 1.0 - (distance / max_length)
        return max(0.0, min(1.0, similarity))
    
    def _normalize_domain(self, domain: str) -> str:
        """
        Normalize domain name for comparison.

        Strips protocol, ``www.`` prefix, port, trailing slash, and the TLD
        (including compound TLDs such as ``.co.jp``).  The returned value is
        the domain-name part only, suitable for similarity comparison.

        Args:
            domain: Domain name to normalize

        Returns:
            Normalized domain name (without TLD)
        """
        # Remove protocol if present
        if '://' in domain:
            domain = urlparse(domain).netloc

        # Remove www prefix
        domain = re.sub(r'^www\.', '', domain.lower())

        # Remove port if present
        domain = domain.split(':')[0]

        # Remove trailing slash
        domain = domain.rstrip('/')

        # Strip TLD — check compound TLDs first, then fall back to simple split
        for compound_tld in COMPOUND_TLDS:
            suffix = '.' + compound_tld
            if domain.endswith(suffix):
                return domain[:-len(suffix)]

        # Simple TLD: split on the last dot
        parts = domain.rsplit('.', 1)
        if len(parts) == 2:
            return parts[0]

        return domain

    def _normalize_visual_chars(self, domain: str) -> str:
        """
        Normalize visually similar character sequences in a domain name.

        Replaces sequences like 'rn' → 'm', 'vv' → 'w', etc. using the
        VISUAL_SIMILAR_CHARS mapping. Longer keys are applied first so that
        overlapping patterns are handled correctly.

        Applies replacements iteratively until the result stabilizes
        (fixed-point), ensuring idempotency.

        Args:
            domain: Domain name to normalize

        Returns:
            Domain with visual similar sequences replaced
        """
        # Sort keys by length descending so longer patterns match first
        sorted_keys = sorted(VISUAL_SIMILAR_CHARS, key=len, reverse=True)
        while True:
            prev = domain
            for seq in sorted_keys:
                domain = domain.replace(seq, VISUAL_SIMILAR_CHARS[seq])
            if domain == prev:
                break
        return domain
    
    def _damerau_levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Damerau-Levenshtein distance between two strings.

        Uses the Optimal String Alignment (OSA) variant which treats
        adjacent character transpositions as a single edit operation,
        in addition to insertions, deletions, and substitutions.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Damerau-Levenshtein distance (number of edits needed)
        """
        len1 = len(s1)
        len2 = len(s2)

        # Create a matrix of size (len1+1) x (len2+1)
        d = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        # Initialize base cases
        for i in range(len1 + 1):
            d[i][0] = i
        for j in range(len2 + 1):
            d[0][j] = j

        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1

                d[i][j] = min(
                    d[i - 1][j] + 1,       # deletion
                    d[i][j - 1] + 1,       # insertion
                    d[i - 1][j - 1] + cost  # substitution
                )

                # Transposition of adjacent characters
                if (i > 1 and j > 1
                        and s1[i - 1] == s2[j - 2]
                        and s1[i - 2] == s2[j - 1]):
                    d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)

        return d[len1][len2]
    
    def scan_similar_domains(
        self,
        legitimate_domain: str,
        candidate_domains: list[str]
    ) -> list[SuspiciousDomain]:
        """
        Scan a list of candidate domains for similarity to legitimate domain.
        
        Args:
            legitimate_domain: The legitimate domain to compare against
            candidate_domains: List of candidate domains to check
        
        Returns:
            List of suspicious domains that exceed the similarity threshold
        """
        suspicious_domains = []
        
        for candidate in candidate_domains:
            similarity = self.calculate_domain_similarity(legitimate_domain, candidate)
            
            if similarity >= self.domain_similarity_threshold:
                suspicious_domain = SuspiciousDomain(
                    domain=candidate,
                    similarity_score=similarity,
                    content_similarity=None,
                    is_confirmed_fake=False,
                    legitimate_domain=legitimate_domain
                )
                suspicious_domains.append(suspicious_domain)
        
        return suspicious_domains
    
    def calculate_content_similarity(
        self,
        content1: str,
        content2: str,
        img_path1: Optional[str] = None,
        img_path2: Optional[str] = None,
    ) -> float:
        """
        Calculate content similarity as a weighted average of four sub-scores.

        Weights (with visual similarity available):
            text similarity  : 0.40
            field similarity : 0.30
            structure similarity : 0.15
            visual similarity    : 0.15

        When visual similarity is unavailable (image paths missing or visual
        similarity returns 0.0 due to error), the visual weight is
        redistributed proportionally among the remaining components:
            text similarity  : 0.47
            field similarity : 0.35
            structure similarity : 0.18

        Args:
            content1: First content (HTML or text)
            content2: Second content (HTML or text)
            img_path1: Optional file path to the first screenshot image
            img_path2: Optional file path to the second screenshot image

        Returns:
            Similarity score clamped to [0.0, 1.0]
        """
        # 1. Text similarity (TF-IDF cosine similarity)
        words1 = self._extract_words(content1)
        words2 = self._extract_words(content2)

        if not words1 or not words2:
            text_sim = 0.0
        else:
            tf1 = self._calculate_word_frequency(words1)
            tf2 = self._calculate_word_frequency(words2)
            tfidf1, tfidf2 = self._calculate_tfidf_vectors(tf1, tf2)
            text_sim = self._cosine_similarity(tfidf1, tfidf2)

        # 2. Field similarity
        field_sim = self.calculate_field_similarity(content1, content2)

        # 3. Structure similarity
        structure_sim = self.calculate_structure_similarity(content1, content2)

        # 4. Visual similarity (only when both image paths are provided)
        visual_sim = 0.0
        visual_available = False
        if img_path1 is not None and img_path2 is not None:
            visual_sim = self.calculate_visual_similarity(img_path1, img_path2)
            if visual_sim > 0.0:
                visual_available = True

        # Weighted average
        if visual_available:
            score = (
                text_sim * 0.4
                + field_sim * 0.3
                + structure_sim * 0.15
                + visual_sim * 0.15
            )
        else:
            # Redistribute visual weight proportionally
            score = (
                text_sim * 0.47
                + field_sim * 0.35
                + structure_sim * 0.18
            )

        return max(0.0, min(1.0, score))

    def calculate_field_similarity(self, content1: str, content2: str) -> float:
        """
        Calculate similarity based on important fields extracted from HTML content.

        Extracts product names, prices, and brand names from both documents
        and compares them.  Each matching field type contributes equally to
        the final score.

        Args:
            content1: First HTML content
            content2: Second HTML content

        Returns:
            Similarity score between 0.0 and 1.0
        """
        fields1 = self._extract_important_fields(content1)
        fields2 = self._extract_important_fields(content2)

        if not fields1 and not fields2:
            return 0.0

        scores: list[float] = []

        # Compare prices
        prices1 = fields1.get("prices", set())
        prices2 = fields2.get("prices", set())
        if prices1 or prices2:
            if prices1 and prices2:
                overlap = len(prices1 & prices2)
                total = len(prices1 | prices2)
                scores.append(overlap / total if total > 0 else 0.0)
            else:
                scores.append(0.0)

        # Compare product names (case-insensitive Jaccard on words)
        names1 = fields1.get("product_names", set())
        names2 = fields2.get("product_names", set())
        if names1 or names2:
            if names1 and names2:
                words1 = {w for name in names1 for w in name.lower().split()}
                words2 = {w for name in names2 for w in name.lower().split()}
                overlap = len(words1 & words2)
                total = len(words1 | words2)
                scores.append(overlap / total if total > 0 else 0.0)
            else:
                scores.append(0.0)

        # Compare brand names (exact match, case-insensitive)
        brands1 = fields1.get("brands", set())
        brands2 = fields2.get("brands", set())
        if brands1 or brands2:
            if brands1 and brands2:
                norm1 = {b.lower() for b in brands1}
                norm2 = {b.lower() for b in brands2}
                overlap = len(norm1 & norm2)
                total = len(norm1 | norm2)
                scores.append(overlap / total if total > 0 else 0.0)
            else:
                scores.append(0.0)

        if not scores:
            return 0.0

        return sum(scores) / len(scores)

    def _extract_important_fields(self, content: str) -> dict[str, set[str]]:
        """
        Extract important fields (prices, product names, brands) from HTML.

        Uses regex patterns to find:
        - Prices: currency symbols followed by numbers (e.g. $19.99, ¥1000, €29.50)
        - Product names: from <title>, <h1>, and og:title meta tags
        - Brand names: from brand-related meta tags and structured data

        Args:
            content: HTML content to extract fields from

        Returns:
            Dictionary with keys 'prices', 'product_names', 'brands',
            each mapping to a set of extracted string values.
        """
        fields: dict[str, set[str]] = {
            "prices": set(),
            "product_names": set(),
            "brands": set(),
        }

        # --- Prices ---
        # Match currency patterns: $, ¥, €, £ followed by numbers
        price_patterns = re.findall(
            r'[\$¥€£]\s*[\d,]+(?:\.\d{1,2})?', content
        )
        for p in price_patterns:
            # Normalize: remove spaces and commas for comparison
            normalized = re.sub(r'[\s,]', '', p)
            fields["prices"].add(normalized)

        # --- Product names ---
        # From <title> tag
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title_text = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            if title_text:
                fields["product_names"].add(title_text)

        # From <h1> tags
        h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
        for h1 in h1_matches:
            h1_text = re.sub(r'<[^>]+>', '', h1).strip()
            if h1_text:
                fields["product_names"].add(h1_text)

        # From og:title meta tag
        og_title_match = re.search(
            r'<meta\s+[^>]*property\s*=\s*["\']og:title["\']\s+[^>]*content\s*=\s*["\']([^"\']*)["\']',
            content, re.IGNORECASE
        )
        if not og_title_match:
            og_title_match = re.search(
                r'<meta\s+[^>]*content\s*=\s*["\']([^"\']*?)["\']\s+[^>]*property\s*=\s*["\']og:title["\']',
                content, re.IGNORECASE
            )
        if og_title_match:
            og_text = og_title_match.group(1).strip()
            if og_text:
                fields["product_names"].add(og_text)

        # --- Brand names ---
        # From meta brand tag
        brand_meta_match = re.search(
            r'<meta\s+[^>]*name\s*=\s*["\'](?:brand|author)["\'][^>]*content\s*=\s*["\']([^"\']*)["\']',
            content, re.IGNORECASE
        )
        if not brand_meta_match:
            brand_meta_match = re.search(
                r'<meta\s+[^>]*content\s*=\s*["\']([^"\']*?)["\']\s+[^>]*name\s*=\s*["\'](?:brand|author)["\']',
                content, re.IGNORECASE
            )
        if brand_meta_match:
            brand_text = brand_meta_match.group(1).strip()
            if brand_text:
                fields["brands"].add(brand_text)

        # From JSON-LD structured data (brand field)
        brand_ld_matches = re.findall(
            r'"brand"\s*:\s*(?:\{[^}]*"name"\s*:\s*"([^"]+)"[^}]*\}|"([^"]+)")',
            content
        )
        for match in brand_ld_matches:
            brand_val = match[0] or match[1]
            if brand_val.strip():
                fields["brands"].add(brand_val.strip())

        return fields

    def calculate_structure_similarity(self, html1: str, html2: str) -> float:
        """
        Calculate DOM structure similarity between two HTML documents.

        Compares the tag hierarchy (sequence of opening tag names) and
        CSS class names found in both documents using Jaccard similarity.
        The final score is the average of the two Jaccard scores.

        Args:
            html1: First HTML document
            html2: Second HTML document

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Extract opening tag names (e.g. <div>, <p>, <span>)
        tags1 = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', html1)
        tags2 = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>', html2)

        tag_set1 = set(t.lower() for t in tags1)
        tag_set2 = set(t.lower() for t in tags2)

        # Extract CSS class names from class="..." attributes
        classes1 = set()
        for match in re.findall(r'class\s*=\s*["\']([^"\']*)["\']', html1, re.IGNORECASE):
            classes1.update(match.split())
        classes2 = set()
        for match in re.findall(r'class\s*=\s*["\']([^"\']*)["\']', html2, re.IGNORECASE):
            classes2.update(match.split())

        # Jaccard similarity for tags
        tag_union = tag_set1 | tag_set2
        if tag_union:
            tag_similarity = len(tag_set1 & tag_set2) / len(tag_union)
        else:
            tag_similarity = 0.0

        # Jaccard similarity for CSS classes
        class_union = classes1 | classes2
        if class_union:
            class_similarity = len(classes1 & classes2) / len(class_union)
        else:
            class_similarity = 0.0

        # If neither tags nor classes were found, return 0
        if not tag_union and not class_union:
            return 0.0

        # Average of both Jaccard scores (only count components that exist)
        components: list[float] = []
        if tag_union:
            components.append(tag_similarity)
        if class_union:
            components.append(class_similarity)

        return sum(components) / len(components) if components else 0.0

    def calculate_visual_similarity(self, img_path1: str, img_path2: str) -> float:
        """
        Calculate visual similarity between two images using perceptual hashing (pHash).

        Uses the imagehash library to compute perceptual hashes and compares them
        via Hamming distance. Returns a similarity score between 0.0 and 1.0.

        Args:
            img_path1: File path to the first image (e.g. screenshot)
            img_path2: File path to the second image (e.g. screenshot)

        Returns:
            Similarity score between 0.0 (completely different) and 1.0 (identical).
            Returns 0.0 if imagehash/PIL is not installed or if any error occurs
            (e.g. file not found, corrupt image).
        """
        try:
            import imagehash
            from PIL import Image
        except ImportError:
            return 0.0

        try:
            img1 = Image.open(img_path1)
            img2 = Image.open(img_path2)

            hash1 = imagehash.phash(img1)
            hash2 = imagehash.phash(img2)

            hamming_distance = hash1 - hash2
            hash_size = hash1.hash.size

            similarity = 1.0 - (hamming_distance / hash_size)
            return max(0.0, min(1.0, similarity))
        except Exception:
            return 0.0



    
    def _extract_words(self, content: str) -> list[str]:
        """
        Extract words from content.
        
        Args:
            content: Content to extract words from
        
        Returns:
            List of words
        """
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\w+', content.lower())
        
        # Filter out very short words
        words = [w for w in words if len(w) > 2]
        
        return words
    
    def _calculate_word_frequency(self, words: list[str]) -> dict[str, float]:
        """
        Calculate term frequency (TF) for a document.

        TF(term) = count(term) / total_words

        Args:
            words: List of words

        Returns:
            Dictionary mapping words to their term frequency
        """
        total = len(words)
        if total == 0:
            return {}

        freq: dict[str, float] = {}
        for word in words:
            freq[word] = freq.get(word, 0) + 1

        # Normalize by total count to get TF
        for word in freq:
            freq[word] = freq[word] / total

        return freq

    def _calculate_tfidf_vectors(
        self,
        tf1: dict[str, float],
        tf2: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, float]]:
        """
        Calculate TF-IDF vectors for two documents.

        IDF(term) = log(2 / (1 + df(term))) where df is the number of
        documents (out of 2) that contain the term.

        Args:
            tf1: Term frequency dict for document 1
            tf2: Term frequency dict for document 2

        Returns:
            Tuple of TF-IDF weighted vectors for each document
        """
        all_terms = set(tf1.keys()) | set(tf2.keys())

        tfidf1: dict[str, float] = {}
        tfidf2: dict[str, float] = {}

        for term in all_terms:
            # df = number of documents containing the term (1 or 2)
            df = (1 if term in tf1 else 0) + (1 if term in tf2 else 0)
            idf = math.log(2.0 / (1.0 + df))

            if term in tf1:
                tfidf1[term] = tf1[term] * idf
            if term in tf2:
                tfidf2[term] = tf2[term] * idf

        return tfidf1, tfidf2
    
    def _cosine_similarity(
        self,
        freq1: dict[str, float],
        freq2: dict[str, float]
    ) -> float:
        """
        Calculate cosine similarity between two frequency dictionaries.
        
        Args:
            freq1: First frequency dictionary
            freq2: Second frequency dictionary
        
        Returns:
            Cosine similarity score (0.0-1.0)
        """
        # Get all unique words
        all_words = set(freq1.keys()) | set(freq2.keys())
        
        if not all_words:
            return 0.0
        
        # Calculate dot product and magnitudes
        dot_product = 0.0
        magnitude1 = 0.0
        magnitude2 = 0.0
        
        for word in all_words:
            f1 = freq1.get(word, 0.0)
            f2 = freq2.get(word, 0.0)
            
            dot_product += f1 * f2
            magnitude1 += f1 * f1
            magnitude2 += f2 * f2
        
        # Calculate cosine similarity
        magnitude1 = magnitude1 ** 0.5
        magnitude2 = magnitude2 ** 0.5
        
        if magnitude1 == 0.0 or magnitude2 == 0.0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        
        return max(0.0, min(1.0, similarity))
    
    def verify_fake_site(
        self,
        suspicious_domain: SuspiciousDomain,
        legitimate_content: str,
        suspicious_content: str,
        legitimate_screenshot: Optional[str] = None,
        suspicious_screenshot: Optional[str] = None,
    ) -> SuspiciousDomain:
        """
        Verify if a suspicious domain is a confirmed fake site by comparing content.

        Args:
            suspicious_domain: The suspicious domain to verify
            legitimate_content: Content from the legitimate site
            suspicious_content: Content from the suspicious site
            legitimate_screenshot: Optional path to legitimate site screenshot
            suspicious_screenshot: Optional path to suspicious site screenshot

        Returns:
            Updated SuspiciousDomain with content similarity and confirmation status
        """
        content_similarity = self.calculate_content_similarity(
            legitimate_content,
            suspicious_content,
            img_path1=legitimate_screenshot,
            img_path2=suspicious_screenshot,
        )

        is_confirmed_fake = content_similarity >= self.content_similarity_threshold

        return SuspiciousDomain(
            domain=suspicious_domain.domain,
            similarity_score=suspicious_domain.similarity_score,
            content_similarity=content_similarity,
            is_confirmed_fake=is_confirmed_fake,
            legitimate_domain=suspicious_domain.legitimate_domain
        )
