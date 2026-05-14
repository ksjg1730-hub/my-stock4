import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Silver Race 150", layout="wide")
st.title("🏆 글로벌 은(Silver) 가격 150인 경주: 상위 5선 전략")

# 2. 데이터 생성 함수 (오류 수정 완료)
@st.cache_data
def generate_silver_data():
    """글로벌 은 가격 10분봉 가상 데이터 생성"""
    np.random.seed(42)
    # 최신 Pandas 버전 호환용 '10min' 설정
    times = pd.date_range(start="2026-05-01", periods=200, freq='10min')
    
    # 최근의 하락 변동성을 반영한 가상 가격 흐름
    prices = 90 + np.cumsum(np.random.normal(-0.1, 0.6, size=200)) 
    return pd.DataFrame({'Time': times, 'Price': prices})

# 3. 150명의 선수 엔진
def run_150_agents(df):
    agents_results = []
    price_array = df['Price'].values
    
    for i in range(1, 151):
        window = np.random.randint(5, 40)
        threshold = np.random.uniform(0.0005, 0.003)
        
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2  # 레버리지 2배
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

# 실행 로직
try:
    df = generate_silver_data()
    top_agents = run_150_agents(df)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📊 실시간 은 시세 (현재가: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        for agent in top_agents[:5]:
            fig.add_trace(go.Scatter(x=df['Time'][1:], y=agent['equity'], name=f"{agent['id']}"))
        fig.update_layout(hovermode="x unified", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 Top 5 순위")
        for i, agent in enumerate(top_agents[:5]):
            profit_pct = (agent['final_return'] - 1) * 100
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final_return']:.4f}", delta=f"{agent['current_color']} ({profit_pct:+.2f}%)")
            st.write("---")

except Exception as e:
    st.error(f"오류 발생: {e}")
