import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. 설정 및 가상 데이터 생성 (실제 API 연결 전 시뮬레이션용)
st.set_page_config(page_title="Silver Race 150", layout="wide")
st.title("🏆 글로벌 은(Silver) 가격 150인 경주: 상위 5선 전략")

@st.cache_data
def generate_silver_data():
    """글로벌 은 가격 10분봉 가상 데이터 생성"""
    np.random.seed(42)
    times = pd.date_range(start="2026-05-01", periods=200, freq='10T')
    prices = 85 + np.cumsum(np.random.normal(0, 0.5, size=200)) # 85달러 기준 파동
    return pd.DataFrame({'Time': times, 'Price': prices})

# 2. 150명의 선수(전략) 로직 엔진
def run_150_agents(df):
    agents_results = []
    price_array = df['Price'].values
    
    for i in range(1, 151):
        # 각 선수마다 고유한 성격(변수) 부여
        window = np.random.randint(5, 30)  # 이격도 기준 기간
        threshold = np.random.uniform(0.001, 0.005) # 베팅 민감도
        
        # 전략: 가격이 이동평균선보다 높으면 빨강(콜), 낮으면 파랑(풋)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        # 수익률 계산
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns
        equity_curve = np.cumprod(1 + strategy_returns)
        
        current_color = "🔴 매수(콜)" if signals[-1] == 1 else ("🔵 매도(풋)" if signals[-1] == -1 else "⚪ 관망")
        
        agents_results.append({
            'id': f"{i}호 선수",
            'equity': equity_curve,
            'final_return': equity_curve[-1],
            'current_color': current_color,
            'color_code': 'red' if signals[-1] == 1 else 'blue' if signals[-1] == -1 else 'gray'
        })
    
    # 수익률 기준 내림차순 정렬
    return sorted(agents_results, key=lambda x: x['final_return'], reverse=True)

# 데이터 로드 및 실행
df = generate_silver_data()
top_agents = run_150_agents(df)

# 3. 대시보드 시각화
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("📊 상위 5개 전략 수익 곡선 (10분봉)")
    fig = go.Figure()
    for agent in top_agents[:5]:
        fig.add_trace(go.Scatter(
            x=df['Time'][1:], 
            y=agent['equity'], 
            name=f"{agent['id']} ({agent['current_color']})",
            mode='lines'
        ))
    fig.update_layout(hovermode="x unified", template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🥇 현재 순위 및 색깔")
    for i, agent in enumerate(top_agents[:5]):
        st.metric(label=f"{i+1}위: {agent['id']}", 
                  value=f"{agent['final_return']:.4f}", 
                  delta=agent['current_color'],
                  delta_color="normal" if agent['color_code'] != 'gray' else "off")
        st.write("---")

# 4. 하위권 쓰레기 처리 및 분석
st.sidebar.header("🔍 지휘자 대시보드")
st.sidebar.write(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.info(f"총 참여 선수: 150명")
st.sidebar.warning(f"수익률 마이너스 선수: {len([a for a in top_agents if a['final_return'] < 1.0])}명 (쓰레기 처리 중)")

if st.sidebar.button("데이터 새로고침"):
    st.rerun()
