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
        # 주말 제외 (해외 선물 시장 기준)
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
                max_perf = -999999
                
                # t시점에 3명 중 주중 누적 수익이 가장 높은 사람 선발
                for config in top_3_configs:
                    cid = config['id']
                    # 이번 봉의 수익을 후보군 각자에게 가산
                    candidate_rets
