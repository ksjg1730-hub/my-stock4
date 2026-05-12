import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="종합 자산 분석기 (금/구리 비율)", layout="wide")

# 2. 종목 설정 (국내 ETF 기준)
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 5},
    '132030.KS': {'name': '원유선물', 'color': '#E67E22', 'width': 2},
    '261240.KS': {'name': '달러선물(x5)', 'color': '#34495E', 'width': 2},
    '144600.KS': {'name': '은선물', 'color': '#7F8C8D', 'width': 2},
    '138920.KS': {'name': '금선물', 'color': '#F1C40F', 'width': 2}, # 금 다시 추가
    '138910.KS': {'name': '구리선물', 'color': '#C36428', 'width': 2} # 구리 추가
}

@st.cache_data(ttl=30)
def get_processed_data():
    raw_data = {}
    for sym in tickers_info.keys():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            series = df['Close'][sym] if isinstance(df.columns, pd.MultiIndex) else df['Close']
            if series.index.tz is None:
                series.index = series.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                series.index = series.index.tz_convert('Asia/Seoul')
            raw_data[sym] = series.ffill()
        except: continue

    # 금/구리 비율 생성 (Gold / Copper)
    if '138920.KS' in raw_data and '138910.KS' in raw_data:
        raw_data['GC_RATIO'] = (raw_data['138920.KS'] / raw_data['138910.KS']).ffill()

    processed_list = []
    stats = {}
    targets = {
        '005930.KS': '삼성전자', '132030.KS': '원유선물', 
        '261240.KS': '달러선물', '144600.KS': '은선물',
        '138920.KS': '금선물', '138910.KS': '구리선물', 
        'GC_RATIO': '금/구리 비율'
    }

    for sym, name in targets.items():
        if sym not in raw_data: continue
        series = raw_data[sym]
        year_week = series.index.strftime('%Y-%U')
        weekly_returns = []

        for wk in year_week.unique():
            wk_data = series[year_week == wk]
            prior = series[series.index < wk_data.index[0]]
            # 기준점: 전주 금요일 14:00
            base_point = prior[(prior.index.weekday == 4) & (prior.index.hour == 14)]
            base_val = base_point.iloc[-1] if not base_point.empty else wk_data.iloc[0]
            
            ret = (wk_data / base_val - 1) * 100
            if sym == '261240.KS': ret *= 5   # 달러 x5
            if sym == 'GC_RATIO': ret *= 2    # 비율 변동 강조 (x2)
            weekly_returns.append(ret)
        
        final_ret = pd.concat(weekly_returns)
        final_ret.name = sym
        processed_list.append(final_ret)
        stats[sym] = {'price': series.iloc[-1], 'pct': final_ret.iloc[-1]}

    return pd.concat(processed_list, axis=1).ffill(), stats

def run_app():
    st.title("📊 자산 종합 분석 (금/구리 비율 지표)")
    st.markdown("##### 🟦 삼성전자 | 🟠 구리 | 🟡 금 | 📉 금/구리 비율(x2) | 🟥 금요일 마감")

    df, stats = get_processed_data()
    if df is None: return

    fig = go.Figure()
    # 스타일 정의
    style = {
        '005930.KS': ('#0057D8', 6, '삼성전자'),
        '132030.KS': ('#E67E22', 2, '원유'),
        '261240.KS': ('#34495E', 1, '달러(x5)'),
        '144600.KS': ('#7F8C8D', 1, '은'),
        '138920.KS': ('#F1C40F', 2, '금'),
        '138910.KS': ('#C36428', 2, '구리'),
        'GC_RATIO': ('#1ABC9C', 4, '(금/구리)비율(x2)') # 청록색 강조
    }

    for sym in style.keys():
        if sym in df.columns:
            color, width, name = style[sym]
            s = stats[sym]
            p_val = f"{s['price']:.4f}" if sym == 'GC_RATIO' else f"{s['price']:,.0f}"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{name} [{p_val} | {s['pct']:+.2f}%]",
                line=dict(color=color, width=width),
                connectgaps=True
            ))

    # 금요일 마감선
    fri_ends = df.index[df.index.weekday == 4]
    for wk in fri_ends.strftime('%Y-%U').unique():
        last_t = fri_ends[fri_ends.strftime('%Y-%U') == wk][-1]
        fig.add_vline(x=last_t, line_width=2, line_color="red")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[15.5, 9], pattern="hour")]),
        yaxis=dict(title="수익률 변동 (%)", range=[-15, 15], ticksuffix="%"),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_app()
