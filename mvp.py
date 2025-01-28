#--- 모듈 임포트(라이브러리 불러오기)
import os
from dotenv import load_dotenv

#--- .env 파일 로드
load_dotenv()

def ai_trading():
    #---------------------------------------------------
    # 1. upbit 차트 데이터 가져오기(30일 일봉 데이터)
    #---------------------------------------------------
    import pyupbit
    df = pyupbit.get_ohlcv("KRW-ETH", count=30, interval="day")

    #---------------------------------------------------
    # 2. AI에게 데이터 제공하고 예측 결과 받기
    #---------------------------------------------------
    from openai import OpenAI
    client = OpenAI()

    response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        # Prompts
        {
        "role": "system",
        "content": [
            {
            "type": "text",
            "text": "You are a Bitcoin investing expert.\nBased on the chart data provided, tell us whether you feel like buying, selling, or holding at the moment. Response in json format\n\nResopnse Example:\n{\"decision\":\"buy\",\"reaseon\":\"some  technical reason\"}\n{\"decision\":\"sell\",\"reaseon\":\"some  technical reason\"}\n{\"decision\":\"hold\",\"reaseon\":\"some  technical reason\"}"
            }
        ]
        },
        # 차트 데이터
        {
        "role": "user",
        "content": [
            {
            "type": "text",
            "text": df.to_json()
            }
        ]
        }
    ],
    response_format={
        "type": "json_object"
    },
    # temperature=1, max_completion_tokens=2048, top_p=1, frequency_penalty=0,  presence_penalty=0
    )

    #print(response.choices[0].message.content)  # message 안이 content만 필요
    result = response.choices[0].message.content # 문자열 형태로 받음

    #---------------------------------------------------
    # 3. Chatgpt의 판단에 따라 실제로 자동매매 진행하기
    #---------------------------------------------------
    import json
    result = json.loads(result) # 문자열을 json 형태로 변환

    #upbit 로그인
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    upbit = pyupbit.Upbit(access, secret)

    print("### Chatgpt Decision: ", result['decision'].upper(), "###")
    if 'reason' in result:
        print("### Chatgpt Reason: ", result['reason'], "###")
    else:
        print("### HOLD: No reason provided by ChatGPT ###")

    # Chatgpt 판단에 따라 매매 진행 시장가 매도/매수 주문
    if result['decision'] == 'buy':    # 매수
        my_krw = upbit.get_balance("KRW")
        if my_krw > 5000:
            print("### Buy Order Executed ###")
            print(upbit.buy_market_order("KRW-ETH", my_krw * 0.9995)) # 수수료 0.05% 적용
        else:
            print("잔액이 부족합니다.(KRW 5000원 이상 보유 필요)")
    elif result['decision'] == 'sell': # 매도
        my_eth = upbit.get_balance("KRW-ETH")
        current_price = pyupbit.get_orderbook(ticker="KRW-ETH")['orderbook_units'][0]["ask_price"] # 매도 1호가 기준으로 현재가격 측정
        if my_eth * current_price > 5000:
            print("### Sell Order Executed ###")
            print(upbit.sell_market_order("KRW-ETH", my_eth))
        else:
            print("매도 주문 잔액이 부족합니다.(ETH 5000원 이상 보유 필요)")
    elif result['decision'] == 'hold': # hold
        print("### Hold Order Executed ###")

#---------------------------------------------------
# 4. 매매 실행 주기 설정
#---------------------------------------------------
while True:
    import time
    time.sleep(10) # 10초마다 매매 진행
    ai_trading()
