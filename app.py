import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# ... (기존 설정 및 데이터 수집 부분 동일)

def run_advanced_relay_engine(df):
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
    
    # 지난주 TOP 3 후보군
    top_3_candidates = []

    for week in unique_weeks:
        week_df = df[df['week_grp'] == week].copy()
        if len(week_df) == 0: continue
        
        prices = week_df['Price'].values
        # 수익률 계산 시점을 한 봉 뒤로 미룸 (봉 완성 후 다음 봉 시가/종가 매매 가정)
        returns = np.diff(prices, prepend=prices[0]) / prices 

        if len(top_3_candidates) > 0:
            # --- [주중 실시간 1등 선발 로직] ---
            # 지난주 TOP 3 중 현재(주중) 가장 수익이 좋은 선수를 매 시점 찾음
            week_best_equity = np.zeros(len(prices))
            week_best_signals = np.zeros(len(prices))
            week_best_ids = [""] * len(prices)
            
            # 주중 누적 수익 추적용
            candidate_performances = {c['id']: 0 for c in top_3_candidates}
            
            for t in range(1, len(prices)):
                best_id_at_t = top_3_candidates[0]['id']
                max_perf = -9999
                
                for config in top_3_candidates:
                    # 봉 완성 기준: t-1 시점까지의 데이터로 MA 계산
                    sub_prices = prices[:t]
                    if len(sub_prices) < config['window']:
                        current_sig = 0
                    else:
                        ma = np.mean(sub_prices[-config['window']:])
                        # t-1 시점 봉 완성 후 신호 발생 -> t 시점에 진입
                        current_sig = 1 if sub_prices[-1] > ma * (1 + config['threshold']) else 0
                    
                    # 실시간 성적 업데이트
                    candidate_performances[config['id']] += current_sig * returns[t] * 2 * 100
                    
                    if candidate_performances[config['id']] > max_perf:
                        max_perf = candidate_performances[config['id']]
                        best_id_at_t = config['id']
                        active_sig = current_sig
                
                week_best_ids[t] = best_id_at_t
                week_best_signals[t] = active_sig
                week_best_equity[t] = max_perf

            relay_equity.extend((week_best_equity + last_total_equity).tolist())
            relay_signals.extend(week_best_signals.tolist())
            relay_ids.extend(week_best_ids)
            last_total_equity = relay_equity[-1]
            
        else:
            # 데이터 수집 주차
            relay_equity.extend([0.0] * len(prices))
            relay_signals.extend([0] * len(prices))
            relay_ids.extend(["선발중"] * len(prices))

        # --- [주말: 다음 주를 위한 TOP 3 선발] ---
        all_agent_rets = []
        for config in agent_configs:
            ma_full = pd.Series(prices).rolling(window=config['window']).mean().shift(1).values # 한 봉 뒤로 밀림
            sig_full = np.where(prices > ma_full * (1 + config['threshold']), 1, 0)
            sig_full = np.nan_to_num(sig_full)
            total_ret = np.sum(sig_full * returns * 2) * 100
            all_agent_rets.append({'config': config, 'ret': total_ret})
        
        # 성적순 정렬 후 상위 3명 추출
        top_3_candidates = [x['config'] for x in sorted(all_agent_rets, key=lambda x: x['ret'], reverse=True)[:3]]

    min_len = min(len(df), len(relay_equity))
    return relay_equity[:min_len], relay_signals[:min_len], relay_ids[:min_len], df.iloc[:min_len]
