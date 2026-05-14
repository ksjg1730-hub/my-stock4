import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Weekly Champ 6Mo", layout="wide")
st.title("🏆 은(Silver) 주간 1위 챔피언: 6개월 분석 궤적")

# 2. 데이터 수집 (6개월치, 1시간봉)
@st.cache_data(ttl=600)
def get_silver_data_6mo():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="6mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 데이터 제거
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 주간 1위 선발 엔진
def find_weekly_champion(df):
    now = df['Time'].iloc[-1]
    # 이번 주 리셋 기준점 (금요일 01:00)
    last_fri = now - timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 1: last_fri -= timedelta(days=7)
    ref_time = last_fri.replace(hour=1, minute=0, second=0, microsecond=0)
    
    price_all = df['Price'].values
    weekly_mask = df['Time'] >= ref_time
    price_weekly = df.loc[weekly_mask, 'Price'].values
    
    agents = []
    for i in range(1, 151):
        # 150명의 선수에게 다양한 성격(이평선, 임계값) 부여
        window = np.random.randint(15, 65)
        threshold = np.random.uniform(0.0004, 0.002)
        
        # 전체 기간 신호 계산
        ma_all = pd.Series(price_all).rolling(window=window).mean().values
        sig_all = np.where(price_all > ma_all * (1 + threshold), 1, 0)
        ret_all = np.diff(price_all) / price_array[:-1] if 'price_array' in locals() else np.diff(price_all) / price_all[:-1]
        cum_all = np.concatenate([[0], np.cumsum(sig_all[:-1] * ret_all * 2)]) * 100
        
        # 주간 성과 계산 (선발 기준)
        if len(price_weekly) > 1:
            ma_w = pd.Series(price_weekly).rolling(window=window).mean().values
            sig_w = np.where(price_weekly > ma_w * (1 + threshold), 1, 0)
            ret_w = np.diff(price_weekly) / price_weekly[:-1]
            final_w = np.sum(sig_w[:-1] * ret_w * 2) * 100
        else:
            final_w = -999
            
        agents.append({
            'id': f"{i}호",
            'equity': cum_all,
            'signals': sig_all,
            'final_w': final_w
        })
    
    # 이번 주 수익률이 가장 높은 선수 1명만 선발
    return sorted(agents, key=lambda x: x['final_w'], reverse=True)[0]

# 4. 구간별 선 그리기 (매수: 레드, 청산: 그린)
def draw_champ_path(fig, time, equity, signals, name):
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else "#00FF00" # 매수 레드 / 청산 그린
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=3 if curr_sig == 1 else 1.2),
            name=f"{name} ({'매수' if curr_sig==1 else '청산'})",
            showlegend=True if start_idx == 0 else False,
            legendgroup=name
        ))
        start_idx = end_idx

# 실행 로직
df = get_silver_data_6mo()
if df is not None:
    champ = find_weekly_champion(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"📊 주간 1위({champ['id']})의 6개월 누적 수익 궤적")
        fig = go.Figure()
        
        # 월간 구분선 표시
        month_starts = df[df['Time'].dt.day == 1]
        for m_time in month_starts['Time']:
            fig.add_vline(x=m_time, line_width=1, line_dash="dash", line_color="white", opacity=0.3)

        # 주간 1위 선수만 그래프에 드로잉
        draw_champ_path(fig, df['Time'].values, champ['equity'], champ['signals'], champ['id'])
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="6개월 누적 수익률 (%)",
            xaxis_title="한국 시간 (KST)",
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 주간 챔피언 정보")
        st.success(f"**현재 1위: {champ['id']} 선수**")
        st.write(f"이번 주 수익: {champ['final_w']:+.2f}%")
        st.write(f"6개월 총수익: {champ['equity'][-1]:+.2f}%")
        st.write("---")
        
        last_sig = champ['signals'][-1]
        status = "🔴 현재 매수 중" if last_sig == 1 else "🟢 현재 청산(대기) 중"
        st.info(status)
        
    st.sidebar.markdown("### 🎨 색상 가이드\n- **레드(Red)**: 매수 구간\n- **그린(Green)**: 청산 구간")
