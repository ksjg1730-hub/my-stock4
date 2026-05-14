import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Weekly Race", layout="wide")
st.title("🏆 주간 은(Silver) 경주: 금요일 01:00 기준 (0%)")

# 2. 실제 데이터 수집
@st.cache_data(ttl=600)
def get_silver_data():
    try:
        silver = yf.Ticker("SI=F")
        # 최근 1개월 데이터를 1시간 단위로 가져옴
        df = silver.history(period="1mo", interval="1h")
        if df.empty:
            return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        # 시간대 변환 (UTC -> KST)
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return None

# 3. 주간 리셋 및 150명 엔진
def run_weekly_race(df):
    now = df['Time'].iloc[-1]
    # 가장 최근 금요일 새벽 1시 계산
    last_friday = now - timedelta(days=(now.weekday() - 4) % 7)
    # 만약 오늘이 금요일 1시 이전이라면 지난주 금요일로 설정
    if now.weekday() == 4 and now.hour < 1:
        last_friday = last_friday - timedelta(days=7)
    
    ref_time = last_friday.replace(hour=1, minute=0, second=0, microsecond=0)
    
    # 기준점 이후 데이터 필터링
    weekly_df = df[df['Time'] >= ref_time].copy()
    if len(weekly_df) < 2:
        weekly_df = df.tail(24).copy() # 데이터가 너무 적으면 최근 24시간 사용
        
    price_array = weekly_df['Price'].values
    agents_results = []
    
    for i in range(1, 151):
        window = np.random.randint(5, 30)
        threshold = np.random.uniform(0.0002, 0.001)
        
        # 20년 전 가격의 비밀 기법: 이평선 이격 베팅
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        # 수익률 계산 (레버리지 2배)
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2
        
        # 금요일 1시를 0%로 초기화하여 누적 수익률 계산
        cumulative_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        last_sig = signals[-1]
        current_color = "🔴 매수" if last_sig == 1 else ("🔵 매도" if last_sig == -1 else "⚪ 관망")
        
        agents_results.append({
            'id': f"{i}호 선수",
            'equity_pct': cumulative_returns,
            'final_pct': cumulative_returns[-1],
            'current_color': current_color
        })
    
    return weekly_df, sorted(agents_results, key=lambda x: x['final_pct'], reverse=True)

# 실행 및 시각화
raw_df = get_silver_data()

if raw_df is not None:
    weekly_df, top_agents = run_weekly_race(raw_df)
    
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📅 주간 누적 수익률 (기준: {weekly_df['Time'].iloc[0].strftime('%m/%d %H:%M')})")
        fig = go.Figure()
        
        # 상위 5선 그래프
        for agent in top_agents[:5]:
            fig.add_trace(go.Scatter(
                x=weekly_df['Time'], 
                y=agent['equity_pct'], 
                name=f"{agent['id']} ({agent['final_pct']:+.2f}%)",
                mode='lines'
            ))
        
        # 오류 방지: yaxis_suffix 대신 tickformat 사용
        fig.update_layout(
            hovermode="x unified", 
            template="plotly_dark",
            yaxis=dict(tickformat="+.2f", title="누적 수익률 (%)"),
            xaxis_title="한국 시간 (KST)",
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 주간 TOP 5")
        for i, agent in enumerate(top_agents[:5]):
            st.metric(
                label=f"{i+1}위: {agent['id']}", 
                value=f"{agent['final_pct']:+.2f}%", 
                delta=agent['current_color']
            )
            st.write("---")

    st.sidebar.info(f"현재 은 가격: ${weekly_df['Price'].iloc[-1]:.2f}")
    if st.sidebar.button("데이터 갱신"):
        st.cache_data.clear()
        st.rerun()
else:
    st.error("데이터를 불러올 수 없습니다. 나중에 다시 시도해주세요.")
