import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Gold Long-Only Race", layout="wide")
st.title("🏆 글로벌 금(Gold) 6개월 경주: 매수 & 청산 전략")

# 2. 금 데이터 수집 (6개월치, 1시간봉)
@st.cache_data(ttl=3600)
def get_gold_data_6mo():
    try:
        # 금 선물 티커: GC=F
        gold = yf.Ticker("GC=F")
        df = gold.history(period="6mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 제거
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"금 데이터 연결 오류: {e}")
        return None

# 3. 매수-청산 전용 엔진 (금 시장 최적화)
def run_gold_engine(df):
    price_array = df['Price'].values
    agents = []
    
    for i in range(1, 151):
        # 금은 은보다 변동성이 낮으므로 윈도우와 임계값을 소폭 조정
        window = np.random.randint(15, 55)
        threshold = np.random.uniform(0.0003, 0.0012)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        
        # 신호: 매수(1) 또는 청산(0)
        signals = np.where(price_array > ma * (1 + threshold), 1, 0)
        
        returns = np.diff(price_array) / price_array[:-1]
        # 레버리지 2배 적용
        strategy_returns = signals[:-1] * returns * 2
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'signals': signals,
            'final': cum_returns[-1]
        })
    # 6개월 성과 기준 상위 3인
    return sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 4. 시각화 함수 (빨강: 매수 / 회색: 청산)
def add_gold_trace(fig, time, equity, signals, name):
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF4B4B" if curr_sig == 1 else "#666666" # 금 시장용 레드와 다크그레이
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=3 if curr_sig == 1 else 1.5),
            showlegend=True if start_idx == 0 else False,
            name=f"{name} ({'BUY' if curr_sig==1 else 'CASH'})",
            legendgroup=name
        ))
        start_idx = end_idx

# 실행 로직
df = get_gold_data_6mo()
if df is not None:
    top_3 = run_gold_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📊 금(Gold) 6개월 전략 수익률 (현재가: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        # 월간 구분선
        month_starts = df[df['Time'].dt.day == 1]
        for m_time in month_starts['Time']:
            fig.add_vline(x=m_time, line_width=1, line_dash="dash", line_color="gold", opacity=0.4)

        for agent in top_3:
            add_gold_trace(fig, df['Time'].values, agent['equity'], agent['signals'], agent['id'])
        
        fig.update_layout(
            template="plotly_dark",
            yaxis_title="누적 수익률 (%)",
            plot_bgcolor='#0E1117',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 금광 TOP 3")
        for i, agent in enumerate(top_3):
            last_sig = agent['signals'][-1]
            status = "🔴 매수 유지" if last_sig == 1 else "⚪ 현금 확보"
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=status)
            st.write("---")

    st.sidebar.warning("⚠️ 금(Gold) 전용 엔진 가동 중")
    st.sidebar.info("은(Silver)보다 변동성이 낮아 안정적인 우상향 곡선이 특징입니다.")
