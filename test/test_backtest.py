################################################################################
# FILE NAME   : test_backtest.py
# DESCRIPTION : core.backtest 백테스트 엔진 단위 테스트 (수수료·슬리피지 포함)
# DATA        : 2026-06-02
# Modification: 2026-06-02
################################################################################

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.backtest import (
    Bar,
    Signal,
    BUY,
    SELL,
    HOLD,
    run_backtest,
)


#===============================================================================
# 테스트용 스크립트 전략 — bar 인덱스별로 미리 정한 신호를 반환
#===============================================================================
class ScriptedStrategy:
    def __init__(self, script: dict[int, Signal]) -> None:
        self._script = script

    def decide(self, history: list[Bar]) -> Signal:
        bar_index = len(history) - 1
        return self._script.get(bar_index, Signal(HOLD))


def make_bars(closes: list[float]) -> list[Bar]:
    return [Bar(close=float(price)) for price in closes]


#-------------------------------------------------------------------------------
# hold 전략 — 거래 없음, 자산 불변
#-------------------------------------------------------------------------------
def test_hold_전략은_거래없이_초기자산_유지():
    bars = make_bars([100, 110, 90, 120])
    strategy = ScriptedStrategy({})

    result = run_backtest(bars, strategy, initial_cash=1_000_000.0)

    assert result.trades == []
    assert result.final_value == 1_000_000.0
    assert result.equity_curve == [1_000_000.0] * 4


#-------------------------------------------------------------------------------
# 매수 후 보유 — 가격 상승 시 평가액 증가 (매수 수수료 차감 반영)
#-------------------------------------------------------------------------------
def test_매수후보유_가격상승시_평가액_증가():
    bars = make_bars([100, 110])
    strategy = ScriptedStrategy({0: Signal(BUY, 100.0)})

    result = run_backtest(bars, strategy, initial_cash=1_000_000.0, fee_rate=0.0005)

    assert len(result.trades) == 1
    assert result.trades[0].action == BUY
    # net_eth = 1_000_000 / 100 * (1 - 0.0005) = 9995.0
    assert math.isclose(result.trades[0].eth_amount, 9995.0, abs_tol=1e-6)
    # 평가액(110원) = 9995 * 110 = 1_099_450
    assert math.isclose(result.final_value, 1_099_450.0, abs_tol=1e-6)


#-------------------------------------------------------------------------------
# 매수 → 매도 라운드트립 — 실현손익이 수수료 반영해 정확히 계산됨
#-------------------------------------------------------------------------------
def test_매수후매도_실현손익_정확히_계산():
    bars = make_bars([100, 110])
    strategy = ScriptedStrategy({0: Signal(BUY, 100.0), 1: Signal(SELL, 100.0)})

    result = run_backtest(bars, strategy, initial_cash=1_000_000.0, fee_rate=0.0005)

    # 매수: spend=1_000_000, net_eth=9995, cost_basis=1_000_000
    # 매도: gross=9995*110=1_099_450, net=1_099_450*0.9995=1_098_900.275
    # realized = 1_098_900.275 - 1_000_000 = 98_900.275
    assert len(result.trades) == 2
    assert len(result.realized_pnls) == 1
    assert math.isclose(result.realized_pnls[0], 98_900.275, abs_tol=1e-6)
    assert math.isclose(result.final_value, 1_098_900.275, abs_tol=1e-6)


#-------------------------------------------------------------------------------
# 최소 주문금액 미만 매수는 무시
#-------------------------------------------------------------------------------
def test_최소주문금액_미만_매수는_무시():
    bars = make_bars([100, 110])
    # 1% 매수 → spend=10_000 (min 5000 이상) → 체결됨을 먼저 확인
    ok = run_backtest(
        bars, ScriptedStrategy({0: Signal(BUY, 1.0)}),
        initial_cash=1_000_000.0, min_order_krw=5_000.0,
    )
    assert len(ok.trades) == 1

    # min을 20_000으로 올리면 spend=10_000 < 20_000 → 무시
    skipped = run_backtest(
        bars, ScriptedStrategy({0: Signal(BUY, 1.0)}),
        initial_cash=1_000_000.0, min_order_krw=20_000.0,
    )
    assert skipped.trades == []


#-------------------------------------------------------------------------------
# 슬리피지 — 매수는 불리하게(비싸게), 매도는 불리하게(싸게) 체결
#-------------------------------------------------------------------------------
def test_슬리피지_매수는_비싸게_체결():
    bars = make_bars([100, 100])
    no_slip = run_backtest(
        bars, ScriptedStrategy({0: Signal(BUY, 100.0)}),
        initial_cash=1_000_000.0, fee_rate=0.0, slippage=0.0,
    )
    with_slip = run_backtest(
        bars, ScriptedStrategy({0: Signal(BUY, 100.0)}),
        initial_cash=1_000_000.0, fee_rate=0.0, slippage=0.01,
    )
    # 슬리피지가 있으면 같은 금액으로 더 적은 ETH 매수
    assert with_slip.trades[0].eth_amount < no_slip.trades[0].eth_amount


#-------------------------------------------------------------------------------
# warmup 구간에서는 거래하지 않음
#-------------------------------------------------------------------------------
def test_warmup_구간은_거래하지_않음():
    bars = make_bars([100, 110, 120])
    strategy = ScriptedStrategy({0: Signal(BUY, 100.0), 1: Signal(BUY, 100.0)})

    result = run_backtest(bars, strategy, initial_cash=1_000_000.0, warmup=2)

    # 인덱스 0,1 은 warmup → 무시, 첫 거래 가능 인덱스는 2 (신호 없음 → hold)
    assert result.trades == []
    assert len(result.equity_curve) == 3


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
