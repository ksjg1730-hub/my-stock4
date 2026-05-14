import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="Silver 15m Real-time Winner Relay", layout="wide")
st.title("🏆 은(Silver) 실전형 릴레이: 지난주 1위의 이번 주 성적")
st.markdown("가장 최근에 검증된 1위 전략을 이번 주에 투입했을 때의 실제 수익 곡선입니다.")

# 2. 데이터 수집 (최근 1개월+, 15분봉)
@st.cache_data(ttl=600)
def get_silver_15m_data():
    try:
        silver = yf.Ticker("SI=F")
        # 전진 분석을 위해 충분한 데이터 확보 (최근 59일까지 가능)
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

# 3. 실전형 릴레이 엔진: 전진 분석(Walk-forward)
def run_real_relay_engine(df):
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = sorted(df['week_grp'].unique())
    
    # 150명의 후보 선수(전략) 생성
    np.random.seed(42) # 재현성을 위해 시드 고정
    agent_configs = []
    for i in range(1, 151):
        agent_configs.append({
            'id': f"{i}호",
            'window': np.random.randint(15, 100),
            'threshold': np.random.uniform(0.0001, 0.0015)
        })

    relay_equity = [0]
    relay_signals = [0]
    relay_ids = []
    
    last_total_equity = 0
    current_champion_config = None # 이번 주에 뛸 선수
    
    for i, week in enumerate(unique_weeks):
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 10: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices) / prices[:-1]

        # [STEP 1] 이번 주 매매 실행 (지난주에 뽑힌 챔피언이 있다면)
        if current_champion_config is not None:
            ma = pd.Series(prices).rolling(window=current_champion_config['window']).mean().values
            # 실전 신호: 현재 가격이 이평선+임계값보다 높으면 매수
            signals = np.where(prices > ma * (1 + current_champion_config['threshold']), 1, 0)
            
            # 실제 이번 주 수익률 (레버리지 2배 적용)
            week_perf_returns = signals[:-1] * returns * 2 * 100
            week_equity_curve = np.cumsum(np.concatenate([[0], week_perf_returns]))
            
            # 전체 궤적에 기록
            relay_equity.extend(list(week_equity_curve[1:] + last_total_equity))
            relay_signals.extend(list(signals[1:]))
            relay_ids.extend([current_champion_config['id']] * (len(week_equity_curve)-1))
            
            last_total_equity = relay_equity[-1]
        else:
            # 첫 주차는 챔피언이 없으므로 '준비 중'으로 기록
            relay_equity.extend([0] * len(prices))
            relay_signals.extend([0] * len(prices))
            relay_ids.extend(["선발중"] * len(prices))

        # [STEP 2] 다음 주에 투입할 챔피언 선발 (이번 주 성적 기준 1위)
        best_week_ret = -999
        for config in agent_configs:
            temp_ma = pd.Series(prices).rolling(window=config['window']).mean().values
            temp_sig = np.where(prices > temp_ma * (1 + config['threshold']), 1, 0)
            temp_ret = np.sum(temp_sig[:-1] * returns * 2) * 100
            
            if temp_ret > best_week_ret:
                best_week_ret = temp_ret
                current_champion_config = config # 이 선수가 다음 주 실전 투입됨

    return relay_equity, relay_signals, relay_ids, df.iloc[:len(relay_equity)]

# 4. 시각화 함수
def draw_relay_segments(fig, time, equity, signals, ids):
    # 신호나 챔피언이 바뀔 때 구간을 나눔
    change_points = []
    for i in range(1, len(signals)):
        if signals[i] != signals[i-1] or ids[i] != ids[i-1]:
            change_points.append(i)
            
    start_idx = 0
    for end_idx in list(change_points) + [len(signals)]:
        curr_sig = signals[start_idx]
        curr_id = ids[start_idx]
        
        # 선 색상: 매수(Red), 청산(Green), 선발중(Gray)
        if curr_id == "선발중":
            color = "#808080"
        else:
            color = "#FF4B4B" if curr_sig == 1 else "#00CC96"
            
        fig.add_trace(go.Scatter(
            x=time[start_idx:end_idx+1], 
            y=equity[start_idx:end_idx+1],
            mode='lines',
            line=dict(color=color, width=2.5 if curr_sig == 1 else 1),
            hoverinfo='text',
            text=f"투입선수: {curr_id}",
            showlegend=False
        ))
        start_idx = end_idx

# 실행 및 대시보드 구성
df = get_silver_15m_data()
if df is not None:
    equity, signals, ids, plot_df = run_real_relay_engine(df)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📊 실전 릴레이 수익 곡선 (지난주 1위 투입)")
        fig = go.Figure()
        
        # 챔피언 교체 지점 (노란 점선)
        week_changes = np.where(np.array(ids[:-1]) != np.array(ids[1:]))[0]
        for idx in week_changes:
            fig.add_vline(x=plot_df['Time'].iloc[idx], line_width=1, line_dash="dot", line_color="yellow")

        draw_relay_segments(fig, plot_df['Time'].values, equity, signals, ids)
        
        fig.update_layout(
            template="plotly_dark", plot_bgcolor='black',
            yaxis_title="실전 누적 수익률 (%)",
            xaxis_title="한국 시간 (KST)",
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🏁 현재 투입 선수")
        current_hero = ids[-1]
        st.success(f"**이름: {current_hero}**")
        
        # 성과 지표
        total_ret = equity[-1]
        st.metric("실전 누적 수익", f"{total_ret:+.2f}%")
        
        # 상태 표시
        last_sig = signals[-1]
        if current_hero == "선발중":
            status = "⏳ 데이터 수집 및 선발 중"
        else:
            status = "🔴 매수 유지" if last_sig == 1 else "🟢 관망 중 (현금)"
        st.info(f"현재 상태: {status}")
        
        st.write("---")
        # MDD 계산
        peak = np.maximum.accumulate(equity)
        mdd = np.max(peak - equity)
        st.metric("최대 낙폭 (MDD)", f"{mdd:.2f}%")
        
        st.write("---")
        st.caption("※ 이 엔진은 매주 금요일 장 마감 시점에 지난주의 최고 성과 에이전트를 선발하여 다음 주 월요일부터 실전에 투입합니다.")

    st.sidebar.markdown("""
    ### 🕵️ 실전형 엔진 원리
    1. **1주차**: 150명 전원의 성적 모니터링 (실전 투입 없음)
    2. **주말**: 1주차 수익률 1위 선수 선발
    3. **2주차**: 선발된 선수가 실제 매매 수행
    4. **무한 반복**: 매주 챔피언을 교체하며 릴레이
    
    **시각화 가이드**
    - **빨간 실선**: 1위 선수의 매수 구간
    - **초록 가는선**: 1위 선수의 현금 보유 구간
    - **회색선**: 데이터 수집 기간
    """)
