import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 1Mo Race", layout="wide")
st.title("🏆 글로벌 은(Silver) 150인 경주: 최근 1개월 추적")

# 2. 실제 데이터 수집 (최근 1개월)
@st.cache_data(ttl=600)
def get_silver_data():
    try:
        silver = yf.Ticker("SI=F")
        # 최근 1개월 데이터를 1시간 단위로 수집 (속도와 정확도의 균형)
        df = silver.history(period="1mo", interval="1h")
        if df.empty:
            return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        # 한국 시간(KST)으로 변환
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        return df
    except Exception as e:
        st.error(f"데이터 수집 오류: {e}")
        return None

# 3. 150인 전략 엔진 (포지션 컬러 반영)
def run_silver_race(df):
    price_array = df['Price'].values
    agents_results = []
    
    for i in range(1, 151):
        # 20년 전 가격의 비밀 기법: 변동성 및 이평선 조합
        window = np.random.randint(10, 50)
        threshold = np.random.uniform(0.0003, 0.0015)
        
        ma = pd.Series(price_array).rolling(window=window).mean().values
        # 매수(Call): 1, 매도(Put): -1
        signals = np.where(price_array > ma * (1 + threshold), 1, 
                  np.where(price_array < ma * (1 - threshold), -1, 0))
        
        # 수익률 계산 (레버리지 2배 적용)
        returns = np.diff(price_array) / price_array[:-1]
        strategy_returns = signals[:-1] * returns * 2
        equity_curve = np.cumprod(1 + strategy_returns)
        
        # 현재 포지션 및 컬러 설정
        last_sig = signals[-1]
        if last_sig == 1:
            pos_text = "🔴 CALL (매수)"
            pos_color = "red"
        elif last_sig == -1:
            pos_text = "🟢 PUT (매도)"
            pos_color = "green"
        else:
            pos_text = "⚪ WAIT (관망)"
            pos_color = "gray"
            
        agents_results.append({
            'id': f"{i}호",
            'equity': equity_curve,
            'final_return': equity_curve[-1],
            'pos_text': pos_text,
            'pos_color': pos_color
        })
    
    return sorted(agents_results, key=lambda x: x['final_return'], reverse=True)

# 실행 및 대시보드 출력
df = get_silver_data()

if df is not None:
    top_agents = run_silver_race(df)
    
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📊 최근 1개월 누적 수익 흐름 (현재가: ${df['Price'].iloc[-1]:.2f})")
        fig = go.Figure()
        
        # 상위 5선 그래프
        for agent in top_agents[:5]:
            fig.add_trace(go.Scatter(
                x=df['Time'][1:], 
                y=agent['equity'], 
                name=f"{agent['id']} {agent['pos_text']}",
                line=dict(width=2, color=agent['pos_color']) # 현재 포지션 색상으로 라인 강조
            ))
        
        fig.update_layout(
            hovermode="x unified", 
            template="plotly_dark",
            yaxis_title="수익률 (1.0 기준)",
            xaxis_title="한국 시간 (KST)",
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 Top 5 실시간 포지션")
        for i, agent in enumerate(top_agents[:5]):
            profit_pct = (agent['final_return'] - 1) * 100
            st.metric(
                label=f"{i+1}위: {agent['id']} 선수", 
                value=f"{agent['final_return']:.4f}", 
                delta=f"{agent['pos_text']} ({profit_pct:+.2f}%)",
                delta_color="normal" # 포지션 텍스트와 연동
            )
            st.write("---")

    st.sidebar.success(f"데이터 갱신 완료: {datetime.now().strftime('%H:%M')}")
    if st.sidebar.button("새로고침"):
        st.cache_data.clear()
        st.rerun()
