import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

# 10초(10000ms)마다 자동 새로고침
st.experimental_rerun()  # 이건 무한루프가 되니 아래처럼 사용해야 함

from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=10 * 1000, key="datarefresh")

# 환경변수 로드
def get_db_conn():
    load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv("PG_DBNAME"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432")
    )

def load_eth_auto_trad(limit=100):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM eth_auto_trad ORDER BY time DESC LIMIT %s", (limit,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=columns)
    return df

st.set_page_config(page_title="ETH Auto Trading Log", layout="wide")
st.title("ETH Auto Trading Log")

def format_expander_title(row):
    # 날짜 포맷
    try:
        dt = pd.to_datetime(row['time'])
        date_str = dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        date_str = str(row['time'])
    # 결정 한글 변환
    decision_map = {'sell': '매도', 'buy': '매수', 'hold': '홀드'}
    decision = row.get('decision', '')
    decision_kr = decision_map.get(str(decision).lower(), str(decision))
    # 비중
    percent = row.get('percentage', '')
    try:
        percent_str = f"{float(percent):.0f}%"
    except Exception:
        percent_str = str(percent)
    return f"{date_str} | {decision_kr} | {percent_str}"

try:
    df = load_eth_auto_trad(100)

    # 상세 내용(expander) 맨 위로
    def clean_md(text):
        # 앞뒤의 **, *, 공백, 줄바꿈, 각 줄 맨 앞 숫자+점+공백 제거
        import re
        if not isinstance(text, str):
            return text
        cleaned = re.sub(r'^[*\s]*|[*\s]*$', '', text.strip())
        # 각 줄의 맨 앞 숫자+점+공백 제거
        cleaned = re.sub(r'^\d+\.\s*', '', cleaned, flags=re.MULTILINE)
        return cleaned

    for idx, row in df.iterrows():
        with st.expander(format_expander_title(row)):
            # Reason
            if "reason" in row:
                st.markdown("#### 📊 Reason")
                st.markdown(f"> {row['reason']}")
                st.markdown("---")
            # Reflection (구조화된 구분)
            if "reflection" in row and row['reflection']:
                st.markdown("#### 💡 Reflection")
                import re
                reflection = row['reflection']
                section_titles = [
                    ("Reflection", ["Reflection", "회고"]),
                    ("What worked well", ["What worked well", "잘된 점"]),
                    ("What didn't work", ["What didn't work", "아쉬운 점"]),
                    ("Actionable improvement", ["Actionable improvement", "개선 방안"]),
                    ("Market pattern/trend", ["Market pattern/trend", "시장 패턴", "시장 트렌드"]),
                ]
                found_sections = {}
                for i, (eng_title, aliases) in enumerate(section_titles):
                    next_aliases = []
                    for j in range(i+1, len(section_titles)):
                        next_aliases += section_titles[j][1]
                    # 숫자+점+공백 허용 (예: '1. Reflection:')
                    this_pat = r"(?:\d+\.\s*)?(?:" + "|".join([re.escape(a) for a in aliases]) + r")\s*:\s*([\s\S]*?)"
                    if next_aliases:
                        next_pat = r"(?:(?:\d+\.\s*)?(?:" + "|".join([re.escape(a) for a in next_aliases]) + r")\s*:|$)"
                    else:
                        next_pat = r"$"
                    pat = this_pat + next_pat
                    m = re.search(pat, reflection, re.IGNORECASE)
                    if m:
                        found_sections[eng_title] = clean_md(m.group(1))
                for eng_title, _ in section_titles:
                    if eng_title in found_sections:
                        st.markdown(f"**{eng_title}**")
                        st.markdown(f"> {found_sections[eng_title]}")
                st.markdown("---")
            # 잔고/가격
            st.markdown("#### 💰 잔고 및 가격 정보")
            def fmt(val, unit=None):
                try:
                    if val is None or pd.isna(val):
                        return "-"
                    fval = float(val)
                    if unit == 'ETH':
                        return f"{fval:,.6f} ETH"
                    elif unit == 'KRW':
                        return f"{fval:,.0f} KRW"
                    else:
                        return f"{fval:,.0f}"
                except Exception:
                    return str(val)
            balance_rows = [
                ["ETH 잔고", fmt(row['eth_balance'], 'ETH')],
                ["KRW 잔고", fmt(row['krw_balance'], 'KRW')],
                ["ETH 평균매수가", fmt(row['eth_avg_buy_price'], 'KRW')],
                ["ETH 현재가", fmt(row['eth_krw_price'], 'KRW')],
            ]
            st.table(pd.DataFrame(balance_rows, columns=["항목", "값"]).set_index("항목"))
            # 기타 정보
            for col in ["confidence", "stop_loss", "take_profit"]:
                if col in row:
                    st.markdown(f"- **{col}:** {row[col]}")

    # 표는 맨 아래로
    main_cols = [
        "time", "decision", "percentage", "eth_balance", "krw_balance", "eth_avg_buy_price", "eth_krw_price"
    ]
    if "reason" in df.columns:
        df["reason_short"] = df["reason"].astype(str).str.slice(0, 30) + "..."
        main_cols.append("reason_short")
    if "reflection" in df.columns:
        df["reflection_short"] = df["reflection"].astype(str).str.slice(0, 30) + "..."
        main_cols.append("reflection_short")
    for col in ["confidence", "stop_loss", "take_profit"]:
        if col in df.columns:
            main_cols.append(col)
    st.dataframe(df[main_cols], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"DB에서 데이터를 불러오는 중 오류 발생: {e}")
