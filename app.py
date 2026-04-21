import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# 1. 페이지 설정
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
            # 1개월치 15분봉 데이터 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 멀티인덱스 대응 및 Close 데이터 추출
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym].copy()
            else:
                close = df['Close'].copy()
            
            # 시간대 KST 변환
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [핵심] 월요일 아침 첫 가격 기준 수익률 계산 ---
            year_week = close.index.strftime('%Y-%U')
            
            def get_first_valid(series):
                valid = series.dropna()
                return valid.iloc[0] if not valid.empty else np.nan

            monday_open_price = close.groupby(year_week).transform(get_first_valid)
            
            # 월요일 아침 대비 상승률 (%)
            ret = ((close - monday_open_price) / monday_open_price * 100)
            
            # 달러지수 가중치 (x5)
            if sym == 'DX-Y.NYB': ret *= 5
            
            # 실시간 수치 저장용
            latest_val = close.dropna().iloc[-1]
            latest_ret = ret.dropna().iloc[-1]
            current_stats[sym] = {'price': latest_val, 'ret': latest_ret}

            ret.name = sym
            combined_df_list.append(ret)
        except: continue
    
    if not combined_df_list:
        return None, None
        
    # --- [해결 포인트] 데이터 통합 및 빈 구간 채우기 ---
    # 모든 종목을 하나의 시계열로 합친 후, 데이터가 없는 시간대를 직전 데이터로 채워 선을 잇습니다.
    final_df = pd.concat(combined_df_list, axis=1)
    final_df = final_df.ffill() # 삼성전자 개장 전 새벽 시간을 직전 주의 종가 데이터로 연결
    
    return final_df, current_stats

def run_app():
    st.title("📊 월요일 아침 대비 주간 상승률 (%)")
    st.markdown("##### 🟦 삼성전자 강조 | ⬛ 월요일 0% 시작 | ✂️ 밤 시간/주말 삭제")

    df, stats = get_weekly_performance_data()
    if df is None:
        st.error("데이터 로딩 실패")
        return

    fig = go.Figure()

    # 종목 그리기 (삼성전자를 가장 마지막에 추가하여 레이어 최상단 배치)
    plot_order = ['CL=F', 'DX-Y.NYB', 'SI=F', '005930.KS']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            
            # 이름 옆에 [현재가격 | 월요일 대비 상승률] 표시
            display_name = f"{info['name']} [{curr['price']:,.0f} | {curr['ret']:+.2f}%]"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=display_name,
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True, # 빈 구간 직선 연결 강제
                hovertemplate=f"<b>{info['name']}</b><br>월요일대비: %{{y:.2f}}%<extra></extra>"
            ))

    # 기준선 (월요일 오전 9시 개장 시점 수직선)
    monday_starts = df.index[(df.index.weekday == 0) & (df.index.hour == 9) & (df.index.minute == 0)]
    for m_start in monday_starts:
        fig.add_vline(x=m_start, line_width=2, line_color="black")

    fig.update_layout(
        hovermode="x unified",
        height=800,
        template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),           # 주말 삭제
                dict(bounds=[15.5, 9], pattern="hour"), # 밤 시간(15:30~09:00) 삭제
            ]
        ),
        yaxis=dict(
            title="상승률 (기준: 월요일 시가 = 0%)",
            range=[-20, 20],   # Y축 ±20% 고정
            ticksuffix="%",
            zeroline=True, zerolinewidth=3, zerolinecolor='black' # 0% 라인 강조
        ),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center", font=dict(size=13))
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info(f"💡 모든 지표는 해당 주의 월요일 첫 거래 가격을 0%로 잡고 계산되었습니다. (최종 업데이트: {df.index[-1].strftime('%H:%M:%S')})")

if __name__ == "__main__":
    run_app()
