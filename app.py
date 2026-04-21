import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="주간 수익률 분석 (금요일 2시 기준)", layout="wide")

# 2. 국내 종목 설정
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 6},
    '132030.KS': {'name': 'KODEX 원유선물(H)', 'color': '#E67E22', 'width': 2},
    '261240.KS': {'name': 'KODEX 미국달러선물(x5)', 'color': '#34495E', 'width': 2},
    '144600.KS': {'name': 'KODEX 은선물(H)(x2)', 'color': '#BDC3C7', 'width': 2}
}

@st.cache_data(ttl=30)
def get_weekly_performance_data():
    combined_df_list = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            close = df['Close'][sym].copy() if isinstance(df.columns, pd.MultiIndex) else df['Close'].copy()
            
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            year_week = close.index.strftime('%Y-%U')
            
            def get_friday_2pm_base(group):
                week_start = group.index[0]
                prior_data = close[close.index < week_start]
                friday_points = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 14)]
                if not friday_points.empty:
                    return friday_points.iloc[-1]
                return group.dropna().iloc[0]

            base_prices = close.groupby(year_week).apply(get_friday_2pm_base, include_groups=False)
            
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                b_val = base_prices[wk]
                ret[mask] = ((close[mask] - b_val) / b_val * 100)
            
            if sym == '261240.KS': ret *= 5   # 달러 x5
            if sym == '144600.KS': ret *= 2   # 은 x2
            
            current_stats[sym] = {'price': close.dropna().iloc[-1], 'ret': ret.dropna().iloc[-1]}
            ret.name = sym
            combined_df_list.append(ret)
        except: continue
    
    if not combined_df_list: return None, None
    return pd.concat(combined_df_list, axis=1).ffill(), current_stats

def run_app():
    st.title("📈 주간 수익률 분석 (기준: 전주 금요일 14:00)")
    st.markdown("##### 🟦 삼성전자 강조 | 🟥 빨간 실선: 전주 금요일 15:30 (장 마감) | 🥈 은(Silver) 2배")

    df, stats = get_weekly_performance_data()
    if df is None:
        st.error("데이터 로딩 실패")
        return

    fig = go.Figure()
    plot_order = ['13
