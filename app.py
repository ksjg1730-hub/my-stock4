import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 페이지 설정
st.set_page_config(page_title="24H 글로벌 자산 & 변동성 분석", layout="wide")

# 2. 종목 설정
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 2},
    '^SOX': {'name': '필라델피아 반도체', 'color': '#0057D8', 'width': 4},
    'SI=F': {'name': '글로벌 은', 'color': '#95A5A6', 'width': 2},
    'CL=F': {'name': 'WTI 원유', 'color': '#27AE60', 'width': 1.5},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 1.5}
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
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # 기준점 설정 (금요일 13:00)
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
        except: continue
            
    if not combined_df: return None, {}
    final_df = pd.concat(combined_df, axis=1)
    
    # 4가지 수치(구리, 반도체, 은, 원유)의 절대값 총합 계산
    vol_targets = ['HG=F', '^SOX', 'SI=F', 'CL=F']
    available_targets = [t for t in vol_targets if t in final_df.columns]
    final_df['Total_Abs_Sum'] = final_df[available_targets].abs().sum(axis=1)
    
    return final_df, current_stats

def run_app():
    st.title("📊 글로벌 자산 실시간 분석 & 변동성 에너지")
    st.markdown("##### 🟦 필라델피아 반도체 강조 | ⬛ 굵은 점선: 4대 자산 절대값 수익률 합계 | 🌙 24H")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터 로딩 중...")
        return

    # 서브플롯 생성 (수익률 차트와 절대값 합계 차트 분리)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3],
                        subplot_titles=("개별 자산 수익률 (%)", "변동성 에너지 합계 (Sum of Abs Returns)"))

    # 1. 상단: 개별 자산 차트
    plot_order = ['CL=F', 'DX-Y.NYB', 'HG=F', 'SI=F', '^SOX']
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True
            ), row=1, col=1)

    # 2. 하단: 절대값 총합 차트
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Total_Abs_Sum'],
        name="변동성 합계(Abs Sum)",
        line=dict(color='black', width=3, dash='dot'),
        fill='tozeroy', fillcolor='rgba(0,0,0,0.1)'
    ), row=2, col=1)

    # 공통 레이아웃 설정
    fig.update_layout(
        hovermode="x unified", height=850, template="plotly_white",
        xaxis2=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )
    
    # 기준선 (금요일 13시)
    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    st.plotly_chart(fig, use_container_width=True)
    
    # 메트릭 카드
    cols = st.columns(len(plot_order) + 1)
    for i, sym in enumerate(plot_order):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'Total_Abs_Sum' in df.columns:
        cols[-1].metric("변동성 합계", f"{df['Total_Abs_Sum'].iloc[-1]:.2f}%", help="구리+반도체+은+원유 수익률의 절대값 합산")

if __name__ == "__main__":
    run_app()
