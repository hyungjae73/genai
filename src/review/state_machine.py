"""
ReviewStateMachine — 審査ワークフローの状態遷移制御（純粋関数）

要件: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_review"},
    "in_review": {"approved", "rejected", "escalated"},
    "escalated": {"approved", "rejected"},
    "approved": set(),   # 最終状態
    "rejected": set(),   # 最終状態
}

ALL_STATUSES: set[str] = set(VALID_TRANSITIONS.keys())


def validate_transition(current_status: str, new_status: str) -> bool:
    """状態遷移が許可されているか検証する。

    Args:
        current_status: 現在のステータス
        new_status: 遷移先のステータス

    Returns:
        遷移が許可されている場合 True、それ以外は False
    """
    return new_status in VALID_TRANSITIONS.get(current_status, set())


def get_allowed_transitions(current_status: str) -> set[str]:
    """現在のステータスから遷移可能なステータスの集合を返す。

    Args:
        current_status: 現在のステータス

    Returns:
        遷移可能なステータスの集合（最終状態の場合は空集合）
    """
    return VALID_TRANSITIONS.get(current_status, set())


def is_terminal_state(status: str) -> bool:
    """最終状態（approved/rejected）かどうかを返す。

    Args:
        status: 確認するステータス

    Returns:
        最終状態の場合 True
    """
    return status in {"approved", "rejected"}
