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
            
            # 데이터 추출 (MultiIndex 대응)
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym]
            else:
                close = df['Close']

            close = close.dropna()
            
            # KST 변환
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
            
            if sym == 'DX-Y.NYB': ret *= 5 # 달러 가중치
            
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
            
    if not combined_df: return None, {}
    final_df = pd.concat(combined_df, axis=1)
    
    # --- [변동성 에너지: 수축/팽창 로직] ---
    vol_targets = list(tickers_info.keys())
    available_targets = [t for t in vol_targets if t in final_df.columns]
    
    # 1. 절대값 합산 * 0.5 (에너지 실시간 값)
    final_df['Energy_Raw'] = final_df[available_targets].abs().sum(axis=1) * 0.5
    
    # 2. 에너지 이동평균선 (흐름 파악용, 5개 데이터 평균)
    final_df['Energy_MA'] = final_df['Energy_Raw'].rolling(window=5).mean()
    
    return final_df, current_stats

def run_app():
    st.title("📊 매크로 자산 & 변동성 에너지 흐름 분석")
    st.markdown("##### ⬛ 검은 실선: 에너지 흐름(MA) | ⬛ 점선: 실시간 에너지(x0.5) | 🌙 24H")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    fig = go.Figure()
    
    # 1. 개별 자산 수익률 차트
    for sym, info in tickers_info.items():
        if sym in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True
            ))

    # 2. 변동성 에너지 - 수축/팽창 가이드 라인
    if 'Energy_Raw' in df.columns:
        # 실시간 값 (점선)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Energy_Raw'],
            name="실시간 에너지",
            line=dict(color='rgba(0,0,0,0.3)', width=1.5, dash='dot'),
            hovertemplate="현재 에너지: %{y:.2f}%<extra></extra>"
        ))
        
        # 이동평균선 (실선 - 에너지의 방향성)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Energy_MA'],
            name="에너지 흐름(MA)",
            line=dict(color='black', width=3.5),
            hovertemplate="평균 에너지: %{y:.2f}%<extra></extra>"
        ))

    # 금요일 13시 기준선
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
    
    # 하단 지표 카드
    cols = st.columns(len(tickers_info) + 1)
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'Energy_MA' in df.columns:
        curr_energy = df['Energy_Raw'].iloc[-1]
        cols[-1].metric("에너지 강도", f"{curr_energy:.2f}%", help="4대 자산 절대값 합산 * 0.5")

if __name__ == "__main__":
    run_app()
