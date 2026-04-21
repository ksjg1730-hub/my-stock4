import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정 (반드시 import 바로 다음에 와야 합니다)
st.set_page_config(page_title="주간 상승률 분석기", layout="wide")

# 2. 종목 및 기본 설정
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 6},
    'CL=F': {'name': 'WTI 원유', 'color': '#E67E22', 'width': 2},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 2},
    'SI=F': {'name': '글로벌 은', 'color': '#BDC3C7', 'width': 2}
}

@st.cache_data(ttl=30)
def get_weekly_performance_data():
    combined_df_list = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            # 데이터 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 멀티인덱스 대응
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym].copy()
            else:
                close = df['Close'].copy()
            
            # 시간대 KST 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [월요일 보정 로직] ---
            year_week = close.index.strftime('%Y-%U')
            
            # 주차별로 월요일의 첫 가격을 명확히 추출
            def get_monday_base(group):
                monday_data = group[group.index.weekday == 0]
                if not monday_data.empty:
                    return monday_data.dropna().iloc[0]
                return group.dropna().iloc[0]

            # 최신 Pandas 버전 대응 (include_groups=False)
            try:
                base_prices = close.groupby(year_week).apply(get_monday_base, include_groups=False)
            except:
                base_prices = close.groupby(year_week).apply(get_monday_base)
            
            # 수익률 계산
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                b_price = base_prices[wk]
                ret[mask] = ((close[mask] - b_price) / b_price * 100)
            
            if sym == 'DX-Y.NYB': ret *= 5
            
            latest_val = close.dropna().iloc[-1]
            latest_ret = ret.dropna().iloc[-1]
            current_stats[sym] = {'price': latest_val, 'ret': latest_ret}

            ret.name = sym
            combined_df_list.append(ret)
        except: continue
    
    if not combined_df_list: return None, None
        
    # 데이터 통합 및 전방 채우기
    final_df = pd.concat(combined_df_list, axis=1)
    # 월요일 개장 전 공백을 0(기준점)으로 채워 그래프 끊김 방지
    final_df = final_df.ffill().fillna(0)
    
    return final_df, current_stats

def run_app():
    st.title("📊 월요일 아침 대비 주간 상승률 (%)")
    st.markdown("##### 🟦 삼성전자 강조 | ⬛ 월요일 0% 시작 | ✂️ 밤 시간/주말 삭제")

    df, stats = get_weekly_performance_data()
    if df is None:
        st.error("데이터 로딩 실패")
        return

    fig = go.Figure()
    plot_order = ['CL=F', 'DX-Y.NYB', 'SI=F', '005930.KS']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            display_name = f"{info['name']} [{curr['price']:,.0f} | {curr['ret']:+.2f}%]"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=display_name,
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate=f"<b>{info['name']}</b><br>수익률: %{{y:.2f}}%<extra></extra>"
            ))

    # 월요일 구분선
    monday_starts = df.index[(df.index.weekday == 0) & (df.index.hour == 9) & (df.index.minute == 0)]
    for m_start in monday_starts:
        fig.add_vline(x=m_start, line_width=2, line_color="black", line_dash="dash")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
                dict(bounds=[15.5, 9], pattern="hour"),
            ]
        ),
        yaxis=dict(title="상승률 (%)", range=[-20, 20], ticksuffix="%", zeroline=True, zerolinewidth=3, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info(f"💡 마지막 업데이트: {df.index[-1].strftime('%H:%M:%S')}")

if __name__ == "__main__":
    run_app()
