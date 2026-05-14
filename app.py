import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="24H 글로벌 자산 분석기", layout="wide")

# 2. 종목 설정 (SOX는 야후 파이낸스 공식 심볼 ^SOX 사용)
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 2},
    '^SOX': {'name': '필라델피아 반도체', 'color': '#0057D8', 'width': 4},
    'SI=F': {'name': '글로벌 은', 'color': '#95A5A6', 'width': 2},
    'CL=F': {'name': 'WTI 원유', 'color': '#27AE60', 'width': 1.5},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 1.5}
}

@st.cache_data(ttl=30)
def get_performance_data():
    combined_df = []
    current_stats = {}
    
    # 데이터 일괄 다운로드 (에러 방지를 위해 하나씩 처리)
    for sym, info in tickers_info.items():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 데이터 컬럼 추출 (MultiIndex 및 단일 인덱스 모두 대응)
            if 'Close' in df.columns:
                if isinstance(df.columns, pd.MultiIndex):
                    # MultiIndex인 경우 해당 심볼의 Close만 선택
                    close = df['Close'][sym]
                else:
                    # 단일 인덱스인 경우 Close 선택
                    close = df['Close']
            else:
                continue

            close = close.dropna()
            if close.empty: continue
            
            # KST 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # 기준점 설정
            year_week = close.index.strftime('%G-%V')
            def get_base_price(series):
                target = series[(series.index.weekday == 4) & (series.index.hour == 13)]
                return target.iloc[0] if not target.empty else series.iloc[0]

            base_price = close.groupby(year_week).transform(get_base_price)
            ret = ((close - base_price) / base_price * 100)
            
            if sym == 'DX-Y.NYB': ret *= 5
            
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except:
            continue
            
    if not combined_df: return None, {}
    return pd.concat(combined_df, axis=1), current_stats

def run_app():
    st.title("📊 글로벌 주요 자산 24H 실시간 분석")
    st.markdown("##### 🟦 필라델피아 반도체 강조 | ⬛ 기준: 매주 금요일 13:00 (0%) | 🌙 전 종목 24시간 추적")

    df, stats = get_performance_data()
    if df is None or not stats:
        st.warning("데이터를 불러오는 중입니다. 잠시 후 새로고침 해주세요.")
        return

    fig = go.Figure()
    plot_order = ['CL=F', 'DX-Y.NYB', 'HG=F', 'SI=F', '^SOX']
    
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

    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified", height=750, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 (%)", range=[-20, 20], ticksuffix="%", zeroline=True, zerolinewidth=2, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 지표 카드
    cols = st.columns(len(plot_order))
    for i, sym in enumerate(plot_order):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")

if __name__ == "__main__":
    run_app()
