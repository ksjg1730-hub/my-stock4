import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 15m Real-time Winner Relay", layout="wide")
st.title("🏆 은(Silver) 실전형 릴레이: 지난주 1위의 이번 주 성적")

# 2. 데이터 수집
@st.cache_data(ttl=600)
def get_silver_15m_data():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="1mo", interval="15m")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 연동 오류: {e}")
        return None

# 3. 실전형 릴레이 엔진 (인덱스 버그 수정판)
def run_real_relay_engine(df):
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = sorted(df['week_grp'].unique())
    
    np.random.seed(42)
    agent_configs = []
    for i in range(1, 151):
        agent_configs.append({
            'id': f"{i}호",
            'window': np.random.randint(15, 100),
            'threshold': np.random.uniform(0.0001, 0.0015)
        })

    relay_equity = []
    relay_signals = []
    relay_ids = []
    
    last_total_equity = 0
    current_champion_config = None 
    
    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) == 0: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices, prepend=prices[0]) / prices # 길이 유지를 위해 prepend 사용
        
        # [실전 매매]
        if current_champion_config is not None:
            ma = pd.Series(prices).rolling(window=current_champion_config['window'], min_periods=1).mean().values
            signals = np.where(prices > ma * (1 + current_champion_config['threshold']), 1, 0)
            week_perf_returns = signals * (np.diff(prices, prepend=prices[0]) / prices) * 2 * 100
            
            current_week_equity = np.cumsum(week_perf_returns) + last_total_equity
            relay_equity.extend(current_week_equity.tolist())
            relay_signals.extend(signals.tolist())
            relay_ids.extend([current_champion_config['id']] * len(prices))
            last_total_equity = relay_equity[-1]
        else:
            # 첫 주차 (챔피언 선발 전)
            relay_equity.extend([0.0] * len(prices))
            relay_signals.extend([0] * len(prices))
            relay_ids.extend(["선발중"] * len(prices))

        # [다음 주 선수 선발]
        best_week_ret = -999
        for config in agent_configs:
            temp_ma = pd.Series(prices).rolling(window=config['window'], min_periods=1).mean().values
            temp_sig = np.where(prices > temp_ma * (1 + config['threshold']), 1, 0)
            temp_ret = np.sum(temp_sig * (np.diff(prices, prepend=prices[0]) / prices) * 2) * 100
            if temp_ret > best_week_ret:
                best_week_ret = temp_ret
                current_champion_config = config

    # 최종 결과 데이터프레임과 길이 맞춤
    min_len = min(len(df), len(relay_equity))
    return relay_equity[:min_len], relay_signals[:min_len], relay_ids[:min_len], df.iloc[:min_len]

# 4. 시각화 (IndexError 안전 로직)
def draw_relay_segments(fig, time, equity, signals, ids):
    if len(signals) == 0: return
    
    start_idx = 0
    for i in range(1, len(signals)):
        # 신호가 바뀌거나 챔피언(ID)이 바뀌면 선을 새로 그림
        if signals[i] != signals[i-1] or ids[i] != ids[i-1]:
            plot_segment(fig, time, equity, signals, ids, start_idx, i)
            start_idx = i
    # 마지막 구간
    plot_segment(fig, time, equity, signals, ids, start_idx, len(signals))

def plot_segment(fig, time, equity, signals, ids, start, end):
    curr_sig = signals[start]
    curr_id = ids[start]
    color = "#808080" if curr_id == "선발중" else ("#FF4B4B" if curr_sig == 1 else "#00CC96")
    
    fig.add_trace(go.Scatter(
        x=time[start:end+1], 
        y=equity[start:end+1],
        mode='lines',
        line=dict(color=color, width=2.5 if curr_sig == 1 else 1),
        hoverinfo='text',
        text=f"투입선수: {curr_id}",
        showlegend=False
    ))

# 실행
df = get_silver_15m_data()
if df is not None:
    equity, signals, ids, plot_df = run_real_relay_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 실전 릴레이 (지난주 1위 투입)")
        fig = go.Figure()
        
        # 챔피언 교체선 (안전한 인덱스 접근)
        for i in range(1, len(ids)):
            if ids[i] != ids[i-1]:
                fig.add_vline(x=plot_df['Time'].iloc[i], line_width=1, line_dash="dot", line_color="yellow")

        draw_relay_segments(fig, plot_df['Time'].values, equity, signals, ids)
        fig.update_layout(template="plotly_dark", plot_bgcolor='black', height=600)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🏁 현재 투입")
        st.success(f"**이름: {ids[-1]}**")
        st.metric("누적 수익", f"{equity[-1]:+.2f}%")
        
        peak = np.maximum.accumulate(equity)
        mdd = np.max(peak - equity)
        st.metric("MDD", f"{mdd:.2f}%")
