import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 4-Week Winner Relay", layout="wide")
st.title("🏆 은(Silver) 최근 4주 승자 릴레이: 매주 1위가 바뀌는 성배 궤적")

# 2. 데이터 수집 (최근 1개월, 1시간봉)
@st.cache_data(ttl=600)
def get_silver_data_4w():
    try:
        silver = yf.Ticker("SI=F")
        # 최근 1개월(1mo) 데이터를 1시간(1h) 단위로 수집
        df = silver.history(period="1mo", interval="1h")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 데이터 제외
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 오류: {e}")
        return None

# 3. 주 단위로 1위를 새로 선발하여 연결하는 엔진
def run_4w_relay_engine(df):
    # 주차별 그룹핑 (연도-주차)
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = df['week_grp'].unique()
    
    relay_equity = [0]
    relay_signals = [0]
    relay_ids = []
    
    # 150명의 선수 설정
    agent_configs = []
    for i in range(1, 151):
        agent_configs.append({
            'id': f"{i}호",
            'window': np.random.randint(12, 45), # 최근 장세에 맞춰 조금 더 빠른 호흡
            'threshold': np.random.uniform(0.0003, 0.0012)
        })

    last_total_equity = 0
    
    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 2: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices) / prices[:-1]
        
        best_week_return = -999
        best_agent_data = None
        
        # 해당 주차의 최고 수익률 선수 선발
        for config in agent_configs:
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
        
        # 1위 선수의 데이터를 누적 궤적에 병합
        current_week_equity = np.cumsum(np.concatenate([[0], best_agent_data['returns']]))
        relay_equity.extend(list(current_week_equity[1:] + last_total_equity))
        relay_signals.extend(list(best_agent_data['signals'][1:]))
        relay_ids.extend([best_agent_data['id']] * (len(current_week_equity)-1))
        
        last_total_equity = relay_equity[-1]

    # 데이터 길이 불일치 방지
    final_len = len(relay_equity)
    return relay_equity, relay_signals, relay_ids, df.iloc[:final_len]

# 4. 구간별 선 그리기 (매수: 레드 / 청산: 그린)
def draw_relay_path_4w(fig, time, equity, signals, ids):
    for j in range(len(signals) - 1):
        # 매수(1)면 레드, 청산(0)이면 그린
        color = "#FF0000" if signals[j] == 1 else "#00FF00"
        fig.add_trace(go.Scatter(
            x=time[j:j+2], 
            y=equity[j:j+2],
            mode='lines',
            line=dict(color=color, width=4 if signals[j] == 1 else 2),
            hoverinfo='text',
            text=f"챔피언: {ids[j]}",
            showlegend=False
        ))

# 메인 실행
df = get_silver_data_4w()
if df is not None:
    equity, signals, ids, plot_df = run_4w_relay_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 최근 4주 챔피언 릴레이 궤적")
        fig = go.Figure()
        
        # 주간 경계선 (노란 점선)
        week_changes = np.where(np.array(ids[:-1]) != np.array(ids[1:]))[0]
        for idx in week_changes:
            fig.add_vline(x=plot_df['Time'].iloc[idx], line_width=1.5, line_dash="dot", line_color="yellow")

        draw_relay_path_4w(fig, plot_df['Time'].values, equity, signals, ids)
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="최근 4주 누적 수익률 (%)",
            xaxis_title="매주 금요일 01:00 승자 교체 (노란 점선)",
            hovermode="x"
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🥇 현재의 승자")
        current_winner = ids[-1]
        st.success(f"**현재 지휘 중: {current_winner}**")
        st.write(f"최종 누적 수익: {equity[-1]:+.2f}%")
        st.write("---")
        
        last_sig = signals[-1]
        if last_sig == 1:
            st.error("🔴 현재 매수(BUY) 유지")
        else:
            st.success("🟢 현재 청산(CASH) 대기")
        
        st.caption("최근 4주간 매주 금요일 01:00에 가장 수익이 높았던 선수가 바통을 이어받은 결과입니다.")
