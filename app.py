import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 동적 주도주 분석", layout="wide")

# 2. 종목 설정 (기본 색상 및 굵기)
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 1.5},
    'SI=F': {'name': '글로벌 은', 'color': '#F1C40F', 'width': 2.5}, # 노랑
    'CL=F': {'name': 'WTI 원유', 'color': '#27AE60', 'width': 1.5},
    'DX-Y.NYB': {'name': '달러지수(x5)', 'color': '#2C3E50', 'width': 1.5}
}

@st.cache_data(ttl=60)
def get_performance_data():
    combined_df = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            # 최근 1개월 데이터 15분 간격 로드
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            # 멀티인덱스 처리
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym]
            else:
                close = df['Close']

            # 비거래 시간 결측치 보정 (LOCF)
            close = close.replace(0, np.nan).ffill()
            
            # 시간대 설정 (KST)
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # 주간 수익률 계산 (금요일 13시 기준)
            year_week = close.index.strftime('%G-%V')
            def get_base_price(series):
                target = series[(series.index.weekday == 4) & (series.index.hour == 13)]
                return target.iloc[0] if not target.empty else series.iloc[0]

            base_price = close.groupby(year_week).transform(get_base_price)
            ret = ((close - base_price) / base_price * 100)
            
            # 달러지수 가중치 부여
            if sym == 'DX-Y.NYB': ret *= 5
            
            ret = ret.ffill()
            current_stats[sym] = {'price': close.iloc[-1], 'ret': ret.iloc[-1]}
            ret.name = sym
            combined_df.append(ret)
        except: continue
            
    if not combined_df: return None, {}
    final_df = pd.concat(combined_df, axis=1).ffill()
    
    # --- [상승 동력 에너지 로직] ---
    vol_targets = list(tickers_info.keys())
    available_targets = [t for t in vol_targets if t in final_df.columns]
    
    # 하락은 무시하고 상승률(0 이상)만 추출
    pos_ret_df = final_df[available_targets].clip(lower=0)
    
    # 매 시점 상위 2개 자산의 평균 에너지 산출
    def get_bull_energy(row):
        valid_values = row.dropna()
        if len(valid_values) >= 2:
            return valid_values.nlargest(2).sum() * 0.5
        elif len(valid_values) == 1:
            return valid_values.iloc[0] * 0.5
        return 0.0

    raw_energy = pos_ret_df.apply(get_bull_energy, axis=1)
    
    # 이평선 주기 설정: 20, 50
    final_df['MA20'] = raw_energy.rolling(window=20, min_periods=1).mean()
    final_df['MA50'] = raw_energy.rolling(window=50, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("📊 매크로 동적 주도주 감지 시스템 (Ver 3.0)")
    st.markdown("##### 🟢 **매 시점 1등 종목 추적** | 에너지 음전 시 해당 종목 초록색 전환 | 이평: 20-50")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    # 1. 동적 주도주 및 에너지 상태 판단
    # 매 시간대(row)마다 수익률이 가장 높은 종목의 이름을 기록
    vol_targets = list(tickers_info.keys())
    df['current_top'] = df[vol_targets].idxmax(axis=1)

    # 에너지 하락 구간 판단 (MA20 또는 MA50이 꺾일 때)
    ma20_diff = df['MA20'].diff().fillna(0)
    ma50_diff = df['MA50'].diff().fillna(0)
    is_crisis = (ma20_diff < 0) | (ma50_diff < 0)

    fig = go.Figure()

    # 2. 자산별 동적 렌더링
    for sym, info in tickers_info.items():
        if sym in df.columns:
            x_vals = df.index
            y_vals = df[sym]
            
            # 로직: 해당 시점에 이 종목이 1등이었고 + 에너지가 음전인가?
            is_target_crisis = (df['current_top'] == sym) & is_crisis
            
            # A. 정상/비주도 구간 (본래 색상)
            y_normal = y_vals.copy()
            y_normal[is_target_crisis] = np.nan
            
            fig.add_trace(go.Scatter(
                x=x_vals, y=y_normal,
                name=f"{info['name']}",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=False # 색상 분리를 위해 연결 해제
            ))
            
            # B. 위기 구간 (당시 1등이었는데 에너지가 꺾인 순간 -> 초록색)
            y_crisis = y_vals.copy()
            y_crisis[~is_target_crisis] = np.nan
            
            fig.add_trace(go.Scatter(
                x=x_vals, y=y_crisis,
                name=f"{info['name']} (🚨에너지음전)",
                line=dict(color='#2ECC71', width=info['width'] + 2.5), # 두꺼운 초록색
                showlegend=False, # 범례 중복 방지
                connectgaps=False
            ))

    # 3. 상승 에너지 이평선 (배경)
    def add_adaptive_ma(ma_col, name, width, dash=None):
        diff = df[ma_col].diff().fillna(0)
        
        # 기본 배경선 (연한 검정)
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma_col], name=name,
            line=dict(color='black', width=width, dash=dash),
            opacity=0.15,
            showlegend=True
        ))
        
        # 이평선 자체의 하락 구간 강조 (초록)
        df_down = df[ma_col].copy()
        df_down[diff >= 0] = np.nan
        
        fig.add_trace(go.Scatter(
            x=df_down.index, y=df_down,
            name=f"{name} (하락)",
            line=dict(color='#27AE60', width=width + 1, dash=dash),
            showlegend=False,
            connectgaps=False
        ))

    add_adaptive_ma('MA20', '상승에너지 MA 20', 2.5)
    add_adaptive_ma('MA50', '상승에너지 MA 50', 3.5, 'dot')

    # 4. 차트 레이아웃 설정
    fig.update_layout(
        hovermode="x unified",
        height=850,
        template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[dict(bounds=["sat", "mon"])] # 주말 제거
        ),
        yaxis=dict(
            title="주간 수익률 / 에너지 강도 (%)",
            range=[-12, 12],
            ticksuffix="%",
            zeroline=True,
            zerolinecolor='black'
        ),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 5. 하단 데이터 대시보드
    cols = st.columns(len(tickers_info) + 2)
    # 현재 실시간 1등 종목 확인
    realtime_top = df['current_top'].iloc[-1]
    
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            label = f"⭐ {tickers_info[sym]['name']}" if sym == realtime_top else tickers_info[sym]['name']
            cols[i].metric(label, f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    cols[-2].metric("BULL MA 20", f"{df['MA20'].iloc[-1]:.2f}%", 
                    delta=round(df['MA20'].diff().iloc[-1], 2), delta_color="inverse")
    cols[-1].metric("BULL MA 50", f"{df['MA50'].iloc[-1]:.2f}%", 
                    delta=round(df['MA50'].diff().iloc[-1], 2), delta_color="inverse")

if __name__ == "__main__":
    run_app()
