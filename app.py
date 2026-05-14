import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 트리플 이평 분석", layout="wide")

# 2. 종목 설정
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

            # 비거래 시간 0값 보정 (LOCF)
            close = close.replace(0, np.nan).ffill()
            
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
            
            ret = ret.ffill()
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
            
    if not combined_df: return None, {}
    final_df = pd.concat(combined_df, axis=1).ffill()
    
    # --- [트리플 에너지 이평선 로직] ---
    vol_targets = list(tickers_info.keys())
    available_targets = [t for t in vol_targets if t in final_df.columns]
    
    # 기초 에너지 (절대값 합산 * 0.5)
    raw_energy = final_df[available_targets].abs().sum(axis=1, min_count=1) * 0.5
    raw_energy = raw_energy.ffill()
    
    # 이평선 계산 (10, 30, 60)
    final_df['MA10'] = raw_energy.rolling(window=10, min_periods=1).mean()
    final_df['MA30'] = raw_energy.rolling(window=30, min_periods=1).mean()
    final_df['MA60'] = raw_energy.rolling(window=60, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("📊 매크로 자산 & 트리플 에너지 이평 분석")
    st.markdown("##### ⬛ 굵은점선: MA 60 (장기) | ⬛ 굵은실선: MA 30 (중기) | ⬛ 얇은실선: MA 10 (단기)")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    fig = go.Figure()
    
    # 1. 개별 자산 수익률
    for sym, info in tickers_info.items():
        if sym in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True 
            ))

    # 2. 트리플 이평선
    if 'MA10' in df.columns:
        # MA 10 (단기)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA10'], name="에너지 MA 10",
            line=dict(color='rgba(0,0,0,0.4)', width=1.2),
            connectgaps=True
        ))
        # MA 30 (중기)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA30'], name="에너지 MA 30",
            line=dict(color='black', width=3),
            connectgaps=True
        ))
        # MA 60 (장기) - 새로 추가
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA60'], name="에너지 MA 60",
            line=dict(color='black', width=4, dash='tightdot'),
            connectgaps=True
        ))

    # 금요일 13시 기준선
    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 에너지 (%)", range=[-12, 12], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 지표 정보
    cols = st.columns(len(tickers_info) + 3)
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'MA10' in df.columns:
        cols[-3].metric("MA 10", f"{df['MA10'].iloc[-1]:.2f}%")
        cols[-2].metric("MA 30", f"{df['MA30'].iloc[-1]:.2f}%")
        cols[-1].metric("MA 60", f"{df['MA60'].iloc[-1]:.2f}%")

if __name__ == "__main__":
    run_app()
