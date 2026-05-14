import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Top 3 Race", layout="wide")
st.title("🏆 은(Silver) TOP 3 경주: 금요일 01:00 리셋")

# 2. 데이터 수집 및 주말 제거
@st.cache_data(ttl=600)
def get_cleaned_silver_data():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        
        # 주말 데이터 제거 (토요일 06시 ~ 월요일 07시 사이 제외)
        df['weekday'] = df['Time'].dt.weekday
        df['hour'] = df['Time'].dt.hour
        # 단순화를 위해 평일 데이터만 남김 (월~금)
        df = df[df['weekday'] < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 전략 엔진 (금요일 01:00 기준 초기화)
def run_top3_strategy(df):
    now = df['Time'].iloc[-1]
    last_friday = now - timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 1:
        last_friday -= timedelta(days=7)
    ref_time = last_friday.replace(hour=1, minute=0, second=0, microsecond=0)
    
    weekly_df = df[df['Time'] >= ref_time].copy()
    if len(weekly_df) < 2: weekly_df = df.tail(48).copy()
    
    price_array = weekly_df['Price'].values
    agents = []
    
    for i in range(1, 151):
        window = np.random.randint(10, 40)
        threshold = np.random.uniform(0.0004, 0.0012)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2 # 레버리지 2배
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        last_sig = signals[-1]
        # 콜이면 레드, 풋이면 그린, 관망이면 그레이
        color = "red" if last_sig == 1 else ("green" if last_sig == -1 else "gray")
        pos_text = "CALL" if last_sig == 1 else ("PUT" if last_sig == -1 else "WAIT")
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'final': cum_returns[-1],
            'color': color,
            'pos_text': pos_text
        })
    
    return weekly_df, sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 실행 및 시각화
df = get_cleaned_silver_data()
if df is not None:
    weekly_df, top_3 = run_top3_strategy(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📊 TOP 3 주간 수익률 (%) - 현재가: ${weekly_df['Price'].iloc[-1]:.2f}")
        fig = go.Figure()
        
        # 월요일 아침 08:00 수직선 추가 (개장 시점 구분)
        mondays = weekly_df[weekly_df['Time'].dt.weekday == 0]
        if not mondays.empty:
            mon_open = mondays['Time'].iloc[0].replace(hour=8, minute=0)
            fig.add_vline(x=mon_open, line_width=2, line_dash="dash", line_color="yellow", annotation_text="월요일 개장")

        for agent in top_3:
            fig.add_trace(go.Scatter(
                x=weekly_df['Time'], y=agent['equity'],
                name=f"{agent['id']} ({agent['pos_text']})",
                line=dict(color=agent['color'], width=3)
            ))
        
        fig.update_layout(hovermode="x unified", template="plotly_dark", yaxis_title="수익률 (%)", xaxis_title="한국 시간")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 TOP 3 현황")
        for i, agent in enumerate(top_3):
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=agent['pos_text'], delta_color="inverse" if agent['pos_text']=="PUT" else "normal")
            st.write("---")

    if st.sidebar.button("새로고침"):
        st.cache_data.clear()
        st.rerun()
