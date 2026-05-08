import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="국내 ETF 수익률 비교 분석", layout="wide")

# 2. 종목 설정 (금 데이터 138920.KS 포함)
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 5},
    '132030.KS': {'name': 'KODEX 원유선물(H)', 'color': '#E67E22', 'width': 2},
    '261240.KS': {'name': 'KODEX 미국달러선물', 'color': '#34495E', 'width': 2},
    '144600.KS': {'name': 'KODEX 은선물(H)', 'color': '#BDC3C7', 'width': 2},
    '138920.KS': {'name': 'KODEX 골드선물(H)', 'color': '#F1C40F', 'width': 0} # 계산용
}

@st.cache_data(ttl=30)
def get_processed_data():
    raw_data = {}
    # 데이터 다운로드
    for sym in tickers_info.keys():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            close = df['Close'][sym].copy() if isinstance(df.columns, pd.MultiIndex) else df['Close'].copy()
            # KST 변환
            close.index = close.index.tz_convert('Asia/Seoul') if close.index.tz else close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            raw_data[sym] = close
        except: continue

    if '144600.KS' in raw_data and '138920.KS' in raw_data:
        # 은/금 비율 생성 (가격 데이터)
        raw_data['SILVER_GOLD_RATIO'] = raw_data['144600.KS'] / raw_data['138920.KS']

    combined_list = []
    stats = {}

    for sym, series in raw_data.items():
        if sym == '138920.KS': continue # 금 자체는 표시 제외
        
        year_week = series.index.strftime('%Y-%U')
        
        # --- 전주 금요일 14:00 기준가(0%) 추출 함수 ---
        def get_base_val(group):
            prior = series[series.index < group.index[0]]
            f_point = prior[(prior.index.weekday == 4) & (prior.index.hour == 14)]
            return f_point.iloc[-1] if not f_point.empty else group.dropna().iloc[0]

        # 주차별 기준가격 계산
        bases = series.groupby(year_week).apply(get_base_val, include_groups=False)
        
        # % 수익률로 변환 (모든 종목을 동일한 스케일로 만듦)
        pct_change = series.copy()
        for wk in year_week.unique():
            m = (year_week == wk)
            b = bases[wk]
            pct_change[m] = ((series[m] - b) / b * 100)
        
        # 배수 적용
        if sym == '261240.KS': pct_change *= 5       # 달러 x5
        if sym == 'SILVER_GOLD_RATIO': pct_change *= 2 # 은/금 비율 x2
        
        stats[sym] = {'last_price': series.iloc[-1], 'last_pct': pct_change.iloc[-1]}
        pct_change.name = sym
        combined_list.append(pct_change)

    return pd.concat(combined_list, axis=1).ffill(), stats

def run_app():
    st.title("📊 주간 수익률 동기화 분석")
    st.markdown("##### 🟥 빨간 실선: 금요일 마감 | 🥈 모든 선은 전주 금요일 14:00 대비 % 변동률")

    df, stats = get_processed_data()
    if df is None: return

    fig = go.Figure()
    
    # 그릴 종목 정의
    display_map = {
        '005930.KS': ('삼성전자', '#0057D8', 6),
        '132030.KS': ('원유선물', '#E67E22', 2),
        '261240.KS': ('달러선물(x5)', '#34495E', 2),
        '144600.KS': ('은선물', '#BDC3C7', 2),
        'SILVER_GOLD_RATIO': ('(은/금)비율(x2)', '#8E44AD', 3)
    }

    for sym, (name, color, width) in display_map.items():
        if sym in df.columns:
            s = stats[sym]
            price_str = f"{s['last_price']:.4f}" if "RATIO" in sym else f"{s['last_price']:,.0f}"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{name} [{price_str} | {s['last_pct']:+.2f}%]",
                line=dict(color=color, width=width),
                connectgaps=True
            ))

    # 금요일 마감선 (15:30)
    fri_ends = df.index[df.index.weekday == 4]
    for wk in fri_ends.strftime('%Y-%U').unique():
        last_t = fri_ends[fri_ends.strftime('%Y-%U') == wk][-1]
        fig.add_vline(x=last_t, line_width=2, line_color="red")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[15.5, 9], pattern="hour")]),
        yaxis=dict(title="수익률 (%)", range=[-12, 12], ticksuffix="%"),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_app()
