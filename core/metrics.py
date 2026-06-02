################################################################################
# FILE NAME   : metrics.py
# DESCRIPTION : 백테스트 성과 지표 — 총수익률·최대낙폭·샤프지수·승률·손익비
# DATA        : 2026-06-02
# Modification: 2026-06-02
################################################################################
#
# 모든 함수는 순수 함수다. 자산 곡선(equity_curve) 또는 실현손익 리스트
# (realized_pnls)만 입력으로 받으며 외부 상태에 의존하지 않는다.
# core.backtest.BacktestResult 와 조합해 사용한다.
#
################################################################################

from __future__ import annotations

import math
from typing import Sequence

# 일봉 기준 연환산 계수 (필요 시 호출부에서 재정의)
TRADING_PERIODS_PER_YEAR = 365.0


#===============================================================================
# FUNCTION    : total_return
# DESCRIPTION : 자산 곡선의 시작 대비 종료 총수익률
# PARAMETERS  : Sequence[float] equity_curve - 시간순 자산 평가액
# RETURNED    : float - 수익률 (0.1 = +10%), 데이터 부족 시 0.0
#===============================================================================
def total_return(equity_curve: Sequence[float]) -> float:
    if len(equity_curve) < 2 or equity_curve[0] == 0:
        return 0.0
    return (equity_curve[-1] - equity_curve[0]) / equity_curve[0]


#===============================================================================
# FUNCTION    : max_drawdown
# DESCRIPTION : 최대낙폭 — 직전 고점 대비 최대 하락폭 (양수 비율)
# PARAMETERS  : Sequence[float] equity_curve - 시간순 자산 평가액
# RETURNED    : float - 최대낙폭 (0.5 = -50%), 데이터 부족 시 0.0
#===============================================================================
def max_drawdown(equity_curve: Sequence[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown
    return max_dd


#===============================================================================
# FUNCTION    : sharpe_ratio
# DESCRIPTION : 연환산 샤프지수. 봉 간 단순 수익률의 평균/표준편차 기반.
# PARAMETERS  : Sequence[float] equity_curve   - 시간순 자산 평가액
#               float periods_per_year         - 연환산 계수 (기본 일봉 365)
#               float risk_free                 - 봉당 무위험 수익률
# RETURNED    : float - 샤프지수, 표본 부족·무변동 시 0.0
#===============================================================================
def sharpe_ratio(
    equity_curve: Sequence[float],
    periods_per_year: float = TRADING_PERIODS_PER_YEAR,
    risk_free: float = 0.0,
) -> float:
    returns = _period_returns(equity_curve)
    if len(returns) < 2:
        return 0.0

    excess = [ret - risk_free for ret in returns]
    mean = sum(excess) / len(excess)

    #--- 표본 표준편차 (n - 1)
    variance = sum((value - mean) ** 2 for value in excess) / (len(excess) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0

    return (mean / std) * math.sqrt(periods_per_year)


#===============================================================================
# FUNCTION    : win_rate
# DESCRIPTION : 실현손익 리스트에서 이익 거래 비율
# PARAMETERS  : Sequence[float] realized_pnls - 청산별 실현손익
# RETURNED    : float - 승률 (0~1), 거래 없으면 0.0
#===============================================================================
def win_rate(realized_pnls: Sequence[float]) -> float:
    if not realized_pnls:
        return 0.0
    wins = sum(1 for pnl in realized_pnls if pnl > 0)
    return wins / len(realized_pnls)


#===============================================================================
# FUNCTION    : profit_factor
# DESCRIPTION : 손익비 — 총이익 / 총손실(절댓값)
# PARAMETERS  : Sequence[float] realized_pnls - 청산별 실현손익
# RETURNED    : float - 손익비, 손실 없고 이익 있으면 inf, 거래 없으면 0.0
#===============================================================================
def profit_factor(realized_pnls: Sequence[float]) -> float:
    if not realized_pnls:
        return 0.0

    gains = sum(pnl for pnl in realized_pnls if pnl > 0)
    losses = sum(-pnl for pnl in realized_pnls if pnl < 0)

    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


#-------------------------------------------------------------------------------
# 내부 헬퍼 — 봉 간 단순 수익률 시퀀스
#-------------------------------------------------------------------------------
def _period_returns(equity_curve: Sequence[float]) -> list[float]:
    returns: list[float] = []
    for prev, curr in zip(equity_curve, equity_curve[1:]):
        if prev != 0:
            returns.append((curr - prev) / prev)
    return returns
