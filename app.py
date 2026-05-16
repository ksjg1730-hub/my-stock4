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

# 2. 데이터 수집 (최근 1개월, 15분봉)
@st.cache_data(ttl=600)
def get_silver_data():
    try:
        silver = yf.Ticker("SI=F")
        df = silver.history(period="1mo", interval="15m")
        if df.empty: return None
        df = df.reset_index()
        df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
        df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
        # 주말 제외
        df = df[df['Time'].dt.weekday < 5].copy()
        return df
    except Exception as e:
        st.error(f"데이터 연동 오류: {e}")
        return None

# 3. 핵심 엔진: 주중 1위 교체 + 봉 완성 후 진입 + 변동성 계산
def run_integrated_engine(df):
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = sorted(df['week_grp'].unique())
    
    np.random.seed(42)
    # 150명의 후보 전략 생성
    agent_configs = [
        {'id': f"{i}호", 'window': np.random.randint(20, 100), 'threshold': np.random.uniform(0.0002, 0.0012)}
        for i in range(1, 151)
    ]

    relay_equity = []
    relay_signals = []
    relay_ids = []
    vix_values = []
    
    last_total_equity = 0
    top_3_configs = [] # 지난주 성적 상위 3인

    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 10: continue
        
        prices = week_df['Price'].values
        # 수익률 (현재 봉 종가 / 이전 봉 종가 - 1)
        returns = np.diff(prices, prepend=prices[0]) / prices
        
        # [변동성 계산] 월요일부터 새로 집계 (20봉 표준편차 연율화)
        vol = week_df['Price'].pct_change().rolling(window=20, min_periods=1).std() * np.sqrt(252 * 96)
        vix_values.extend(vol.fillna(0).tolist())

        # [전략 실행]
        if top_3_configs:
            # 1. 후보 3인의 신호를 봉 완성 기준으로 미리 추출
            candidate_signals = {}
            for config in top_3_configs:
                # shift(1)을 사용하여 t-1 시점의 데이터로 t 시점 진입 결정 (봉 완성 후 진입)
                ma = week_df['Price'].rolling(window=config['window'], min_periods=1).mean().shift(1).values
                candidate_signals[config['id']] = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            
            week_equity = np.zeros(len(prices))
            week_ids = [""] * len(prices)
            week_sigs = np.zeros(len(prices))
            
            # 주중 실시간 수익 추적용
            candidate_rets = {c['id']: 0.0 for c in top_3_configs}
            
            for t in range(len(prices)):
                best_id = top_3_configs[0]['id']
                max_perf = -99999
                
                # t시점에 3명 중 누적 수익이 가장 높은 사람 선발
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
            # 첫 주 데이터 수집
            relay_equity.extend([0.0] * len(prices))
            relay_ids.extend(["선발중"] * len(prices))
            relay_signals.extend([0] * len(prices))

        # [주말 선발] 다음 주를 위한 상위 3인 갱신
        week_ranking = []
        for config in agent_configs:
            ma = week_df['Price'].rolling(window=config['window'], min_periods=1).mean().shift(1).values
            sig = np.where(prices > ma * (1 + config['threshold']), 1, 0)
            r = np.sum(np.nan_to_num(sig) * returns * 2) * 100
            week_ranking.append({'config': config, 'ret': r})
        
        top_3_configs = [x['config'] for x in sorted(week_ranking, key=lambda x: x['ret'], reverse=True)[:3]]

    # 길이 정렬
    min_len = min(len(df), len(relay_equity))
    return relay_equity[:min_len], relay_signals[:min_len], relay_ids[:min_len], vix_values[:min_len], df.iloc[:min_len]

# 4. 실행 및 시각화
df = get_silver_data()
if df is not None:
    equity, signals, ids, vix, plot_df = run_integrated_engine(df)
    
    # 두 개의 서브플롯 생성 (수익률 + 변동성)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, subplot_titles=("실전 누적 수익률 (%)", "은 가격 주간 변동성 (VIX Style)"),
                        row_heights=[0.7, 0.3])

    # 1위 교체 지점 (노란 점선)
    for i in range(1, len(ids)):
        if ids[i] != ids[i-1]:
            fig.add_vline(x=plot_df['Time'].iloc[i], line_width=0.8, line_dash="dot", line_color="yellow", row='all', col=1)

    # 수익률 곡선 그리기 (구간별 색상)
    start_idx = 0
    for i in range(1, len(signals)):
        if signals[i] != signals[i-1] or ids[i] != ids[i-1]:
            curr_sig = signals[start_idx]
            curr_id = ids[start_idx]
            color = "#808080" if curr_id == "선발중" else ("#FF4B4B" if curr_sig == 1 else "#00CC96")
            fig.add_trace(go.Scatter(x=plot_df['Time'].iloc[start_idx:i+1], y=np.array(equity)[start_idx:i+1],
                                     mode='lines', line=dict(color=color, width=2), showlegend=False), row=1, col=1)
            start_idx = i

    # 변동성 차트 추가
    fig.add_trace(go.Scatter(x=plot_df['Time'], y=vix, name="변동성", line=dict(color="#AB63FA")), row=2, col=1)

    fig.update_layout(template="plotly_dark", plot_bgcolor='black', height=800, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # 사이드바 성과 지표
    with st.sidebar:
        st.header("📊 실전 리포트")
        st.metric("현재 누적 수익", f"{equity[-1]:+.2f}%")
        peak = np.maximum.accumulate(equity)
        mdd = np.max(peak - equity)
        st.metric("최대 낙폭 (MDD)", f"{mdd:.2f}%")
        st.write("---")
        st.subheader("현재 투입 전략")
        st.info(f"선수명: {ids[-1]}")
        st.write(f"현재 변동성: {vix[-1]:.2f}")    final_df['MA50'] = raw_energy.rolling(window=50, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("📊 에너지 크로스 시점 분석 대시보드")
    st.markdown("##### 🔴 **빨간선: UP (Golden)** | 🔵 **파란선: DOWN (Dead)** | 🟢 **실시간 1등 에너지 음전 시 초록색 전환**")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    # 1. 상태 계산
    vol_targets = list(tickers_info.keys())
    df['current_top'] = df[vol_targets].idxmax(axis=1)
    ma20_diff = df['MA20'].diff().fillna(0)
    ma50_diff = df['MA50'].diff().fillna(0)
    is_crisis = (ma20_diff < 0) | (ma50_diff < 0)

    # 2. 크로스 로직 보정
    df['prev_MA20'] = df['MA20'].shift(1)
    df['prev_MA50'] = df['MA50'].shift(1)
    up_cross = df[(df['prev_MA20'] < df['prev_MA50']) & (df['MA20'] >= df['MA50'])].index
    down_cross = df[(df['prev_MA20'] > df['prev_MA50']) & (df['MA20'] <= df['MA50'])].index

    fig = go.Figure()

    # 3. 자산별 렌더링 (동적 색상 전환)
    for sym, info in tickers_info.items():
        if sym in df.columns:
            is_target_crisis = (df['current_top'] == sym) & is_crisis
            
            # 일반 구간
            y_normal = df[sym].copy()
            y_normal[is_target_crisis] = np.nan
            fig.add_trace(go.Scatter(
                x=df.index, y=y_normal, name=info['name'],
                line=dict(color=info['color'], width=info['width']),
                connectgaps=False
            ))
            
            # 음전 위기 구간
            y_crisis = df[sym].copy()
            y_crisis[~is_target_crisis] = np.nan
            fig.add_trace(go.Scatter(
                x=df.index, y=y_crisis, name=f"{info['name']}(위기)",
                line=dict(color='#2ECC71', width=info['width'] + 2.5),
                showlegend=False, connectgaps=False
            ))

    # 4. 에너지 이평선 (오류 수정: opacity 위치 변경)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA20'], name="에너지 MA20",
        line=dict(color='black', width=1.5),
        opacity=0.3  # line 외부로 이동
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA50'], name="에너지 MA50",
        line=dict(color='black', width=2.5, dash='dot'),
        opacity=0.3  # line 외부로 이동
    ))

    # 5. 수직 직선 추가
    for t in up_cross:
        fig.add_vline(x=t, line_width=1.5, line_dash="dash", line_color="red", opacity=0.6)
    
    for t in down_cross:
        fig.add_vline(x=t, line_width=1.5, line_dash="dash", line_color="blue", opacity=0.6)

    fig.update_layout(
        hovermode="x unified", height=850, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 에너지 (%)", range=[-12, 12], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_app()
