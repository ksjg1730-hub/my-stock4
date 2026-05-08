import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="국내 ETF 및 은/금 비율 분석", layout="wide")

# 2. 종목 설정 (금 데이터는 계산용으로만 사용하거나 표시 가능)
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 5},
    '132030.KS': {'name': 'KODEX 원유선물(H)', 'color': '#E67E22', 'width': 2},
    '261240.KS': {'name': 'KODEX 미국달러선물(x5)', 'color': '#34495E', 'width': 2},
    '144600.KS': {'name': 'KODEX 은선물(H)', 'color': '#BDC3C7', 'width': 2},
    '138920.KS': {'name': 'KODEX 골드선물(H)', 'color': '#F1C40F', 'width': 0} # 계산용 (차트 미표시 시 width=0)
}

@st.cache_data(ttl=30)
def get_weekly_performance_data():
    combined_list = []
    current_stats = {}
    
    # 데이터 다운로드
    raw_data = {}
    for sym in tickers_info.keys():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            close = df['Close'][sym].copy() if isinstance(df.columns, pd.MultiIndex) else df['Close'].copy()
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')
            raw_data[sym] = close
        except: continue

    if '144600.KS' in raw_data and '138920.KS' in raw_data:
        # --- [핵심] (은 가격 / 금 가격) 비율 생성 ---
        ratio_series = raw_data['144600.KS'] / raw_data['138920.KS']
        raw_data['SILVER_GOLD_RATIO'] = ratio_series

    # 기준 주차별 수익률 계산
    for sym, close in raw_data.items():
        if sym == '138920.KS': continue # 금 자체는 차트에서 제외 (비율 계산용)
        
        year_week = close.index.strftime('%Y-%U')
        
        def get_base(group):
            prior = close[close.index < group.index[0]]
            f_point = prior[(prior.index.weekday == 4) & (prior.index.hour == 14)]
            return f_point.iloc[-1] if not f_point.empty else group.dropna().iloc[0]

        base_prices = close.groupby(year_week).apply(lambda x: get_base(x), include_groups=False)
        
        ret = close.copy()
        for wk in year_week.unique():
            mask = (year_week == wk)
            b_val = base_prices[wk]
            ret[mask] = ((close[mask] - b_val) / b_val * 100)
        
        # 가중치 적용
        if sym == '261240.KS': ret *= 5       # 달러 x5
        if sym == 'SILVER_GOLD_RATIO': ret *= 2 # (은/금) 비율 x2 레버리지 (요청사항)
        
        current_stats[sym] = {'price': close.dropna().iloc[-1], 'ret': ret.dropna().iloc[-1]}
        ret.name = sym
        combined_list.append(ret)

    if not combined_list: return None, None
    return pd.concat(combined_list, axis=1).ffill(), current_stats

def run_app():
    st.title("📈 국내 ETF 및 (은/금) 비율 분석")
    st.markdown("##### 🟦 삼성전자 | 🟥 금요일 마감선 | 🥈 (은 가격 / 금 가격) 레버리지 2배 추가")

    df, stats = get_weekly_performance_data()
    if df is None: return

    fig = go.Figure()
    
    # 렌더링 순서 및 정보 설정
    custom_names = {
        '005930.KS': '삼성전자',
        '132030.KS': 'KODEX 원유선물',
        '261240.KS': 'KODEX 달러(x5)',
        '144600.KS': 'KODEX 은선물',
        'SILVER_GOLD_RATIO': '(은/금) 비율 x2'
    }
    colors = {'005930.KS': '#0057D8', '132030.KS': '#E67E22', '261240.KS': '#34495E', 
              '144600.KS': '#BDC3C7', 'SILVER_GOLD_RATIO': '#8E44AD'}

    for sym in custom_names.keys():
        if sym in df.columns:
            curr = stats[sym]
            width = 6 if sym == '005930.KS' else 2
            display_price = f"{curr['price']:.4f}" if sym == 'SILVER_GOLD_RATIO' else f"{curr['price']:,.0f}"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{custom_names[sym]} [{display_price} | {curr['ret']:+.2f}%]",
                line=dict(color=colors[sym], width=width),
                connectgaps=True
            ))

    # 금요일 마감 붉은 선
    friday_ends = df.index[df.index.weekday == 4]
    if not friday_ends.empty:
        for wk in friday_ends.strftime('%Y-%U').unique():
            last_time = friday_ends[friday_ends.strftime('%Y-%U') == wk][-1]
            fig.add_vline(x=last_time, line_width=2, line_color="red")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[15.5, 9], pattern="hour")]),
        yaxis=dict(title="수익률 (%)", range=[-15, 15], ticksuffix="%", zeroline=True, zerolinewidth=3),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_app()
