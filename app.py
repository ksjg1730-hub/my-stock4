import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="24H 글로벌 자산 분석기", layout="wide")

# 2. 종목 설정 (구리, 반도체, 은, 달러/유가)
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 2},      # 구리색
    'SOX': {'name': '필라델피아 반도체', 'color': '#0057D8', 'width': 4}, # 강조(청색)
    'SI=F': {'name': '글로벌 은', 'color': '#95A5A6', 'width': 2},      # 은색
    'CL=F': {'name': 'WTI 원유', 'color': '#27AE60', 'width': 1.5},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 1.5}
}

@st.cache_data(ttl=30)
def get_performance_data():
    combined_df = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            # 심볼 처리 (SOX 지수는 ^SOX로 호출)
            ticker_sym = f"^{sym}" if sym == "SOX" else sym
            df = yf.download(ticker_sym, period='1mo', interval='15m', progress=False)
            
            if df.empty: continue
            
            close = df['Close'][ticker_sym] if isinstance(df.columns, pd.MultiIndex) else df['Close']
            close = close.dropna()
            
            # KST 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # 기준점 설정 (매주 금요일 13:00 / 아직 안 왔으면 해당 주 시가)
            year_week = close.index.strftime('%G-%V')
            
            def get_base_price(series):
                target = series[(series.index.weekday == 4) & (series.index.hour == 13)]
                return target.iloc[0] if not target.empty else series.iloc[0]

            base_price = close.groupby(year_week).transform(get_base_price)
            
            # 수익률 계산
            ret = ((close - base_price) / base_price * 100)
            if sym == 'DX-Y.NYB': ret *= 5 # 달러지수 레버리지 효과
            
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
        
    return pd.concat(combined_df, axis=1) if combined_df else (None, {})

def run_app():
    st.title("📊 글로벌 주요 자산 24H 실시간 분석")
    st.markdown("##### 🟦 필라델피아 반도체 강조 | ⬛ 기준: 매주 금요일 13:00 (0%) | 🌙 전 종목 24시간 추적")

    df, stats = get_performance_data()
    if df is None or not stats:
        st.error("데이터 로딩 중입니다. 잠시 후 새로고침 해주세요.")
        return

    fig = go.Figure()
    # 그리기 순서 (강조할 종목을 나중에 배치)
    plot_order = ['CL=F', 'DX-Y.NYB', 'HG=F', 'SI=F', 'SOX']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({curr['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate=f"<b>{info['name']}</b>: %{{y:.2f}}%<extra></extra>"
            ))

    # 금요일 13시 기준선 표시
    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified",
        height=750,
        template="plotly_white",
        xaxis=dict(
            title="일시 (KST)",
            tickformat="%m/%d %H:%M",
            rangebreaks=[dict(bounds=["sat", "mon"])] # 주말만 삭제
        ),
        yaxis=dict(
            title="수익률 (%)",
            range=[-20, 20],
            ticksuffix="%",
            zeroline=True, zerolinewidth=2, zerolinecolor='black'
        ),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 지표 카드 (5열 배치)
    cols = st.columns(len(plot_order))
    for i, sym in enumerate(plot_order):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")

if __name__ == "__main__":
    run_app()
