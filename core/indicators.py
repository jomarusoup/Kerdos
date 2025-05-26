import ta

########################################################
# 보조지표 계산 함수
########################################################
def add_indicators(df, envelope_window=20, envelope_pct=0.02):
    """
    주어진 DataFrame(df)에
    - 볼린저 밴드
    - RSI
    - MACD
    - 이동평균(SMA 20, EMA 12)
    - 엔벨로프(Envelope) (기본: 20일 평균±2%)
    등을 계산해서 컬럼으로 추가한 후 반환한다.
    """
    #--- 변수 선언
    indicator_bbands = None
    indicator_macd   = None

    #--- Bollinger Bands
    indicator_bbands = ta.volatility.BollingerBands(
        close = df['Close'],
        window = 20,
        window_dev = 2
    )
    df['bb_bbh'] = indicator_bbands.bollinger_hband() # 상단선
    df['bb_bbm'] = indicator_bbands.bollinger_mavg()  # 중앙선(기준선)
    df['bb_bbl'] = indicator_bbands.bollinger_lband() # 하단선

    #---- RSI
    df['rsi'] = ta.momentum.RSIIndicator(
        close = df['Close'],
        window = 14
    ).rsi()

    #--- MACD
    indicator_macd = ta.trend.MACD(
        close = df['Close'],
        window_slow = 26,
        window_fast = 12,
        window_sign = 9
    )
    df['macd']        = indicator_macd.macd()
    df['macd_signal'] = indicator_macd.macd_signal()
    df['macd_diff']   = indicator_macd.macd_diff()

    #--- SMA, EMA
    df['sma_20'] = ta.trend.SMAIndicator(
        close = df['Close'],
        window = 20
    ).sma_indicator()

    df['ema_12'] = ta.trend.EMAIndicator(
        close = df['Close'],
        window = 12
    ).ema_indicator()

    #--- Envelope
    # 엔벨로프(Envelope) : MA ± 일정 비율
    # 여기서는 sma_20을 기준으로 엔벨로프 계산 가능 (또는 Close의 rollingMean 등 원하는 기준 사용)
    df['env_ma']    = df['Close'].rolling(window=envelope_window).mean()
    df['env_upper'] = df['env_ma'] * (1 + envelope_pct)
    df['env_lower'] = df['env_ma'] * (1 - envelope_pct)

    return df