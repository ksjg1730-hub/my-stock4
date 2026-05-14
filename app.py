import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Multi-Color Race", layout="wide")
st.title("🏆 은(Silver) TOP 3: 과거 시점별 포지션 컬러 (Red/Green) 반영")

# 2. 데이터 수집 (1개월치)
@st.cache_data(ttl=600)
def get_silver_data_1mo():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 제거
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 구간별 선 그리기를 위한 함수
def add_colored_trace(fig, time, equity, signals, name, show_legend=True):
    """포지션 변화에 따라 선의 색상을 잘라서 추가"""
    # 신호가 바뀌는 지점 찾기
    for j in range(len(signals) - 1):
        color = "#FF0000" if signals[j] == 1 else ("#00FF00" if signals[j] == -1 else "#808080")
        fig.add_trace(go.Scatter(
            x=time[j:j+2], 
            y=equity[j:j+2],
            mode='lines',
            line=dict(color=color, width=3),
            hoverinfo='none',
            showlegend=show_legend if j == 0 else False,
            name=name if j == 0 else None,
            legendgroup=name
        ))

# 4. 전략 엔진
def run_enhanced_engine(df):
    price_array = df['Price'].values
    agents = []
    
    for i in range(1, 151):
        window = np.random.randint(15, 45)
        threshold = np.random.uniform(0.0004, 0.0015)
        ma = pd.Series(price_array).rolling(window=window).mean().values
        # 시계열 전체 포지션 계산 (과거 시점 포함)
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'signals': signals,
            'final': cum_returns[-1]
        })
    return sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 실행
df = get_silver_data_1mo()
if df is not None:
    top_3 = run_enhanced_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📅 구간별 포지션 컬러 추적 (현재: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        
        # 월요일 구분선
        monday_opens = df[(df['Time'].dt.weekday == 0) & (df['Time'].dt.hour == 8)]
        for m_time in monday_opens['Time']:
            fig.add_vline(x=m_time, line_width=1, line_dash="dot", line_color="yellow")

        # 각 선수별로 포지션에 따른 색상 구간 추가
        for agent in top_3:
            add_colored_trace(fig, df['Time'].values, agent['equity'], agent['signals'], agent['id'])
        
        fig.update_layout(
            template="plotly_dark",
            yaxis_title="수익률 (%)",
            plot_bgcolor='black',
            showlegend=True,
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 실시간 TOP 3")
        for i, agent in enumerate(top_3):
            last_sig = agent['signals'][-1]
            status = "🔴 CALL" if last_sig == 1 else ("🟢 PUT" if last_sig == -1 else "⚪ WAIT")
            st.metric(label=f"{i+1}위: {agent['id']}", value=f"{agent['final']:+.2f}%", delta=status)
            st.write("---")

    st.sidebar.info("🔴 레드: 콜 구간 / 🟢 그린: 풋 구간")
