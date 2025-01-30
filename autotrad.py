import os
import time
import json
import pyupbit
from dotenv import load_dotenv
from openai import OpenAI

def ai_trading():
    # .env 파일에서 환경변수 로드
    load_dotenv()

    # 업비트 로그인 (잔고 조회 포함)
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    upbit = pyupbit.Upbit(access, secret)

    # 현재 투자 상태(잔고) 조회
    all_balance = upbit.get_balances()
    filtered_balance = [item for item in all_balance if item['currency'] == 'KRW' or item['currency'] == 'ETH']
    print(filtered_balance)

    #---------------------------------------------------------------------------
    # 1. 업비트 차트 데이터(30일 일봉, 24시간 차트), 오더북, 투자상태 가져오기
    #---------------------------------------------------------------------------
    df_30d = pyupbit.get_ohlcv("KRW-ETH", count=30, interval="day")       # 30일 일봉 데이터
    df_24h = pyupbit.get_ohlcv("KRW-ETH", count=24, interval="minute60")  # 24시간 동안의 1시간봉 (minute60) 24개
    orderbook = pyupbit.get_orderbook("KRW-ETH")                          # 오더북(호가정보): KRW-ETH 매수/매도 호가

    print(df_30d)
    print(df_24h)
    print(orderbook)

#    #---------------------------------------------------------------------------
#    # 2. ChatGPT에게 데이터 제공 (json 형태) & 판단 결과 받기
#    #---------------------------------------------------------------------------
#    # GPT에게 넘길 데이터를 딕셔너리로 모아서, JSON 형태로 직렬화
#    # 데이터가 많을 수 있으니, 필요시 축약/가공해서 보내는 방법도 고려 필요
#    data_for_gpt = {                           # -------------------------- 데이터 전용 딕셔너리 ---------------------------- #
#        "chart_data_30d": df_30d.to_dict(),    # 30일 일봉 데이터                         (df를 to_dict()로 변환)             #
#        "chart_data_24h": df_24h.to_dict(),    # 24시간 동안의 1시간봉 (minute60) 24개    (df를 to_dict()로 변환)             #
#        "orderbook": orderbook,                # 오더북(호가정보): KRW-ETH 매수/매도 호가 (orderbook 변수 그대로 전달)        #
#        "investment_status": filtered_balance  # 투자상태(잔고): KRW, ETH                 (filtered_balance 변수 그대로 전달) #
#    }                                          #------------------------------------------------------------------------------#
#    data_for_gpt_json = json.dumps(data_for_gpt, ensure_ascii=False)
#
#    client = OpenAI()
#    response = client.chat.completions.create(
#        model="gpt-4o",
#        messages=[
#            # 역할: system
#            {
#                "role": "system",
#                "content": [
#                    {
#                        "type": "text",
#                        "text": (
#                            "You are a Bitcoin investing expert. \n"
#                            "Based on the following data (chart, orderbook, balance, etc.), \n"
#                            "tell us whether you feel like buying, selling, or holding at the moment. \n"
#                            "Response in JSON format.\n\n"
#                            "Example:\n"
#                            "{\"decision\":\"buy\",\"reason\":\"some technical reason\"}\n"
#                            "{\"decision\":\"sell\",\"reason\":\"some technical reason\"}\n"
#                            "{\"decision\":\"hold\",\"reason\":\"some technical reason\"}"
#                        )
#                    }
#                ]
#            },
#            # 역할: user (실제 데이터 전달)
#            {
#                "role": "user",
#                "content": [
#                    {
#                        "type": "text",
#                        "text": data_for_gpt_json
#                    }
#                ]
#            }
#        ],
#        response_format={"type": "json_object"},
#    )
#
#    # GPT의 응답(result)을 JSON 문자열로 수신
#    gpt_result_str = response.choices[0].message.content
#
#    #---------------------------------------------------------------------------
#    # 3. ChatGPT의 판단에 따라 실제 자동매매 진행
#    #---------------------------------------------------------------------------
#    try:
#        gpt_result = json.loads(gpt_result_str)
#    except:
#        print("GPT 응답이 JSON 형식이 아닙니다. 응답:", gpt_result_str)
#        return
#
#    # 콘솔에 ChatGPT 결정/사유 출력
#    if "decision" not in gpt_result or "reason" not in gpt_result:
#        print("Error: GPT 응답에 필수 필드(decision/reason)가 누락되었습니다.")
#        print("GPT 응답:", gpt_result)
#        return
#
#    decision = gpt_result["decision"]
#    reason = gpt_result["reason"]
#    print("### ChatGPT Decision:", decision.upper(), "###")
#    print("### ChatGPT Reason:", reason, "###")
#
#    if decision == "buy":
#        # 매수 로직
#        if my_krw > 5000:
#            print("### Buy Order Executed ###")
#            # 수수료 0.05% 적용, KRW 전액을 매수
#            buy_result = upbit.buy_market_order("KRW-ETH", my_krw * 0.9995)
#            print(buy_result)
#        else:
#            print("잔액이 부족합니다.(KRW 5000원 이상 보유 필요)")
#
#    elif decision == "sell":
#        # 매도 로직
#        # 현재가: 오더북의 매도 1호가
#        ob = pyupbit.get_orderbook(ticker="KRW-ETH")
#        current_price = ob[0]["orderbook_units"][0]["ask_price"]
#        total_value  = my_eth * current_price
#        if total_value > 5000:
#            print("### Sell Order Executed ###")
#            sell_result = upbit.sell_market_order("KRW-ETH", my_eth)
#            print(sell_result)
#        else:
#            print("매도할 ETH가 부족합니다.(ETH 5000원 이상 가치 보유 필요)")
#
#    else:
#        # hold
#        print("### Hold: No action taken ###")
#
##---------------------------------------------------------------------------
## 4. 주기적으로 매매 실행
##---------------------------------------------------------------------------
#if __name__ == "__main__":
#    while True:
#        ai_trading()
#        # 10초마다 반복 실행
#        time.sleep(10)

ai_trading() # 테스트 실행