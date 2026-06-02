################################################################################
# FILE NAME   : backtest.py
# DESCRIPTION : 과거 OHLCV 기반 전략 백테스트 엔진 (수수료·슬리피지 시뮬레이션)
# DATA        : 2026-06-02
# Modification: 2026-06-02
################################################################################
#
# 설계 원칙
# - pandas 비의존: 코어 엔진은 순수 파이썬 list[Bar] 위에서 동작한다.
#   프로젝트의 pyupbit DataFrame 연동은 bars_from_dataframe 어댑터에 격리하고,
#   pandas는 해당 함수 안에서만 지연(lazy) 임포트한다.
# - 무미래참조(no lookahead): 인덱스 i 의 신호는 bars[: i + 1] 만으로 결정한다.
# - 체결 모델: 운영 시스템(autotrad.py)이 매 틱 현재가로 즉시 주문하는 방식을
#   따라, 신호 발생 봉의 종가(close)에 체결한다.
# - 수수료: 매수·매도 양방향에 fee_rate 적용 (업비트 Taker 0.05% 기본값).
#   autotrad.py 의 UPBIT_FEE_RATE 와 동일 값을 미러링한다.
#
################################################################################

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

#-------------------------------------------------------------------------------
# 상수 — autotrad.py 의 UPBIT_FEE_RATE 미러링 (업비트 시장가 Taker 0.05%)
#-------------------------------------------------------------------------------
UPBIT_FEE_RATE = 0.0005
DEFAULT_MIN_ORDER_KRW = 5000.0

# 매매 신호 액션
BUY = "buy"
SELL = "sell"
HOLD = "hold"


#===============================================================================
# 데이터 구조
#===============================================================================
@dataclass(frozen=True)
class Bar:
    """단일 캔들. close 만 필수, 나머지는 선택."""

    close: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    timestamp: str | None = None


@dataclass(frozen=True)
class Signal:
    """전략 출력 신호. percentage 는 0~100 비중.

    - BUY  : 보유 현금 대비 매수 비중
    - SELL : 보유 ETH 대비 매도 비중
    """

    action: str
    percentage: float = 0.0


@dataclass(frozen=True)
class Trade:
    """체결 기록."""

    bar_index: int
    timestamp: str | None
    action: str
    price: float          # 슬리피지 반영 체결가
    eth_amount: float     # 매수=순수령 ETH, 매도=매도 ETH 수량
    krw_amount: float     # 이동한 총 KRW (매수=지출액, 매도=총 수령액)
    fee: float            # KRW 환산 수수료
    realized_pnl: float   # 매도 시 평균단가 기준 실현손익 (매수는 0.0)


@dataclass(frozen=True)
class BacktestResult:
    """백테스트 결과."""

    initial_cash: float
    final_value: float
    equity_curve: list[float] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    realized_pnls: list[float] = field(default_factory=list)


class Strategy(Protocol):
    """전략 인터페이스 — 현재까지의 봉 이력을 받아 신호를 반환."""

    def decide(self, history: Sequence[Bar]) -> Signal: ...


#===============================================================================
# FUNCTION    : run_backtest
# DESCRIPTION : 봉 시퀀스에 전략을 적용해 자산 곡선·체결·실현손익을 산출
# PARAMETERS  : Sequence[Bar] bars       - 시간순 정렬된 OHLCV 봉
#               Strategy      strategy   - decide(history) -> Signal 구현체
#               float initial_cash       - 초기 현금 (KRW)
#               float fee_rate           - 편도 수수료율 (기본 0.05%)
#               float slippage           - 체결 슬리피지율 (불리한 방향 적용)
#               int   warmup             - 거래 금지 초기 봉 개수
#               float min_order_krw      - 최소 주문 금액 (KRW)
# RETURNED    : BacktestResult
#===============================================================================
def run_backtest(
    bars: Sequence[Bar],
    strategy: Strategy,
    initial_cash: float = 1_000_000.0,
    fee_rate: float = UPBIT_FEE_RATE,
    slippage: float = 0.0,
    warmup: int = 0,
    min_order_krw: float = DEFAULT_MIN_ORDER_KRW,
) -> BacktestResult:
    cash = float(initial_cash)
    eth = 0.0
    cost_basis = 0.0   # 현재 보유 ETH 의 누적 취득원가 (KRW)

    equity_curve: list[float] = []
    trades: list[Trade] = []
    realized_pnls: list[float] = []

    for index, bar in enumerate(bars):
        price = bar.close

        #--- warmup 구간: 거래 없이 자산만 기록
        if index < warmup:
            equity_curve.append(cash + eth * price)
            continue

        signal = strategy.decide(list(bars[: index + 1]))

        #-----------------------------------------------------------------------
        # 매수 — 현금 대비 percentage 비율 지출, 체결가는 슬리피지만큼 비싸게
        #-----------------------------------------------------------------------
        if signal.action == BUY and signal.percentage > 0:
            spend = cash * (signal.percentage / 100.0)
            fill_price = price * (1.0 + slippage)
            if spend >= min_order_krw and fill_price > 0:
                fee = spend * fee_rate
                net_eth = (spend / fill_price) * (1.0 - fee_rate)

                cash -= spend
                eth += net_eth
                cost_basis += spend

                trades.append(Trade(
                    bar_index=index,
                    timestamp=bar.timestamp,
                    action=BUY,
                    price=fill_price,
                    eth_amount=net_eth,
                    krw_amount=spend,
                    fee=fee,
                    realized_pnl=0.0,
                ))

        #-----------------------------------------------------------------------
        # 매도 — 보유 ETH 대비 percentage 비율 청산, 체결가는 슬리피지만큼 싸게
        #-----------------------------------------------------------------------
        elif signal.action == SELL and signal.percentage > 0 and eth > 0:
            eth_to_sell = eth * (signal.percentage / 100.0)
            fill_price = price * (1.0 - slippage)
            gross = eth_to_sell * fill_price
            net_krw = gross * (1.0 - fee_rate)
            if net_krw >= min_order_krw:
                proportion = eth_to_sell / eth
                realized = net_krw - cost_basis * proportion

                cost_basis *= (1.0 - proportion)
                eth -= eth_to_sell
                cash += net_krw

                realized_pnls.append(realized)
                trades.append(Trade(
                    bar_index=index,
                    timestamp=bar.timestamp,
                    action=SELL,
                    price=fill_price,
                    eth_amount=eth_to_sell,
                    krw_amount=gross,
                    fee=gross * fee_rate,
                    realized_pnl=realized,
                ))

        #--- 봉 종료 시점 자산 평가 (종가 기준)
        equity_curve.append(cash + eth * price)

    final_value = equity_curve[-1] if equity_curve else float(initial_cash)

    return BacktestResult(
        initial_cash=float(initial_cash),
        final_value=final_value,
        equity_curve=equity_curve,
        trades=trades,
        realized_pnls=realized_pnls,
    )


#===============================================================================
# FUNCTION    : bars_from_dataframe
# DESCRIPTION : pyupbit OHLCV DataFrame(Open/High/Low/Close/Volume)을 Bar 리스트로
#               변환. pandas 는 이 함수 내부에서만 지연 임포트한다.
# PARAMETERS  : DataFrame df - reset_index() 후 컬럼명이 대문자화된 OHLCV
# RETURNED    : list[Bar]
#===============================================================================
def bars_from_dataframe(df) -> list[Bar]:
    bars: list[Bar] = []

    #--- 인덱스(날짜)를 timestamp 로 활용 가능하면 사용
    has_named_index = getattr(df.index, "name", None) is not None

    for position, (_, row) in enumerate(df.iterrows()):
        timestamp = None
        if has_named_index:
            timestamp = str(df.index[position])

        bars.append(Bar(
            close=float(row["Close"]),
            open=float(row.get("Open", 0.0)),
            high=float(row.get("High", 0.0)),
            low=float(row.get("Low", 0.0)),
            volume=float(row.get("Volume", 0.0)),
            timestamp=timestamp,
        ))

    return bars
