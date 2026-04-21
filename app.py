import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(page_title="주간 상승률 분석기 (금요일 기준)", layout="wide")

# 2. 종목 및 기본 설정
# 달러지수의 경우 변동폭이 작아 시각화를 위해 5배 가중치를 유지했습니다.
tickers_info = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 6},
    'CL=F': {'name': 'WTI 원유', 'color': '#E67E22', 'width': 2},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 2},
    'SI=F': {'name': '글로벌 은', 'color': '#BDC3C7', 'width': 2}
}

@st.cache_data(ttl=60)
def get_weekly_performance_data():
    combined_df = []
    current_stats = {}

    for sym, info in tickers_info.items():
        try:
            # 1개월치 15분봉 데이터 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False, group_by='ticker')
            if df.empty: continue
            
            # 종가 데이터 추출
            close = df['Close'].iloc[:, 0].copy() if isinstance(df.columns, pd.MultiIndex) else df['Close'].copy()
            
            # 시간대 KST(서울) 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [핵심 로직] 지난주 금요일 14:00 가격을 기준점으로 설정 ---
            year_week = close.index.strftime('%Y-%U')
            
            def get_base_price(group):
                # 해당 주의 시작점 이전 데이터 중 가장 가까운 금요일 14:00 찾기
                start_of_week = group.index[0]
                prior_data = close[close.index < start_of_week]
                
                # 금요일(weekday 4) 14시 데이터 필터링
                friday_2pm = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 14)]
                
                if not friday_2pm.empty:
                    return friday_2pm.iloc[-1]  # 가장 최근 금요일 14:00 가격
                else:
                    return group.iloc[0]        # 없을 경우 해당 주 첫 가격 사용

            # 주차별 기준 가격 계산
            base_prices_map = close.groupby(year_week).apply(get_base_price)
            
            # 수익률 계산: (현재가 - 기준가) / 기준가 * 100
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                base_val = base_prices_map[wk]
                ret[mask] = ((close[mask] - base_val) / base_val * 100)

            # 달러지수 가중치 적용
            if sym == 'DX-Y.NYB': ret *= 5
            
            # 실시간 수치 저장
            latest_val = close.dropna().iloc[-1]
            latest_ret = ret.dropna().iloc[-1]
            current_stats[sym] = {'price': latest_val, 'ret': latest_ret}

            ret.name = sym
            combined_df.append(ret)
            
        except Exception as e:
            st.warning(f"{info['name']} 데이터를 불러오는 중 오류 발생: {e}")
            continue
    
    return pd.concat(combined_df, axis=1) if combined_df else (None, None), current_stats

def run_app():
    st.title("📈 주간 상승률 분석 (기준: 전주 금요일 14:00)")
    st.markdown("##### 🟦 삼성전자 강조 | ⬛ 기준점: 전주 금요일 14:00 (0%) | ✂️ 휴장 시간 제거")

    df, stats = get_weekly_performance_data()
    
    if df is None or df.empty:
        st.error("데이터 로딩 실패. 잠시 후 다시 시도해 주세요.")
        return

    fig = go.Figure()

    # 종목 그리기 순서 (삼성전자가 가장 위 레이어에 오도록 마지막에 배치)
    plot_order = ['CL=F', 'DX-Y.NYB', 'SI=F', '005930.KS']

    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            
            # 범례에 실시간 가격 및 수익률 표시
            display_name = f"{info['name']} [{curr['price']:,.0f} | {curr['ret']:+.2f}%]"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=display_name,
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate=f"<b>{info['name']}</b><br>기준대비: %{{y:.2f}}%<extra></extra>"
            ))

    # 시각적 가이드라인 (0% 라인 및 월요일 구분선)
    monday_starts = df.index[(df.index.weekday == 0) & (df.index.hour == 9) & (df.index.minute == 0)]
    for m_start in monday_starts:
        fig.add_vline(x=m_start, line_width=1, line_dash="dot", line_color="gray")

    fig.update_layout(
        hovermode="x unified",
        height=750,
        template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),           # 주말 제거
                dict(bounds=[15.5, 9], pattern="hour"), # 밤 시간(15:30~09:00) 제거
            ]
        ),
        yaxis=dict(
            title="상승률 (%)",
            range=[-15, 15],  # 변동성을 고려하여 ±15%로 설정
            ticksuffix="%",
            zeroline=True, zerolinewidth=3, zerolinecolor='black'
        ),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center", font=dict(size=13))
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 정보창
    last_update = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
    st.info(f"💡 모든 지표는 **전주 금요일 오후 2시 가격을 0%**로 설정하여 계산되었습니다. (최종 업데이트: {last_update})")

if __name__ == "__main__":
    run_app()
