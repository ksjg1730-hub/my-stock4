import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Race 150", layout="wide")
st.title("🏆 글로벌 은(Silver) 가격 150인 경주: 상위 5선 전략")

# 2. 실제 데이터 수집 함수 (최근 1개월 + 실시간)
@st.cache_data(ttl=600) # 10분마다 데이터 갱신
def get_real_silver_data():
    """야후 파이낸스에서 실시간 은 선물 가격 수집"""
    try:
        # 은 선물(SI=F) 데이터 가져오기
        silver = yf.Ticker("SI=F")
        # 과거 1개월간의 30분봉 데이터 (가장 안정적인 단위)
        df = silver.history(period="1mo", interval="30m")
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return None

# 3. 150명의 선수 엔진 (사용자님의 '가격의 비밀' 로직)
def run_150_agents(df):
    agents_results = []
    price_array = df['Price'].values
    
    for i in range(1, 151):
        # 각 선수마다 고유한 기술적 변수 부여
        window = np.random.randint(10, 60) # 이평선 기간
        threshold = np.random.uniform(0.0005, 0.002) # 민감도
        
        # 전략: 가격과 이평선 비교
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        # 수익률 계산 (레버리지 2배 반영)
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2
        equity_curve = np.cumprod(1 + strategy_returns)
        
        last_sig = signals[-1]
        current_color = "🔴 매수" if last_sig == 1 else ("🔵 매도" if last_sig == -1 else "⚪ 관망")
        
        agents_results.append({
            'id': f"{i}호 선수",
            'equity': equity_curve,
            'final_return': equity_curve[-1],
            'current_color': current_color,
            'color_code': 'red' if last_sig == 1 else 'blue' if last_sig == -1 else 'gray'
        })
    
    return sorted(agents_results, key=lambda x: x['final_return'], reverse=True)

# 실행 및 시각화
df = get_real_silver_data()

if df is not None:
    top_agents = run_150_agents(df)
    current_price = df['Price'].iloc[-1]

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📊 실시간 은 시세 (현재: ${current_price:.2f})")
        fig = go.Figure()
        
        # 상위 5선 그래프
        for agent in top_agents[:5]:
            fig.add_trace(go.Scatter(
                x=df['Time'][1:], 
                y=agent['equity'], 
                name=f"{agent['id']} ({agent['current_color']})",
                line=dict(width=2)
            ))
        
        fig.update_layout(
            hovermode="x unified", 
            template="plotly_dark",
            xaxis_title="최근 1개월 흐름",
            yaxis_title="전략 수익률 (1.0 기준)"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 현재 순위 (Top 5)")
        for i, agent in enumerate(top_agents[:5]):
            profit_pct = (agent['final_return'] - 1) * 100
            st.metric(
                label=f"{i+1}위: {agent['id']}", 
                value=f"{agent['final_return']:.4f}", 
                delta=f"{agent['current_color']} ({profit_pct:+.2f}%)"
            )
            st.write("---")
            
    st.sidebar.write(f"최종 업데이트: {df['Time'].iloc[-1].strftime('%Y-%m-%d %H:%M')}")
