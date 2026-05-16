import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Silver Real-time Strategy & Vol", layout="wide")
st.title("🏆 은(Silver) 실전 릴레이 및 주간 변동성 분석")
st.markdown("지난주 상위 3인 중 **주중 현재 1위**를 실시간으로 추적하며, **봉 완성 후 진입**을 준수합니다.")

# 2. 데이터 수집 함수
@st.cache_data(ttl=600)
def get_silver_data():
    try:
        silver = yf.Ticker("SI=F")
        # 최근 1개월 15분봉 데이터 호출
        df = silver.history(period="1mo", interval="15m")
        
        if df is None or df.empty:
            return None
            
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        # 한국 시간 변환
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 제외
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 로딩 오류: {e}")
        return None

# 3. 분석 엔진 함수 (내부에 직접 포함)
def run_integrated_engine(df):
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = sorted(df['week_grp'].unique())
    
    np.random.seed(42)
    agent_configs = [
        {'id': f"{i}호", 'window': np.random.randint(20, 100), 'threshold': np.random.uniform(0.0002, 0.0012)}
        for i in range(1, 151)
    ]

    relay_equity = []
    relay_signals = []
    relay_ids = []
    vix_values = []
    
    last_total_equity = 0
    top_3_configs = [] 

    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 10: continue
        
        prices = week_df['Price'].values
        returns = np.diff(prices, prepend=prices[0]) / prices
        
        # 주간 변동성 계산
        vol = week_df['Price'].pct_change().rolling(window=20, min_periods=1).std() * np.sqrt(252 * 96)
        vix_values.extend(vol.fillna(0).tolist())

        if top_3_configs:
            candidate_signals = {}
            for config in top_3_configs:
                ma = week_df['Price'].rolling(window=config['window'], min_periods=1).mean().shift(1).values
                candidate_signals[config['id']] = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            
            week_equity = np.zeros(len(prices))
            week_ids = [""] * len(prices)
            week_sigs = np.zeros(len(prices))
            candidate_rets = {c['id']: 0.0 for c in top_3_configs}
            
            for t in range(len(prices)):
                best_id = top_3_configs[0]['id']
                max_perf = -999999
                for config in top_3_configs:
                    cid = config['id']
                    candidate_rets[cid] += candidate_signals[cid][t] * returns[t] * 2 * 100
                    if candidate_rets[cid] > max_perf:
                        max_perf = candidate_rets[cid]
                        best_id = cid
                week_equity[t] = max_perf + last_total_equity
                week_ids[t] = best_id
                week_sigs[t] = candidate_signals[best_id][t]

            relay_equity.extend(week_equity.tolist())
            relay_ids.extend(week_ids)
            relay_signals.extend(week_sigs.tolist())
            last_total_equity = relay_equity[-1]
        else:
            relay_equity.extend([0.0] * len(prices))
            relay_ids.extend(["선발중"] * len(prices))
            relay_signals.extend([0] * len(prices))

        # 주말 선발 로직
        week_ranking = []
        for config in agent_configs:
            ma = week_df['Price'].rolling(window=config['window'], min_periods=1).mean().shift(1).values
            sig = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            r = np.sum(np.nan_to_num(sig) * returns * 2) * 100
            week_ranking.append({'config': config, 'ret': r})
        top_3_configs = [x['config'] for x in sorted(week_ranking, key=lambda x: x['ret'], reverse=True)[:3]]

    min_len = min(len(df), len(relay_equity))
    return relay_equity[:min_len], relay_signals[:min_len], relay_ids[:min_len], vix_values[:min_len], df.iloc[:min_len]

# 4. 실행 및 출력
raw_df = get_silver_data()

if raw_df is not None:
    equity, signals, ids, vix, plot_df = run_integrated_engine(raw_df)
    
    # 그래프 생성
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.08, subplot_titles=("📈 실전 누적 수익률 (%)", "📉 주간 변동성 추이 (VIX Style)"),
                        row_heights=[0.7, 0.3])

    for i in range(1, len(ids)):
        if ids[i] != ids[i-1]:
            fig.add_vline(x=plot_df['Time'].iloc[i], line_width=0.8, line_dash="dot", line_color="yellow", row='all', col=1)

    start_idx = 0
    for i in range(1, len(signals)):
        if signals[i] != signals[i-1] or ids[i] != ids[i-1]:
            curr_sig = signals[start_idx]
            curr_id = ids[start_idx]
            color = "#808080" if curr_id == "선발중" else ("#FF4B4B" if curr_sig == 1 else "#00CC96")
            fig.add_trace(go.Scatter(x=plot_df['Time'].iloc[start_idx:i+1], y=np.array(equity)[start_idx:i+1],
                                     mode='lines', line=dict(color=color, width=2.5), showlegend=False), row=1, col=1)
            start_idx = i

    fig.add_trace(go.Scatter(x=plot_df['Time'], y=vix, name="변동성", line=dict(color="#AB63FA", width=1.5)), row=2, col=1)
    fig.update_layout(template="plotly_dark", plot_bgcolor='black', height=800)
    st.plotly_chart(fig, use_container_width=True)

    with st.sidebar:
        st.header("🏁 실전 요약")
        st.metric("누적 수익률", f"{equity[-1]:+.2f}%")
        peak = np.maximum.accumulate(equity)
        mdd = np.max(peak - equity)
        st.metric("최대 낙폭(MDD)", f"{mdd:.2f}%")
        st.write("---")
        st.success(f"현재 투입: {ids[-1]}")
        st.info(f"변동성: {vix[-1]:.4f}")
else:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
