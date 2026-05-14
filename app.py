import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 15m 4-Week Relay", layout="wide")
st.title("⏱️ 은(Silver) 15분봉 초정밀 릴레이: 최근 1달 승자 궤적")

# 2. 데이터 수집 (15분봉 데이터)
@st.cache_data(ttl=600)
def get_silver_data_15m():
    try:
        silver = yf.Ticker("SI=F")
        # 15분봉(15m)은 최근 60일까지만 제공됨 (1달 분석 가능)
        df = silver.history(period="1mo", interval="15m")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 15분봉 기반 주간 1위 선발 엔진
def run_15m_relay_engine(df):
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = df['week_grp'].unique()
    
    relay_equity = [0]
    relay_signals = [0]
    relay_ids = []
    
    # 150명의 선수 설정 (15분봉에 맞는 파라미터)
    agent_configs = []
    for i in range(1, 151):
        agent_configs.append({
            'id': f"{i}호",
            'window': np.random.randint(20, 100), # 15분봉이므로 더 긴 윈도우 사용
            'threshold': np.random.uniform(0.0002, 0.001) # 더 정밀한 문턱값
        })

    last_total_equity = 0
    
    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 5: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices) / prices[:-1]
        
        best_week_return = -999
        best_agent_data = None
        
        for config in agent_configs:
            # 15분봉 이평선 계산
            ma = pd.Series(prices).rolling(window=config['window']).mean().values
            signals = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            
            # 주간 수익률 (레버리지 2배)
            week_ret = np.sum(signals[:-1] * returns * 2) * 100
            
            if week_ret > best_week_return:
                best_week_return = week_ret
                best_agent_data = {
                    'id': config['id'],
                    'signals': signals,
                    'returns': signals[:-1] * returns * 2 * 100
                }
        
        # 데이터 병합
        current_week_equity = np.cumsum(np.concatenate([[0], best_agent_data['returns']]))
        relay_equity.extend(list(current_week_equity[1:] + last_total_equity))
        relay_signals.extend(list(best_agent_data['signals'][1:]))
        relay_ids.extend([best_agent_data['id']] * (len(current_week_equity)-1))
        
        last_total_equity = relay_equity[-1]

    return relay_equity, relay_signals, relay_ids, df.iloc[:len(relay_equity)]

# 4. 시각화 함수 (레드/그린)
def draw_relay_15m(fig, time, equity, signals, ids):
    # 속도를 위해 벡터화된 방식 사용 가능하나, 색상 변경을 위해 세그먼트 드로잉
    # 15분봉은 데이터가 많으므로 변화 지점만 추출
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else "#00FF00"
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=2.5 if curr_sig == 1 else 1.2),
            hoverinfo='skip',
            showlegend=False
        ))
        start_idx = end_idx

# 실행
df = get_silver_data_15m()
if df is not None:
    equity, signals, ids, plot_df = run_15m_relay_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("⏱️ 15분봉 정밀 분석: 최근 1달 릴레이")
        fig = go.Figure()
        
        # 1위 교체 지점 (노란 선)
        week_changes = np.where(np.array(ids[:-1]) != np.array(ids[1:]))[0]
        for idx in week_changes:
            fig.add_vline(x=plot_df['Time'].iloc[idx], line_width=1, line_dash="dot", line_color="yellow")

        draw_relay_15m(fig, plot_df['Time'].values, equity, signals, ids)
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="누적 수익률 (%)",
            xaxis_title="15분 단위 정밀 궤적",
            hovermode="x"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 실시간 챔피언")
        st.success(f"**현재 지휘: {ids[-1]}**")
        st.metric("최종 수익률", f"{equity[-1]:+.2f}%")
        
        last_sig = signals[-1]
        if last_sig == 1:
            st.error("🔴 15분봉: 매수 유지")
        else:
            st.success("🟢 15분봉: 청산 완료")
            
        st.info(f"데이터 포인트: {len(plot_df)}개")
