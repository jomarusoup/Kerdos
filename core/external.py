import os
import requests
import base64
import io
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from youtube_transcript_api import YouTubeTranscriptApi
from core.reflection import generate_reflection

########################################################
# 1) 공포-탐욕 지수 수집 함수
########################################################
def get_fear_greed_index():
    # 공포-탐욕 지수 API에서 최신 데이터 가져오기
    url = "https://api.alternative.me/fng/"
    params = {'limit': 1, 'format': 'json', 'date_format': 'kr'}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        fng_entry = data['data'][0]
        return {
            'value': int(fng_entry['value']),  # 지수 값
            'classification': fng_entry['value_classification']  # 분류(예: Neutral)
        }
    except Exception as e:
        print("[FNG] API Error:", e)
        return {'value': 50, 'classification': 'Neutral'}  # 실패 시 기본값 반환

########################################################
# 2) 이더리움 관련 최신 뉴스 헤드라인 수집 함수
########################################################
def get_latest_eth_news_headlines():
    """
    SerpAPI를 활용해 Google News에서 'Ethereum' 관련 최신 뉴스 헤드라인 5개를 가져온다.
    쿼터 초과 등으로 뉴스가 없을 경우 빈 리스트 반환.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("[NEWS] SERPAPI_KEY가 설정되어 있지 않습니다.")
        return []
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_news",
        "q": "ethereum OR 이더리움",
        "gl": "kr",
        "hl": "ko",
        "api_key": api_key
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            print(f"[NEWS] SerpAPI Error: {data['error']}")
            return []
        news_results = data.get("news_results", [])
        headlines = [
            {
                "title": item.get("title"),
                "date": item.get("date")
            }
            for item in news_results[:5]  # 최대 5개만 반환
        ]
        return headlines
    except Exception as e:
        print("[NEWS] SerpAPI Exception:", e)
        return []

########################################################
# 3) 차트 이미지 캡처 함수
########################################################

# 3-1) 크롬 드라이버 설정 함수
def setup_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    return chrome_options

# 3-2) 크롬 드라이버 생성 함수
def create_driver():

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=setup_chrome_options())
    return driver

# 3-3) 스크린샷 캡처 및 인코딩 함수
def capture_and_encode_screenshot(driver, save_dir="/home/kerdos/gptbitcoin/capture"):
    import logging
    logger = logging.getLogger("capture")
    try:
        png = driver.get_screenshot_as_png()
        img = Image.open(io.BytesIO(png))
        img.thumbnail((2000, 2000))  # 이미지 크기 제한
        from datetime import datetime
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"upbit_chart_{current_time}.png"
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, filename)
        img.save(file_path)
        logger.info(f"스크린샷이 저장되었습니다: {file_path}")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return base64_image, file_path
    except Exception as e:
        logger.error(f"스크린샷 캡처 및 인코딩 중 오류 발생: {e}")
        return None, None

# 3-4) 업비트 차트 페이지 캡처 함수
def capture_full_page_screenshot_and_save_and_encode(url="https://upbit.com/full_chart?code=CRIX.UPBIT.KRW-ETH", save_dir="/home/kerdos/gptbitcoin/capture"):
    import logging
    from datetime import datetime
    logger = logging.getLogger("capture")
    start_time = datetime.now()
    driver = None
    try:
        driver = create_driver()
        driver.get(url)
        import time
        logger.info("페이지 로딩 대기 중...")
        time.sleep(5)  # 페이지 로딩 대기
        # 1시간봉 메뉴 클릭
        menu_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, menu_xpath))
        ).click()
        # 드롭다운 메뉴 대기
        dropdown_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, dropdown_xpath))
        )
        # 1시간 선택
        one_hour_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown/cq-item[8]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, one_hour_xpath))
        ).click()
        time.sleep(2)
        # 인디케이터 메뉴 클릭
        indicator_menu_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, indicator_menu_xpath))
        ).click()
        # 인디케이터 드롭다운 대기
        indicator_dropdown_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, indicator_dropdown_xpath))
        )
        # 볼린저밴드 선택
        bollinger_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[15]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, bollinger_xpath))
        ).click()
        time.sleep(2)
        # 스크린샷 캡처 및 저장
        base64_image, file_path = capture_and_encode_screenshot(driver, save_dir)
        logger.info(f"최종 캡처 파일: {file_path}")
        return base64_image, file_path
    except Exception as e:
        logger.error(f"[CAPTURE] 오류 발생: {e}")
        return None, None
    finally:
        if driver:
            driver.quit()
        end_time = datetime.now()
        logger.info(f"[CAPTURE] 종료 시각: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"[CAPTURE] 총 소요 시간: {end_time - start_time}")

# 3-5) 차트 이미지 base64 반환 함수
def get_latest_chart_image_base64(capture_dir="/home/kerdos/gptbitcoin/capture"):
    import glob
    image_files = sorted(
        glob.glob(os.path.join(capture_dir, "*.png")),
        key=os.path.getmtime,
        reverse=True
    )
    if not image_files:
        print("[Vision] 캡처 이미지가 없습니다.")
        return None
    image_path = image_files[0]
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

########################################################
# 4) 유튜브 영상 자막 합치기 함수
########################################################
def get_combined_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        combined_text = ' '.join(entry['text'] for entry in transcript)
        return combined_text
    except Exception as e:
        print(f"[YouTube] 자막 추출 실패: {e}")
        return ""