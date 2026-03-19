"""
Property-based tests for FakeSiteDetector.

Tests universal properties that should hold for domain similarity calculations.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from src.fake_detector import FakeSiteDetector


# Strategy for generating valid domain names
@st.composite
def domain_strategy(draw):
    """Generate valid domain names."""
    # Generate domain parts
    parts = draw(st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Nd')),
            min_size=2,
            max_size=10
        ),
        min_size=2,
        max_size=3
    ))
    return '.'.join(parts)


class TestFakeSiteDetectorProperties:
    """Property-based tests for FakeSiteDetector."""
    
    @settings(max_examples=5)
    @given(
        domain1=domain_strategy(),
        domain2=domain_strategy()
    )
    def test_property_domain_similarity_range(self, domain1, domain2):
        """
        Property 9: Domain similarity calculation
        
        For any pair of domain strings, the similarity score should be
        between 0.0 and 1.0.
        
        **Validates: Requirements 4.2**
        """
        detector = FakeSiteDetector()
        
        similarity = detector.calculate_domain_similarity(domain1, domain2)
        
        # Property: Similarity score must be in valid range
        assert 0.0 <= similarity <= 1.0
    
    @settings(max_examples=5)
    @given(domain=domain_strategy())
    def test_property_domain_similarity_identity(self, domain):
        """
        Property: A domain compared to itself should have similarity 1.0.
        
        **Validates: Requirements 4.2**
        """
        detector = FakeSiteDetector()
        
        similarity = detector.calculate_domain_similarity(domain, domain)
        
        # Property: Identity should yield perfect similarity
        assert similarity == 1.0
    
    @settings(max_examples=5)
    @given(
        domain1=domain_strategy(),
        domain2=domain_strategy()
    )
    def test_property_domain_similarity_symmetry(self, domain1, domain2):
        """
        Property: Domain similarity should be symmetric.
        
        For any pair of domains, similarity(A, B) should equal similarity(B, A).
        
        **Validates: Requirements 4.2**
        """
        detector = FakeSiteDetector()
        
        similarity_ab = detector.calculate_domain_similarity(domain1, domain2)
        similarity_ba = detector.calculate_domain_similarity(domain2, domain1)
        
        # Property: Symmetry
        assert abs(similarity_ab - similarity_ba) < 0.0001  # Allow for floating point errors
    
    @settings(max_examples=5)
    @given(
        content1=st.text(min_size=10, max_size=200),
        content2=st.text(min_size=10, max_size=200)
    )
    def test_property_content_similarity_range(self, content1, content2):
        """
        Property: Content similarity should be in valid range.
        
        For any pair of content strings, the similarity score should be
        between 0.0 and 1.0.
        
        **Validates: Requirements 4.4**
        """
        detector = FakeSiteDetector()
        
        similarity = detector.calculate_content_similarity(content1, content2)
        
        # Property: Similarity score must be in valid range
        assert 0.0 <= similarity <= 1.0
    
    @settings(max_examples=5)
    @given(
        content=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=10, max_size=200)
    )
    def test_property_content_similarity_identity(self, content):
        """
        Property: Content compared to itself should have similarity 1.0.
        
        **Validates: Requirements 4.4**
        
        Note: Uses alphabetic characters to ensure TF-IDF can extract meaningful words.
        """
        # Skip if content has no extractable words
        detector = FakeSiteDetector()
        words = detector._extract_words(content)
        if not words:
            return  # Skip this example
        
        similarity = detector.calculate_content_similarity(content, content)
        
        # Property: Identity should yield perfect similarity (allow small floating point error)
        assert abs(similarity - 1.0) < 1e-10, f"Expected similarity ~1.0, got {similarity}"
    
    @settings(max_examples=5)
    @given(
        legitimate_domain=domain_strategy(),
        candidates=st.lists(domain_strategy(), min_size=0, max_size=10)
    )
    def test_property_scan_returns_valid_suspicious_domains(self, legitimate_domain, candidates):
        """
        Property: Scanning should return valid SuspiciousDomain objects.
        
        All returned suspicious domains should have valid similarity scores
        and proper structure.
        
        **Validates: Requirements 4.1, 4.2, 4.3**
        """
        detector = FakeSiteDetector(domain_similarity_threshold=0.8)
        
        suspicious = detector.scan_similar_domains(legitimate_domain, candidates)
        
        # Property: All returned domains should be valid
        for domain in suspicious:
            assert hasattr(domain, 'domain')
            assert hasattr(domain, 'similarity_score')
            assert hasattr(domain, 'content_similarity')
            assert hasattr(domain, 'is_confirmed_fake')
            assert hasattr(domain, 'legitimate_domain')
            
            # Property: Similarity score should be above threshold
            assert domain.similarity_score >= 0.8
            
            # Property: Similarity score should be in valid range
            assert 0.0 <= domain.similarity_score <= 1.0
            
            # Property: Legitimate domain should match input
            assert domain.legitimate_domain == legitimate_domain
            
            # Property: Initially not confirmed as fake
            assert domain.is_confirmed_fake is False
            assert domain.content_similarity is None
