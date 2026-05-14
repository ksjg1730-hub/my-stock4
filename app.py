import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Race 150 - Weekly", layout="wide")
st.title("🏆 주간 은(Silver) 경주: 금요일 01:00 기준 수익률")

# 2. 실제 데이터 수집 (최근 1개월)
@st.cache_data(ttl=600)
def get_silver_data():
    try:
        silver = yf.Ticker("SI=F")
        # 주말 갭 제거를 위해 1시간봉 데이터 사용 (안정성 확보)
        df = silver.history(period="1mo", interval="1h")
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
    # 가장 최근 금요일 새벽 1시 찾기
    now = df['Time'].iloc[-1]
    last_friday_1am = now - timedelta(days=(now.weekday() - 4) % 7)
    last_friday_1am = last_friday_1am.replace(hour=1, minute=0, second=0, microsecond=0)
    
    # 해당 시점 이후 데이터만 필터링 (주간 수익률 계산용)
    weekly_df = df[df['Time'] >= last_friday_1am].copy()
    if len(weekly_df) < 5: # 데이터가 부족하면 전체 데이터 사용
        weekly_df = df.copy()
        
    price_array = weekly_df['Price'].values
    agents_results = []
    
    for i in range(1, 151):
        window = np.random.randint(5, 30)
        threshold = np.random.uniform(0.0002, 0.001)
        
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        # 수익률 계산 (레버리지 2배)
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2
        
        # 첫 지점(금요일 1시)을 0%로 만들기 위해 0부터 누적 합계 계산
        cumulative_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        last_sig = signals[-1]
        current_color = "🔴 매수" if last_sig == 1 else ("🔵 매도" if last_sig == -1 else "⚪ 관망")
        
        agents_results.append({
            'id': f"{i}호",
            'equity_pct': cumulative_returns,
            'final_pct': cumulative_returns[-1],
            'current_color': current_color,
            'color_code': 'red' if last_sig == 1 else 'blue' if last_sig == -1 else 'gray'
        })
    
    return weekly_df, sorted(agents_results, key=lambda x: x['final_pct'], reverse=True)

# 실행 및 시각화
raw_df = get_silver_data()

if raw_df is not None:
    weekly_df, top_agents = run_weekly_race(raw_df)
    
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📅 주중 누적 상승률 (기준: {weekly_df['Time'].iloc[0].strftime('%m/%d %H:%M')})")
        fig = go.Figure()
        
        # 상위 5선 그래프 (퍼센트 단위)
        for agent in top_agents[:5]:
            fig.add_trace(go.Scatter(
                x=weekly_df['Time'], 
                y=agent['equity_pct'], 
                name=f"{agent['id']} ({agent['final_pct']:.2f}%)",
                mode='lines'
            ))
        
        fig.update_layout(
            hovermode="x unified", 
            template="plotly_dark",
            yaxis_suffix="%",
            yaxis_title="누적 수익률 (%)",
            xaxis_title="한국 시간 (KST)"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 주간 순위")
        for i, agent in enumerate(top_agents[:5]):
            st.metric(
                label=f"{i+1}위: {agent['id']}", 
                value=f"{agent['final_pct']:+.2f}%", 
                delta=agent['current_color']
            )
            st.write("---")

    st.info(f"💡 현재 은 시세: ${weekly_df['Price'].iloc[-1]:.2f} (금요일 1시 대비 변동 반영)")
