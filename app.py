import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="주간 수익률 정밀 분석기", layout="wide")

# 2. 설정 데이터
TICKERS_INFO = {
    '005930.KS': {'name': '삼성전자', 'color': '#0057D8', 'width': 6},
    'CL=F': {'name': 'WTI 원유', 'color': '#E67E22', 'width': 2},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#34495E', 'width': 2},
    'SI=F': {'name': '글로벌 은', 'color': '#BDC3C7', 'width': 2}
}

@st.cache_data(ttl=60)
def get_safe_data():
    """데이터 로드 및 수익률 계산 (오류 방지 강화)"""
    combined_list = []
    current_stats = {}
    
    for sym, info in TICKERS_INFO.items():
        try:
            # 1개월치 데이터 로드 (안정성을 위해 1시간 단위 데이터 사용 권장하나 요청대로 15m 유지)
            raw = yf.download(sym, period='1mo', interval='15m', progress=False, group_by='ticker')
            if raw.empty:
                continue
            
            # 멀티인덱스 구조 처리
            if isinstance(raw.columns, pd.MultiIndex):
                df_close = raw['Close'].iloc[:, 0].copy()
            else:
                df_close = raw['Close'].copy()
            
            # KST 시간대 변환 및 결측치 처리
            if df_close.index.tz is None:
                df_close.index = df_close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                df_close.index = df_close.index.tz_convert('Asia/Seoul')
            
            df_close = df_close.dropna()

            # --- [핵심] 금요일 14:00 기준 수익률 계산 로직 ---
            year_week = df_close.index.strftime('%Y-%U')
            
            def find_friday_base(group):
                # 현재 그룹(해당 주)의 시작 시간
                week_start = group.index[0]
                # 해당 주 시작 전의 전체 데이터 중 금요일 14:00~14:45 사이의 마지막 값 찾기
                prior_data = df_close[df_close.index < week_start]
                target_points = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 14)]
                
                if not target_points.empty:
                    return target_points.iloc[-1]
                return group.iloc[0] # 없으면 해당 주 시가 사용

            # 주차별 기준가 맵 생성
            base_map = df_close.groupby(year_week).apply(find_friday_base)
            
            # 수익률 계산
            rets = []
            for wk in year_week.unique():
                wk_data = df_close[year_week == wk]
                base_val = base_map[wk]
                wk_ret = (wk_data - base_val) / base_val * 100
                rets.append(wk_ret)
            
            final_ret = pd.concat(rets)
            
            # 달러지수 가중치 적용
            if sym == 'DX-Y.NYB': 
                final_ret = final_ret * 5
                
            final_ret.name = sym
            combined_list.append(final_ret)
            
            # 실시간 상태 저장
            current_stats[sym] = {
                'price': df_close.iloc[-1],
                'ret': final_ret.iloc[-1]
            }
            
        except Exception as e:
            st.error(f"{sym} 데이터 처리 중 오류: {e}")
            continue

    if not combined_list:
        return None, None
        
    return pd.concat(combined_list, axis=1), current_stats

def main():
    st.title("📊 삼성전자 및 주요 지수 수익률 비교")
    st.markdown("##### 💡 기준: **매주 전 금요일 오후 2시 가격 (0%)**")

    df_ret, stats = get_safe_data()

    if df_ret is None:
        st.warning("표시할 데이터가 없습니다. Yahoo Finance 연결을 확인하세요.")
        return

    # 그래프 생성
    fig = go.Figure()

    # 표시 순서 고정 (삼성전자가 가장 나중에 그려져 위로 올라옴)
    render_order = ['CL=F', 'DX-Y.NYB', 'SI=F', '005930.KS']

    for sym in render_order:
        if sym in df_ret.columns:
            info = TICKERS_INFO[sym]
            s_info = stats[sym]
            
            label = f"{info['name']} ({s_info['price']:,.0f} | {s_info['ret']:+.2f}%)"
            
            fig.add_trace(go.Scatter(
                x=df_ret.index,
                y=df_ret[sym],
                name=label,
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate="<b>" + info['name'] + "</b><br>수익률: %{y:.2f}%<extra></extra>"
            ))

    # 월요일 구분선 (가독성 증대)
    monday_marks = df_ret.index[(df_ret.index.weekday == 0) & (df_ret.index.hour == 9) & (df_ret.index.minute == 0)]
    for mark in monday_marks:
        fig.add_vline(x=mark, line_width=1, line_dash="dash", line_color="rgba(0,0,0,0.3)")

    fig.update_layout(
        height=700,
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        xaxis=dict(
            tickformat="%m/%d\n%H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),            # 주말 삭제
                dict(bounds=[15.5, 9], pattern="hour"),  # 밤 시간 삭제
            ]
        ),
        yaxis=dict(
            title="수익률 (%)",
            ticksuffix="%",
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='black',
            range=[-12, 12] # 화면을 꽉 채우기 위해 ±12% 고정
        )
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 마지막 업데이트 시각
    st.caption(f"최종 업데이트 (KST): {df_ret.index[-1].strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
