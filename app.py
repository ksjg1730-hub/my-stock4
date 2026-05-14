import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver Weekly Winner Relay", layout="wide")
st.title("🏆 은(Silver) 주간 챔피언 릴레이: 매주 1위가 바뀌는 6개월 궤적")

# 2. 데이터 수집 (6개월치)
@st.cache_data(ttl=600)
def get_silver_data_relay():
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

# 3. 주 단위로 1위를 새로 뽑아 궤적을 잇는 엔진
def run_relay_engine(df):
    # 금요일 01:00 기준으로 주간 구간 나누기
    df['week_grp'] = df['Time'].apply(lambda x: x.strftime('%Y-%U')) # 연도-주차별 그룹
    unique_weeks = df['week_grp'].unique()
    
    relay_equity = [0]
    relay_signals = [0]
    relay_ids = []
    
    # 150명의 선수 설정 (이평선, 임계값 고정)
    agent_configs = []
    for i in range(1, 151):
        agent_configs.append({
            'id': f"{i}호",
            'window': np.random.randint(15, 60),
            'threshold': np.random.uniform(0.0004, 0.0015)
        })

    last_total_equity = 0
    
    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 2: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices) / prices[:-1]
        
        best_week_return = -999
        best_agent_data = None
        
        # 이번 주에 가장 잘한 선수 찾기
        for config in agent_configs:
            ma = pd.Series(prices).rolling(window=config['window']).mean().values
            signals = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            
            # 이번 주 수익률 (레버리지 2배)
            week_ret = np.sum(signals[:-1] * returns * 2) * 100
            
            if week_ret > best_week_return:
                best_week_return = week_ret
                best_agent_data = {
                    'id': config['id'],
                    'signals': signals,
                    'returns': signals[:-1] * returns * 2 * 100
                }
        
        # 1위 선수의 데이터를 전체 궤적에 추가
        current_week_equity = np.cumsum(np.concatenate([[0], best_agent_data['returns']]))
        relay_equity.extend(list(current_week_equity[1:] + last_total_equity))
        relay_signals.extend(list(best_agent_data['signals'][1:]))
        relay_ids.extend([best_agent_data['id']] * (len(current_week_equity)-1))
        
        last_total_equity = relay_equity[-1]

    return relay_equity, relay_signals, relay_ids, df.iloc[:len(relay_equity)]

# 4. 구간별 선 그리기 (매수: 레드, 청산: 그린)
def draw_relay_path(fig, time, equity, signals, ids):
    for j in range(len(signals) - 1):
        color = "#FF0000" if signals[j] == 1 else "#00FF00" # 매수 레드 / 청산 그린
        fig.add_trace(go.Scatter(
            x=time[j:j+2], 
            y=equity[j:j+2],
            mode='lines',
            line=dict(color=color, width=3 if signals[j] == 1 else 1.5),
            hoverinfo='text',
            text=f"챔피언: {ids[j]}",
            showlegend=False
        ))

# 실행
df = get_silver_data_relay()
if df is not None:
    equity, signals, ids, plot_df = run_relay_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 주간 승자들의 릴레이 궤적 (6개월)")
        fig = go.Figure()
        
        # 주간 경계선 (노란 점선)
        week_changes = np.where(np.array(ids[:-1]) != np.array(ids[1:]))[0]
        for idx in week_changes:
            fig.add_vline(x=plot_df['Time'].iloc[idx], line_width=1, line_dash="dot", line_color="yellow")

        draw_relay_path(fig, plot_df['Time'].values, equity, signals, ids)
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="누적 수익률 (%)",
            xaxis_title="매주 금요일 01:00 승자 교체"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 이번 주 챔피언")
        current_winner = ids[-1]
        st.success(f"**현재 지휘 중: {current_winner}**")
        st.write(f"최종 누적 수익: {equity[-1]:+.2f}%")
        st.write("---")
        
        last_sig = signals[-1]
        status = "🔴 매수 중" if last_sig == 1 else "🟢 청산(그린) 중"
        st.info(status)
        st.caption("노란 점선은 매주 1위가 교체된 지점입니다.")
