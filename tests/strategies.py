"""
Hypothesis custom strategies for crawl pipeline property-based tests.

Provides reusable strategies for generating MonitoringSite, VariantCapture,
and CrawlContext instances with valid, JSON-serializable data.
"""

from datetime import datetime

from hypothesis import strategies as st

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext, VariantCapture


# Simple JSON-serializable value strategy (str, int, float, bool, None)
json_value_strategy = st.one_of(
    st.text(min_size=0, max_size=50),
    st.integers(min_value=-10000, max_value=10000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    st.booleans(),
    st.none(),
)


def monitoring_site_strategy():
    """Generate MonitoringSite instances with id, name, and url."""
    return st.builds(
        MonitoringSite,
        id=st.integers(min_value=1, max_value=100000),
        name=st.text(min_size=1, max_size=100),
        url=st.from_regex(r"https?://[a-z]+\.[a-z]{2,4}", fullmatch=True),
    )


def variant_capture_strategy():
    """Generate VariantCapture instances with valid fields."""
    return st.builds(
        VariantCapture,
        variant_name=st.text(min_size=1, max_size=50),
        image_path=st.text(min_size=1, max_size=200),
        captured_at=st.datetimes(
            min_value=datetime(2000, 1, 1),
            max_value=datetime(2099, 12, 31),
            timezones=st.none(),
        ),
        metadata=st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.text(max_size=50),
            max_size=5,
        ),
    )


def crawl_context_strategy():
    """Generate CrawlContext instances with all fields populated."""
    return st.builds(
        CrawlContext,
        site=monitoring_site_strategy(),
        url=st.from_regex(r"https?://[a-z]+\.[a-z]{2,4}", fullmatch=True),
        html_content=st.one_of(st.none(), st.text(min_size=10, max_size=1000)),
        screenshots=st.lists(variant_capture_strategy(), max_size=5),
        extracted_data=st.dictionaries(
            st.text(min_size=1, max_size=20), st.text(max_size=50), max_size=10
        ),
        violations=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=10), st.text(max_size=50), max_size=5
            ),
            max_size=10,
        ),
        evidence_records=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=10), st.text(max_size=50), max_size=5
            ),
            max_size=10,
        ),
        errors=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=10), st.text(max_size=50), max_size=5
            ),
            max_size=5,
        ),
        metadata=st.dictionaries(
            st.text(min_size=1, max_size=30), st.text(max_size=50), max_size=10
        ),
    )


def pre_capture_script_strategy():
    """Generate random valid PreCaptureScript action lists.

    Each action is a dict with a valid 'action' type and the required fields
    for that type.  An optional 'label' string may be attached to any action.
    """
    label_st = st.one_of(st.none(), st.text(min_size=1, max_size=30))

    click_action = st.fixed_dictionaries(
        {"action": st.just("click"), "selector": st.text(min_size=1, max_size=50)},
        optional={"label": label_st},
    )
    wait_action = st.fixed_dictionaries(
        {"action": st.just("wait"), "ms": st.integers(min_value=100, max_value=5000)},
        optional={"label": label_st},
    )
    select_action = st.fixed_dictionaries(
        {
            "action": st.just("select"),
            "selector": st.text(min_size=1, max_size=50),
            "value": st.text(min_size=1, max_size=50),
        },
        optional={"label": label_st},
    )
    type_action = st.fixed_dictionaries(
        {
            "action": st.just("type"),
            "selector": st.text(min_size=1, max_size=50),
            "text": st.text(min_size=1, max_size=100),
        },
        optional={"label": label_st},
    )

    action_st = st.one_of(click_action, wait_action, select_action, type_action)
    return st.lists(action_st, min_size=1, max_size=10)

