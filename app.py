import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="수익률 정밀 분석 (은 지표 추가)", layout="wide")

# 2. 종목 설정
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 5},
    '132030.KS': {'name': '원유선물', 'color': '#E67E22', 'width': 2},
    '261240.KS': {'name': '달러선물', 'color': '#34495E', 'width': 2},
    '144600.KS': {'name': '은선물', 'color': '#BDC3C7', 'width': 2}, # 다시 표시
    '138920.KS': {'name': '금선물', 'color': '#F1C40F', 'width': 0}  # 비율 계산용
}

@st.cache_data(ttl=30)
def get_clean_data():
    raw_data = {}
    for sym in tickers_info.keys():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            col = 'Close'
            series = df[col][sym] if isinstance(df.columns, pd.MultiIndex) else df[col]
            series.index = series.index.tz_convert('Asia/Seoul') if series.index.tz else series.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            raw_data[sym] = series.ffill()
        except: continue

    # 은/금 비율 생성
    if '144600.KS' in raw_data and '138920.KS' in raw_data:
        raw_data['RATIO'] = (raw_data['144600.KS'] / raw_data['138920.KS']).ffill()

    processed_df_list = []
    stats = {}

    # 계산 및 표시 대상 (은선물 추가)
    targets = {
        '005930.KS': '삼성전자', 
        '132030.KS': '원유선물', 
        '261240.KS': '달러선물', 
        '144600.KS': '은선물',
        'RATIO': '은/금 비율'
    }

    for sym, name in targets.items():
        if sym not in raw_data: continue
        
        series = raw_data[sym]
        year_week = series.index.strftime('%Y-%U')
        weekly_returns = []
        
        for wk in year_week.unique():
            wk_data = series[year_week == wk]
            if wk_data.empty: continue
            
            prior_data = series[series.index < wk_data.index[0]]
            base_point = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 14)]
            base_val = base_point.iloc[-1] if not base_point.empty else wk_data.iloc[0]
            
            ret = (wk_data / base_val - 1) * 100
            
            # 배수 적용 로직
            if sym == '261240.KS': ret *= 5   # 달러 x5
            if sym == 'RATIO': ret *= 2       # 은/금비율 x2
            # '144600.KS'(은선물)은 1배수로 표시 (필요시 수정 가능)
            
            weekly_returns.append(ret)
        
        final_series = pd.concat(weekly_returns)
        final_series.name = sym
        processed_df_list.append(final_series)
        
        stats[sym] = {
            'price': series.iloc[-1],
            'pct': final_series.iloc[-1]
        }

    return pd.concat(processed_df_list, axis=1).ffill(), stats

def run_app():
    st.title("📊 주간 수익률 변동 분석")
    st.markdown("##### 🟦 삼성전자 | 🥈 은선물(1배) & (은/금)비율(2배) | 🟥 금요일 마감선")
    
    df, stats = get_clean_data()
    if df is None: return

    fig = go.Figure()

    style = {
        '005930.KS': ('#0057D8', 6, '삼성전자'),
        '132030.KS': ('#E67E22', 2, '원유선물'),
        '261240.KS': ('#34495E', 2, '달러선물(x5)'),
        '144600.KS': ('#7F8C8D', 2, '은선물'),        # 진한 회색
        'RATIO': ('#8E44AD', 3, '(은/금)비율(x2)')   # 보라색
    }

    for sym, (color, width, name) in style.items():
        if sym in df.columns:
            s = stats[sym]
            p_label = f"{s['price']:.4f}" if sym == 'RATIO' else f"{s['price']:,.0f}"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{name} [{p_label} | {s['pct']:+.2f}%]",
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
