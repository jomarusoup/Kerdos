################################################################################
# FILE NAME   : test_metrics.py
# DESCRIPTION : core.metrics 성과 지표 단위 테스트 (수익률·MDD·샤프·승률·손익비)
# DATA        : 2026-06-02
# Modification: 2026-06-02
################################################################################

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.metrics import (
    total_return,
    max_drawdown,
    sharpe_ratio,
    win_rate,
    profit_factor,
)


#-------------------------------------------------------------------------------
# 총수익률
#-------------------------------------------------------------------------------
def test_총수익률_계산():
    assert math.isclose(total_return([100.0, 110.0]), 0.10, abs_tol=1e-9)
    assert math.isclose(total_return([100.0, 50.0]), -0.50, abs_tol=1e-9)


def test_총수익률_빈곡선은_0():
    assert total_return([]) == 0.0
    assert total_return([100.0]) == 0.0


#-------------------------------------------------------------------------------
# 최대낙폭(MDD)
#-------------------------------------------------------------------------------
def test_최대낙폭_계산():
    # peak=100 -> 60 까지: (120-60)/120 = 0.5 가 최대
    assert math.isclose(max_drawdown([100, 80, 120, 60]), 0.5, abs_tol=1e-9)


def test_최대낙폭_상승만하면_0():
    assert max_drawdown([100, 110, 130]) == 0.0
    assert max_drawdown([]) == 0.0


#-------------------------------------------------------------------------------
# 샤프지수 — 상승 곡선은 양수, 데이터 부족 시 0
#-------------------------------------------------------------------------------
def test_샤프지수_상승곡선은_양수():
    assert sharpe_ratio([100, 110, 121, 133.1]) > 0


def test_샤프지수_데이터부족시_0():
    assert sharpe_ratio([100]) == 0.0
    assert sharpe_ratio([]) == 0.0


def test_샤프지수_변동없으면_0():
    assert sharpe_ratio([100, 100, 100]) == 0.0


#-------------------------------------------------------------------------------
# 승률
#-------------------------------------------------------------------------------
def test_승률_계산():
    assert math.isclose(win_rate([100.0, -50.0, 30.0]), 2.0 / 3.0, abs_tol=1e-9)


def test_승률_거래없으면_0():
    assert win_rate([]) == 0.0


#-------------------------------------------------------------------------------
# 손익비(profit factor)
#-------------------------------------------------------------------------------
def test_손익비_계산():
    # gains=130, losses=50 -> 2.6
    assert math.isclose(profit_factor([100.0, -50.0, 30.0]), 2.6, abs_tol=1e-9)


def test_손익비_손실없으면_무한대():
    assert profit_factor([10.0, 20.0]) == float("inf")


def test_손익비_거래없으면_0():
    assert profit_factor([]) == 0.0


#===============================================================================
# 직접 실행용 러너 (pytest 미설치 환경 대응)
#===============================================================================
def _run_all() -> int:
    tests = [obj for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except AssertionError as err:
            failed += 1
            print(f"[FAIL] {test.__name__}: {err}")
        except Exception as err:  # noqa: BLE001
            failed += 1
            print(f"[ERROR] {test.__name__}: {type(err).__name__}: {err}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
