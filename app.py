import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Weekly Long-Only", layout="wide")
st.title("🏆 실시간 은(Silver) 주간 경주: 매수-청산 전략")

# 2. 실시간 데이터 수집 (최근 1주일 집중)
@st.cache_data(ttl=300) # 5분마다 갱신
def get_silver_weekly_data():
    try:
        silver = yf.Ticker("SI=F")
        # 정밀한 분석을 위해 15분봉 데이터 수집 (최근 5일치)
        df = silver.history(period="5d", interval="15m")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 데이터 제외
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return None

# 3. 주간 리셋 엔진 (금요일 01:00 기준 0% 시작)
def run_weekly_long_engine(df):
    now = df['Time'].iloc[-1]
    # 이번 주 금요일 01:00 (또는 지난주 금요일 01:00) 기준점 계산
    last_friday = now - timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 1:
        last_friday -= timedelta(days=7)
    ref_time = last_friday.replace(hour=1, minute=0, second=0, microsecond=0)
    
    # 기준점 이후 데이터만 필터링
    weekly_df = df[df['Time'] >= ref_time].copy()
    if len(weekly_df) < 2:
        weekly_df = df.tail(50).copy() # 데이터 부족 시 최근 50개 캔들 사용
        
    price_array = weekly_df['Price'].values
    agents = []
    
    for i in range(1, 151):
        # 15분봉에 최적화된 짧은 호흡의 변수들
        window = np.random.randint(10, 40)
        threshold = np.random.uniform(0.0002, 0.0008)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        
        # 매수(1) 또는 청산(0) 신호
        signals = np.where(price_array > ma * (1 + threshold), 1, 0)
        
        returns = np.diff(price_array) / price_array[:-1]
        # 레버리지 2배 적용
        strategy_returns = signals[:-1] * returns * 2
        # 금요일 1시를 0%로 하여 누적 수익률 계산
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'signals': signals,
            'final': cum_returns[-1]
        })
    # 현재 시점 주간 수익률 상위 3인
    return weekly_df, sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 4. 구간별 선 그리기 (레드: 매수 / 회색: 청산)
def draw_colored_path(fig, time, equity, signals, name):
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else "#555555"
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=4 if curr_sig == 1 else 1.5),
            showlegend=True if start_idx == 0 else False,
            name=f"{name} ({'BUY' if curr_sig==1 else 'CASH'})",
            legendgroup=name
        ))
        start_idx = end_idx

# 실행
df = get_silver_weekly_data()
if df is not None:
    weekly_df, top_3 = run_weekly_long_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📅 주간 누적 수익률 (기준: {weekly_df['Time'].iloc[0].strftime('%m/%d %H:%M')})")
        fig = go.Figure()
        
        # 월요일 개장 수직선 (08:00)
        mon_open = weekly_df[weekly_df['Time'].dt.weekday == 0]
        if not mon_open.empty:
            fig.add_vline(x=mon_open['Time'].iloc[0], line_width=2, line_dash="dash", line_color="yellow")

        for agent in top_3:
            draw_colored_path(fig, weekly_df['Time'].values, agent['equity'], agent['signals'], agent['id'])
        
        fig.update_layout(
            template="plotly_dark",
            yaxis_title="수익률 (%)",
            plot_bgcolor='black',
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 주간 TOP 3")
        for i, agent in enumerate(top_3):
            last_sig = agent['signals'][-1]
            status = "🔴 매수 중" if last_sig == 1 else "⚪ 현금 관망"
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=status)
            st.write("---")
            
    st.sidebar.write(f"현재가: ${weekly_df['Price'].iloc[-1]:.2f}")
    st.sidebar.caption("5분마다 자동 갱신됩니다.")
