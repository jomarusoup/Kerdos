#--- 모듈 임포트
import os                      # os 모듈 임포트
from dotenv import load_dotenv # dotenv 모듈 임포트

#--- .env 파일 로드
load_dotenv()

print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("UPBIT_ACCESS_KEY"))
print(os.getenv("UPBIT_SECRET_KEY"))

