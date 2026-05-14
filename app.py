import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# ... (페이지 설정 및 데이터 수집 get_silver_15m_data 동일)

def run_stable_advanced_engine(df):
    df['week_grp'] = df['Time'].dt.strftime('%Y-%U')
    unique_weeks = sorted(df['week_grp'].unique())
    
    np.random.seed(42)
    agent_configs = [
        {'id': f"{i}호", 'window': np.random.randint(15, 80), 'threshold': np.random.uniform(0.0001, 0.001)}
        for i in range(1, 151)
    ]

    relay_equity = []
    relay_signals = []
    relay_ids = []
    last_total_equity = 0
    top_3_configs = [] # 지난주 상위 3인

    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) < 5: continue
        
        prices = week_df['Price'].values
        # 1. 봉 완성 후 진입을 위해 모든 에이전트의 '전 봉 기준 신호'를 미리 계산
        agent_signals = {}
        for config in (agent_configs if not top_3_configs else top_3_configs):
            # shift(1)을 통해 t-1봉의 데이터로 t봉의 진입 여부를 결정 (미리보기 방지)
            ma = week_df['Price'].rolling(window=config['window'], min_periods=1).mean().shift(1).values
            sig = np.where(week_df['Price'].values > ma * (1 + config['threshold']), 1, 0)
            agent_signals[config['id']] = np.nan_to_num(sig)

        # 2. 주중 실시간 수익률 계산 및 1등 교체
        returns = np.diff(prices, prepend=prices[0]) / prices
        
        if top_3_configs:
            week_equity = np.zeros(len(prices))
            week_ids = [""] * len(prices)
            week_sigs = np.zeros(len(prices))
            
            # 주중 성적 추적 (3명 중 누가 지금 제일 잘하나?)
            cum_rets = {c['id']: 0.0 for c in top_3_configs}
            
            for t in range(len(prices)):
                best_id = top_3_configs[0]['id']
                max_r = -9999
                # t시점에 각 후보의 '현재까지' 수익 확인
                for config in top_3_configs:
                    cid = config['id']
                    cum_rets[cid] += agent_signals[cid][t] * returns[t] * 2 * 100
                    if cum_rets[cid] > max_r:
                        max_r = cum_rets[cid]
                        best_id = cid
                
                week_equity[t] = max_r + last_total_equity
                week_ids[t] = best_id
                week_sigs[t] = agent_signals[best_id][t]

            relay_equity.extend(week_equity.tolist())
            relay_ids.extend(week_ids)
            relay_signals.extend(week_sigs.tolist())
            last_total_equity = relay_equity[-1]
        else:
            # 첫 주: 선발만 하고 수익은 0
            relay_equity.extend([0.0] * len(prices))
            relay_ids.extend(["선발중"] * len(prices))
            relay_signals.extend([0] * len(prices))

        # 3. 주말: 다음 주를 위한 TOP 3 갱신 (이번 주 성적 기준)
        week_results = []
        for config in agent_configs:
            ma = week_df['Price'].rolling(window=config['window'], min_periods=1).mean().shift(1).values
            sig = np.nan_to_num(np.where(week_df['Price'].values > ma * (1 + config['threshold']), 1, 0))
            r = np.sum(sig * returns * 2) * 100
            week_results.append({'config': config, 'ret': r})
        
        top_3_configs = [x['config'] for x in sorted(week_results, key=lambda x: x['ret'], reverse=True)[:3]]

    # 길이 맞춤
    min_len = min(len(df), len(relay_equity))
    return relay_equity[:min_len], relay_signals[:min_len], relay_ids[:min_len], df.iloc[:min_len]
