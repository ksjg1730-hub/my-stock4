import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 크로스 분석 시스템", layout="wide")

# 2. 종목 설정
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 1.5},
    'SI=F': {'name': '글로벌 은', 'color': '#F1C40F', 'width': 2.5},
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
    
    vol_targets = list(tickers_info.keys())
    available_targets = [t for t in vol_targets if t in final_df.columns]
    pos_ret_df = final_df[available_targets].clip(lower=0)
    
    def get_bull_energy(row):
        valid_values = row.dropna()
        if len(valid_values) >= 2:
            return valid_values.nlargest(2).sum() * 0.5
        elif len(valid_values) == 1:
            return valid_values.iloc[0] * 0.5
        return 0.0

    raw_energy = pos_ret_df.apply(get_bull_energy, axis=1)
    
    # 이평선 계산
    final_df['MA20'] = raw_energy.rolling(window=20, min_periods=1).mean()
    final_df['MA50'] = raw_energy.rolling(window=50, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("📊 에너지 크로스 시점 분석 대시보드")
    st.markdown("##### 🔴 **빨간선: UP (Golden)** | 🔵 **파란선: DOWN (Dead)** | 🟢 **실시간 1등 에너지 음전 시 초록색 전환**")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    # 1. 상태 계산
    vol_targets = list(tickers_info.keys())
    df['current_top'] = df[vol_targets].idxmax(axis=1)
    ma20_diff = df['MA20'].diff().fillna(0)
    ma50_diff = df['MA50'].diff().fillna(0)
    is_crisis = (ma20_diff < 0) | (ma50_diff < 0)

    # 2. 크로스 로직 보정
    df['prev_MA20'] = df['MA20'].shift(1)
    df['prev_MA50'] = df['MA50'].shift(1)
    up_cross = df[(df['prev_MA20'] < df['prev_MA50']) & (df['MA20'] >= df['MA50'])].index
    down_cross = df[(df['prev_MA20'] > df['prev_MA50']) & (df['MA20'] <= df['MA50'])].index

    fig = go.Figure()

    # 3. 자산별 렌더링 (동적 색상 전환)
    for sym, info in tickers_info.items():
        if sym in df.columns:
            is_target_crisis = (df['current_top'] == sym) & is_crisis
            
            # 일반 구간
            y_normal = df[sym].copy()
            y_normal[is_target_crisis] = np.nan
            fig.add_trace(go.Scatter(
                x=df.index, y=y_normal, name=info['name'],
                line=dict(color=info['color'], width=info['width']),
                connectgaps=False
            ))
            
            # 음전 위기 구간
            y_crisis = df[sym].copy()
            y_crisis[~is_target_crisis] = np.nan
            fig.add_trace(go.Scatter(
                x=df.index, y=y_crisis, name=f"{info['name']}(위기)",
                line=dict(color='#2ECC71', width=info['width'] + 2.5),
                showlegend=False, connectgaps=False
            ))

    # 4. 에너지 이평선 (오류 수정: opacity 위치 변경)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA20'], name="에너지 MA20",
        line=dict(color='black', width=1.5),
        opacity=0.3  # line 외부로 이동
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MA50'], name="에너지 MA50",
        line=dict(color='black', width=2.5, dash='dot'),
        opacity=0.3  # line 외부로 이동
    ))

    # 5. 수직 직선 추가
    for t in up_cross:
        fig.add_vline(x=t, line_width=1.5, line_dash="dash", line_color="red", opacity=0.6)
    
    for t in down_cross:
        fig.add_vline(x=t, line_width=1.5, line_dash="dash", line_color="blue", opacity=0.6)

    fig.update_layout(
        hovermode="x unified", height=850, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 에너지 (%)", range=[-12, 12], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_app()
