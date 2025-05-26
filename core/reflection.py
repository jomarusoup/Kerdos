from openai import OpenAI
from .db import calculate_performance

# 트레이드 데이터와 현재 시장 데이터를 바탕으로 AI에게 반성문을 생성하도록 요청하는 함수
def generate_reflection(trades_df, current_market_data):
    # 최근 10건만 사용
    if len(trades_df) > 10:
        trades_df = trades_df.head(10)
    # 최근 7일간의 트레이드 성과를 계산
    performance = calculate_performance(trades_df)
    # 트레이드 데이터에 'reflection' 컬럼이 있고 비어있지 않으면 마지막 반성문을 가져옴, 없으면 빈 문자열
    last_reflection = trades_df.iloc[0]['reflection'] if not trades_df.empty and 'reflection' in trades_df.columns and trades_df.iloc[0]['reflection'] else ""
    # OpenAI 클라이언트 생성
    client = OpenAI()
    # GPT-4o 모델에 대화형 프롬프트로 반성문 생성 요청
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                # 시스템 프롬프트: AI의 역할과 목표 설명
                "content": (
                    "You are an autonomous crypto trading AI that learns from its own mistakes and successes. "
                    "Your goal is to become a better trader by reflecting on your recent trades, market conditions, and your previous self-reflection. "
                    "Be honest and critical. Focus on actionable lessons and practical improvements."
                )
            },
            {
                "role": "user",
                # 사용자 프롬프트: 최근 트레이드 데이터, 시장 데이터, 성과, 이전 반성문 등 전달
                "content": f"""
Recent trading data:
{trades_df.to_json(orient='records')}

Current market data:
{current_market_data}

Overall performance in the last 7 days: {performance:.2f}%

Previous reflection:
{last_reflection}

Please analyze this data and provide a structured reflection with the following sections:
1. **Reflection:** Briefly summarize your overall trading performance and decision quality.
2. **What worked well:** List specific strategies or decisions that were effective.
3. **What didn't work:** Identify mistakes, missed opportunities, or poor decisions.
4. **Actionable improvement:** Clearly state what you will do differently in your next trades.
5. **Market pattern/trend:** Note any patterns or trends you observe in the market data.

Be concise and practical. Limit your response to 200 words or less.
"""
            }
        ]
    )
    # AI가 생성한 반성문 텍스트 반환
    return response.choices[0].message.content