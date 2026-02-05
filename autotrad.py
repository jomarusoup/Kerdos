# 기본 라이브러리
import os
import time
import json
import requests
import logging
from datetime import datetime, timedelta

# 데이터 처리 관련
import pandas as pd
import ta
import base64
import io
from PIL import Image

# 환경 설정
from dotenv import load_dotenv

# OpenAI API
from openai import OpenAI

# 웹 스크래핑 관련
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 유튜브 관련
from youtube_transcript_api import YouTubeTranscriptApi

# 데이터베이스 관련
import psycopg2

# 암호화폐 거래 관련
import pyupbit

# 코어 모듈 import
from core.indicators import add_indicators
from core.external import (
    get_fear_greed_index,
    get_latest_eth_news_headlines,
    capture_full_page_screenshot_and_save_and_encode,
    get_combined_transcript,
    get_latest_chart_image_base64
)
from core.db import (
    init_postgres_table,
    log_trade_postgres,
    get_recent_trades_postgres,
    calculate_performance,
    update_last_trade_reflection
)
from core.reflection import generate_reflection

########################################################
# 1) 보조지표 계산 함수
########################################################
def add_indicators(df, envelope_window=20, envelope_pct=0.02):
    """
    주어진 DataFrame(df)에
    - 볼린저 밴드
    - RSI
    - MACD
    - 이동평균(SMA 20, EMA 12)
    - 엔벨로프(Envelope) (기본: 20일 평균±2%)
    등을 계산해서 컬럼으로 추가한 후 반환한다.
    """
    #--- 변수 선언
    indicator_bbands = None
    indicator_macd   = None

    #--- Bollinger Bands
    indicator_bbands = ta.volatility.BollingerBands(
        close = df['Close'],
        window = 20,
        window_dev = 2
    )

    df['bb_bbh'] = indicator_bbands.bollinger_hband() # 상단선
    df['bb_bbm'] = indicator_bbands.bollinger_mavg()  # 중앙선(기준선)
    df['bb_bbl'] = indicator_bbands.bollinger_lband() # 하단선

    #---- RSI
    df['rsi'] = ta.momentum.RSIIndicator(
        close = df['Close'],
        window = 14
    ).rsi()

    #--- MACD
    indicator_macd = ta.trend.MACD(
        close = df['Close'],
        window_slow = 26,
        window_fast = 12,
        window_sign = 9
    )

    df['macd']        = indicator_macd.macd()
    df['macd_signal'] = indicator_macd.macd_signal()
    df['macd_diff']   = indicator_macd.macd_diff()

    #--- SMA, EMA
    df['sma_20'] = ta.trend.SMAIndicator(
        close = df['Close'],
        window = 20
    ).sma_indicator()

    df['ema_12'] = ta.trend.EMAIndicator(
        close = df['Close'],
        window = 12
    ).ema_indicator()

    #--- Envelope
    # 엔벨로프(Envelope) : MA ± 일정 비율
    # 여기서는 sma_20을 기준으로 엔벨로프 계산 가능 (또는 Close의 rollingMean 등 원하는 기준 사용)
    df['env_ma']    = df['Close'].rolling(window=envelope_window).mean()
    df['env_upper'] = df['env_ma'] * (1 + envelope_pct)
    df['env_lower'] = df['env_ma'] * (1 - envelope_pct)

    return df

########################################################
# 2) 외부 데이터 수집 함수
########################################################

#========================================================
# 2-1) 공포·탐욕 지수 호출 함수
#========================================================
def get_fear_greed_index():

    #--- 변수 선언
    url       = "https://api.alternative.me/fng/"
    params    = {}
    response  = None
    data      = None
    fng_entry = None

    params['limit']       = 1
    params['format']      = 'json'
    params['date_format'] = 'kr'

    try:
        response  = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data      = response.json()
        fng_entry = data['data'][0]

        return {
            'value': int(fng_entry['value']),
            'classification': fng_entry['value_classification']
        }

    except Exception as e:
        print("[FNG] API Error:", e)
        return {
            'value': 50,
            'classification': 'Neutral'
        }

#========================================================
# 2-2) Google News 최신 뉴스 헤드라인 수집 함수 (SerpAPI)
#========================================================
def get_latest_eth_news_headlines():
    """
    SerpAPI를 활용해 Google News에서 'Ethereum' 관련 최신 뉴스 헤드라인 5개를 가져온다.
    쿼터 초과 등으로 뉴스가 없을 경우 빈 리스트 반환.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("[NEWS] SERPAPI_KEY가 설정되어 있지 않습니다.")
        return []

    # request를 이용해서 GET요청으로 api요청
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

        # 헤드라인 5개만 추출 (title, date만)
        headlines = [
            {
                "title": item.get("title"),
                "date": item.get("date")
            }
            for item in news_results[:5]
        ]
        return headlines
    except Exception as e:
        print("[NEWS] SerpAPI Exception:", e)
        return []

#========================================================
# 2-3) 차트 이미지 캡처 함수
#========================================================

#--- chrome 옵션 설정 함수
def setup_chrome_options():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")           # 최신 Headless 모드 사용
    chrome_options.add_argument("--disable-gpu")            # GPU 비활성화 (호환성 개선)
    chrome_options.add_argument("--no-sandbox")             # 샌드박스 비활성화
    chrome_options.add_argument("--window-size=1920,1080")  # 가상 브라우저 해상도 지정
    return chrome_options

#--- chrome 드라이버 생성 함수
def create_driver():
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=setup_chrome_options())
    return driver

#--- 캡처 + 리사이즈 + 파일저장 + base64 인코딩 함수
def capture_and_encode_screenshot(driver, save_dir="/home/kerdos/gptbitcoin/capture"):
    logger = logging.getLogger("capture")
    try:
        # 스크린샷 캡처
        png = driver.get_screenshot_as_png()
        # PIL Image로 변환
        img = Image.open(io.BytesIO(png))
        # 이미지 리사이즈 (OpenAI API 제한에 맞춤)
        img.thumbnail((2000, 2000))
        # 현재 시간을 파일명에 포함
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"upbit_chart_{current_time}.png"
        # 저장 경로 생성
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, filename)
        # 이미지 파일로 저장
        img.save(file_path)
        logger.info(f"스크린샷이 저장되었습니다: {file_path}")
        # 이미지를 바이트로 변환
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        # base64로 인코딩
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return base64_image, file_path
    except Exception as e:
        logger.error(f"스크린샷 캡처 및 인코딩 중 오류 발생: {e}")
        return None, None

#--- 전체 페이지 캡처 함수
def capture_full_page_screenshot_and_save_and_encode(url="https://upbit.com/full_chart?code=CRIX.UPBIT.KRW-ETH", save_dir="/home/kerdos/gptbitcoin/capture"):
    logger = logging.getLogger("capture")
    start_time = datetime.now()
    logger.info(f"[CAPTURE] 시작 시각: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    driver = None
    try:
        driver = create_driver()
        driver.get(url)
        logger.info("페이지 로딩 대기 중...")
        time.sleep(5)

        # 1. 시간 메뉴 버튼 클릭
        menu_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, menu_xpath))
        ).click()
        logger.info("시간 메뉴 버튼 클릭 완료")

        # 메뉴가 완전히 열릴 때까지 대기
        dropdown_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, dropdown_xpath))
        )
        logger.info("드롭다운 메뉴 열림 확인 완료")

        # 2. '1시간' 옵션 클릭
        one_hour_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[1]/cq-menu-dropdown/cq-item[8]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, one_hour_xpath))
        ).click()
        logger.info("'1시간' 옵션 클릭 완료")
        time.sleep(2)

        # 3. 지표 메뉴 버튼 클릭
        indicator_menu_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, indicator_menu_xpath))
        ).click()
        logger.info("지표 메뉴 버튼 클릭 완료")

        # 지표 드롭다운이 완전히 열릴 때까지 대기
        indicator_dropdown_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown"
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.XPATH, indicator_dropdown_xpath))
        )
        logger.info("지표 드롭다운 메뉴 열림 확인 완료")

        # 4. 볼린저 밴드 옵션 클릭
        bollinger_xpath = "/html/body/div[1]/div[2]/div[3]/span/div/div/div[1]/div/div/cq-menu[3]/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[15]"
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, bollinger_xpath))
        ).click()
        logger.info("'볼린저 밴드' 옵션 클릭 완료")
        time.sleep(2)
        # 캡처+리사이즈+base64 인코딩
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

#--- 캡처 디렉토리에서 가장 최근에 저장된 이미지를 base64로 인코딩하여 반환
def get_latest_chart_image_base64(capture_dir="/home/kerdos/gptbitcoin/capture"):
    """
    캡처 디렉토리에서 가장 최근에 저장된 이미지를 base64로 인코딩하여 반환
    """
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

#========================================================
# 2-4) 유튜브 자막 데이터 추출 함수
#========================================================
def get_combined_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        combined_text = ' '.join(entry['text'] for entry in transcript)
        return combined_text
    except Exception as e:
        print(f"[YouTube] 자막 추출 실패: {e}")
        return ""

########################################################
# 3) Postgres 관련 함수
########################################################

#--- Postgres 테이블 초기화 함수
def init_postgres_table():
    """
    Create eth_auto_trad table with reflection column if it does not exist.
    """
    with psycopg2.connect(
        dbname=os.getenv("PG_DBNAME"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432")
    ) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS eth_auto_trad (
                    id SERIAL PRIMARY KEY,
                    time TIMESTAMP NOT NULL,
                    decision VARCHAR(10),
                    percentage NUMERIC,
                    reason TEXT,
                    eth_balance NUMERIC,
                    krw_balance NUMERIC,
                    eth_avg_buy_price NUMERIC,
                    eth_krw_price NUMERIC,
                    reflection TEXT
                );
            ''')
            conn.commit()

#--- Postgres 매매 기록 저장 함수
def log_trade_postgres(decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price, reflection=None):
    """
    매매 기록을 eth_autotrad 테이블에 저장 (reflection 포함)
    """
    # reflection 문자열에서 NUL(\x00) 문자 제거 및 타입 보장
    if reflection is not None:
        if not isinstance(reflection, str):
            reflection = str(reflection)
        reflection = reflection.replace('\x00', '')
    with psycopg2.connect(
        dbname=os.getenv("PG_DBNAME"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432")
    ) as conn:
        with conn.cursor() as cur:
            now = datetime.now()
            if reflection is not None:
                cur.execute('''
                    INSERT INTO eth_auto_trad
                    (time, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price, reflection)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (now, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price, reflection))
            else:
                cur.execute('''
                    INSERT INTO eth_auto_trad
                    (time, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (now, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price))
            conn.commit()

#--- Postgres 최근 매매 내역 조회 함수
def get_recent_trades_postgres(days=7):
    """
    최근 days일간의 매매 내역을 DataFrame으로 반환 (최신순)
    """
    with psycopg2.connect(
        dbname=os.getenv("PG_DBNAME"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432")
    ) as conn:
        with conn.cursor() as cur:
            since = datetime.now() - timedelta(days=days)
            cur.execute("SELECT * FROM eth_auto_trad WHERE time > %s ORDER BY time DESC", (since,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=columns)
    return df

#--- 매매 성과 계산 함수
def calculate_performance(trades_df):
    if trades_df.empty:
        return 0
    initial_balance = trades_df.iloc[-1]['krw_balance'] + trades_df.iloc[-1]['eth_balance'] * trades_df.iloc[-1]['eth_krw_price']
    final_balance = trades_df.iloc[0]['krw_balance'] + trades_df.iloc[0]['eth_balance'] * trades_df.iloc[0]['eth_krw_price']
    return (final_balance - initial_balance) / initial_balance * 100

########################################################
# 5) 메인 자동매매 함수
########################################################
def ai_trading():
    #--- 변수 초기화
    access            = None  # 업비트 API 액세스 키
    secret            = None  # 업비트 API 시크릿 키
    upbit             = None  # pyupbit.Upbit 객체 (API 연결)
    all_balance       = None  # 전체 잔고 정보 (모든 코인)
    filtered_balance  = None  # KRW, ETH만 필터링한 잔고 정보
    df_30d            = None  # 30일치 일봉 데이터프레임
    df_24h            = None  # 24시간치 1시간봉 데이터프레임
    orderbook         = None  # 현재 오더북 정보
    fng               = None  # 공포·탐욕 지수 정보
    system_prompt     = None  # ChatGPT 시스템 프롬프트
    client            = None  # OpenAI API 클라이언트 객체
    response          = None  # ChatGPT API 응답 객체
    gpt_result_str    = None  # ChatGPT 응답(문자열)
    gpt_result        = None  # ChatGPT 응답(JSON 파싱 결과)
    my_krw            = None  # 내 KRW(원화) 잔고
    my_eth            = None  # 내 ETH(이더리움) 잔고
    decision          = None  # ChatGPT의 매매 결정값
    reason            = None  # ChatGPT의 매매 결정 사유
    orderbook_now     = None  # 실시간 오더북 정보(매도 시)
    current_price     = None  # 현재가(매도 시)
    total_value       = None  # ETH 총 평가금액(매도 시)

    #--- .env 파일에서 환경변수 로드
    load_dotenv()
    # Postgres 테이블 초기화(최초 1회만 실행, 반복 호출해도 무방)
    # (테이블이 없으면 생성, 있으면 아무 일도 안 함)
    init_postgres_table()
    #--- 업비트 로그인
    access = os.getenv("UPBIT_ACCESS_KEY")
    secret = os.getenv("UPBIT_SECRET_KEY")
    if not access or not secret:
        raise RuntimeError("UPBIT_ACCESS_KEY/SECRET not set")
    upbit  = pyupbit.Upbit(access, secret)

    #--- 현재 잔고 조회 (KRW, ETH만 필터)
    all_balance      = upbit.get_balances()
    filtered_balance = [
        item for item in all_balance
        if item['currency'] in ['KRW', 'ETH']
    ]

    print("=== filtered_balance ===")
    print(filtered_balance)

    #====================================================================
    # 1. 업비트 차트 데이터 (일봉 30일치, 1시간봉 24개) + 오더북
    #====================================================================
    df_30d    = pyupbit.get_ohlcv("KRW-ETH", count=30, interval="day")
    df_24h    = pyupbit.get_ohlcv("KRW-ETH", count=24, interval="minute60")
    orderbook = pyupbit.get_orderbook("KRW-ETH")

    #====================================================================
    # 2. 컬럼명 변경(ta 호환) + dropna + 보조지표 추가
    #====================================================================
    #--- 일봉
    df_30d = df_30d.reset_index()  # 날짜 인덱스 -> 칼럼
    df_30d.rename(
        columns={
            'open':   'Open',
            'high':   'High',
            'low':    'Low',
            'close':  'Close',
            'volume': 'Volume'
        },
        inplace=True
    )
    df_30d.dropna(inplace=True)
    df_30d = add_indicators(df_30d)

    #--- 1시간봉
    df_24h = df_24h.reset_index()
    df_24h.rename(
        columns={
            'open':   'Open',
            'high':   'High',
            'low':    'Low',
            'close':  'Close',
            'volume': 'Volume'
        },
        inplace=True
    )

    df_24h.dropna(inplace=True)
    df_24h = add_indicators(df_24h)

    #====================================================================
    # 3-1. 공포·탐욕 지수 수집
    #====================================================================
    fng = get_fear_greed_index()

    #====================================================================
    # 3-2. 최신 이더리움 뉴스 헤드라인 수집
    #====================================================================
    eth_news_headlines = get_latest_eth_news_headlines()

    #====================================================================
    # 3-3. 차트 이미지 캡처 (내장 로직 직접 실행, base64 바로 활용)
    #====================================================================
    try:
        print("[Vision] 차트 이미지 캡처 및 인코딩 시작...")
        chart_image_base64, file_path = capture_full_page_screenshot_and_save_and_encode()
        if file_path:
            print(f"[Vision] 차트 이미지 캡처 완료: {file_path}")
        else:
            print("[Vision] 차트 이미지 캡처 실패")
    except Exception as e:
        print(f"[Vision] 차트 이미지 캡처 실패: {e}")
        chart_image_base64 = None

    #====================================================================
    # 3-4. 유튜브 자막 데이터 추출
    #====================================================================
    youtube_video_id = os.getenv("YOUTUBE_VIDEO_ID", "3XbtEX3jUv4")  # 기본값 예시
    youtube_transcript = get_combined_transcript(youtube_video_id)

    #====================================================================
    # 4. ChatGPT에게 전달할 데이터 준비 (JSON)
    #====================================================================
    # 최근 reflection 불러오기
    recent_trades = get_recent_trades_postgres(days=7)
    last_reflection = recent_trades.iloc[0]['reflection'] if not recent_trades.empty and 'reflection' in recent_trades.columns and recent_trades.iloc[0]['reflection'] else ""

    # 프롬프트에 추가 (reflection은 system_prompt에서 제거)
    system_prompt = (
        "You are an Ethereum trading expert with deep experience in technical analysis, on-chain metrics, and market sentiment.\n"
        "You will receive the following data encoded in JSON or as text fields.\n"
        "- 30-day OHLCV chart for ETH (Open, High, Low, Close, Volume)\n"
        "- 1-hour OHLCV chart for ETH\n"
        "- Current ETH orderbook snapshot\n"
        "- Account balances (e.g., KRW, ETH)\n"
        "- Fear & Greed Index { 'value': int, 'classification': string }\n"
        "- Latest Ethereum-related news headlines (list of title, snippet, source, date)\n"
        "- Estimated trading fees (in %) and maximum risk per trade (in % of account)\n"
        "- Chart image analysis (summary from OpenAI Vision API)\n"
        "- Recent YouTube transcript (investment-related, in Korean)\n"
        "- Recent self-reflection (your own trading review and improvement plan)\n"
        "\n"
        "IMPORTANT: The YouTube transcript provided below contains the trading method of '워뇨띠', a legendary Korean investor. You MUST always refer to the full transcript (in Korean) and incorporate Wonyotti's trading principles into your analysis and decision-making. If there is any conflict between technical indicators and Wonyotti's method, explain your reasoning clearly.\n"
        "\n"
        "Your task:\n"
        "1. Analyze technical indicators (e.g., MACD, RSI, Bollinger Bands) on both timeframes.\n"
        "2. Incorporate Fear & Greed Index as an additional risk-sentiment signal:\n"
        "   - Extreme Fear → consider contrarian buys  \n"
        "   - Extreme Greed → consider profit-taking or avoid new longs\n"
        "3. Consider the latest news headlines for any major events or sentiment that could affect ETH price (e.g., regulations, hacks, ETF news, etc).\n"
        "   - If no news is provided, ignore this factor and focus on other data.\n"
        "4. You MUST always refer to the provided YouTube transcript (Wonyotti's trading method, in Korean) and incorporate its principles into your analysis and trading decision. If there is any conflict between technical indicators and Wonyotti's method, explain your reasoning clearly.\n"
        "5. Calculate an optimal position size based on maximum risk per trade, and output the percentage (%) of available KRW to buy (if decision is 'buy'), or percentage (%) of available ETH to sell (if decision is 'sell'), as 'percentage'. For 'hold', set percentage to 0.\n"
        "6. Recommend stop-loss and take-profit levels if appropriate.\n"
        "7. Decide whether to BUY, SELL, or HOLD ETH at market.\n"
        "8. Assign a confidence score between 0.0 and 1.0.\n"
        "\n"
        "Respond in JSON format. The JSON must include: decision, percentage, reason, confidence, stop_loss, take_profit.\n"
        "Example:\n"
        '{"decision":"buy","percentage":50,"reason":"기술적 분석 결과 및 워뇨띠 매매법에 따라 매수 신호가 강함 (보유 KRW의 50% 매수)","confidence":0.85,"stop_loss":3200000,"take_profit":3600000}' "\n"
        '{"decision":"sell","percentage":100,"reason":"과매수 구간 진입 및 워뇨띠 매매법에 따라 매도 신호 (보유 ETH의 100% 매도)","confidence":0.9,"stop_loss":null,"take_profit":null}' "\n"
        '{"decision":"hold","percentage":0,"reason":"명확한 신호 없음 (매매 없음, 워뇨띠 매매법 참고)","confidence":0.6,"stop_loss":null,"take_profit":null}' "\n"
    )

    #====================================================================
    # 5. ChatGPT API 콜 (gpt-4o, etc.)
    #====================================================================
    client   = OpenAI()

    trade_schema = {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["buy", "sell", "hold"],
                "description": "매매 결정 (buy, sell, hold 중 하나)"
            },
            "percentage": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "매매에 투입할 비중(%)"
            },
            "reason": {
                "type": "string",
                "description": "매매 결정의 사유"
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "매매 결정에 대한 신뢰도 (0.0~1.0)"
            },
            "stop_loss": {
                "type": ["number", "null"],
                "description": "손절가 (없으면 null)"
            },
            "take_profit": {
                "type": ["number", "null"],
                "description": "익절가 (없으면 null)"
            }
        },
        "required": ["decision", "percentage", "reason", "confidence", "stop_loss", "take_profit"],
        "additionalProperties": False
    }

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Current investment status: {json.dumps(filtered_balance)}\n"
                            f"Orderbook: {json.dumps(orderbook)}\n"
                            f"Daily OHLCV with indicators (30 days): {df_30d.to_json()}\n"
                            f"Hourly OHLCV with indicators (24 hours): {df_24h.to_json()}\n"
                            f"Recent news headlines: {json.dumps(eth_news_headlines)}\n"
                            f"Fear and Greed Index: {json.dumps(fng)}\n"
                            f"Recent YouTube transcript (Wonyotti's trading method, in Korean):\n{youtube_transcript}\n"
                            f"Recent self-reflection: {last_reflection}"
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{chart_image_base64}"
                        }
                    }
                ]
            }
        ],
        max_tokens=4095, # JSON응답이 잘리는 경우를 대비 해 최대 토큰 수 증가
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "trade_decision", # json_schema에 명시된 이름이 무조건 들어가야 함
                "strict": True,
                "schema": trade_schema
            }
        }
    )

    # ChatGPT 응답
    gpt_result_str = response.choices[0].message.content

    #====================================================================
    # 6. ChatGPT 응답(JSON) 파싱 및 실제 매매 로직 (예외처리 보강)
    #====================================================================
    import re

    def save_failed_response(raw_content, filename_prefix="gpt_failed_response"):
        """
        GPT 응답이 JSON 파싱에 실패할 경우, 원문을 파일로 저장
        """
        import os
        from datetime import datetime
        dt = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{filename_prefix}_{dt}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(raw_content)
        print(f"[경고] GPT 응답 원문이 {fname}에 저장되었습니다.")

    gpt_result = None
    refusal_detected = False

    # 1. 응답이 JSON인지 확인 및 파싱
    try:
        # OpenAI의 structured output에서 거부(refusal) 메시지는 일반적으로 아래와 같이 올 수 있음
        # {"type": "refusal", "refusal": "I'm sorry, I cannot assist with that request."}
        # 또는 그냥 텍스트로 올 수도 있음
        if gpt_result_str.strip().startswith("{"):
            gpt_result = json.loads(gpt_result_str)
            # 거부 메시지 패턴 체크
            if (isinstance(gpt_result, dict) and
                (gpt_result.get("type") == "refusal" or "refusal" in gpt_result)):
                refusal_detected = True
        else:
            # JSON이 아닌 경우(거부 등)
            refusal_detected = True
    except Exception as e:
        print("[오류] GPT 응답이 JSON 형식이 아닙니다. 원문 저장 후 종료.")
        print("[원문]", gpt_result_str)
        save_failed_response(gpt_result_str)
        return

    if refusal_detected:
        print("[거부] GPT가 요청을 거부했습니다. 응답:")
        print(gpt_result_str)
        save_failed_response(gpt_result_str, filename_prefix="gpt_refusal")
        return

    # 2. 필수 필드 체크
    required_fields = ["decision", "percentage", "reason", "confidence", "stop_loss", "take_profit"]
    missing_fields = [f for f in required_fields if f not in gpt_result]
    if missing_fields:
        print(f"[오류] GPT 응답에 필수 필드가 누락됨: {missing_fields}")
        print("GPT 응답:", gpt_result)
        save_failed_response(gpt_result_str, filename_prefix="gpt_missing_fields")
        return

    # (매매 직전 잔고 재확인)
    my_krw = upbit.get_balance("KRW")
    my_eth = upbit.get_balance("KRW-ETH")

    decision = gpt_result["decision"]
    reason   = gpt_result["reason"]
    percentage = gpt_result["percentage"]

    print("### ChatGPT Decision:", decision.upper(), "###")
    print("### ChatGPT Reason:", reason, "###")
    print(f"### ChatGPT Percentage: {percentage}% ###")

    #====================================================================
    # 7. 매매 실행
    #====================================================================
    if decision == "buy":
        if my_krw > 5000:
            buy_amount = my_krw * (percentage / 100) * 0.9995  # 비율 반영 + 수수료 차감
            if buy_amount > 5000:
                print(f"=== Buy Order Executed: {buy_amount:.0f} KRW ===")
                buy_result = upbit.buy_market_order("KRW-ETH", buy_amount)
                print(buy_result)
            else:
                print("매수 금액이 5000원 미만입니다.")
        else:
            print("KRW 잔액 부족 (5000원 이상 필요)")

    elif decision == "sell":
        my_eth = upbit.get_balance("KRW-ETH")
        sell_amount = my_eth * (percentage / 100)
        orderbook = pyupbit.get_orderbook("KRW-ETH")
        if orderbook and isinstance(orderbook, dict) and 'orderbook_units' in orderbook:
            current_price = orderbook['orderbook_units'][0]['ask_price']
            if sell_amount * current_price > 5000:
                print(f"### Sell Order Executed: {percentage}% of held ETH ###")
                print(upbit.sell_market_order("KRW-ETH", sell_amount))
            else:
                print("### 매도 주문 실패: ETH 부족 (5000 KRW 미만) ###")
        else:
            print("오더북 데이터를 불러오지 못했습니다. 매매를 중단합니다.")

    else:
        print("=== Hold: No action taken ===")

    # 평균 매수단가, 현재 ETH 원화가
    eth_avg_buy_price = None
    eth_krw_price = None
    for item in all_balance:
        if item['currency'] == 'ETH':
            eth_avg_buy_price = float(item.get('avg_buy_price', 0))
            break
    # 현재 ETH 시세
    orderbook_now = pyupbit.get_orderbook("KRW-ETH")
    if orderbook_now and isinstance(orderbook_now, dict) and 'orderbook_units' in orderbook_now:
        eth_krw_price = orderbook_now['orderbook_units'][0]['ask_price']

    # === reflection 생성 ===
    recent_trades = get_recent_trades_postgres(days=7)
    # 날짜 인덱스를 문자열로 변환
    df_30d_tail = df_30d.tail(5).reset_index()
    df_30d_tail['index'] = df_30d_tail['index'].astype(str)
    df_24h_tail = df_24h.tail(5).reset_index()
    df_24h_tail['index'] = df_24h_tail['index'].astype(str)

    current_market_data = {
        "fear_greed_index": fng,
        "news_headlines": eth_news_headlines,
        "orderbook": orderbook,
        "daily_ohlcv": df_30d_tail.to_dict(),
        "hourly_ohlcv": df_24h_tail.to_dict()
    }
    reflection = generate_reflection(recent_trades, json.dumps(current_market_data, default=str))

    # DB 저장 (매매 실행 후, 잔고/가격 등과 함께 기록, reflection 포함)
    # 1. reflection 없이 매매 기록 저장
    log_trade_postgres(
        decision,
        percentage,
        reason,
        my_eth,      # eth_balance
        my_krw,      # krw_balance
        eth_avg_buy_price,
        eth_krw_price
    )
    # 2. reflection 생성 후, 직전 매매 레코드에 reflection만 업데이트
    update_last_trade_reflection(reflection)

########################################################
# 6) 주기 실행
########################################################
if __name__ == "__main__":
    while True:
        ai_trading()
        time.sleep(3600)  # 1시간 간격
