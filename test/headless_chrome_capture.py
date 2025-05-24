# headless_chrome_capture.py
# Rocky Linux CLI 환경에서 Headless Chrome을 사용하여
# Upbit 이더리움 차트를 전체 화면 캡처하여 지정된 경로에 이미지로 저장하는 코드

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 로깅 설정 (INFO 레벨로 설정)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 크롬 옵션 설정 함수
def setup_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")           # 최신 Headless 모드 사용
    chrome_options.add_argument("--disable-gpu")            # GPU 비활성화 (호환성 개선)
    chrome_options.add_argument("--no-sandbox")             # 샌드박스 비활성화
    chrome_options.add_argument("--window-size=1920,1080")  # 가상 브라우저 해상도 지정
    return chrome_options

# 크롬 드라이버 생성 함수 (webdriver_manager로 자동 설치)
def create_driver():
    logger.info("ChromeDriver 설정 중...")
    service = Service(ChromeDriverManager().install())  # 드라이버 자동 설치 및 서비스 객체 생성
    driver = webdriver.Chrome(service=service, options=setup_chrome_options())
    return driver

# 전체 페이지 스크린샷 캡처 함수
def capture_full_page_screenshot(driver, url, filename):
    logger.info(f"{url} 로딩 중...")
    driver.get(url)  # 지정한 URL로 이동
    logger.info("페이지 로딩 대기 중...")
    time.sleep(5)    # 페이지 렌더링 대기 (필요시 조정)

    # 1. 시간 메뉴 버튼 클릭
    menu_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]"
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, menu_xpath))
        ).click()
        logger.info("시간 메뉴 버튼 클릭 완료")
    except Exception as e:
        logger.error(f"시간 메뉴 버튼 클릭 실패: {e}")
        raise

    # 메뉴가 완전히 열릴 때까지 대기
    dropdown_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown"
    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, dropdown_xpath))
        )
        logger.info("드롭다운 메뉴 열림 확인 완료")
    except Exception as e:
        logger.error(f"드롭다운 메뉴 대기 실패: {e}")
        raise

    # 2. '1시간' 옵션 클릭 (정확한 Xpath 사용)
    one_hour_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown/cq-item[8]"
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, one_hour_xpath))
        ).click()
        logger.info("'1시간' 옵션 클릭 완료")
    except Exception as e:
        logger.error(f"'1시간' 옵션 클릭 실패: {e}")
        raise

    time.sleep(2)  # 차트 갱신 대기

    logger.info("전체 페이지 스크린샷 촬영 중...")
    driver.save_screenshot(filename)  # 스크린샷 저장
    logger.info(f"스크린샷이 성공적으로 저장되었습니다: {filename}")

# 메인 함수 (프로그램 진입점)
def main():
    start_time = datetime.now()  # 시작 시각 기록
    logger.info(f"시작 시각: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    now_str = start_time.strftime("%Y%m%d_%H%M%S")
    output_path = f"/home/kerdos/gptbitcoin/test/capture/headless_{now_str}.png"  # 파일명 자동 생성
    url = "https://upbit.com/full_chart?code=CRIX.UPBIT.KRW-ETH"  # 캡처할 차트 URL
    driver = None
    try:
        driver = create_driver()  # 드라이버 생성
        capture_full_page_screenshot(driver, url, output_path)  # 스크린샷 캡처
    except Exception as e:
        logger.error(f"오류 발생: {e}")  # 예외 발생 시 에러 로그 출력
    finally:
        if driver:
            driver.quit()  # 드라이버 종료 (자원 정리)
        end_time = datetime.now()  # 종료 시각 기록
        logger.info(f"종료 시각: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"총 소요 시간: {end_time - start_time}")

# 프로그램 실행 진입점
if __name__ == "__main__":
    main()

