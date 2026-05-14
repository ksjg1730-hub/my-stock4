import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 6Mo Backtest", layout="wide")
st.title("🏆 은(Silver) 6개월 백테스트: TOP 3 성배 궤적")

# 2. 6개월 데이터 수집 및 주말 제거
@st.cache_data(ttl=3600) # 데이터가 많으므로 1시간 동안 캐시 유지
def get_silver_data_6mo():
    try:
        silver = yf.Ticker("SI=F")
        # 6개월(6mo) 데이터를 1시간(1h) 단위로 수집
        df = silver.history(period="6mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        
        # 주말 데이터 제거
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return None

# 3. 구간별 선 그리기를 위한 세그먼트 함수
def add_colored_trace(fig, time, equity, signals, name):
    # 성능 최적화를 위해 신호가 바뀌는 지점만 계산하여 선을 끊어 그림
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else ("#00FF00" if curr_sig == -1 else "#808080")
        
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=2),
            hoverinfo='none',
            showlegend=True if start_idx == 0 else False,
            name=f"{name} ({'CALL' if curr_sig==1 else 'PUT' if curr_sig==-1 else 'WAIT'})",
            legendgroup=name
        ))
        start_idx = end_idx

# 4. 전략 엔진 (6개월 누적 수익률 계산)
def run_6mo_engine(df):
    price_array = df['Price'].values
    agents = []
    
    # 지휘자님의 '가격의 비밀' 로직 적용
    for i in range(1, 151):
        window = np.random.randint(20, 60) # 6개월 데이터에 맞게 조금 더 긴 호흡
        threshold = np.random.uniform(0.0005, 0.002)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2 # 레버리지 2배 적용
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'signals': signals,
            'final': cum_returns[-1]
        })
    return sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 실행
df = get_silver_data_6mo()
if df is not None:
    top_3 = run_6mo_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📊 6개월 누적 수익률 (현재가: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        
        # 월간 구분선 (월초 기준)
        month_starts = df[df['Time'].dt.day == 1]
        for m_time in month_starts['Time']:
            fig.add_vline(x=m_time, line_width=1, line_dash="dash", line_color="white", opacity=0.3)

        for agent in top_3:
            add_colored_trace(fig, df['Time'].values, agent['equity'], agent['signals'], agent['id'])
        
        fig.update_layout(
            template="plotly_dark",
            yaxis_title="누적 수익률 (%)",
            plot_bgcolor='black',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 6개월 챔피언")
        for i, agent in enumerate(top_3):
            last_sig = agent['signals'][-1]
            status = "🔴 CALL" if last_sig == 1 else ("🟢 PUT" if last_sig == -1 else "⚪ WAIT")
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=status)
            st.write("---")
