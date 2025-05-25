import pyupbit
import time
from dotenv import load_dotenv
import os

#--- .env 파일에서 환경변수 로드
load_dotenv()

#--- 업비트 로그인
access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
if not access or not secret:
    raise RuntimeError("UPBIT_ACCESS_KEY/SECRET not set")
upbit  = pyupbit.Upbit(access, secret)

ticker = "KRW-ETH"

for i in range(5):
    try:
        orderbook = pyupbit.get_orderbook(ticker)
        print(f"\n[{i+1}회차] pyupbit.get_orderbook('{ticker}') 결과:")
        print(orderbook)
        if orderbook and isinstance(orderbook, dict) and 'orderbook_units' in orderbook:
            print("✅ 오더북 정상 수신!")
            print("최상위 매도호가(ask_price):", orderbook['orderbook_units'][0]['ask_price'])
            print("최상위 매수호가(bid_price):", orderbook['orderbook_units'][0]['bid_price'])
            break
        else:
            print("❌ 오더북 데이터가 None이거나 orderbook_units가 없습니다.")
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
    time.sleep(2)
else:
    print("5회 시도에도 오더북 데이터를 받아오지 못했습니다.")