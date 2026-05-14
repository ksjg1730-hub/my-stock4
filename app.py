import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Long-Only Race", layout="wide")
st.title("🏆 은(Silver) 6개월 경주: 매수(Call) & 청산(Wait) 전용")

# 2. 데이터 수집 (6개월치, 1시간봉)
@st.cache_data(ttl=3600)
def get_silver_data_6mo_long():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="6mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        df = df[df['Time'].dt.weekday < 5].copy() # 주말 제거
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 매수-청산 전용 엔진 (매도 수익 제외)
def run_long_only_engine(df):
    price_array = df['Price'].values
    agents = []
    
    for i in range(1, 151):
        # 20년 전 가격의 비밀: 보수적인 이평선 필터
        window = np.random.randint(20, 60)
        threshold = np.random.uniform(0.0005, 0.002)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        
        # 신호 로직: 매수(1) 또는 관망/청산(0). 매도(-1)는 절대 없음.
        signals = np.where(price_array > ma * (1 + threshold), 1, 0)
        
        returns = np.diff(price_array) / price_array[:-1]
        
        # 수익률 계산: 매수 신호(1)일 때만 수익/손실 발생, 청산(0)일 때는 0.
        strategy_returns = signals[:-1] * returns * 2 # 레버리지 2배
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'signals': signals,
            'final': cum_returns[-1]
        })
    return sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 4. 구간별 선 그리기 (빨강: 매수 중 / 회색: 청산 중)
def add_long_only_trace(fig, time, equity, signals, name):
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        # 매수 중이면 레드, 청산 중이면 회색
        color = "#FF0000" if curr_sig == 1 else "#555555"
        
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=3 if curr_sig == 1 else 1.5),
            hoverinfo='none',
            showlegend=True if start_idx == 0 else False,
            name=f"{name} ({'BUYING' if curr_sig==1 else 'CASH'})",
            legendgroup=name
        ))
        start_idx = end_idx

# 실행
df = get_silver_data_6mo_long()
if df is not None:
    top_3 = run_long_only_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 매수-청산 전략 수익률 (Long-Only)")
        fig = go.Figure()
        
        for agent in top_3:
            add_long_only_trace(fig, df['Time'].values, agent['equity'], agent['signals'], agent['id'])
        
        fig.update_layout(
            template="plotly_dark",
            yaxis_title="누적 수익률 (%)",
            plot_bgcolor='black',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 매수형 TOP 3")
        for i, agent in enumerate(top_3):
            last_sig = agent['signals'][-1]
            status = "🔴 매수 중" if last_sig == 1 else "⚪ 청산/대기"
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=status)
            st.write("---")
