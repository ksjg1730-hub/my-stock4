import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 변동성 분석기", layout="wide")

# 2. 종목 설정 (4대 매크로 자산)
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 2},
    'SI=F': {'name': '글로벌 은', 'color': '#7F8C8D', 'width': 2},
    'CL=F': {'name': 'WTI 원유', 'color': '#27AE60', 'width': 1.5},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#2C3E50', 'width': 1.5}
}

@st.cache_data(ttl=60)
def get_performance_data():
    combined_df = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym]
            else:
                close = df['Close']

            close = close.dropna()
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

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
    
    # --- [변동성 총합 * 0.5 적용] ---
    vol_targets = list(tickers_info.keys())
    available_targets = [t for t in vol_targets if t in final_df.columns]
    # 4개 자산 절대값 합산 후 0.5 곱하기
    final_df['Scaled_Abs_Sum'] = final_df[available_targets].abs().sum(axis=1) * 0.5
    
    return final_df, current_stats

def run_app():
    st.title("📊 매크로 자산 분석 & 변동성 에너지 (Scaled)")
    st.markdown("##### ⬛ 굵은 점선: 4대 자산(구리+은+원유+달러) 절대값 합계 * 0.5 | 🌙 24H 추적")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    fig = go.Figure()
    
    # 1. 개별 자산 그리기
    for sym, info in tickers_info.items():
        if sym in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True
            ))

    # 2. 변동성 합계(Scaled) 그리기
    if 'Scaled_Abs_Sum' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Scaled_Abs_Sum'],
            name=f"변동성 합계*0.5 ({df['Scaled_Abs_Sum'].iloc[-1]:.2f}%)",
            line=dict(color='black', width=4, dash='dot'),
            hovertemplate="<b>변동성 에너지(x0.5)</b>: %{y:.2f}%<extra></extra>"
        ))

    # 레이아웃 및 기준선 설정
    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified", height=750, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 에너지 (%)", range=[-15, 15], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 메트릭
    cols = st.columns(len(tickers_info) + 1)
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'Scaled_Abs_Sum' in df.columns:
        cols[-1].metric("변동성 에너지", f"{df['Scaled_Abs_Sum'].iloc[-1]:.2f}%", delta_color="off")

if __name__ == "__main__":
    run_app()
