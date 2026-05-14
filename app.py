import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 자산 실시간 분석", layout="wide")

# 2. 종목 설정 (반도체 완전 제거)
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 2.5},
    'SI=F': {'name': '글로벌 은', 'color': '#7F8C8D', 'width': 2.5},
    'CL=F': {'name': 'WTI 원유', 'color': '#27AE60', 'width': 2},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#2C3E50', 'width': 2}
}

@st.cache_data(ttl=60)
def get_performance_data():
    combined_df = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 데이터 추출 (MultiIndex 대응)
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym]
            else:
                close = df['Close']

            close = close.dropna()
            
            # 한국 시간(KST) 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # 기준점 설정 (매주 금요일 13:00)
            year_week = close.index.strftime('%G-%V')
            def get_base_price(series):
                target = series[(series.index.weekday == 4) & (series.index.hour == 13)]
                return target.iloc[0] if not target.empty else series.iloc[0]

            base_price = close.groupby(year_week).transform(get_base_price)
            ret = ((close - base_price) / base_price * 100)
            
            if sym == 'DX-Y.NYB': ret *= 5 # 달러지수 가중치 적용
            
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
            
    if not combined_df: return None, {}
    return pd.concat(combined_df, axis=1), current_stats

def run_app():
    st.title("📊 4대 매크로 자산 24H 실시간 분석")
    st.markdown("##### ⬛ 기준: 매주 금요일 13:00 (0%) | 🌙 구리·은·원유·달러 24시간 추적")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다. 잠시만 기다려주세요.")
        return

    # 메인 차트 하나로 구성
    fig = go.Figure()
    plot_order = ['CL=F', 'DX-Y.NYB', 'SI=F', 'HG=F']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr_ret = stats[sym]['ret']
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({curr_ret:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate=f"<b>{info['name']}</b>: %{{y:.2f}}%<extra></extra>"
            ))

    # 금요일 13시 수직 기준선
    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified",
        height=700,
        template="plotly_white",
        xaxis=dict(
            title="일시 (KST)",
            tickformat="%m/%d %H:%M",
            rangebreaks=[dict(bounds=["sat", "mon"])] # 주말 제거
        ),
        yaxis=dict(
            title="수익률 (%)",
            range=[-15, 15],
            ticksuffix="%",
            zeroline=True, zerolinewidth=2, zerolinecolor='black'
        ),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 지표 카드 (4열)
    cols = st.columns(len(plot_order))
    for i, sym in enumerate(plot_order):
        if sym in stats:
            cols[i].metric(
                tickers_info[sym]['name'], 
                f"{stats[sym]['price']:,.2f}", 
                f"{stats[sym]['ret']:.2f}%"
            )

if __name__ == "__main__":
    run_app()
