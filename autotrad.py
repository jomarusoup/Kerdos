import os
import time
import json
import pyupbit
import pandas as pd

# ta 라이브러리
from ta import add_all_ta_features
from ta.utils import dropna

from dotenv import load_dotenv
from openai import OpenAI

def ai_trading():
    # [STEP 1] .env 파일에서 환경변수 로드
    load_dotenv()

    # [STEP 2] 업비트 로그인 (잔고 조회 포함)
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    upbit = pyupbit.Upbit(access, secret)

    # 현재 투자 상태(잔고) 조회
    all_balance = upbit.get_balances()
    # KRW, ETH만 필터링
    filtered_balance = [item for item in all_balance if item['currency'] in ['KRW', 'ETH']]
    print("=== filtered_balance ===")
    print(filtered_balance)

    #---------------------------------------------------------------------------
    # [STEP 3] 업비트 차트 데이터(30일 일봉, 24시간 차트), 오더북 가져오기
    #---------------------------------------------------------------------------
    df_30d = pyupbit.get_ohlcv("KRW-ETH", count=30, interval="day")       # 30일 일봉
    df_24h = pyupbit.get_ohlcv("KRW-ETH", count=24, interval="minute60")  # 24시간(1시간봉)
    orderbook = pyupbit.get_orderbook("KRW-ETH")                          # 오더북(호가정보)

    #---------------------------------------------------------------------------
    # [STEP 4] TA 라이브러리를 활용한 보조 지표 추가
    #---------------------------------------------------------------------------
    # (1) df_30d(일봉) 전처리
    df_30d = df_30d.reset_index()  # 날짜 인덱스를 일반 칼럼으로 변환
    df_30d.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        },
        inplace=True
    )
    df_30d = dropna(df_30d)  # NaN 제거
    df_30d = add_all_ta_features(
        df_30d,
        open="Open",
        high="High",
        low="Low",
        close="Close",
        volume="Volume",
    )

    # (2) df_24h(1시간봉) 전처리
    df_24h = df_24h.reset_index()
    df_24h.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        },
        inplace=True
    )
    df_24h = dropna(df_24h)
    df_24h = add_all_ta_features(
        df_24h,
        open="Open",
        high="High",
        low="Low",
        close="Close",
        volume="Volume",
    )

    #---------------------------------------------------------------------------
    # [STEP 5] 엔벨로프(Envelope) 계산 추가
    #---------------------------------------------------------------------------
    # (예시) 20일 이동평균 기준으로 ±2% 폭
    envelope_window = 20  # 이동평균 기간
    envelope_pct = 0.02   # 위/아래 각각 2%

    # ========== 일봉(df_30d)에 엔벨로프 추가 ==========
    # 1) 이동평균
    df_30d["MA_Envelope"] = df_30d["Close"].rolling(window=envelope_window).mean()
    # 2) 엔벨로프 상단/하단
    df_30d["env_upper"] = df_30d["MA_Envelope"] * (1 + envelope_pct)
    df_30d["env_lower"] = df_30d["MA_Envelope"] * (1 - envelope_pct)

    # ========== 1시간봉(df_24h)에 엔벨로프 추가 ==========
    df_24h["MA_Envelope"] = df_24h["Close"].rolling(window=envelope_window).mean()
    df_24h["env_upper"] = df_24h["MA_Envelope"] * (1 + envelope_pct)
    df_24h["env_lower"] = df_24h["MA_Envelope"] * (1 - envelope_pct)

    #---------------------------------------------------------------------------
    # [STEP 6] ChatGPT에게 전달할 데이터 생성 (json 형태)
    #---------------------------------------------------------------------------
    data_for_gpt = {
        "chart_data_30d": df_30d.to_dict(),    # 일봉 (보조지표 + 엔벨로프 포함)
        "chart_data_24h": df_24h.to_dict(),    # 1시간봉 (보조지표 + 엔벨로프 포함)
        "orderbook": orderbook,               # 오더북(호가 정보)
        "investment_status": filtered_balance  # 투자 상태 (잔고)
    }
    data_for_gpt_json = json.dumps(data_for_gpt, ensure_ascii=False)

    # OpenAI 연결
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            # system 역할
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a Bitcoin investing expert.\n"
                            "Based on the following data (chart, orderbook, balance, etc.),\n"
                            "tell us whether you feel like buying, selling, or holding at the moment.\n"
                            "Response in JSON format.\n\n"
                            "Example:\n"
                            "{\"decision\":\"buy\",\"reason\":\"some technical reason\"}\n"
                            "{\"decision\":\"sell\",\"reason\":\"some technical reason\"}\n"
                            "{\"decision\":\"hold\",\"reason\":\"some technical reason\"}"
                        )
                    }
                ]
            },
            # user 역할
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": data_for_gpt_json
                    }
                ]
            }
        ],
        response_format={"type": "json_object"},
    )

    # GPT 응답
    gpt_result_str = response.choices[0].message.content

    #---------------------------------------------------------------------------
    # [STEP 7] ChatGPT 판단에 따른 매매 로직
    #---------------------------------------------------------------------------
    try:
        gpt_result = json.loads(gpt_result_str)
    except:
        print("GPT 응답이 JSON 형식이 아닙니다. 응답:", gpt_result_str)
        return

    # 재확인: 현재 잔고
    my_krw = upbit.get_balance("KRW")
    my_eth = upbit.get_balance("KRW-ETH")

    if "decision" not in gpt_result or "reason" not in gpt_result:
        print("Error: GPT 응답에 필수 필드(decision/reason)가 누락되었습니다.")
        print("GPT 응답:", gpt_result)
        return

    decision = gpt_result["decision"]
    reason = gpt_result["reason"]

    print("### ChatGPT Decision:", decision.upper(), "###")
    print("### ChatGPT Reason:", reason, "###")

    if decision == "buy":
        # 매수 로직
        if my_krw > 5000:
            print("### Buy Order Executed ###")
            buy_result = upbit.buy_market_order("KRW-ETH", my_krw * 0.9995)
            print(buy_result)
        else:
            print("잔액 부족 (KRW 5000 이상 필요)")

    elif decision == "sell":
        # 매도 로직
        ob = pyupbit.get_orderbook(ticker="KRW-ETH")
        current_price = ob[0]["orderbook_units"][0]["ask_price"]
        total_value = my_eth * current_price

        if total_value > 5000:
            print("### Sell Order Executed ###")
            sell_result = upbit.sell_market_order("KRW-ETH", my_eth)
            print(sell_result)
        else:
            print("매도할 ETH 가치 부족 (ETH 5000원 이상 보유 필요)")

    else:
        # hold
        print("### Hold: No action taken ###")

#---------------------------------------------------------------------------
# [STEP 8] 주기적으로 매매 실행
#---------------------------------------------------------------------------
if __name__ == "__main__":
    while True:
        ai_trading()
        # 10초마다 반복 실행 (실제 운영 시 주기를 적절히 조절하세요)
        time.sleep(10)