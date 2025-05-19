import os
import time
import json
import requests
import pyupbit
import pandas as pd
import ta

from dotenv import load_dotenv
from openai import OpenAI

##############################
# 1) 보조지표 계산 함수
##############################
def add_indicators(df, envelope_window=20, envelope_pct=0.02):
    # 변수 선언
    indicator_bbands = None
    indicator_macd   = None

    # Bollinger Bands
    indicator_bbands = ta.volatility.BollingerBands(
        close=df['Close'],
        window=20,
        window_dev=2
    )
    df['bb_bbm']     = indicator_bbands.bollinger_mavg()
    df['bb_bbh']     = indicator_bbands.bollinger_hband()
    df['bb_bbl']     = indicator_bbands.bollinger_lband()

    # RSI
    df['rsi']        = ta.momentum.RSIIndicator(
        close=df['Close'],
        window=14
    ).rsi()

    # MACD
    indicator_macd   = ta.trend.MACD(
        close=df['Close'],
        window_slow=26,
        window_fast=12,
        window_sign=9
    )
    df['macd']       = indicator_macd.macd()
    df['macd_signal']= indicator_macd.macd_signal()
    df['macd_diff']  = indicator_macd.macd_diff()

    # SMA, EMA
    df['sma_20']     = ta.trend.SMAIndicator(
        close=df['Close'],
        window=20
    ).sma_indicator()
    df['ema_12']     = ta.trend.EMAIndicator(
        close=df['Close'],
        window=12
    ).ema_indicator()

    # Envelope
    df['env_ma']     = df['Close'].rolling(window=envelope_window).mean()
    df['env_upper']  = df['env_ma'] * (1 + envelope_pct)
    df['env_lower']  = df['env_ma'] * (1 - envelope_pct)

    return df

##############################
# 2) 공포·탐욕 지수 호출 함수
##############################
def get_fear_greed_index():
    # 변수 선언
    url       = "https://api.alternative.me/fng/"
    params    = {}
    response  = None
    data      = None
    fng_entry = None

    params['limit']       = 1
    params['format']      = 'json'
    params['date_format'] = 'kr'

    try:
        response  = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data      = response.json()
        fng_entry = data['data'][0]

        return {
            'value': int(fng_entry['value']),
            'classification': fng_entry['value_classification']
        }
    except Exception as e:
        print("[FNG] API Error:", e)
        return {
            'value': 50,
            'classification': 'Neutral'
        }

##############################
# 3) 메인 자동매매 함수
##############################
def ai_trading():
    # 변수 선언
    access            = None
    secret            = None
    upbit             = None
    all_balance       = None
    filtered_balance  = None
    df_30d            = None
    df_24h            = None
    orderbook         = None
    fng               = None
    data_for_gpt_json = None
    system_prompt     = None
    client            = None
    response          = None
    gpt_result_str    = None
    gpt_result        = None
    my_krw            = None
    my_eth            = None
    decision          = None
    reason            = None
    orderbook_now     = None
    current_price     = None
    total_value       = None

    # .env 파일에서 환경변수 로드 (UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY 등)
    load_dotenv()

    # 업비트 로그인
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    upbit  = pyupbit.Upbit(access, secret)

    # 현재 잔고 조회 (KRW, ETH만 필터)
    all_balance      = upbit.get_balances()
    filtered_balance = [
        item for item in all_balance
        if item['currency'] in ['KRW', 'ETH']
    ]

    #====================================================================
    # 1. 업비트 차트 데이터 (일봉 30일치, 1시간봉 24개) + 오더북
    #====================================================================
    df_30d    = pyupbit.get_ohlcv("KRW-ETH", count=30, interval="day")
    df_24h    = pyupbit.get_ohlcv("KRW-ETH", count=24, interval="minute60")
    orderbook = pyupbit.get_orderbook("KRW-ETH")

    #====================================================================
    # 2. 컬럼명 변경(ta 호환) + dropna + 보조지표 추가
    #====================================================================
    # --- 일봉 ---
    df_30d = df_30d.reset_index()  # 날짜 인덱스 -> 칼럼
    df_30d.rename(
        columns={
            'open':   'Close',   ## 잘못된 수정: 'open'이 'Open'으로 되어야 함
            'high':   'High',
            'low':    'Low',
            'close':  'Close',
            'volume': 'Volume'
        },
        inplace=True
    )
    df_30d.dropna(inplace=True)
    df_30d = add_indicators(df_30d)

    # --- 1시간봉 ---
    df_24h = df_24h.reset_index()
    df_24h.rename(
        columns={
            'open':   'Open',
            'high':   'High',
            'low':    'Low',
            'close':  'Close',
            'volume': 'Volume'
        },
        inplace=True
    )
    df_24h.dropna(inplace=True)
    df_24h = add_indicators(df_24h)

    #====================================================================
    # 3. 공포·탐욕 지수 수집
    #====================================================================
    fng = get_fear_greed_index()

    #====================================================================
    # 4. ChatGPT에게 전달할 데이터 준비 (JSON)
    #====================================================================
    data_for_gpt_json = json.dumps(
        {
            "chart_data_30d":    df_30d.to_dict(),
            "chart_data_24h":    df_24h.to_dict(),
            "orderbook":         orderbook,
            "investment_status": filtered_balance,
            "fear_greed":        fng
        },
        ensure_ascii=False,
        default=str
    )

    # 시스템 프롬프트 설정
    system_prompt = (
        "You are an Ethereum trading expert with deep experience in technical analysis, on-chain metrics, and market sentiment.\n"
        "You will receive the following data encoded in JSON:\n"
        "- 30-day OHLCV chart for ETH (Open, High, Low, Close, Volume)\n"
        "- 1-hour OHLCV chart for ETH\n"
        "- Current ETH orderbook snapshot\n"
        "- Account balances (e.g., KRW, ETH)\n"
        "- Fear & Greed Index { \"value\": int, \"classification\": string }\n"
        "- Estimated trading fees (in %) and maximum risk per trade (in % of account)\n\n"
        "Your task:\n"
        "1. Analyze technical indicators (e.g., MACD, RSI, Bollinger Bands) on both timeframes.\n"
        "2. Incorporate Fear & Greed Index as an additional risk-sentiment signal:\n"
        "   - Extreme Fear → consider contrarian buys  \n"
        "   - Extreme Greed → consider profit-taking or avoid new longs\n"
        "3. Calculate an optimal position size based on maximum risk per trade.\n"
        "4. Recommend stop-loss and take-profit levels if appropriate.\n"
        "5. Decide whether to BUY, SELL, or HOLD ETH at market.\n"
        "6. Assign a confidence score between 0.0 and 1.0.\n\n"
        "Respond in JSON format.\n"
        "Example:\n"
        "{\"decision\":\"buy\",\"reason\":\"some technical reason\"}\n"
        "{\"decision\":\"sell\",\"reason\":\"some technical reason\"}\n"
        "{\"decision\":\"hold\",\"reason\":\"some technical reason\"}"
    )

    #====================================================================
    # 5. ChatGPT API 콜 (gpt-4o, etc.)
    #====================================================================
    client   = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": data_for_gpt_json}
        ],
        response_format={"type": "json_object"}
    )

    # ChatGPT 응답
    gpt_result_str = response.choices[0].message.content

    #====================================================================
    # 6. ChatGPT 응답(JSON) 파싱 및 실제 매매 로직
    #====================================================================
    try:
        gpt_result = json.loads(gpt_result_str)
    except Exception as e:
        print("GPT 응답이 JSON 형식이 아닙니다:", gpt_result_str)
        return

    # (매매 직전 잔고 재확인)
    my_krw = upbit.get_balance("KRW")
    my_eth = upbit.get_balance("KRW-ETH")

    if "decision" not in gpt_result or "reason" not in gpt_result:
        print("Error: GPT 응답에 필수 필드(decision/reason)가 누락됨.")
        print("GPT 응답:", gpt_result)
        return

    decision = gpt_result["decision"]
    reason   = gpt_result["reason"]

    print(f"### Decision: {decision.upper()} | Reason: {reason}")

    #====================================================================
    # 7. 매매 실행
    #====================================================================
    if decision == "buy":
        if my_krw > 5000:
            print("=== Buy Order Executed ===")
            upbit.buy_market_order("KRW-ETH", my_krw * 0.9995)
        else:
            print("KRW 잔액 부족 (5000원 이상 필요)")
    elif decision == "sell":
        orderbook_now = pyupbit.get_orderbook("KRW-ETH")
        if (orderbook_now and isinstance(orderbook_now, list) and
                orderbook_now[0].get("orderbook_units")):
            current_price = orderbook_now[0]["orderbook_units"][0]["ask_price"]
            total_value   = my_eth * current_price
            if total_value > 5000:
                print("=== Sell Order Executed ===")
                upbit.sell_market_order("KRW-ETH", my_eth)
            else:
                print("ETH 가치가 5000원 미만. 매도 불가")
        else:
            print("오더북 데이터 오류: 매도 중단")
    else:
        print("=== Hold: No action taken ===")

##############################
# 4) 주기 실행
##############################
if __name__ == "__main__":
    while True:
        ai_trading()
        time.sleep(60)  # 1분 간격
