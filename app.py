import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="주간 수익률 분석기 (금요일 기준)", layout="wide")

# 2. 설정 데이터
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
            # 1개월치 데이터 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 데이터 추출 및 시간대 변환
            close = df['Close'][sym].copy() if isinstance(df.columns, pd.MultiIndex) else df['Close'].copy()
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [수정 핵심] 전주 금요일 15:00 기준가 산출 ---
            year_week = close.index.strftime('%Y-%U')
            
            def get_friday_3pm_base(group):
                week_start = group.index[0]
                # 현재 주 시작 전 데이터 중 금요일 15:00 데이터 찾기
                prior_data = close[close.index < week_start]
                friday_points = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 15)]
                
                if not friday_points.empty:
                    return friday_points.iloc[-1] # 가장 최근 금요일 15:00 가격
                return group.dropna().iloc[0] # 없으면 해당 주 첫 가격

            # 주차별 기준 가격 맵핑
            base_prices = close.groupby(year_week).apply(get_friday_3pm_base)
            
            # 수익률 계산
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                b_val = base_prices[wk]
                ret[mask] = ((close[mask] - b_val) / b_val * 100)
            
            if sym == 'DX-Y.NYB': ret *= 5
            
            current_stats[sym] = {'price': close.dropna().iloc[-1], 'ret': ret.dropna().iloc[-1]}
            ret.name = sym
            combined_df_list.append(ret)
        except: continue
    
    if not combined_df_list: return None, None
        
    # 데이터 통합 및 전방 채우기 (ffill)
    final_df = pd.concat(combined_df_list, axis=1).ffill()
    return final_df, current_stats

def run_app():
    st.title("📊 주간 수익률 분석 (기준: 전주 금요일 15:00)")
    st.markdown("##### 🟦 삼성전자 강조 | ⬛ 기준점: 전주 금요일 15:00 (0%) | ✂️ 휴장 시간 제거")

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

    # 월요일 09:00 가이드라인
    monday_starts = df.index[(df.index.weekday == 0) & (df.index.hour == 9) & (df.index.minute == 0)]
    for m_start in monday_starts:
        fig.add_vline(x=m_start, line_width=1, line_dash="dash", line_color="gray")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
                dict(bounds=[15.5, 9], pattern="hour"),
            ]
        ),
        yaxis=dict(title="수익률 (%)", range=[-15, 15], ticksuffix="%", zeroline=True, zerolinewidth=3, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info(f"💡 모든 수익률은 전주 금요일 15:00 가격을 0%로 잡고 계산되었습니다.")

if __name__ == "__main__":
    run_app()
    
