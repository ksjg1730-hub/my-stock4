import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 6Mo Long-Only", layout="wide")
st.title("🏆 은(Silver) 6개월 경주: 매수-청산(Long-Only) 성배 찾기")

# 2. 6개월 데이터 수집 및 주말 제거
@st.cache_data(ttl=3600)
def get_silver_6mo_data():
    try:
        silver = yf.Ticker("SI=F")
        # 6개월(6mo) 데이터를 1시간(1h) 단위로 수집
        df = silver.history(period="6mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 데이터 제거 (평일만 남김)
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return None

# 3. 매수-청산 전용 엔진 (6개월 누적)
def run_6mo_long_engine(df):
    price_array = df['Price'].values
    agents = []
    
    for i in range(1, 151):
        # 6개월 호흡에 맞는 이평선 및 임계값 설정
        window = np.random.randint(20, 70)
        threshold = np.random.uniform(0.0005, 0.0025)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        
        # 신호: 매수(1) 또는 청산(0). 매도 수익은 없음.
        signals = np.where(price_array > ma * (1 + threshold), 1, 0)
        
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2 # 레버리지 2배 적용
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'signals': signals,
            'final': cum_returns[-1]
        })
    # 6개월 최종 수익률 상위 3인 선발
    return sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 4. 구간별 선 그리기 (레드: 매수 중 / 그레이: 청산/대기 중)
def draw_long_segments(fig, time, equity, signals, name):
    # 신호가 바뀌는 지점 계산
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else "#555555"
        width = 3.5 if curr_sig == 1 else 1.2
        
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=width),
            hoverinfo='none',
            showlegend=True if start_idx == 0 else False,
            name=f"{name} ({'BUYING' if curr_sig==1 else 'CASH'})",
            legendgroup=name
        ))
        start_idx = end_idx

# 메인 실행 로직
df = get_silver_6mo_data()
if df is not None:
    top_3 = run_6mo_long_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📊 6개월 누적 수익률 추이 (현재가: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        
        # 월별 수직 구분선
        month_starts = df[df['Time'].dt.day == 1]
        for m_time in month_starts['Time']:
            fig.add_vline(x=m_time, line_width=1, line_dash="dash", line_color="#aaaaaa", opacity=0.3)

        for agent in top_3:
            draw_long_segments(fig, df['Time'].values, agent['equity'], agent['signals'], agent['id'])
        
        fig.update_layout(
            template="plotly_dark",
            yaxis_title="누적 수익률 (%)",
            plot_bgcolor='black',
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 6개월 TOP 3")
        for i, agent in enumerate(top_3):
            last_sig = agent['signals'][-1]
            status = "🔴 매수 중" if last_sig == 1 else "⚪ 청산/대기"
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=status)
            st.write("---")

    st.sidebar.info("💡 빨간색 구간에서만 수익/손실이 발생하며, 회색 구간은 현금을 보유하고 대기하는 상태입니다.")
