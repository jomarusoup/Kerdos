#--- 모듈 임포트(라이브러리 불러오기)
import os
from dotenv import load_dotenv

#--- .env 파일 로드
load_dotenv()

# 1. upbit 차트 데이터 가져오기(30일 일봉 데이터)
import pyupbit
df = pyupbit.get_ohlcv("KRW-BTC", count=30, interval="day")
print(df.to_json())

# 2. AI에게 데이터 제공하고 예측 결과 받기
