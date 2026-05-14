import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 추세 분석기 (LOCF)", layout="wide")

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

            # [핵심] 0 값을 결측치로 바꾼 후, 직전 값으로 채움 (LOCF 방식)
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
            
            # 수익률 데이터도 LOCF 적용하여 0으로 튀는 현상 방지
            ret = ret.ffill()
            
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
            
    if not combined_df: return None, {}
    final_df = pd.concat(combined_df, axis=1)
    
    # --- [에너지 및 듀얼 이평선 로직] ---
    vol_targets = list(tickers_info.keys())
    available_targets = [t for t in vol_targets if t in final_df.columns]
    
    # 1. 개별 종목 간 시차 보정 (종목별로 데이터가 없는 시점 ffill)
    final_df[available_targets] = final_df[available_targets].ffill()
    
    # 2. 기초 에너지 계산 (절대값 합산 * 0.5)
    raw_energy = final_df[available_targets].abs().sum(axis=1, min_count=1) * 0.5
    raw_energy = raw_energy.ffill() # 합산값 자체도 비거래 시간 유지
    
    # 3. 듀얼 이평선 계산
    final_df['MA10'] = raw_energy.rolling(window=10, min_periods=1).mean()
    final_df['MA30'] = raw_energy.rolling(window=30, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("📊 매크로 자산 & 듀얼 이평 (LOCF 모드)")
    st.markdown("##### ⬛ 굵은선: MA 30 | ⬛ 얇은선: MA 10 | 🌙 비거래 시간 값 유지 (No-Drop)")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    fig = go.Figure()
    
    # 1. 개별 자산
    for sym, info in tickers_info.items():
        if sym in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True 
            ))

    # 2. 듀얼 이평선
    if 'MA10' in df.columns and 'MA30' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA10'],
            name="에너지 MA 10",
            line=dict(color='rgba(0,0,0,0.5)', width=1.2),
            connectgaps=True
        ))
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA30'],
            name="에너지 MA 30",
            line=dict(color='black', width=3.5),
            connectgaps=True
        ))

    # 기준선 (금요일 13시)
    friday_lines = df.index[(df.index.weekday == 4) & (df.index.hour == 13) & (df.index.minute == 0)]
    for f_line in friday_lines:
        fig.add_vline(x=f_line, line_width=1, line_dash="dot", line_color="red")

    fig.update_layout(
        hovermode="x unified", height=750, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 에너지 (%)", range=[-12, 12], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 메트릭
    cols = st.columns(len(tickers_info) + 2)
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'MA10' in df.columns:
        cols[-2].metric("MA 10", f"{df['MA10'].iloc[-1]:.2f}%")
        cols[-1].metric("MA 30", f"{df['MA30'].iloc[-1]:.2f}%")

if __name__ == "__main__":
    run_app()
