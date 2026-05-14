import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="24H 수익률 분석기", layout="wide")

# 2. 종목 설정
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 5},
    'CL=F': {'name': 'WTI 원유', 'color': '#E67E22', 'width': 1.5},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 1.5},
    'SI=F': {'name': '글로벌 은', 'color': '#BDC3C7', 'width': 1.5}
}

@st.cache_data(ttl=30)
def get_performance_data():
    combined_df = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            # 데이터 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            close = df['Close'][sym] if isinstance(df.columns, pd.MultiIndex) else df['Close']
            close = close.dropna()
            
            # KST 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [에러 방지 로직] ---
            year_week = close.index.strftime('%G-%V')
            
            def get_base_price(series):
                # 1. 금요일 13:00 데이터가 있는지 확인
                target = series[(series.index.weekday == 4) & (series.index.hour == 13)]
                if not target.empty:
                    return target.iloc[0]
                # 2. 없으면(아직 금요일 1시 전이면) 해당 주차의 가장 첫 가격 사용
                return series.iloc[0]

            base_price = close.groupby(year_week).transform(get_base_price)
            
            # 수익률 계산
            ret = ((close - base_price) / base_price * 100)
            if sym == 'DX-Y.NYB': ret *= 5
            
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
        
    if not combined_df: return None, {}
    return pd.concat(combined_df, axis=1), current_stats

def run_app():
    st.title("📊 24H 국제 시세 및 수익률 비교")
    st.markdown("##### 🟦 삼성전자 강조 | ⬛ 기준: 금요일 13:00 (미도달 시 월요일 시가) | 🌙 24시간 모드")

    df, stats = get_performance_data()
    if df is None or not stats:
        st.warning("데이터를 불러오는 중입니다... 잠시만 기다려주세요.")
        return

    fig = go.Figure()
    plot_order = ['CL=F', 'DX-Y.NYB', 'SI=F', '005930.KS']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({curr['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True
            ))

    # 기준선 표시 (데이터에 존재하는 경우만)
    friday_points = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for pt in friday_points:
        fig.add_vline(x=pt, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified", height=700, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 (%)", range=[-15, 15], ticksuffix="%", zeroline=True, zerolinewidth=2, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 지표 카드
    cols = st.columns(4)
    for i, sym in enumerate(plot_order):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")

if __name__ == "__main__":
    run_app()
