"""Unified retry decorator using Tenacity."""
import logging
from typing import Callable, Optional, Tuple, Type

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    before_sleep_log,
    retry_if_exception_type,
    retry_if_exception,
    retry_if_result,
)

logger = logging.getLogger(__name__)


def with_retry(
    *,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
    max_jitter: float = 1.0,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
    retry_if: Optional[Callable] = None,
) -> retry:
    """統一リトライデコレータを生成する。

    指数バックオフ + ランダムジッター + WARNINGログ出力。

    Args:
        max_attempts: 最大リトライ回数 (デフォルト: 3)
        min_wait: 最小待機時間 秒 (デフォルト: 1.0)
        max_wait: 最大待機時間 秒 (デフォルト: 10.0)
        multiplier: バックオフ倍率 (デフォルト: 2.0)
        max_jitter: 最大ジッター 秒 (デフォルト: 1.0)
        retry_on: リトライ対象の例外型タプル
        retry_if: カスタムリトライ条件コーラブル（例外を受け取りboolを返す）。
                  指定時は retry_on の型マッチングと AND 結合される。
    """
    if retry_if is not None:
        # When retry_if is provided, use it as an exception filter combined
        # with the type check: retry only if exception matches retry_on types
        # AND the retry_if callable returns True.
        conditions = retry_if_exception_type(retry_on) & retry_if_exception(retry_if)
    else:
        conditions = retry_if_exception_type(retry_on)

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait)
        + wait_random(0, max_jitter),
        retry=conditions,
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
