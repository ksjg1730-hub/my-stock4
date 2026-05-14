import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 15m Winner Relay", layout="wide")
st.title("🏆 은(Silver) 15분봉 주간 릴레이: 최근 1달 승자 궤적")

# 2. 데이터 수집 (최근 1개월, 15분봉)
@st.cache_data(ttl=600)
def get_silver_15m_data():
    try:
        silver = yf.Ticker("SI=F")
        # 15분봉은 최근 60일 데이터까지 호출 가능
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

# 3. 릴레이 엔진: 매주 금요일 01:00 기준 1위 선발 및 궤적 통합
def run_relay_engine_15m(df):
    # 주차별 그룹핑
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = df['week_grp'].unique()
    
    relay_equity = [0]
    relay_signals = [0]
    relay_ids = []
    
    # 150명의 독립된 전략 선수 생성
    agent_configs = []
    for i in range(1, 151):
        agent_configs.append({
            'id': f"{i}호",
            'window': np.random.randint(20, 80), # 15분봉용 이평선 설정
            'threshold': np.random.uniform(0.0003, 0.0012)
        })

    last_total_equity = 0
    
    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 5: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices) / prices[:-1]
        
        best_week_return = -999
        best_agent_data = None
        
        # 해당 주차의 1위 선수 선발
        for config in agent_configs:
            ma = pd.Series(prices).rolling(window=config['window']).mean().values
            signals = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            
            # 주간 누적 수익률 (레버리지 2배)
            week_ret = np.sum(signals[:-1] * returns * 2) * 100
            
            if week_ret > best_week_return:
                best_week_return = week_ret
                best_agent_data = {
                    'id': config['id'],
                    'signals': signals,
                    'returns': signals[:-1] * returns * 2 * 100
                }
        
        # 1위 선수의 성과를 전체 궤적에 이어붙임
        current_week_equity = np.cumsum(np.concatenate([[0], best_agent_data['returns']]))
        relay_equity.extend(list(current_week_equity[1:] + last_total_equity))
        relay_signals.extend(list(best_agent_data['signals'][1:]))
        relay_ids.extend([best_agent_data['id']] * (len(current_week_equity)-1))
        
        last_total_equity = relay_equity[-1]

    return relay_equity, relay_signals, relay_ids, df.iloc[:len(relay_equity)]

# 4. 구간별 선 그리기 (Red: 매수 / Green: 청산)
def draw_relay_segments(fig, time, equity, signals, ids):
    # 신호 변화 지점 추출
    change_points = np.where(np.diff(signals) != 0)[0] + 1
    start_idx = 0
    
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        color = "#FF0000" if curr_sig == 1 else "#00FF00" # 레드: 매수 / 그린: 청산
        
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=3 if curr_sig == 1 else 1.5),
            hoverinfo='text',
            text=f"챔피언: {ids[start_idx]}",
            showlegend=False
        ))
        start_idx = end_idx

# 실행
df = get_silver_15m_data()
if df is not None:
    equity, signals, ids, plot_df = run_relay_engine_15m(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 최근 1달 15분봉 승자 릴레이 (금요일 01:00 교체)")
        fig = go.Figure()
        
        # 1위 교체 지점 (노란 점선)
        week_changes = np.where(np.array(ids[:-1]) != np.array(ids[1:]))[0]
        for idx in week_changes:
            fig.add_vline(x=plot_df['Time'].iloc[idx], line_width=1, line_dash="dot", line_color="yellow")

        draw_relay_segments(fig, plot_df['Time'].values, equity, signals, ids)
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="누적 수익률 (%)",
            xaxis_title="한국 시간 (KST)"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 현재의 승자")
        st.success(f"**현재 지휘: {ids[-1]}**")
        st.metric("최종 누적 수익", f"{equity[-1]:+.2f}%")
        
        last_sig = signals[-1]
        status = "🔴 매수 유지" if last_sig == 1 else "🟢 청산(그린) 완료"
        st.info(f"상태: {status}")
        st.write("---")
        st.write(f"현재가: ${df['Price'].iloc[-1]:.2f}")

    st.sidebar.markdown("### 🎨 시각화 가이드\n- **레드(Red)**: 매수 포지션\n- **그린(Green)**: 청산(현금) 상태\n- **노란 점선**: 매주 1위 교체 시점")
