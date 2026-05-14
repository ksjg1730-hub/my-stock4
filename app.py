import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Top 1 Duel", layout="wide")
st.title("🏆 은(Silver) 챔피언 결투: 6개월 1위 vs 주간 1위")

# 2. 데이터 수집 (6개월치, 1시간봉)
@st.cache_data(ttl=600)
def get_silver_data_full():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="6mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 챔피언 선발 및 수익률 계산 엔진
def select_champions(df):
    now = df['Time'].iloc[-1]
    # 이번 주 금요일 01:00 기준점 (주간 리셋용)
    last_fri = now - timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 1: last_fri -= timedelta(days=7)
    ref_time = last_fri.replace(hour=1, minute=0, second=0, microsecond=0)
    
    price_all = df['Price'].values
    weekly_mask = df['Time'] >= ref_time
    price_weekly = df.loc[weekly_mask, 'Price'].values
    
    all_agents = []
    for i in range(1, 151):
        window = np.random.randint(15, 65)
        threshold = np.random.uniform(0.0004, 0.002)
        
        # 전체 6개월 신호 및 수익률
        ma_all = pd.Series(price_all).rolling(window=window).mean().values
        sig_all = np.where(price_all > ma_all * (1 + threshold), 1, 0)
        ret_all = np.diff(price_all) / price_all[:-1]
        cum_all = np.concatenate([[0], np.cumsum(sig_all[:-1] * ret_all * 2)]) * 100
        
        # 주간 신호 및 수익률 (금요일 1시 기준 0% 시작)
        ma_w = pd.Series(price_weekly).rolling(window=window).mean().values
        sig_w = np.where(price_weekly > ma_w * (1 + threshold), 1, 0)
        ret_w = np.diff(price_weekly) / price_weekly[:-1]
        cum_w = np.concatenate([[0], np.cumsum(sig_w[:-1] * ret_w * 2)]) * 100
        
        all_agents.append({
            'id': f"{i}호",
            'cum_all': cum_all,
            'sig_all': sig_all,
            'final_all': cum_all[-1],
            'cum_w': cum_w,
            'sig_w': sig_w,
            'final_w': cum_w[-1]
        })
    
    # 6개월 1위와 주간 1위 선발
    top_6mo = sorted(all_agents, key=lambda x: x['final_all'], reverse=True)[0]
    top_weekly = sorted(all_agents, key=lambda x: x['final_w'], reverse=True)[0]
    return top_6mo, top_weekly, df[weekly_mask]

# 4. 세그먼트 그리기 함수 (매수: 레드, 청산: 그린)
def draw_top_path(fig, time, equity, signals, name, opacity=1.0):
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else "#00FF00" # 매수 레드 / 청산 그린
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=4 if curr_sig == 1 else 1.5),
            opacity=opacity,
            name=f"{name} ({'BUY' if curr_sig==1 else 'CASH'})",
            legendgroup=name,
            showlegend=True if start_idx == 0 else False
        ))
        start_idx = end_idx

# 실행
raw_df = get_silver_data_full()
if raw_df is not None:
    top_6mo, top_weekly, weekly_df = select_champions(raw_df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 주간 수익률 레이스 (Top 1 매치업)")
        fig = go.Figure()
        
        # 6개월 챔피언의 주간 성적 (점선 스타일)
        draw_top_path(fig, weekly_df['Time'].values, top_6mo['cum_w'], top_6mo['sig_w'], f"6개월왕 {top_6mo['id']}", opacity=0.6)
        
        # 주간 챔피언의 성적 (실선 스타일)
        draw_top_path(fig, weekly_df['Time'].values, top_weekly['cum_w'], top_weekly['sig_w'], f"주간왕 {top_weekly['id']}")
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="주간 수익률 (%)",
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🏆 현재 랭킹")
        st.info(f"**6개월 1위: {top_6mo['id']}**\n\n주간 수익: {top_6mo['final_w']:+.2f}%")
        st.success(f"**주간 1위: {top_weekly['id']}**\n\n주간 수익: {top_weekly['final_w']:+.2f}%")
        
        current_price = raw_df['Price'].iloc[-1]
        st.metric("현재 은 시세", f"${current_price:.2f}")

    st.sidebar.markdown("### 🎨 범례\n- **레드(Red)**: 매수 포지션\n- **그린(Green)**: 청산(현금) 상태")
