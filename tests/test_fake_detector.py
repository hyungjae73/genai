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
        
        assert similarity > 0.9
    
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
        
        assert normalized == 'example.com'
    
    def test_normalize_domain_removes_protocol(self):
        """Test domain normalization removes protocol."""
        detector = FakeSiteDetector()
        
        normalized = detector._normalize_domain('https://example.com')
        
        assert normalized == 'example.com'
    
    def test_normalize_domain_lowercase(self):
        """Test domain normalization converts to lowercase."""
        detector = FakeSiteDetector()
        
        normalized = detector._normalize_domain('EXAMPLE.COM')
        
        assert normalized == 'example.com'
    
    def test_levenshtein_distance_identical(self):
        """Test Levenshtein distance for identical strings."""
        detector = FakeSiteDetector()
        
        distance = detector._levenshtein_distance('test', 'test')
        
        assert distance == 0
    
    def test_levenshtein_distance_one_substitution(self):
        """Test Levenshtein distance for one substitution."""
        detector = FakeSiteDetector()
        
        distance = detector._levenshtein_distance('test', 'best')
        
        assert distance == 1
    
    def test_levenshtein_distance_one_insertion(self):
        """Test Levenshtein distance for one insertion."""
        detector = FakeSiteDetector()
        
        distance = detector._levenshtein_distance('test', 'tests')
        
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
        """Test content similarity for identical content."""
        detector = FakeSiteDetector()
        
        content = '<html><body>This is a test page with some content</body></html>'
        
        similarity = detector.calculate_content_similarity(content, content)
        
        assert similarity == 1.0
    
    def test_calculate_content_similarity_similar(self):
        """Test content similarity for similar content."""
        detector = FakeSiteDetector()
        
        content1 = '<html><body>Payment page with credit card and bank transfer</body></html>'
        content2 = '<html><body>Payment page with credit card and paypal</body></html>'
        
        similarity = detector.calculate_content_similarity(content1, content2)
        
        # Should be similar due to shared words
        assert similarity > 0.5
    
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
        detector = FakeSiteDetector(content_similarity_threshold=0.7)
        
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
        assert verified.content_similarity > 0.7
        assert verified.is_confirmed_fake is True
    
    def test_verify_fake_site_rejects_low_similarity(self):
        """Test fake site verification rejects low content similarity."""
        detector = FakeSiteDetector(content_similarity_threshold=0.7)
        
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
        assert verified.content_similarity < 0.7
        assert verified.is_confirmed_fake is False
