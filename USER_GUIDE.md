# Kerdos 사용자 가이드

이 가이드는 Kerdos 자동매매 시스템을 처음 설정하고 실행하는 전 과정을 단계별로 안내한다.

---

## 1. 사전 준비 — API 키 발급

### 1-1. OpenAI API 키

1. [https://platform.openai.com](https://platform.openai.com) 로그인
2. 우측 상단 프로필 → **API keys** → **Create new secret key**
3. 발급된 키 복사 후 안전한 곳에 저장 (재확인 불가)
4. **GPT-4o 모델 접근 권한** 및 결제 수단 등록 필요

### 1-2. 업비트 API 키

1. [https://upbit.com](https://upbit.com) 로그인 → 마이페이지 → **Open API 관리**
2. 허용 IP 주소에 서버 IP 추가
3. 권한: **자산 조회**, **주문 조회**, **주문하기** 체크
4. Access Key / Secret Key 복사

> **주의:** 주문하기 권한은 실제 매매가 실행됨. 테스트 시 소액으로 시작 권장.

### 1-3. SerpAPI 키 (뉴스 수집)

1. [https://serpapi.com](https://serpapi.com) 회원가입
2. 대시보드 → **API Key** 복사
3. 무료 플랜: 월 100회 제한 (초과 시 뉴스 수집 비활성화, 매매는 계속 동작)

### 1-4. PostgreSQL 설정

```bash
# PostgreSQL 설치 (Rocky Linux 9)
sudo dnf install -y postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl enable --now postgresql

# DB 및 사용자 생성
sudo -u postgres psql <<EOF
CREATE DATABASE kerdos_db;
CREATE USER kerdos_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE kerdos_db TO kerdos_user;
EOF
```

---

## 2. 프로젝트 설치

### 2-1. 저장소 클론

```bash
git clone <저장소_URL> ~/Kerdos
cd ~/Kerdos
```

### 2-2. Python 가상환경 생성 및 의존성 설치

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

> Python 3.9.23 기준으로 테스트됨.

### 2-3. Chrome / ChromeDriver 설치

Selenium이 업비트 차트를 캡처하기 위해 Chrome이 필요하다.

```bash
# Rocky Linux 9 기준
sudo dnf install -y google-chrome-stable

# 또는 Chromium
sudo dnf install -y chromium
```

`webdriver-manager`가 ChromeDriver를 자동으로 설치하므로 별도 설치는 불필요.

### 2-4. 환경변수 파일 생성

```bash
cp .env.example .env   # 예시 파일이 있는 경우
# 또는 직접 생성
vi ~/.env
```

`.env` 내용:

```env
OPENAI_API_KEY=sk-...
UPBIT_ACCESS_KEY=...
UPBIT_SECRET_KEY=...
SERPAPI_KEY=...
YOUTUBE_VIDEO_ID=3XbtEX3jUv4
PG_DBNAME=kerdos_db
PG_USER=kerdos_user
PG_PASSWORD=your_password
PG_HOST=localhost
PG_PORT=5432
```

---

## 3. 자동매매 실행

### 3-1. 수동 실행 (테스트)

```bash
cd ~/Kerdos
source venv/bin/activate
python3 autotrad.py
```

실행 시 다음 단계가 순서대로 진행된다:

```
1. PostgreSQL 테이블 초기화 (최초 1회)
2. 업비트 잔고 및 OHLCV 데이터 수집
3. 보조지표 계산 (볼린저밴드, RSI, MACD, SMA, EMA, 엔벨로프)
4. 업비트 차트 스크린샷 캡처 (약 10~20초 소요)
5. 공포탐욕지수 수집
6. ETH 뉴스 헤드라인 수집 (최대 5개)
7. 유튜브 자막 수집
8. GPT-4o에 데이터 전달 → 매매 결정 수신
9. 매수/매도/홀드 실행
10. 매매 기록 DB 저장
11. 이전 매매에 대한 회고 생성 및 저장
```

### 3-2. 주기적 자동 실행 (cron)

매 1시간마다 실행하는 예시:

```bash
crontab -e
```

```cron
0 * * * * cd /home/Kerdos/Kerdos && /home/Kerdos/Kerdos/venv/bin/python3 autotrad.py >> /home/Kerdos/Kerdos/trade.log 2>&1
```

### 3-3. 백그라운드 실행 (nohup)

```bash
nohup python3 autotrad.py >> trade.log 2>&1 &
echo $! > trade.pid   # 프로세스 ID 저장

# 종료
kill $(cat trade.pid)
```

---

## 4. Streamlit 대시보드 실행

```bash
cd ~/Kerdos
source venv/bin/activate
streamlit run streamlit_app.py --server.port 8501
```

브라우저에서 `http://서버IP:8501` 접속.

- 10초마다 자동 새로고침
- 최근 100건 매매 기록 표시
- 각 항목 클릭 시 매매 사유(Reason)·회고(Reflection)·잔고 상세 확인 가능

### 서버 방화벽 설정 (외부 접속 시)

```bash
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

---

## 5. 매매 결과 확인

### 5-1. DB 직접 조회

```bash
sudo -u postgres psql -d kerdos_db
```

```sql
-- 최근 10건 조회
SELECT time, decision, percentage, eth_krw_price, confidence
FROM eth_auto_trad
ORDER BY time DESC
LIMIT 10;

-- 수익률 확인 (최초 vs 현재 자산)
SELECT
    (krw_balance + eth_balance * eth_krw_price) AS total_asset
FROM eth_auto_trad
ORDER BY time DESC
LIMIT 1;
```

### 5-2. 로그 확인

```bash
tail -f trade.log
```

---

## 6. AI 판단 구조 이해

GPT-4o는 아래 데이터를 받아 JSON으로 응답한다.

| 입력 데이터 | 설명 |
|------------|------|
| 일봉 30일 OHLCV + 보조지표 | 중장기 추세 판단 |
| 1시간봉 24시간 OHLCV + 보조지표 | 단기 진입 타이밍 |
| 오더북 | 현재 호가 스프레드 |
| 공포탐욕지수 | 시장 심리 (0=극도공포, 100=극도탐욕) |
| ETH 뉴스 헤드라인 | 이벤트 리스크 |
| 업비트 차트 이미지 | 시각적 패턴 분석 (볼린저밴드 포함) |
| 유튜브 자막 | 워뇨띠 매매법 원칙 적용 |
| 이전 회고 | 과거 실수 반영 |

**AI 응답 형식:**

```json
{
  "decision": "buy",
  "percentage": 50,
  "reason": "RSI 과매도 + 볼린저밴드 하단 지지 + 극도공포 구간",
  "confidence": 0.82,
  "stop_loss": 3200000,
  "take_profit": 3800000
}
```

| 필드 | 설명 |
|------|------|
| decision | buy / sell / hold |
| percentage | 투입 비중 (buy: KRW 기준, sell: ETH 기준) |
| reason | 판단 근거 |
| confidence | 신뢰도 (0.0 ~ 1.0) |
| stop_loss | 손절가 (없으면 null) |
| take_profit | 익절가 (없으면 null) |

---

## 7. 주요 설정값

`autotrad.py` 내에서 직접 수정 가능한 값들:

| 위치 | 변수 | 기본값 | 설명 |
|------|------|--------|------|
| `add_indicators()` | `envelope_window` | 20 | 엔벨로프 기준 기간 |
| `add_indicators()` | `envelope_pct` | 0.02 (2%) | 엔벨로프 폭 |
| 매수 로직 | 최소 주문금액 | 5,000 KRW | 이 미만 시 주문 미실행 |
| 데이터 수집 | 일봉 수 | 30 | `get_ohlcv count=30` |
| 데이터 수집 | 시간봉 수 | 24 | `get_ohlcv count=24` |
| 회고 | 참조 기간 | 7일 | `get_recent_trades_postgres(days=7)` |

---

## 8. 트러블슈팅

### Chrome 실행 오류

```
Message: unknown error: cannot find Chrome binary
```

```bash
which google-chrome || which chromium-browser
# 경로 확인 후 setup_chrome_options()에 추가
chrome_options.binary_location = "/usr/bin/chromium-browser"
```

### PostgreSQL 연결 오류

```
psycopg2.OperationalError: could not connect to server
```

```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
# pg_hba.conf에서 로컬 접속 허용 확인
```

### SerpAPI 할당량 초과

뉴스 수집만 비활성화되며 매매는 정상 동작.  
`get_latest_eth_news_headlines()`가 빈 리스트 반환.

### GPT 응답 JSON 파싱 실패

`gpt_failed_response_YYYYMMDD_HHMMSS.txt` 파일로 원문 저장됨.  
해당 파일을 확인해 원인 분석.

---

## 9. 보안 주의사항

- `.env` 파일은 절대 git에 커밋하지 않는다 (`.gitignore`에 포함 확인)
- 업비트 API 키에 **출금 권한은 절대 부여하지 않는다**
- 서버 SSH 포트는 기본 22에서 변경 권장
- Streamlit 대시보드는 내부망 또는 VPN 환경에서만 노출 권장

---

## 10. MVP 모드 (단순 테스트)

`mvp.py`는 OHLCV 데이터만 사용하는 최소 버전이다.  
API 연동 테스트 시 활용.

```bash
python3 mvp.py
```
