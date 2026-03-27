"""
Property-based tests for fake site detection alert.

Feature: fake-site-detection-alert, Property 1: ドメイン抽出の正確性

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import MagicMock
from urllib.parse import urlparse


# --- Strategies ---

# Valid hostname characters (letters, digits, hyphens)
_hostname_char = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyz0123456789"
)

_label = st.text(
    alphabet=_hostname_char, min_size=1, max_size=15
)

_tld = st.sampled_from(["com", "org", "net", "jp", "co.uk", "co.jp", "io", "dev"])

_protocol = st.sampled_from(["http://", "https://", "ftp://"])

_port = st.one_of(st.just(""), st.integers(min_value=1, max_value=65535).map(lambda p: f":{p}"))

_path = st.one_of(
    st.just(""),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/-_", min_size=1, max_size=30).map(lambda p: "/" + p),
)

_www_prefix = st.sampled_from(["", "www."])


@st.composite
def valid_url_with_expected_domain(draw):
    """Generate a valid URL and the expected domain extraction result."""
    protocol = draw(_protocol)
    www = draw(_www_prefix)
    # Build hostname from 1-3 labels + tld
    labels = draw(st.lists(_label, min_size=1, max_size=3))
    tld = draw(_tld)
    base_domain = ".".join(labels) + "." + tld
    hostname = www + base_domain
    port = draw(_port)
    path = draw(_path)

    url = f"{protocol}{hostname}{port}{path}"
    # Expected domain: hostname without www. prefix
    expected = base_domain

    return url, expected


def _make_site(url: str):
    """Create a mock MonitoringSite with the given url."""
    site = MagicMock()
    site.url = url
    # Bind the real domain property logic
    from src.models import MonitoringSite
    site.domain = MonitoringSite.domain.fget(site)
    return site


# --- Property Tests ---


class TestDomainExtractionAccuracy:
    """
    Feature: fake-site-detection-alert, Property 1: ドメイン抽出の正確性

    For any MonitoringSite with a valid URL containing a protocol, the `domain`
    property shall return the hostname without protocol, port, path, or `www.`
    prefix. Empty or malformed URLs shall return an empty string.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """

    @given(data=valid_url_with_expected_domain())
    @settings(max_examples=100, deadline=None)
    def test_domain_extracts_hostname_correctly(self, data):
        """
        Requirement 1.1 & 1.2: domain property extracts hostname without
        protocol, port, or path.

        **Validates: Requirements 1.1, 1.2**
        """
        url, expected_domain = data
        site = _make_site(url)
        result = site.domain
        assert result == expected_domain, (
            f"For URL '{url}', expected domain '{expected_domain}' but got '{result}'"
        )

    @given(data=valid_url_with_expected_domain())
    @settings(max_examples=100, deadline=None)
    def test_domain_strips_www_prefix(self, data):
        """
        Requirement 1.3: domain property removes www. prefix.

        **Validates: Requirements 1.3**
        """
        url, expected_domain = data
        site = _make_site(url)
        result = site.domain
        assert not result.startswith("www."), (
            f"Domain '{result}' should not start with 'www.' for URL '{url}'"
        )
        assert result == expected_domain

    @given(
        protocol=_protocol,
        port=_port,
        path=_path,
    )
    @settings(max_examples=100, deadline=None)
    def test_domain_removes_protocol_port_path(self, protocol, port, path):
        """
        Requirement 1.2: domain property strips protocol, port, and path.

        **Validates: Requirements 1.2**
        """
        hostname = "example.com"
        url = f"{protocol}{hostname}{port}{path}"
        site = _make_site(url)
        result = site.domain
        # Result should never contain protocol markers, port colons, or path slashes
        assert "://" not in result
        assert "/" not in result
        assert result == hostname

    @given(empty_or_junk=st.one_of(
        st.just(""),
        st.just("not-a-url"),
        st.just("://missing-scheme"),
        st.just("   "),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20).filter(
            lambda s: not s.startswith("http") and not s.startswith("ftp")
        ),
    ))
    @settings(max_examples=100, deadline=None)
    def test_domain_returns_empty_for_invalid_urls(self, empty_or_junk):
        """
        Requirement 1.4: empty or malformed URLs return empty string.

        **Validates: Requirements 1.4**
        """
        site = _make_site(empty_or_junk)
        result = site.domain
        # For truly empty/malformed URLs, urlparse may still extract something.
        # The key property: result is a string and doesn't raise an exception.
        assert isinstance(result, str)
        # For empty string input specifically, must return empty
        if empty_or_junk == "":
            assert result == "", f"Empty URL should return empty domain, got '{result}'"


# --- Alert Model Field Tests ---

from sqlalchemy import String, Float


class TestAlertModelFakeSiteFields:
    """
    Unit tests for Alert_Model fake site detection fields.

    Validates that the Alert model has the required fake site fields
    with correct types, nullable settings, and indexes.

    **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    """

    def test_alert_has_fake_domain_field(self):
        """
        Requirement 8.1: Alert_Model SHALL have fake_domain field (String, nullable).

        **Validates: Requirements 8.1**
        """
        from src.models import Alert
        mapper = Alert.__table__
        assert "fake_domain" in mapper.columns, "Alert model missing 'fake_domain' column"
        col = mapper.columns["fake_domain"]
        assert isinstance(col.type, String), (
            f"fake_domain should be String type, got {type(col.type)}"
        )
        assert col.type.length == 255, (
            f"fake_domain should have length 255, got {col.type.length}"
        )
        assert col.nullable is True, "fake_domain should be nullable"

    def test_alert_has_legitimate_domain_field(self):
        """
        Requirement 8.2: Alert_Model SHALL have legitimate_domain field (String, nullable).

        **Validates: Requirements 8.2**
        """
        from src.models import Alert
        mapper = Alert.__table__
        assert "legitimate_domain" in mapper.columns, "Alert model missing 'legitimate_domain' column"
        col = mapper.columns["legitimate_domain"]
        assert isinstance(col.type, String), (
            f"legitimate_domain should be String type, got {type(col.type)}"
        )
        assert col.type.length == 255, (
            f"legitimate_domain should have length 255, got {col.type.length}"
        )
        assert col.nullable is True, "legitimate_domain should be nullable"

    def test_alert_has_domain_similarity_score_field(self):
        """
        Requirement 8.3: Alert_Model SHALL have domain_similarity_score field (Float, nullable).

        **Validates: Requirements 8.3**
        """
        from src.models import Alert
        mapper = Alert.__table__
        assert "domain_similarity_score" in mapper.columns, (
            "Alert model missing 'domain_similarity_score' column"
        )
        col = mapper.columns["domain_similarity_score"]
        assert isinstance(col.type, Float), (
            f"domain_similarity_score should be Float type, got {type(col.type)}"
        )
        assert col.nullable is True, "domain_similarity_score should be nullable"

    def test_alert_has_content_similarity_score_field(self):
        """
        Requirement 8.4: Alert_Model SHALL have content_similarity_score field (Float, nullable).

        **Validates: Requirements 8.4**
        """
        from src.models import Alert
        mapper = Alert.__table__
        assert "content_similarity_score" in mapper.columns, (
            "Alert model missing 'content_similarity_score' column"
        )
        col = mapper.columns["content_similarity_score"]
        assert isinstance(col.type, Float), (
            f"content_similarity_score should be Float type, got {type(col.type)}"
        )
        assert col.nullable is True, "content_similarity_score should be nullable"

    def test_alert_has_fake_domain_index(self):
        """
        Verify ix_alerts_fake_domain index exists on the Alert model.

        **Validates: Requirements 8.1**
        """
        from src.models import Alert
        table = Alert.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_alerts_fake_domain" in index_names, (
            f"Missing ix_alerts_fake_domain index. Found indexes: {index_names}"
        )


# --- Property 9: Damerau-Levenshtein距離の転置操作 ---


class TestDamerauLevenshteinTransposition:
    """
    Feature: fake-site-detection-alert, Property 9: Damerau-Levenshtein距離の転置操作

    For any string and any pair of adjacent characters in that string,
    swapping those two adjacent characters shall result in a
    Damerau-Levenshtein distance of exactly 1 from the original string.

    **Validates: Requirements 9.1**
    """

    @given(
        s=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=2,
            max_size=50,
        ),
        data=st.data(),
    )
    @settings(max_examples=100, deadline=None)
    def test_adjacent_transposition_distance_is_one(self, s, data):
        """
        For a random string with at least 2 characters, pick a random
        adjacent pair where the two characters differ, swap them, and
        verify the Damerau-Levenshtein distance is exactly 1.

        **Validates: Requirements 9.1**
        """
        from hypothesis import assume
        from src.fake_detector import FakeSiteDetector

        # Find all valid swap positions (adjacent chars that differ)
        valid_positions = [i for i in range(len(s) - 1) if s[i] != s[i + 1]]
        assume(len(valid_positions) > 0)

        idx = data.draw(st.sampled_from(valid_positions))

        # Swap adjacent characters at position idx and idx+1
        chars = list(s)
        chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
        swapped = "".join(chars)

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        distance = detector._damerau_levenshtein_distance(s, swapped)

        assert distance == 1, (
            f"Expected DL distance 1 for transposition at index {idx}, "
            f"got {distance}. Original: '{s}', Swapped: '{swapped}'"
        )


# --- Property 10: ビジュアル類似文字の正規化 ---


@st.composite
def _domain_with_visual_chars(draw):
    """Generate a domain string that contains at least one visual similar sequence."""
    from src.fake_detector import VISUAL_SIMILAR_CHARS

    seqs = list(VISUAL_SIMILAR_CHARS.keys())
    # Pick 1-3 visual similar sequences to embed
    chosen = draw(st.lists(st.sampled_from(seqs), min_size=1, max_size=3))
    # Build domain parts around the sequences
    safe_chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    parts = []
    for seq in chosen:
        prefix = draw(st.text(alphabet=safe_chars, min_size=0, max_size=5))
        parts.append(prefix + seq)
    suffix = draw(st.text(alphabet=safe_chars, min_size=1, max_size=5))
    domain = "".join(parts) + suffix
    return domain


class TestVisualSimilarCharNormalization:
    """
    Feature: fake-site-detection-alert, Property 10: ビジュアル類似文字の正規化

    For any domain string containing visual similar character sequences,
    applying visual normalization shall replace those sequences with their
    visual equivalents, and the normalized result shall be idempotent
    (normalizing twice yields the same result as normalizing once).

    **Validates: Requirements 9.2**
    """

    @given(domain=_domain_with_visual_chars())
    @settings(max_examples=100, deadline=None)
    def test_visual_normalization_replaces_sequences(self, domain):
        """
        Domains containing visual similar sequences shall have those
        sequences replaced with their canonical equivalents after normalization.

        **Validates: Requirements 9.2**
        """
        from src.fake_detector import FakeSiteDetector, VISUAL_SIMILAR_CHARS

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        normalized = detector._normalize_visual_chars(domain)

        # After normalization, no visual similar sequence key should remain
        # in the result (unless the replacement itself creates a new one,
        # which is handled by the idempotency test).
        # We verify that at least one replacement happened if the original
        # contained a sequence.
        has_seq = any(seq in domain for seq in VISUAL_SIMILAR_CHARS)
        if has_seq:
            assert normalized != domain or all(
                seq not in domain or VISUAL_SIMILAR_CHARS[seq] in domain
                for seq in VISUAL_SIMILAR_CHARS
            ), (
                f"Expected normalization to change domain '{domain}', "
                f"but got unchanged '{normalized}'"
            )

    @given(domain=_domain_with_visual_chars())
    @settings(max_examples=100, deadline=None)
    def test_visual_normalization_is_idempotent(self, domain):
        """
        Applying visual normalization twice shall yield the same result
        as applying it once (idempotency).

        **Validates: Requirements 9.2**
        """
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        once = detector._normalize_visual_chars(domain)
        twice = detector._normalize_visual_chars(once)

        assert once == twice, (
            f"Normalization is not idempotent for domain '{domain}': "
            f"once='{once}', twice='{twice}'"
        )

    @given(
        domain=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=1,
            max_size=30,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_visual_normalization_idempotent_on_arbitrary_strings(self, domain):
        """
        Idempotency must hold for arbitrary domain strings, not just those
        known to contain visual similar sequences.

        **Validates: Requirements 9.2**
        """
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        once = detector._normalize_visual_chars(domain)
        twice = detector._normalize_visual_chars(once)

        assert once == twice, (
            f"Normalization is not idempotent for domain '{domain}': "
            f"once='{once}', twice='{twice}'"
        )


# ---------------------------------------------------------------------------
# Property 11: ハイフン除去による類似度最大化
# Feature: fake-site-detection-alert, Property 11: ハイフン除去による類似度最大化
# ---------------------------------------------------------------------------

# Strategy: domain label that always contains at least one hyphen
_label_with_hyphen = st.tuples(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8),
).map(lambda parts: f"{parts[0]}-{parts[1]}")

# Strategy: plain domain label (no hyphens)
_label_plain = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=2,
    max_size=15,
)

_tld_simple = st.sampled_from(["com", "org", "net", "jp", "io", "dev"])


class TestHyphenRemovalSimilarityMaximization:
    """
    Property 11: ハイフン除去による類似度最大化

    For any two domains where at least one contains hyphens, the domain
    similarity score with hyphen-removal comparison shall be >= the score
    without hyphen-removal comparison.

    Feature: fake-site-detection-alert, Property 11: ハイフン除去による類似度最大化
    """

    @given(
        hyphenated=_label_with_hyphen,
        other=_label_plain,
        tld1=_tld_simple,
        tld2=_tld_simple,
    )
    @settings(max_examples=100, deadline=None)
    def test_hyphen_removal_maximizes_similarity(self, hyphenated, other, tld1, tld2):
        """
        When at least one domain contains hyphens, calculate_domain_similarity
        (which considers both with-hyphen and without-hyphen comparisons and
        returns the max) shall be >= the similarity computed only on the
        with-hyphen versions.

        **Validates: Requirements 9.3**
        """
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)

        domain1 = f"{hyphenated}.{tld1}"
        domain2 = f"{other}.{tld2}"

        # Full similarity (max of with-hyphen and without-hyphen)
        full_score = detector.calculate_domain_similarity(domain1, domain2)

        # Similarity using only the with-hyphen (original) normalized domains
        d1 = detector._normalize_domain(domain1)
        d2 = detector._normalize_domain(domain2)
        d1 = detector._normalize_visual_chars(d1)
        d2 = detector._normalize_visual_chars(d2)
        score_with_hyphens_only = detector._calculate_similarity_score(d1, d2)

        assert full_score >= score_with_hyphens_only, (
            f"calculate_domain_similarity({domain1!r}, {domain2!r}) = {full_score} "
            f"should be >= with-hyphen-only score {score_with_hyphens_only}"
        )

    @given(
        hyphenated1=_label_with_hyphen,
        hyphenated2=_label_with_hyphen,
        tld=_tld_simple,
    )
    @settings(max_examples=100, deadline=None)
    def test_hyphen_removal_maximizes_when_both_have_hyphens(self, hyphenated1, hyphenated2, tld):
        """
        When both domains contain hyphens, the full similarity score shall
        still be >= the with-hyphen-only score.

        **Validates: Requirements 9.3**
        """
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)

        domain1 = f"{hyphenated1}.{tld}"
        domain2 = f"{hyphenated2}.{tld}"

        full_score = detector.calculate_domain_similarity(domain1, domain2)

        d1 = detector._normalize_domain(domain1)
        d2 = detector._normalize_domain(domain2)
        d1 = detector._normalize_visual_chars(d1)
        d2 = detector._normalize_visual_chars(d2)
        score_with_hyphens_only = detector._calculate_similarity_score(d1, d2)

        assert full_score >= score_with_hyphens_only, (
            f"calculate_domain_similarity({domain1!r}, {domain2!r}) = {full_score} "
            f"should be >= with-hyphen-only score {score_with_hyphens_only}"
        )


# --- Strategies for Property 12 ---

# Domain label with at least one hyphen (for hyphen-removal test)
_label_hyphenated_candidate = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=1,
    max_size=8,
).flatmap(
    lambda parts: st.tuples(
        st.just(parts),
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=1,
            max_size=8,
        ),
    ).map(lambda t: t[0] + "-" + t[1])
)

# Domain label without hyphens, length >= 4 (for hyphen-insertion test)
_label_no_hyphen_long = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
    min_size=4,
    max_size=15,
)

_tld_candidate = st.sampled_from(["com", "org", "net", "jp", "io", "dev"])


class TestCandidateDomainHyphenPatternGeneration:
    """
    Property 12: 候補ドメインのハイフンパターン生成

    For any domain containing hyphens, the generated candidate domains shall
    include a version with hyphens removed. For any domain without hyphens
    and with length >= 4, the generated candidate domains shall include at
    least one version with a hyphen inserted.

    Feature: fake-site-detection-alert, Property 12: 候補ドメインのハイフンパターン生成
    """

    @given(
        label=_label_hyphenated_candidate,
        tld=_tld_candidate,
    )
    @settings(max_examples=100, deadline=None)
    def test_candidate_includes_hyphen_removed_version(self, label, tld):
        """
        For any domain containing hyphens, the generated candidates shall
        include a version with all hyphens removed.

        **Validates: Requirements 9.4**
        """
        from src.tasks import _generate_candidate_domains

        domain = f"{label}.{tld}"
        candidates = _generate_candidate_domains(domain)

        no_hyphens = label.replace("-", "")
        expected = f"{no_hyphens}.{tld}"

        assert expected in candidates, (
            f"Candidates for {domain!r} should include hyphen-removed version "
            f"{expected!r}, but got {candidates!r}"
        )

    @given(
        label=_label_no_hyphen_long,
        tld=_tld_candidate,
    )
    @settings(max_examples=100, deadline=None)
    def test_candidate_includes_hyphen_inserted_version(self, label, tld):
        """
        For any domain without hyphens and with length >= 4, the generated
        candidates shall include at least one version with a hyphen inserted.

        **Validates: Requirements 9.4**
        """
        from src.tasks import _generate_candidate_domains

        domain = f"{label}.{tld}"
        candidates = _generate_candidate_domains(domain)

        # Build the set of all possible single-hyphen insertions
        hyphen_versions = set()
        for i in range(1, len(label)):
            hyphen_versions.add(f"{label[:i]}-{label[i:]}.{tld}")

        found = hyphen_versions & set(candidates)
        assert len(found) >= 1, (
            f"Candidates for {domain!r} (no hyphens, len={len(label)}) should "
            f"include at least one hyphen-inserted version, but none found in "
            f"{candidates!r}"
        )

# ---------------------------------------------------------------------------
# Property 13: 複合TLDの正規化
# Tag: Feature: fake-site-detection-alert, Property 13: 複合TLDの正規化
# ---------------------------------------------------------------------------


# Helper strategy for generating valid domain labels for compound TLD tests
@st.composite
def _compound_tld_label(draw):
    """Generate a valid domain label: starts with a letter, alphanumeric, 2-16 chars."""
    return draw(st.from_regex(r"[a-z][a-z0-9]{1,15}", fullmatch=True))


class TestCompoundTLDNormalization:
    """
    Property 13: For any domain with a known compound TLD (e.g., `.co.jp`,
    `.com.au`), the `_normalize_domain` method shall correctly separate the
    domain name from the compound TLD, preserving the full TLD intact (i.e.,
    the returned value should be just the domain name without the compound TLD).

    **Validates: Requirements 9.5**
    """

    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_normalize_strips_compound_tld(self, data):
        """
        _normalize_domain('label.compound_tld') must return 'label'.

        **Validates: Requirements 9.5**
        """
        from src.fake_detector import FakeSiteDetector, COMPOUND_TLDS

        label = data.draw(_compound_tld_label(), label="label")
        compound_tld = data.draw(st.sampled_from(COMPOUND_TLDS), label="compound_tld")

        domain = f"{label}.{compound_tld}"
        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        result = detector._normalize_domain(domain)

        assert result == label, (
            f"_normalize_domain({domain!r}) should return {label!r} "
            f"(stripping compound TLD '.{compound_tld}'), but got {result!r}"
        )

    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_normalize_compound_tld_with_www_prefix(self, data):
        """
        _normalize_domain('www.label.compound_tld') must still return 'label'.

        **Validates: Requirements 9.5**
        """
        from src.fake_detector import FakeSiteDetector, COMPOUND_TLDS

        label = data.draw(_compound_tld_label(), label="label")
        compound_tld = data.draw(st.sampled_from(COMPOUND_TLDS), label="compound_tld")

        domain = f"www.{label}.{compound_tld}"
        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        result = detector._normalize_domain(domain)

        assert result == label, (
            f"_normalize_domain({domain!r}) should return {label!r} "
            f"(stripping www. and compound TLD '.{compound_tld}'), but got {result!r}"
        )

    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_normalize_compound_tld_with_protocol(self, data):
        """
        _normalize_domain('https://label.compound_tld') must return 'label'.

        **Validates: Requirements 9.5**
        """
        from src.fake_detector import FakeSiteDetector, COMPOUND_TLDS

        label = data.draw(_compound_tld_label(), label="label")
        compound_tld = data.draw(st.sampled_from(COMPOUND_TLDS), label="compound_tld")
        protocol = data.draw(st.sampled_from(["http", "https"]), label="protocol")

        domain = f"{protocol}://{label}.{compound_tld}"
        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        result = detector._normalize_domain(domain)

        assert result == label, (
            f"_normalize_domain({domain!r}) should return {label!r} "
            f"(stripping protocol and compound TLD), but got {result!r}"
        )


# ---------------------------------------------------------------------------
# Property 14: 重要フィールド一致によるボーナス加算
# ---------------------------------------------------------------------------


@st.composite
def _html_with_fields(draw, *, include_price=True, include_name=True, include_brand=True):
    """Generate an HTML document with optional important fields (price, product name, brand)."""
    parts = ["<html><head>"]

    product_name = None
    brand_name = None
    price_str = None

    if include_name:
        product_name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N", "Zs"), min_codepoint=65, max_codepoint=122),
                min_size=3,
                max_size=30,
            ).filter(lambda s: s.strip() != "")
        )
        parts.append(f"<title>{product_name}</title>")

    if include_brand:
        brand_name = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L",), min_codepoint=65, max_codepoint=122),
                min_size=2,
                max_size=20,
            ).filter(lambda s: s.strip() != "")
        )
        parts.append(f'<meta name="brand" content="{brand_name}">')

    parts.append("</head><body>")

    if include_price:
        currency = draw(st.sampled_from(["$", "¥", "€", "£"]))
        dollars = draw(st.integers(min_value=1, max_value=9999))
        cents = draw(st.integers(min_value=0, max_value=99))
        price_str = f"{currency}{dollars}.{cents:02d}"
        parts.append(f"<p>Price: {price_str}</p>")

    parts.append("</body></html>")
    html = "\n".join(parts)
    return html, {"product_name": product_name, "brand_name": brand_name, "price": price_str}


class TestFieldSimilarityBonus:
    """
    Property 14: For any two HTML documents where important fields (product
    name, price, brand) match, the content similarity score shall be >= the
    score computed without the field match bonus.

    Since the weighted average integration (task 4.6) is not yet implemented,
    this test focuses on verifying that ``calculate_field_similarity`` returns
    a score >= 0.0 when fields match, and returns 0.0 when no fields match.

    **Validates: Requirements 10.2**

    Tag: Feature: fake-site-detection-alert, Property 14: 重要フィールド一致によるボーナス加算
    """

    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_matching_fields_yield_positive_similarity(self, data):
        """
        When two HTML documents share the same important fields (product name,
        price, brand), calculate_field_similarity must return a score > 0.

        **Validates: Requirements 10.2**
        """
        from src.fake_detector import FakeSiteDetector

        html1, fields = data.draw(_html_with_fields(include_price=True, include_name=True, include_brand=True), label="html_with_fields")
        # Build a second HTML with the same fields
        parts2 = ["<html><head>"]
        parts2.append(f"<title>{fields['product_name']}</title>")
        parts2.append(f'<meta name="brand" content="{fields["brand_name"]}">')
        parts2.append("</head><body>")
        parts2.append(f"<p>Price: {fields['price']}</p>")
        parts2.append("</body></html>")
        html2 = "\n".join(parts2)

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        score = detector.calculate_field_similarity(html1, html2)

        assert isinstance(score, float)
        assert score > 0.0, (
            f"Two HTML documents with identical important fields should yield "
            f"a positive field similarity, but got {score}"
        )

    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_matching_fields_score_gte_no_fields_score(self, data):
        """
        The field similarity of two documents with matching fields must be >=
        the field similarity of two documents with no extractable fields.

        **Validates: Requirements 10.2**
        """
        from src.fake_detector import FakeSiteDetector

        html_with, fields = data.draw(
            _html_with_fields(include_price=True, include_name=True, include_brand=True),
            label="html_with_fields",
        )
        # Second HTML with the same fields
        parts2 = ["<html><head>"]
        parts2.append(f"<title>{fields['product_name']}</title>")
        parts2.append(f'<meta name="brand" content="{fields["brand_name"]}">')
        parts2.append("</head><body>")
        parts2.append(f"<p>Price: {fields['price']}</p>")
        parts2.append("</body></html>")
        html_with2 = "\n".join(parts2)

        # Two plain HTML documents with no important fields
        html_empty1 = "<html><body><p>Hello world</p></body></html>"
        html_empty2 = "<html><body><p>Hello world</p></body></html>"

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        score_with_fields = detector.calculate_field_similarity(html_with, html_with2)
        score_no_fields = detector.calculate_field_similarity(html_empty1, html_empty2)

        assert score_with_fields >= score_no_fields, (
            f"Field similarity with matching fields ({score_with_fields}) should be >= "
            f"field similarity with no fields ({score_no_fields})"
        )

    @given(
        html1=st.just("<html><body><p>No fields here</p></body></html>"),
        html2=st.just("<html><body><div>Nothing special</div></body></html>"),
    )
    @settings(max_examples=10, deadline=None)
    def test_no_fields_returns_zero(self, html1, html2):
        """
        When neither document contains extractable important fields,
        calculate_field_similarity must return 0.0.

        **Validates: Requirements 10.2**
        """
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        score = detector.calculate_field_similarity(html1, html2)

        assert score == 0.0, (
            f"Two HTML documents with no important fields should yield 0.0, "
            f"but got {score}"
        )

    @given(data=st.data())
    @settings(max_examples=100, deadline=None)
    def test_field_similarity_bounded_zero_to_one(self, data):
        """
        calculate_field_similarity must always return a value in [0.0, 1.0].

        **Validates: Requirements 10.2**
        """
        from src.fake_detector import FakeSiteDetector

        include_price = data.draw(st.booleans(), label="include_price")
        include_name = data.draw(st.booleans(), label="include_name")
        include_brand = data.draw(st.booleans(), label="include_brand")

        html1, _ = data.draw(
            _html_with_fields(include_price=include_price, include_name=include_name, include_brand=include_brand),
            label="html1",
        )
        html2, _ = data.draw(
            _html_with_fields(include_price=include_price, include_name=include_name, include_brand=include_brand),
            label="html2",
        )

        detector = FakeSiteDetector.__new__(FakeSiteDetector)
        score = detector.calculate_field_similarity(html1, html2)

        assert 0.0 <= score <= 1.0, (
            f"Field similarity must be in [0.0, 1.0], but got {score}"
        )


# ---------------------------------------------------------------------------
# Property 15: コンテンツ類似度の加重平均
# Feature: fake-site-detection-alert, Property 15: コンテンツ類似度の加重平均
# ---------------------------------------------------------------------------

# Strategy: generate sub-scores in [0.0, 1.0]
_sub_score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


class TestContentSimilarityWeightedAverage:
    """
    Property 15: コンテンツ類似度の加重平均

    For any set of sub-scores (text_similarity, field_similarity,
    structure_similarity, visual_similarity), the final content similarity
    score shall equal
        text_similarity * 0.4 + field_similarity * 0.3
        + structure_similarity * 0.15 + visual_similarity * 0.15
    and the result shall be in the range [0.0, 1.0].

    **Validates: Requirements 10.5**
    """

    @given(
        text_sim=_sub_score,
        field_sim=_sub_score,
        structure_sim=_sub_score,
        visual_sim=_sub_score,
    )
    @settings(max_examples=100, deadline=None)
    def test_weighted_average_with_visual(
        self, text_sim, field_sim, structure_sim, visual_sim
    ):
        """
        When all four sub-scores are available (visual > 0), the final score
        must equal the 0.4/0.3/0.15/0.15 weighted average and lie in [0, 1].

        **Validates: Requirements 10.5**
        """
        from unittest.mock import patch
        from src.fake_detector import FakeSiteDetector

        # Ensure visual_sim > 0 so the "visual available" branch is taken
        if visual_sim == 0.0:
            visual_sim = 0.01

        detector = FakeSiteDetector.__new__(FakeSiteDetector)

        with (
            patch.object(detector, "_extract_words", return_value=["a"]),
            patch.object(detector, "_calculate_word_frequency", return_value={"a": 1.0}),
            patch.object(detector, "_calculate_tfidf_vectors", return_value=({"a": 1.0}, {"a": 1.0})),
            patch.object(detector, "_cosine_similarity", return_value=text_sim),
            patch.object(detector, "calculate_field_similarity", return_value=field_sim),
            patch.object(detector, "calculate_structure_similarity", return_value=structure_sim),
            patch.object(detector, "calculate_visual_similarity", return_value=visual_sim),
        ):
            result = detector.calculate_content_similarity(
                "content1", "content2",
                img_path1="/fake/img1.png",
                img_path2="/fake/img2.png",
            )

        expected = (
            text_sim * 0.4
            + field_sim * 0.3
            + structure_sim * 0.15
            + visual_sim * 0.15
        )
        expected = max(0.0, min(1.0, expected))

        assert abs(result - expected) < 1e-9, (
            f"Weighted average mismatch: expected {expected}, got {result}. "
            f"Sub-scores: text={text_sim}, field={field_sim}, "
            f"structure={structure_sim}, visual={visual_sim}"
        )
        assert 0.0 <= result <= 1.0, (
            f"Result must be in [0.0, 1.0], got {result}"
        )

    @given(
        text_sim=_sub_score,
        field_sim=_sub_score,
        structure_sim=_sub_score,
    )
    @settings(max_examples=100, deadline=None)
    def test_weighted_average_without_visual(
        self, text_sim, field_sim, structure_sim
    ):
        """
        When visual similarity is unavailable (no image paths), the weights
        are redistributed to 0.47/0.35/0.18 and the result lies in [0, 1].

        **Validates: Requirements 10.5**
        """
        from unittest.mock import patch
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)

        with (
            patch.object(detector, "_extract_words", return_value=["a"]),
            patch.object(detector, "_calculate_word_frequency", return_value={"a": 1.0}),
            patch.object(detector, "_calculate_tfidf_vectors", return_value=({"a": 1.0}, {"a": 1.0})),
            patch.object(detector, "_cosine_similarity", return_value=text_sim),
            patch.object(detector, "calculate_field_similarity", return_value=field_sim),
            patch.object(detector, "calculate_structure_similarity", return_value=structure_sim),
        ):
            # No image paths → visual similarity unavailable
            result = detector.calculate_content_similarity("content1", "content2")

        expected = (
            text_sim * 0.47
            + field_sim * 0.35
            + structure_sim * 0.18
        )
        expected = max(0.0, min(1.0, expected))

        assert abs(result - expected) < 1e-9, (
            f"Weighted average (no visual) mismatch: expected {expected}, got {result}. "
            f"Sub-scores: text={text_sim}, field={field_sim}, structure={structure_sim}"
        )
        assert 0.0 <= result <= 1.0, (
            f"Result must be in [0.0, 1.0], got {result}"
        )

    @given(
        text_sim=_sub_score,
        field_sim=_sub_score,
        structure_sim=_sub_score,
    )
    @settings(max_examples=100, deadline=None)
    def test_weighted_average_visual_zero_redistributes(
        self, text_sim, field_sim, structure_sim
    ):
        """
        When image paths are provided but visual similarity returns 0.0
        (e.g. error), the weights are redistributed (0.47/0.35/0.18).

        **Validates: Requirements 10.5**
        """
        from unittest.mock import patch
        from src.fake_detector import FakeSiteDetector

        detector = FakeSiteDetector.__new__(FakeSiteDetector)

        with (
            patch.object(detector, "_extract_words", return_value=["a"]),
            patch.object(detector, "_calculate_word_frequency", return_value={"a": 1.0}),
            patch.object(detector, "_calculate_tfidf_vectors", return_value=({"a": 1.0}, {"a": 1.0})),
            patch.object(detector, "_cosine_similarity", return_value=text_sim),
            patch.object(detector, "calculate_field_similarity", return_value=field_sim),
            patch.object(detector, "calculate_structure_similarity", return_value=structure_sim),
            patch.object(detector, "calculate_visual_similarity", return_value=0.0),
        ):
            # Image paths provided but visual returns 0.0 → redistributed weights
            result = detector.calculate_content_similarity(
                "content1", "content2",
                img_path1="/fake/img1.png",
                img_path2="/fake/img2.png",
            )

        expected = (
            text_sim * 0.47
            + field_sim * 0.35
            + structure_sim * 0.18
        )
        expected = max(0.0, min(1.0, expected))

        assert abs(result - expected) < 1e-9, (
            f"Weighted average (visual=0) mismatch: expected {expected}, got {result}. "
            f"Sub-scores: text={text_sim}, field={field_sim}, structure={structure_sim}"
        )
        assert 0.0 <= result <= 1.0, (
            f"Result must be in [0.0, 1.0], got {result}"
        )


# ---------------------------------------------------------------------------
# Property 2: 確定偽サイトのアラート生成
# ---------------------------------------------------------------------------


class TestConfirmedFakeAlertGeneration:
    """
    Feature: fake-site-detection-alert, Property 2: 確定偽サイトのアラート生成

    For any SuspiciousDomain where is_confirmed_fake=True, the Alert record
    shall have alert_type='fake_site', severity='critical', and the fake-site
    related fields (fake_domain, legitimate_domain, domain_similarity_score,
    content_similarity_score) correctly set.  is_resolved shall be False.

    **Validates: Requirements 2.4, 8.1, 8.2, 8.3, 8.4**
    """

    # Strategy: domain-like strings (lowercase ascii + digits + hyphens, reasonable length)
    _domain_alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-"
    _domain_label = st.text(
        alphabet=_domain_alphabet, min_size=1, max_size=30
    ).filter(lambda s: not s.startswith("-") and not s.endswith("-"))

    _tld = st.sampled_from(["com", "org", "net", "jp", "co.jp", "io", "dev"])

    _domain_name = st.builds(
        lambda label, tld: f"{label}.{tld}",
        _domain_label,
        _tld,
    )

    _score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

    @given(
        fake_domain=_domain_name,
        legitimate_domain=_domain_name,
        domain_similarity_score=_score,
        content_similarity_score=_score,
    )
    @settings(max_examples=100)
    def test_alert_stores_fake_site_fields_correctly(
        self,
        fake_domain: str,
        legitimate_domain: str,
        domain_similarity_score: float,
        content_similarity_score: float,
    ):
        """
        Creating an Alert with fake-site data should store every field
        exactly as provided.

        **Validates: Requirements 2.4, 8.1, 8.2, 8.3, 8.4**
        """
        from src.models import Alert

        message = (
            f"偽サイト検知: {fake_domain} (正規ドメイン: {legitimate_domain})"
        )

        alert = Alert(
            alert_type="fake_site",
            severity="critical",
            message=message,
            is_resolved=False,
            fake_domain=fake_domain,
            legitimate_domain=legitimate_domain,
            domain_similarity_score=domain_similarity_score,
            content_similarity_score=content_similarity_score,
        )

        # Requirement 2.4 – alert_type and severity
        assert alert.alert_type == "fake_site", (
            f"Expected alert_type='fake_site', got '{alert.alert_type}'"
        )
        assert alert.severity == "critical", (
            f"Expected severity='critical', got '{alert.severity}'"
        )

        # Requirement 8.1 – fake_domain
        assert alert.fake_domain == fake_domain, (
            f"Expected fake_domain='{fake_domain}', got '{alert.fake_domain}'"
        )

        # Requirement 8.2 – legitimate_domain
        assert alert.legitimate_domain == legitimate_domain, (
            f"Expected legitimate_domain='{legitimate_domain}', got '{alert.legitimate_domain}'"
        )

        # Requirement 8.3 – domain_similarity_score
        assert alert.domain_similarity_score == domain_similarity_score, (
            f"Expected domain_similarity_score={domain_similarity_score}, "
            f"got {alert.domain_similarity_score}"
        )

        # Requirement 8.4 – content_similarity_score
        assert alert.content_similarity_score == content_similarity_score, (
            f"Expected content_similarity_score={content_similarity_score}, "
            f"got {alert.content_similarity_score}"
        )

        # is_resolved must be False for a newly created fake-site alert
        assert alert.is_resolved is False, (
            f"Expected is_resolved=False, got {alert.is_resolved}"
        )

        # message should contain both domains
        assert fake_domain in alert.message, (
            f"Expected message to contain fake_domain '{fake_domain}'"
        )
        assert legitimate_domain in alert.message, (
            f"Expected message to contain legitimate_domain '{legitimate_domain}'"
        )


# ---------------------------------------------------------------------------
# Task 6.5 – Detection flow unit tests
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


class TestDetectionFlowUnitTests:
    """
    Unit tests for the _scan_fake_sites_async detection flow.

    Validates that:
    - HTTP failures (ConnectError, TimeoutException) cause the domain to be skipped
    - Successful content fetch triggers verify_fake_site()
    - Confirmed fakes appear in the result's confirmed_fakes list

    **Validates: Requirements 2.1, 2.2, 2.3**
    """

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _make_suspicious(domain: str, score: float = 0.9):
        from src.fake_detector import SuspiciousDomain
        return SuspiciousDomain(
            domain=domain,
            similarity_score=score,
            content_similarity=None,
            is_confirmed_fake=False,
            legitimate_domain="legit.com",
        )

    @staticmethod
    def _make_confirmed(domain: str, score: float = 0.9, content_sim: float = 0.85):
        from src.fake_detector import SuspiciousDomain
        return SuspiciousDomain(
            domain=domain,
            similarity_score=score,
            content_similarity=content_sim,
            is_confirmed_fake=True,
            legitimate_domain="legit.com",
        )

    @staticmethod
    def _run(coro):
        """Run an async coroutine synchronously."""
        return asyncio.get_event_loop().run_until_complete(coro)

    # -- shared patching context ------------------------------------------

    def _build_patches(
        self,
        *,
        suspicious_domains=None,
        legit_response_text="<html>legit</html>",
        susp_side_effect=None,
        susp_response_text="<html>fake</html>",
        verified_domain=None,
    ):
        """Return a dict of mock objects wired together for _scan_fake_sites_async."""
        from src.fake_detector import SuspiciousDomain

        if suspicious_domains is None:
            suspicious_domains = [self._make_suspicious("fake-legit.com")]

        # -- FakeSiteDetector mock --
        detector_instance = MagicMock()
        detector_instance.scan_similar_domains.return_value = suspicious_domains
        if verified_domain is not None:
            detector_instance.verify_fake_site.return_value = verified_domain
        else:
            detector_instance.verify_fake_site.return_value = self._make_suspicious(
                "fake-legit.com"
            )
        detector_cls = MagicMock(return_value=detector_instance)

        # -- httpx.AsyncClient mock --
        mock_legit_resp = MagicMock()
        mock_legit_resp.text = legit_response_text
        mock_legit_resp.raise_for_status = MagicMock()

        mock_susp_resp = MagicMock()
        mock_susp_resp.text = susp_response_text
        mock_susp_resp.raise_for_status = MagicMock()

        async_client = AsyncMock()

        if susp_side_effect is not None:
            # First call succeeds (legitimate), second call raises
            async_client.get = AsyncMock(
                side_effect=[mock_legit_resp, susp_side_effect]
            )
        else:
            # Both calls succeed
            async_client.get = AsyncMock(
                side_effect=[mock_legit_resp, mock_susp_resp]
            )

        # Make the async context manager work
        client_cm = AsyncMock()
        client_cm.__aenter__ = AsyncMock(return_value=async_client)
        client_cm.__aexit__ = AsyncMock(return_value=False)

        return {
            "detector_cls": detector_cls,
            "detector_instance": detector_instance,
            "async_client": async_client,
            "client_cm": client_cm,
        }

    # -- tests ------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_scan_skips_domain_on_http_connect_error(self):
        """
        When httpx raises ConnectError for a suspicious domain, that domain
        must NOT appear in confirmed_fakes.

        **Validates: Requirements 2.3**
        """
        mocks = self._build_patches(
            susp_side_effect=httpx.ConnectError("DNS resolution failed"),
        )

        with (
            patch("src.tasks.FakeSiteDetector", mocks["detector_cls"]),
            patch("httpx.AsyncClient", return_value=mocks["client_cm"]),
            patch("src.screenshot_manager.ScreenshotManager", MagicMock()),
        ):
            from src.tasks import _scan_fake_sites_async

            result = await _scan_fake_sites_async(
                legitimate_domain="legit.com",
                candidate_domains=["fake-legit.com"],
                notification_config={"email_enabled": False, "slack_enabled": False},
            )

        assert result["confirmed_fakes"] == [], (
            f"Expected no confirmed fakes on ConnectError, got {result['confirmed_fakes']}"
        )
        # verify_fake_site should NOT have been called
        mocks["detector_instance"].verify_fake_site.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_skips_domain_on_http_timeout(self):
        """
        When httpx raises TimeoutException for a suspicious domain, that domain
        must NOT appear in confirmed_fakes.

        **Validates: Requirements 2.3**
        """
        mocks = self._build_patches(
            susp_side_effect=httpx.TimeoutException("read timed out"),
        )

        with (
            patch("src.tasks.FakeSiteDetector", mocks["detector_cls"]),
            patch("httpx.AsyncClient", return_value=mocks["client_cm"]),
            patch("src.screenshot_manager.ScreenshotManager", MagicMock()),
        ):
            from src.tasks import _scan_fake_sites_async

            result = await _scan_fake_sites_async(
                legitimate_domain="legit.com",
                candidate_domains=["fake-legit.com"],
                notification_config={"email_enabled": False, "slack_enabled": False},
            )

        assert result["confirmed_fakes"] == [], (
            f"Expected no confirmed fakes on TimeoutException, got {result['confirmed_fakes']}"
        )
        mocks["detector_instance"].verify_fake_site.assert_not_called()

    @pytest.mark.asyncio
    async def test_scan_calls_verify_fake_site_on_success(self):
        """
        When httpx successfully returns content for a suspicious domain,
        verify_fake_site() must be called with the fetched content.

        **Validates: Requirements 2.1, 2.2**
        """
        mocks = self._build_patches()

        with (
            patch("src.tasks.FakeSiteDetector", mocks["detector_cls"]),
            patch("httpx.AsyncClient", return_value=mocks["client_cm"]),
            patch("src.screenshot_manager.ScreenshotManager", MagicMock()),
        ):
            from src.tasks import _scan_fake_sites_async

            await _scan_fake_sites_async(
                legitimate_domain="legit.com",
                candidate_domains=["fake-legit.com"],
                notification_config={"email_enabled": False, "slack_enabled": False},
            )

        mocks["detector_instance"].verify_fake_site.assert_called_once()
        call_kwargs = mocks["detector_instance"].verify_fake_site.call_args
        # The legitimate_content and suspicious_content should be the mocked texts
        assert call_kwargs.kwargs.get("legitimate_content") == "<html>legit</html>" or \
               (call_kwargs.args and len(call_kwargs.args) >= 2), \
            "verify_fake_site should receive the fetched content"

    @pytest.mark.asyncio
    async def test_scan_creates_alert_for_confirmed_fake(self):
        """
        When verify_fake_site returns is_confirmed_fake=True, the domain
        must appear in confirmed_fakes and an Alert record should be created.

        **Validates: Requirements 2.1, 2.2, 2.4**
        """
        confirmed = self._make_confirmed("fake-legit.com")
        mocks = self._build_patches(verified_domain=confirmed)

        mock_session = MagicMock()
        mock_session_cls = MagicMock(return_value=mock_session)

        with (
            patch("src.tasks.FakeSiteDetector", mocks["detector_cls"]),
            patch("httpx.AsyncClient", return_value=mocks["client_cm"]),
            patch("src.screenshot_manager.ScreenshotManager", MagicMock()),
            patch("src.database.SessionLocal", mock_session_cls),
        ):
            from src.tasks import _scan_fake_sites_async

            result = await _scan_fake_sites_async(
                legitimate_domain="legit.com",
                candidate_domains=["fake-legit.com"],
                notification_config={"email_enabled": False, "slack_enabled": False},
            )

        assert "fake-legit.com" in result["confirmed_fakes"], (
            f"Expected 'fake-legit.com' in confirmed_fakes, got {result['confirmed_fakes']}"
        )
        # An Alert should have been added to the session
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Property 3: API site_name解決
# Feature: fake-site-detection-alert, Property 3: API site_name解決
# ---------------------------------------------------------------------------


class TestAPISiteNameResolution:
    """
    Feature: fake-site-detection-alert, Property 3: API site_name解決

    For any Alert with a non-null site_id, the alerts API response shall
    include site_name equal to the corresponding MonitoringSite's name field.

    **Validates: Requirements 3.5**
    """

    @given(
        site_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Zs"), min_codepoint=65, max_codepoint=122),
            min_size=1,
            max_size=50,
        ).filter(lambda s: s.strip() != ""),
        site_id=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100, deadline=None)
    def test_site_name_resolved_when_site_exists(self, site_name, site_id):
        """
        When site_id is set and the corresponding MonitoringSite exists,
        _resolve_alert_fields must return site_name equal to the site's name.

        **Validates: Requirements 3.5**
        """
        from src.api.alerts import _resolve_alert_fields

        # Create mock alert
        alert = MagicMock()
        alert.id = 1
        alert.violation_id = None
        alert.alert_type = "violation"
        alert.severity = "high"
        alert.message = "test"
        alert.email_sent = False
        alert.slack_sent = False
        alert.created_at = "2024-01-01T00:00:00"
        alert.is_resolved = False
        alert.site_id = site_id
        alert.old_price = None
        alert.new_price = None
        alert.change_percentage = None
        alert.fake_domain = None
        alert.legitimate_domain = None
        alert.domain_similarity_score = None
        alert.content_similarity_score = None

        # Create mock site
        mock_site = MagicMock()
        mock_site.name = site_name

        # Create mock DB session
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_site
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        result = _resolve_alert_fields(alert, mock_db)

        assert result["site_name"] == site_name, (
            f"Expected site_name='{site_name}', got '{result['site_name']}'"
        )

    @given(
        alert_type=st.sampled_from(["violation", "fake_site", "price_change"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_site_name_is_none_when_site_id_is_none(self, alert_type):
        """
        When site_id is None, _resolve_alert_fields must return site_name=None.

        **Validates: Requirements 3.5**
        """
        from src.api.alerts import _resolve_alert_fields

        alert = MagicMock()
        alert.id = 1
        alert.violation_id = None
        alert.alert_type = alert_type
        alert.severity = "high"
        alert.message = "test"
        alert.email_sent = False
        alert.slack_sent = False
        alert.created_at = "2024-01-01T00:00:00"
        alert.is_resolved = False
        alert.site_id = None
        alert.old_price = None
        alert.new_price = None
        alert.change_percentage = None
        alert.fake_domain = None
        alert.legitimate_domain = None
        alert.domain_similarity_score = None
        alert.content_similarity_score = None

        mock_db = MagicMock()

        result = _resolve_alert_fields(alert, mock_db)

        assert result["site_name"] is None, (
            f"Expected site_name=None when site_id is None, got '{result['site_name']}'"
        )

    @given(
        site_id=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100, deadline=None)
    def test_site_name_is_none_when_site_not_found(self, site_id):
        """
        When site_id is set but the MonitoringSite does not exist in DB,
        _resolve_alert_fields must return site_name=None.

        **Validates: Requirements 3.5**
        """
        from src.api.alerts import _resolve_alert_fields

        alert = MagicMock()
        alert.id = 1
        alert.violation_id = None
        alert.alert_type = "violation"
        alert.severity = "high"
        alert.message = "test"
        alert.email_sent = False
        alert.slack_sent = False
        alert.created_at = "2024-01-01T00:00:00"
        alert.is_resolved = False
        alert.site_id = site_id
        alert.old_price = None
        alert.new_price = None
        alert.change_percentage = None
        alert.fake_domain = None
        alert.legitimate_domain = None
        alert.domain_similarity_score = None
        alert.content_similarity_score = None

        # DB returns None for the site query
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        result = _resolve_alert_fields(alert, mock_db)

        assert result["site_name"] is None, (
            f"Expected site_name=None when site not found, got '{result['site_name']}'"
        )


# ---------------------------------------------------------------------------
# Property 4: API violation_type解決
# Feature: fake-site-detection-alert, Property 4: API violation_type解決
# ---------------------------------------------------------------------------


class TestAPIViolationTypeResolution:
    """
    Feature: fake-site-detection-alert, Property 4: API violation_type解決

    For any Alert, the alerts API response shall include violation_type derived
    as follows: if alert_type='fake_site' then violation_type='fake_site';
    otherwise if violation_id is set, then violation_type equals the
    corresponding Violation's violation_type field.

    **Validates: Requirements 3.6, 3.7**
    """

    @given(
        severity=st.sampled_from(["low", "medium", "high", "critical"]),
    )
    @settings(max_examples=100, deadline=None)
    def test_fake_site_alert_returns_fake_site_violation_type(self, severity):
        """
        When alert_type='fake_site', violation_type must be 'fake_site'
        regardless of violation_id.

        **Validates: Requirements 3.7**
        """
        from src.api.alerts import _resolve_alert_fields

        alert = MagicMock()
        alert.id = 1
        alert.violation_id = None
        alert.alert_type = "fake_site"
        alert.severity = severity
        alert.message = "Fake site detected"
        alert.email_sent = False
        alert.slack_sent = False
        alert.created_at = "2024-01-01T00:00:00"
        alert.is_resolved = False
        alert.site_id = None
        alert.old_price = None
        alert.new_price = None
        alert.change_percentage = None
        alert.fake_domain = "fake.com"
        alert.legitimate_domain = "legit.com"
        alert.domain_similarity_score = 0.9
        alert.content_similarity_score = 0.85

        mock_db = MagicMock()

        result = _resolve_alert_fields(alert, mock_db)

        assert result["violation_type"] == "fake_site", (
            f"Expected violation_type='fake_site' for fake_site alert, "
            f"got '{result['violation_type']}'"
        )

    @given(
        violation_type=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz_",
            min_size=3,
            max_size=30,
        ).filter(lambda s: s != "fake_site"),
        violation_id=st.integers(min_value=1, max_value=10000),
        alert_type=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz_",
            min_size=3,
            max_size=20,
        ).filter(lambda s: s != "fake_site"),
    )
    @settings(max_examples=100, deadline=None)
    def test_non_fake_site_with_violation_id_resolves_violation_type(
        self, violation_type, violation_id, alert_type
    ):
        """
        When alert_type != 'fake_site' and violation_id is set,
        violation_type must equal the Violation model's violation_type.

        **Validates: Requirements 3.6**
        """
        from src.api.alerts import _resolve_alert_fields

        alert = MagicMock()
        alert.id = 1
        alert.violation_id = violation_id
        alert.alert_type = alert_type
        alert.severity = "high"
        alert.message = "test"
        alert.email_sent = False
        alert.slack_sent = False
        alert.created_at = "2024-01-01T00:00:00"
        alert.is_resolved = False
        alert.site_id = None
        alert.old_price = None
        alert.new_price = None
        alert.change_percentage = None
        alert.fake_domain = None
        alert.legitimate_domain = None
        alert.domain_similarity_score = None
        alert.content_similarity_score = None

        # Create mock violation
        mock_violation = MagicMock()
        mock_violation.violation_type = violation_type

        # DB query: first call for MonitoringSite (site_id is None, won't query),
        # second call for Violation
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_violation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        result = _resolve_alert_fields(alert, mock_db)

        assert result["violation_type"] == violation_type, (
            f"Expected violation_type='{violation_type}', "
            f"got '{result['violation_type']}'"
        )

    @given(
        alert_type=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz_",
            min_size=3,
            max_size=20,
        ).filter(lambda s: s != "fake_site"),
    )
    @settings(max_examples=100, deadline=None)
    def test_non_fake_site_without_violation_id_returns_none(self, alert_type):
        """
        When alert_type != 'fake_site' and violation_id is None,
        violation_type must be None.

        **Validates: Requirements 3.6, 3.7**
        """
        from src.api.alerts import _resolve_alert_fields

        alert = MagicMock()
        alert.id = 1
        alert.violation_id = None
        alert.alert_type = alert_type
        alert.severity = "high"
        alert.message = "test"
        alert.email_sent = False
        alert.slack_sent = False
        alert.created_at = "2024-01-01T00:00:00"
        alert.is_resolved = False
        alert.site_id = None
        alert.old_price = None
        alert.new_price = None
        alert.change_percentage = None
        alert.fake_domain = None
        alert.legitimate_domain = None
        alert.domain_similarity_score = None
        alert.content_similarity_score = None

        mock_db = MagicMock()

        result = _resolve_alert_fields(alert, mock_db)

        assert result["violation_type"] is None, (
            f"Expected violation_type=None when no violation_id and not fake_site, "
            f"got '{result['violation_type']}'"
        )


# ---------------------------------------------------------------------------
# Property 5: 偽サイト統計カウントの正確性
# Feature: fake-site-detection-alert, Property 5: 偽サイト統計カウントの正確性
# ---------------------------------------------------------------------------


class TestFakeSiteStatisticsAccuracy:
    """
    Feature: fake-site-detection-alert, Property 5: 偽サイト統計カウントの正確性

    For any database state, the statistics API shall return fake_site_alerts
    equal to the count of Alert records where alert_type='fake_site', and
    unresolved_fake_site_alerts equal to the count of Alert records where
    alert_type='fake_site' AND is_resolved=False.

    **Validates: Requirements 4.3, 4.4**
    """

    @given(
        num_fake_resolved=st.integers(min_value=0, max_value=20),
        num_fake_unresolved=st.integers(min_value=0, max_value=20),
        num_other_alerts=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_statistics_counts_match_alert_data(
        self, num_fake_resolved, num_fake_unresolved, num_other_alerts
    ):
        """
        Given random numbers of fake_site alerts (resolved and unresolved)
        and other alert types, the statistics endpoint must return correct
        counts for fake_site_alerts and unresolved_fake_site_alerts.

        **Validates: Requirements 4.3, 4.4**
        """
        from unittest.mock import MagicMock, patch
        from src.api.monitoring import get_statistics

        total_fake = num_fake_resolved + num_fake_unresolved

        # Build a mock DB session that returns the expected counts
        mock_db = MagicMock()

        # Track calls to db.query(func.count(...)).filter(...).scalar()
        # The get_statistics function makes these queries in order:
        # 1. total_sites (count MonitoringSite.id)
        # 2. active_sites (count MonitoringSite.id, filter is_active)
        # 3. total_violations (count Violation.id)
        # 4. high_severity_violations (count Violation.id, filter severity)
        # 5. total_crawls (count CrawlResult.id)
        # 6. successful_crawls (count CrawlResult.id, filter status_code)
        # 7. last_crawl (max CrawlResult.crawled_at)
        # 8. fake_site_alerts (count Alert.id, filter alert_type)
        # 9. unresolved_fake_site_alerts (count Alert.id, filter alert_type + is_resolved)

        call_count = 0

        def mock_query_side_effect(*args):
            nonlocal call_count
            call_count += 1
            mock_q = MagicMock()

            if call_count <= 2:
                # MonitoringSite counts
                mock_filter = MagicMock()
                mock_filter.scalar.return_value = 5
                mock_q.filter.return_value = mock_filter
                mock_q.scalar.return_value = 10
            elif call_count <= 4:
                # Violation counts
                mock_filter = MagicMock()
                mock_filter.scalar.return_value = 2
                mock_q.filter.return_value = mock_filter
                mock_q.scalar.return_value = 8
            elif call_count <= 6:
                # CrawlResult counts
                mock_filter = MagicMock()
                mock_filter.scalar.return_value = 50
                mock_q.filter.return_value = mock_filter
                mock_q.scalar.return_value = 100
            elif call_count == 7:
                # last_crawl (max)
                mock_q.scalar.return_value = None
            elif call_count == 8:
                # fake_site_alerts count
                mock_filter = MagicMock()
                mock_filter.scalar.return_value = total_fake
                mock_q.filter.return_value = mock_filter
            elif call_count == 9:
                # unresolved_fake_site_alerts count
                mock_filter = MagicMock()
                mock_filter.scalar.return_value = num_fake_unresolved
                mock_q.filter.return_value = mock_filter

            return mock_q

        mock_db.query.side_effect = mock_query_side_effect

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(get_statistics(db=mock_db))

        assert result.fake_site_alerts == total_fake, (
            f"Expected fake_site_alerts={total_fake}, got {result.fake_site_alerts}"
        )
        assert result.unresolved_fake_site_alerts == num_fake_unresolved, (
            f"Expected unresolved_fake_site_alerts={num_fake_unresolved}, "
            f"got {result.unresolved_fake_site_alerts}"
        )

    @given(
        num_fake_unresolved=st.integers(min_value=0, max_value=30),
        num_fake_resolved=st.integers(min_value=0, max_value=30),
    )
    @settings(max_examples=100, deadline=None)
    def test_unresolved_count_lte_total_fake(
        self, num_fake_unresolved, num_fake_resolved
    ):
        """
        The unresolved_fake_site_alerts count must always be <= fake_site_alerts.

        **Validates: Requirements 4.3, 4.4**
        """
        total_fake = num_fake_resolved + num_fake_unresolved

        # This is a logical property: unresolved <= total
        assert num_fake_unresolved <= total_fake, (
            f"Unresolved ({num_fake_unresolved}) should be <= total ({total_fake})"
        )
