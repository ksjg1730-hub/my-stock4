import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="국내 ETF 주간 수익률 비교", layout="wide")

# 2. 국내 ETF 종목 설정 (모두 한국거래소 종목으로 통일)
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 6},
    '132030.KS': {'name': 'KODEX 원유선물(H)', 'color': '#E67E22', 'width': 2},
    '261240.KS': {'name': 'KODEX 미국달러선물(x5)', 'color': '#34495E', 'width': 2}, # 가중치 유지
    '144600.KS': {'name': 'KODEX 은선물(H)', 'color': '#BDC3C7', 'width': 2}
}

@st.cache_data(ttl=30)
def get_weekly_performance_data():
    combined_df_list = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            # 1개월치 15분봉 데이터 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 데이터 추출 (국내 종목은 단일 인덱스인 경우가 많으나 방어적으로 작성)
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym].copy()
            else:
                close = df['Close'].copy()
            
            # 국내 종목이므로 시간대 처리 (UTC -> KST)
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [핵심] 전주 금요일 15:00(장 마감 전) 기준가 산출 ---
            year_week = close.index.strftime('%Y-%U')
            
            def get_friday_3pm_base(group):
                week_start = group.index[0]
                # 현재 주 시작 전 데이터 중 금요일 15:00 데이터 탐색
                prior_data = close[close.index < week_start]
                friday_points = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 15)]
                
                if not friday_points.empty:
                    return friday_points.iloc[-1]
                return group.dropna().iloc[0] # 데이터 없으면 주초 시가 사용

            base_prices = close.groupby(year_week).apply(get_friday_3pm_base, include_groups=False)
            
            # 수익률 계산
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                b_val = base_prices[wk]
                ret[mask] = ((close[mask] - b_val) / b_val * 100)
            
            # 달러 ETF 변동성이 작으므로 x5 가중치 시각화 유지
            if sym == '261240.KS': ret *= 5
            
            current_stats[sym] = {'price': close.dropna().iloc[-1], 'ret': ret.dropna().iloc[-1]}
            ret.name = sym
            combined_df_list.append(ret)
        except: continue
    
    if not combined_df_list: return None, None
        
    # 데이터 통합 및 전방 채우기 (국내 종목은 개장시간이 같아 ffill이 효과적임)
    final_df = pd.concat(combined_df_list, axis=1).ffill()
    return final_df, current_stats

def run_app():
    st.title("🇰🇷 국내 ETF 기반 주간 수익률 분석")
    st.markdown("##### 🟦 삼성전자 강조 | ⬛ 기준점: 전주 금요일 15:00 | ✂️ 한국 장외 시간 삭제")

    df, stats = get_weekly_performance_data()
    if df is None:
        st.error("데이터 로딩 실패")
        return

    fig = go.Figure()
    # 그리기 순서 (삼성전자 최상단)
    plot_order = ['132030.KS', '261240.KS', '144600.KS', '005930.KS']
    
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

    # 월요일 개장선 가이드
    monday_starts = df.index[(df.index.weekday == 0) & (df.index.hour == 9) & (df.index.minute == 0)]
    for m_start in monday_starts:
        fig.add_vline(x=m_start, line_width=1, line_dash="dash", line_color="gray")

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),           # 주말 삭제
                dict(bounds=[15.5, 9], pattern="hour"), # 국내 장 마감 시간(15:30~09:00) 삭제
            ]
        ),
        yaxis=dict(title="수익률 (%)", range=[-10, 10], ticksuffix="%", zeroline=True, zerolinewidth=3, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info(f"💡 모든 수익률은 **전주 금요일 한국 장 마감 직전(15:00)** 가격을 0%로 계산합니다.")

if __name__ == "__main__":
    run_app()
