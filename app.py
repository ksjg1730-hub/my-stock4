import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="국내 ETF 주간 분석", layout="wide")

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
            # 데이터 로드 (1개월치 15분봉)
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # Close 데이터 추출
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym].copy()
            else:
                close = df['Close'].copy()
            
            # KST 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- 전주 금요일 14:00 기준가 산출 ---
            year_week = close.index.strftime('%Y-%U')
            
            def get_friday_2pm_base(group):
                week_start = group.index[0]
                prior_data = close[close.index < week_start]
                # 금요일 14:00 타임스탬프 필터링
                friday_points = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 14)]
                if not friday_points.empty:
                    return friday_points.iloc[-1]
                return group.dropna().iloc[0]

            # 최신 Pandas 대응
            base_prices = close.groupby(year_week).apply(get_friday_2pm_base, include_groups=False)
            
            # 수익률 계산
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                b_val = base_prices[wk]
                ret[mask] = ((close[mask] - b_val) / b_val * 100)
            
            # 가중치 적용
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
    st.markdown("##### 🟦 삼성전자 강조 | 🟥 빨간 실선: 금요일 15:30 (장 마감) | 🥈 은(Silver) 2배")

    df, stats = get_weekly_performance_data()
    if df is None:
        st.error("데이터 로딩 실패")
        return

    fig = go.Figure()
    # 표시 순서 고정 (삼성전자가 가장 위)
    plot_order = ['132030.KS', '261240.KS', '144600.KS', '005930.KS']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            display_name = f"{info['name']} [{curr['price']:,.0f} | {curr['ret']:+.2f}%]"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=display_name,
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate=f"<b>{info['name']}</b><br>수익률: %{{y:.2f}}%<extra></extra>"
            ))

    # --- 붉은색 세로줄: 금요일 마감 지점 ---
    friday_ends = df.index[df.index.weekday == 4]
    if not friday_ends.empty:
        unique_weeks = friday_ends.strftime('%Y-%U').unique()
        for wk in unique_weeks:
            wk_friday = friday_ends[friday_ends.strftime('%Y-%U') == wk]
            if not wk_friday.empty:
                last_time = wk_friday[-1] 
                fig.add_vline(x=last_time, line_width=3, line_color="red")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
                dict(bounds=[15.5, 9], pattern="hour"),
            ]
        ),
        yaxis=dict(title="상승률 (%)", range=[-15, 15], ticksuffix="%", zeroline=True, zerolinewidth=3, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_app()
