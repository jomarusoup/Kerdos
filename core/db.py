import os
import psycopg2
import pandas as pd
from datetime import datetime, timedelta

########################################################
# 1) Postgres 테이블 초기화 함수
########################################################
def init_postgres_table():
    """
    eth_auto_trad 테이블이 없으면 생성한다.
    (매매 기록, 회고 등 저장용)
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
                    id SERIAL PRIMARY KEY,                -- 고유 ID (자동 증가)
                    time TIMESTAMP NOT NULL,              -- 기록 시각
                    decision VARCHAR(10),                 -- 매매 결정 (buy/sell/hold)
                    percentage NUMERIC,                   -- 매매 비중 (%)
                    reason TEXT,                          -- 매매 사유
                    eth_balance NUMERIC,                  -- ETH 잔고
                    krw_balance NUMERIC,                  -- KRW 잔고
                    eth_avg_buy_price NUMERIC,            -- ETH 평균 매수단가
                    eth_krw_price NUMERIC,                -- ETH 현재가
                    reflection TEXT                       -- 회고(리플렉션) 텍스트
                );
            ''')
            conn.commit()

########################################################
# 2) 매매 기록 저장 함수
def log_trade_postgres(decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price, reflection=None):
    """
    매매 결과를 eth_auto_trad 테이블에 저장한다.
    - reflection: 회고 텍스트(선택)
    """
    # reflection에 NUL 문자 제거 및 문자열 변환
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
            now = datetime.now()  # 현재 시각
            if reflection is not None:
                # 회고 포함 저장
                cur.execute('''
                    INSERT INTO eth_auto_trad
                    (time, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price, reflection)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (now, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price, reflection))
            else:
                # 회고 없이 저장
                cur.execute('''
                    INSERT INTO eth_auto_trad
                    (time, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (now, decision, percentage, reason, eth_balance, krw_balance, eth_avg_buy_price, eth_krw_price))
            conn.commit()

########################################################
# 3) 최근 매매 내역 조회 함수
########################################################
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
            since = datetime.now() - timedelta(days=days)  # 조회 시작 시각
            cur.execute("SELECT * FROM eth_auto_trad WHERE time > %s ORDER BY time DESC", (since,))
            columns = [desc[0] for desc in cur.description]  # 컬럼명 추출
            rows = cur.fetchall()                            # 데이터 추출
            df = pd.DataFrame(rows, columns=columns)         # DataFrame 변환
    return df

########################################################
# 4) 매매 성과(수익률) 계산 함수
########################################################
def calculate_performance(trades_df):
    """
    trades_df: 매매 내역 DataFrame
    - 초기 자산 대비 마지막 자산의 수익률(%) 반환
    - 자산 = KRW 잔고 + ETH 잔고 * ETH 현재가
    """
    if trades_df.empty:
        return 0
    # 초기(가장 오래된) 자산
    initial_balance = trades_df.iloc[-1]['krw_balance'] + trades_df.iloc[-1]['eth_balance'] * trades_df.iloc[-1]['eth_krw_price']
    # 마지막(가장 최근) 자산
    final_balance = trades_df.iloc[0]['krw_balance'] + trades_df.iloc[0]['eth_balance'] * trades_df.iloc[0]['eth_krw_price']
    # 수익률(%) 계산
    return (final_balance - initial_balance) / initial_balance * 100

########################################################
# 5) 직전 매매 레코드의 reflection만 업데이트하는 함수
########################################################
def update_last_trade_reflection(reflection):
    """
    eth_auto_trad 테이블에서 가장 최근(최신) 레코드의 reflection 컬럼만 업데이트한다.
    """
    # reflection에 NUL 문자 제거 및 문자열 변환
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
            cur.execute(
                """
                UPDATE eth_auto_trad
                SET reflection = %s
                WHERE id = (
                    SELECT id FROM eth_auto_trad ORDER BY time DESC LIMIT 1
                )
                """,
                (reflection,)
            )
            conn.commit()