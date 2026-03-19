"""
Fake Site Detector for Payment Compliance Monitor.

This module detects similar domains and fake sites that may be impersonating
legitimate monitoring targets.
"""

from dataclasses import dataclass
from typing import Optional
import re
from urllib.parse import urlparse


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
    
    Uses Levenshtein distance for domain similarity and TF-IDF for content similarity.
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
        Calculate similarity between two domain names using Levenshtein distance.
        
        Args:
            domain1: First domain name
            domain2: Second domain name
        
        Returns:
            Similarity score between 0.0 and 1.0 (1.0 = identical)
        """
        # Normalize domains (remove www, convert to lowercase)
        d1 = self._normalize_domain(domain1)
        d2 = self._normalize_domain(domain2)
        
        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(d1, d2)
        
        # Convert distance to similarity score (0.0-1.0)
        max_length = max(len(d1), len(d2))
        if max_length == 0:
            return 1.0
        
        similarity = 1.0 - (distance / max_length)
        return max(0.0, min(1.0, similarity))
    
    def _normalize_domain(self, domain: str) -> str:
        """
        Normalize domain name for comparison.
        
        Args:
            domain: Domain name to normalize
        
        Returns:
            Normalized domain name
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
        
        return domain
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
        
        Returns:
            Levenshtein distance (number of edits needed)
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
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
        content2: str
    ) -> float:
        """
        Calculate content similarity using simple TF-IDF approach.
        
        Args:
            content1: First content (HTML or text)
            content2: Second content (HTML or text)
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Extract words from content
        words1 = self._extract_words(content1)
        words2 = self._extract_words(content2)
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate word frequency
        freq1 = self._calculate_word_frequency(words1)
        freq2 = self._calculate_word_frequency(words2)
        
        # Calculate cosine similarity
        similarity = self._cosine_similarity(freq1, freq2)
        
        return similarity
    
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
        Calculate word frequency.
        
        Args:
            words: List of words
        
        Returns:
            Dictionary mapping words to their frequency
        """
        total = len(words)
        if total == 0:
            return {}
        
        freq = {}
        for word in words:
            freq[word] = freq.get(word, 0) + 1
        
        # Normalize by total count
        for word in freq:
            freq[word] = freq[word] / total
        
        return freq
    
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
        suspicious_content: str
    ) -> SuspiciousDomain:
        """
        Verify if a suspicious domain is a confirmed fake site by comparing content.
        
        Args:
            suspicious_domain: The suspicious domain to verify
            legitimate_content: Content from the legitimate site
            suspicious_content: Content from the suspicious site
        
        Returns:
            Updated SuspiciousDomain with content similarity and confirmation status
        """
        content_similarity = self.calculate_content_similarity(
            legitimate_content,
            suspicious_content
        )
        
        is_confirmed_fake = content_similarity >= self.content_similarity_threshold
        
        return SuspiciousDomain(
            domain=suspicious_domain.domain,
            similarity_score=suspicious_domain.similarity_score,
            content_similarity=content_similarity,
            is_confirmed_fake=is_confirmed_fake,
            legitimate_domain=suspicious_domain.legitimate_domain
        )
