# headless_chrome_capture.py
# Rocky Linux CLI 환경에서 Headless Chrome을 사용하여
# Upbit 이더리움 차트를 전체 화면 캡처하여 지정된 경로에 이미지로 저장하는 코드

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import os
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def capture_chart_headless():
    # 프로그램 시작 시간 출력
    start_time = datetime.now()
    print(f"[Headless] 시작 시각: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    # 현재 날짜와 시간으로 파일명 생성
    now_str = start_time.strftime("%Y%m%d_%H%M%S")
    output_path = f"/home/kerdos/gptbitcoin/test/capture/headless_{now_str}.png"

    # 크롬 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")            # 최신 Headless 모드 사용
    chrome_options.add_argument("--disable-gpu")             # GPU 비활성화 (호환성 개선)
    chrome_options.add_argument("--no-sandbox")              # 샌드박스 비활성화
    chrome_options.add_argument("--window-size=1920,1080")   # 가상 브라우저 해상도

    # 웹드라이버 실행 (headless 모드)
    driver = webdriver.Chrome(options=chrome_options)

    # Upbit 전체 차트 페이지로 이동
    driver.get("https://upbit.com/full_chart?code=CRIX.UPBIT.KRW-ETH")

    # 차트 렌더링 대기 (1차: sleep, 2차: WebDriverWait)
    time.sleep(1)  # 1차: 빠른 대기(8초)
#    try:
#        WebDriverWait(driver, 5).until(
#            EC.presence_of_element_located((By.CSS_SELECTOR, ".tv-chart-view"))
#        )
#        print("[Headless] TradingView 차트 DOM 로드 추가 확인 완료")
#    except Exception as e:
#        print(f"[Headless] 차트 추가 로딩 대기 중 오류(무시): {e}")

    # 전체 화면 스크린샷 저장
    driver.save_screenshot(output_path)

    # 브라우저 종료
    driver.quit()

    # 종료 시각 출력
    end_time = datetime.now()
    print(f"[Headless] 종료 시각: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[Headless] 총 소요 시간: {end_time - start_time}")
    print(f"[Headless] 캡처 완료: {output_path}")

# 진입점
if __name__ == "__main__":
    capture_chart_headless()

