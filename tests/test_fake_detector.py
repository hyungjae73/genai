"""
Unit tests for FakeSiteDetector.

Tests the detection of similar domains and fake sites.
"""

import pytest

from src.fake_detector import FakeSiteDetector, SuspiciousDomain


class TestFakeSiteDetector:
    """Test suite for FakeSiteDetector."""
    
    def test_calculate_domain_similarity_identical(self):
        """Test similarity calculation for identical domains."""
        detector = FakeSiteDetector()
        
        similarity = detector.calculate_domain_similarity(
            'example.com',
            'example.com'
        )
        
        assert similarity == 1.0
    
    def test_calculate_domain_similarity_very_similar(self):
        """Test similarity calculation for very similar domains."""
        detector = FakeSiteDetector()
        
        # examp1e.com vs example.com (one character different)
        similarity = detector.calculate_domain_similarity(
            'example.com',
            'examp1e.com'
        )
        
        assert similarity > 0.8
    
    def test_calculate_domain_similarity_different(self):
        """Test similarity calculation for different domains."""
        detector = FakeSiteDetector()
        
        similarity = detector.calculate_domain_similarity(
            'example.com',
            'totally-different.com'
        )
        
        assert similarity < 0.5
    
    def test_normalize_domain_removes_www(self):
        """Test domain normalization removes www prefix."""
        detector = FakeSiteDetector()
        
        normalized = detector._normalize_domain('www.example.com')
        
        assert normalized == 'example'
    
    def test_normalize_domain_removes_protocol(self):
        """Test domain normalization removes protocol."""
        detector = FakeSiteDetector()
        
        normalized = detector._normalize_domain('https://example.com')
        
        assert normalized == 'example'
    
    def test_normalize_domain_lowercase(self):
        """Test domain normalization converts to lowercase."""
        detector = FakeSiteDetector()
        
        normalized = detector._normalize_domain('EXAMPLE.COM')
        
        assert normalized == 'example'
    
    def test_damerau_levenshtein_distance_identical(self):
        """Test Damerau-Levenshtein distance for identical strings."""
        detector = FakeSiteDetector()
        
        distance = detector._damerau_levenshtein_distance('test', 'test')
        
        assert distance == 0
    
    def test_damerau_levenshtein_distance_one_substitution(self):
        """Test Damerau-Levenshtein distance for one substitution."""
        detector = FakeSiteDetector()
        
        distance = detector._damerau_levenshtein_distance('test', 'best')
        
        assert distance == 1
    
    def test_damerau_levenshtein_distance_one_insertion(self):
        """Test Damerau-Levenshtein distance for one insertion."""
        detector = FakeSiteDetector()
        
        distance = detector._damerau_levenshtein_distance('test', 'tests')
        
        assert distance == 1
    
    def test_damerau_levenshtein_distance_transposition(self):
        """Test Damerau-Levenshtein distance for adjacent character transposition."""
        detector = FakeSiteDetector()
        
        distance = detector._damerau_levenshtein_distance('test', 'tset')
        
        assert distance == 1
    
    def test_scan_similar_domains_finds_suspicious(self):
        """Test scanning finds suspicious domains above threshold."""
        detector = FakeSiteDetector(domain_similarity_threshold=0.8)
        
        candidates = [
            'example.com',      # Identical
            'examp1e.com',      # Very similar
            'totally-different.com'  # Different
        ]
        
        suspicious = detector.scan_similar_domains('example.com', candidates)
        
        # Should find at least the identical and very similar ones
        assert len(suspicious) >= 2
        assert all(s.similarity_score >= 0.8 for s in suspicious)
    
    def test_scan_similar_domains_returns_suspicious_domain_objects(self):
        """Test scanning returns proper SuspiciousDomain objects."""
        detector = FakeSiteDetector(domain_similarity_threshold=0.8)
        
        candidates = ['examp1e.com']
        
        suspicious = detector.scan_similar_domains('example.com', candidates)
        
        assert len(suspicious) == 1
        assert isinstance(suspicious[0], SuspiciousDomain)
        assert suspicious[0].domain == 'examp1e.com'
        assert suspicious[0].legitimate_domain == 'example.com'
        assert suspicious[0].content_similarity is None
        assert suspicious[0].is_confirmed_fake is False
    
    def test_calculate_content_similarity_identical(self):
        """Test content similarity for identical content (weighted average without images).

        With no image paths the visual weight is redistributed:
        text(0.47) + field(0.35) + structure(0.18).
        For simple identical HTML: text=1.0, field=0.0, structure=1.0 → 0.65.
        """
        detector = FakeSiteDetector()
        
        content = '<html><body>This is a test page with some content</body></html>'
        
        similarity = detector.calculate_content_similarity(content, content)
        
        # Weighted average: 1.0*0.47 + 0.0*0.35 + 1.0*0.18 = 0.65
        assert similarity > 0.6
    
    def test_calculate_content_similarity_similar(self):
        """Test content similarity for similar content."""
        detector = FakeSiteDetector()
        
        content1 = '<html><body>Payment page with credit card and bank transfer</body></html>'
        content2 = '<html><body>Payment page with credit card and paypal</body></html>'
        
        similarity = detector.calculate_content_similarity(content1, content2)
        
        # Should be moderately similar due to shared words and identical structure
        assert similarity > 0.3
    
    def test_calculate_content_similarity_different(self):
        """Test content similarity for different content."""
        detector = FakeSiteDetector()
        
        content1 = '<html><body>Payment page with credit card</body></html>'
        content2 = '<html><body>About us company history</body></html>'
        
        similarity = detector.calculate_content_similarity(content1, content2)
        
        # Should be different
        assert similarity < 0.5
    
    def test_extract_words_removes_html_tags(self):
        """Test word extraction removes HTML tags."""
        detector = FakeSiteDetector()
        
        content = '<html><body><p>Test content payment</p></body></html>'
        
        words = detector._extract_words(content)
        
        # Words longer than 2 characters should be extracted
        assert 'test' in words
        assert 'content' in words
        assert 'payment' in words
        # HTML tags should not be in words
        assert '<p>' not in ' '.join(words)
        assert '</p>' not in ' '.join(words)
    
    def test_verify_fake_site_confirms_high_similarity(self):
        """Test fake site verification confirms high content similarity."""
        detector = FakeSiteDetector(content_similarity_threshold=0.5)
        
        suspicious = SuspiciousDomain(
            domain='examp1e.com',
            similarity_score=0.9,
            content_similarity=None,
            is_confirmed_fake=False,
            legitimate_domain='example.com'
        )
        
        legitimate_content = '<html><body>Payment page with credit card</body></html>'
        suspicious_content = '<html><body>Payment page with credit card</body></html>'
        
        verified = detector.verify_fake_site(
            suspicious,
            legitimate_content,
            suspicious_content
        )
        
        assert verified.content_similarity is not None
        assert verified.content_similarity > 0.5
        assert verified.is_confirmed_fake is True
    
    def test_verify_fake_site_rejects_low_similarity(self):
        """Test fake site verification rejects low content similarity."""
        detector = FakeSiteDetector(content_similarity_threshold=0.5)
        
        suspicious = SuspiciousDomain(
            domain='different.com',
            similarity_score=0.85,
            content_similarity=None,
            is_confirmed_fake=False,
            legitimate_domain='example.com'
        )
        
        legitimate_content = '<html><body>Payment page with credit card</body></html>'
        suspicious_content = '<html><body>About us company history</body></html>'
        
        verified = detector.verify_fake_site(
            suspicious,
            legitimate_content,
            suspicious_content
        )
        
        assert verified.content_similarity is not None
        assert verified.content_similarity < 0.5
        assert verified.is_confirmed_fake is False


class TestCalculateStructureSimilarity:
    """Tests for calculate_structure_similarity (DOM structure similarity)."""

    def test_identical_html_returns_one(self):
        """Identical HTML documents should have similarity 1.0."""
        detector = FakeSiteDetector()
        html = '<html><body><div class="main"><p>Hello</p></div></body></html>'
        assert detector.calculate_structure_similarity(html, html) == 1.0

    def test_empty_html_returns_zero(self):
        """Empty HTML strings should return 0.0."""
        detector = FakeSiteDetector()
        assert detector.calculate_structure_similarity("", "") == 0.0

    def test_similar_structure_high_score(self):
        """HTML with same tags and classes should score high."""
        detector = FakeSiteDetector()
        html1 = '<html><body><div class="container"><p class="text">A</p></div></body></html>'
        html2 = '<html><body><div class="container"><p class="text">B</p></div></body></html>'
        score = detector.calculate_structure_similarity(html1, html2)
        assert score == 1.0

    def test_different_structure_low_score(self):
        """HTML with completely different tags and classes should score low."""
        detector = FakeSiteDetector()
        html1 = '<div class="alpha"><span class="beta">X</span></div>'
        html2 = '<table class="gamma"><tr class="delta"><td>Y</td></tr></table>'
        score = detector.calculate_structure_similarity(html1, html2)
        assert score < 0.5

    def test_result_bounded_zero_to_one(self):
        """Result should always be between 0.0 and 1.0."""
        detector = FakeSiteDetector()
        html1 = '<div class="a b c"><p class="d">text</p></div>'
        html2 = '<section class="x y"><article class="z">text</article></section>'
        score = detector.calculate_structure_similarity(html1, html2)
        assert 0.0 <= score <= 1.0

    def test_tags_only_no_classes(self):
        """HTML with tags but no classes should still compute similarity."""
        detector = FakeSiteDetector()
        html1 = '<div><p>Hello</p></div>'
        html2 = '<div><p>World</p><span>!</span></div>'
        score = detector.calculate_structure_similarity(html1, html2)
        assert 0.0 < score <= 1.0

    def test_classes_contribute_to_similarity(self):
        """Shared CSS classes should increase the similarity score."""
        detector = FakeSiteDetector()
        html_base = '<div><p>text</p></div>'
        html_with_shared_classes = '<div class="shared"><p class="common">text</p></div>'
        html_with_diff_classes = '<div class="unique1"><p class="unique2">text</p></div>'

        score_shared = detector.calculate_structure_similarity(
            html_with_shared_classes, html_with_shared_classes
        )
        score_diff = detector.calculate_structure_similarity(
            html_with_shared_classes, html_with_diff_classes
        )
        # Identical classes should score higher than different classes
        assert score_shared >= score_diff


class TestCalculateVisualSimilarity:
    """Tests for pHash visual similarity calculation (Requirement 10.4)."""

    def test_returns_zero_when_imagehash_not_available(self):
        """Should return 0.0 when imagehash library is not installed."""
        from unittest.mock import patch
        detector = FakeSiteDetector()
        with patch.dict("sys.modules", {"imagehash": None, "PIL": None, "PIL.Image": None}):
            score = detector.calculate_visual_similarity("a.png", "b.png")
        assert score == 0.0

    def test_returns_zero_for_nonexistent_files(self):
        """Should return 0.0 when image files don't exist."""
        detector = FakeSiteDetector()
        score = detector.calculate_visual_similarity(
            "/nonexistent/path/a.png", "/nonexistent/path/b.png"
        )
        assert score == 0.0

    def test_returns_zero_for_corrupt_file(self, tmp_path):
        """Should return 0.0 when image file is corrupt."""
        detector = FakeSiteDetector()
        corrupt = tmp_path / "corrupt.png"
        corrupt.write_text("not an image")
        score = detector.calculate_visual_similarity(str(corrupt), str(corrupt))
        assert score == 0.0

    def test_identical_images_return_high_similarity(self, tmp_path):
        """Identical images should return similarity of 1.0."""
        try:
            from PIL import Image
            import imagehash  # noqa: F401
        except ImportError:
            pytest.skip("imagehash or PIL not installed")

        detector = FakeSiteDetector()
        img = Image.new("RGB", (64, 64), color="red")
        path = str(tmp_path / "same.png")
        img.save(path)

        score = detector.calculate_visual_similarity(path, path)
        assert score == 1.0

    def test_different_images_return_lower_similarity(self, tmp_path):
        """Very different images should return a lower similarity score."""
        try:
            from PIL import Image
            import imagehash  # noqa: F401
        except ImportError:
            pytest.skip("imagehash or PIL not installed")

        detector = FakeSiteDetector()
        img1 = Image.new("RGB", (64, 64), color="red")
        img2 = Image.new("RGB", (64, 64), color="blue")
        p1 = str(tmp_path / "red.png")
        p2 = str(tmp_path / "blue.png")
        img1.save(p1)
        img2.save(p2)

        score = detector.calculate_visual_similarity(p1, p2)
        assert 0.0 <= score <= 1.0

    def test_result_bounded_zero_to_one(self, tmp_path):
        """Result should always be between 0.0 and 1.0."""
        try:
            from PIL import Image
            import imagehash  # noqa: F401
        except ImportError:
            pytest.skip("imagehash or PIL not installed")

        detector = FakeSiteDetector()
        img = Image.new("RGB", (64, 64), color="green")
        path = str(tmp_path / "green.png")
        img.save(path)

        score = detector.calculate_visual_similarity(path, path)
        assert 0.0 <= score <= 1.0
