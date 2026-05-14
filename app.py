import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 1Mo Top 3", layout="wide")
st.title("🏆 은(Silver) TOP 3 경주: 1개월 전체 흐름 및 포지션 컬러")

# 2. 데이터 수집 및 주말 제거 (1개월치)
@st.cache_data(ttl=600)
def get_silver_data_1mo():
    try:
        silver = yf.Ticker("SI=F")
        # 최근 1개월 데이터를 1시간 단위로 수집
        df = silver.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        
        # 주말 데이터 제거 (거래가 없는 시간 삭제)
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 연결 오류: {e}")
        return None

# 3. 150인 엔진 및 TOP 3 추출 (금요일 01:00 리셋 로직 포함)
def run_top3_engine(df):
    # 금요일 01:00 리셋 기준점 계산
    now = df['Time'].iloc[-1]
    last_friday = now - timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 1:
        last_friday -= timedelta(days=7)
    ref_time = last_friday.replace(hour=1, minute=0, second=0, microsecond=0)
    
    # 수익률 계산은 전체 1개월치를 하되, 기준점 이후 흐름을 강조
    price_array = df['Price'].values
    agents = []
    
    for i in range(1, 151):
        # 20년 전 가격의 비밀: 변동성 돌파 및 이평선 필터
        window = np.random.randint(15, 45)
        threshold = np.random.uniform(0.0004, 0.0015)
        
        ma = pd.Series(price_array).rolling(window=window).mean().values
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2 # 레버리지 2배
        cum_returns = np.concatenate([[0], np.cumsum(strategy_returns)]) * 100
        
        last_sig = signals[-1]
        # 색상 대비 극대화: 콜(진한 레드), 풋(형광 그린)
        line_color = "#FF0000" if last_sig == 1 else ("#00FF00" if last_sig == -1 else "#808080")
        pos_label = "CALL 🔴" if last_sig == 1 else ("PUT 🟢" if last_sig == -1 else "WAIT ⚪")
        
        agents.append({
            'id': f"{i}호",
            'equity': cum_returns,
            'final': cum_returns[-1],
            'color': line_color,
            'pos_label': pos_label,
            'last_sig': last_sig
        })
    
    # 1개월 누적 수익률 기준 상위 3인 선발
    return sorted(agents, key=lambda x: x['final'], reverse=True)[:3]

# 실행 및 시각화
df = get_silver_data_1mo()
if df is not None:
    top_3 = run_top3_engine(df)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader(f"📅 1개월 누적 수익률 현황 (현재가: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        
        # 매주 월요일 아침 수직선 표시
        monday_opens = df[(df['Time'].dt.weekday == 0) & (df['Time'].dt.hour == 8)]
        for m_time in monday_opens['Time']:
            fig.add_vline(x=m_time, line_width=1, line_dash="dot", line_color="yellow")

        for agent in top_3:
            fig.add_trace(go.Scatter(
                x=df['Time'], 
                y=agent['equity'],
                name=f"{agent['id']} [{agent['pos_label']}]",
                line=dict(color=agent['color'], width=4), # 선 굵기 강화
                mode='lines'
            ))
        
        fig.update_layout(
            hovermode="x unified",
            template="plotly_dark",
            yaxis_title="누적 수익률 (%)",
            xaxis_title="한국 시간 (KST)",
            legend=dict(font=dict(size=14), orientation="h", y=1.1, x=0.5, xanchor="center"),
            # 배경색을 더 어둡게 하여 레드/그린 대비 강조
            plot_bgcolor='black'
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 TOP 3 포지션")
        for i, agent in enumerate(top_3):
            # 포지션에 따른 텍스트 강조
            st.markdown(f"### {i+1}위: {agent['id']} 선수")
            st.title(f"{agent['final']:+.2f}%")
            if agent['last_sig'] == 1:
                st.error(f"현재 포지션: {agent['pos_label']}")
            elif agent['last_sig'] == -1:
                st.success(f"현재 포지션: {agent['pos_label']}")
            else:
                st.secondary(f"현재 포지션: {agent['pos_label']}")
            st.write("---")

    st.sidebar.info("💡 노란 점선은 주간 개장(월요일)을 의미합니다.")
    if st.sidebar.button("데이터 강제 새로고침"):
        st.cache_data.clear()
        st.rerun()
