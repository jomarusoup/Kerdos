#--- 모듈 임포트(라이브러리 불러오기)
import os
from dotenv import load_dotenv

#--- .env 파일 로드
load_dotenv()

# 1. upbit 차트 데이터 가져오기(30일 일봉 데이터)
import pyupbit
df = pyupbit.get_ohlcv("KRW-BTC", count=30, interval="day")

# 2. AI에게 데이터 제공하고 예측 결과 받기
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
)


print(response.choices[0].message.content) # message 안이 content만 필요