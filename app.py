import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 상승 동력 분석", layout="wide")

# 2. 종목 설정 (은 색상: 노랑)
tickers_info = {
    'HG=F': {'name': '국제 구리', 'color': '#D35400', 'width': 2},
    'SI=F': {'name': '글로벌 은', 'color': '#F1C40F', 'width': 2.5}, # 노란색으로 변경
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
    
    # --- [상승률 TOP 2 에너지 로직] ---
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
    raw_energy = raw_energy.ffill().fillna(0)
    
    # 이평선 계산
    final_df['MA10'] = raw_energy.rolling(window=10, min_periods=1).mean()
    final_df['MA30'] = raw_energy.rolling(window=30, min_periods=1).mean()
    final_df['MA60'] = raw_energy.rolling(window=60, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("🚀 매크로 상승 동력 & 음전 감지 시스템")
    st.markdown("##### ✨ **은(Silver): 노랑** | 🟢 **이평선 초록색: 하락 전환(위험)** | ⚫ **이평선 검은색: 상승 유지**")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    fig = go.Figure()
    
    # 1. 개별 자산 수익률
    for sym, info in tickers_info.items():
        if sym in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True 
            ))

    # 2. 색상 가변형 이평선 로직 (음전 시 그린)
    def add_adaptive_ma(ma_col, name, width, dash=None):
        # 현재 값과 이전 값을 비교하여 방향성 판단
        diff = df[ma_col].diff().fillna(0)
        
        # 하락 구간(음전)과 상승 구간 분리
        colors = ['#27AE60' if d < 0 else 'black' for d in diff]
        
        # Plotly에서 실시간 색상 변화를 위해 세그먼트별로 그리는 대신, 
        # 전체 흐름을 검은색으로 하되 하락 시 초록색으로 덧칠하거나 포인트 강조
        # 여기서는 사용자 직관성을 위해 선 전체의 흐름을 보여주되 하락 신호를 강조합니다.
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma_col], name=name,
            line=dict(width=width, dash=dash),
            mode='lines',
            marker=dict(color=colors),
            line_color='black', # 기본값
            connectgaps=True
        ))
        
        # 하락(음전) 구간만 따로 추출하여 초록색으로 덧씌움
        df_down = df.copy()
        df_down.loc[diff >= 0, ma_col] = np.nan
        
        fig.add_trace(go.Scatter(
            x=df_down.index, y=df_down[ma_col],
            name=f"{name} (하락)",
            line=dict(color='#27AE60', width=width + 0.5, dash=dash),
            hoverinfo='skip',
            showlegend=False,
            connectgaps=False
        ))

    if 'MA30' in df.columns:
        # MA 10 (단기 - 얇게)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MA10'], name="에너지 MA 10",
            line=dict(color='rgba(0,0,0,0.2)', width=1),
            showlegend=True
        ))
        # MA 30 (중기)
        add_adaptive_ma('MA30', '상승에너지 MA 30', 3)
        # MA 60 (장기)
        add_adaptive_ma('MA60', '상승에너지 MA 60', 4, 'dot')

    # 기준선 및 레이아웃
    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 상승 에너지 (%)", range=[-12, 12], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 메트릭
    cols = st.columns(len(tickers_info) + 3)
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            cols[i].metric(tickers_info[sym]['name'], f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'MA10' in df.columns:
        cols[-3].metric("BULL MA 10", f"{df['MA10'].iloc[-1]:.2f}%")
        cols[-2].metric("BULL MA 30", f"{df['MA30'].iloc[-1]:.2f}%", 
                        delta=round(df['MA30'].diff().iloc[-1], 2), delta_color="inverse")
        cols[-1].metric("BULL MA 60", f"{df['MA60'].iloc[-1]:.2f}%", 
                        delta=round(df['MA60'].diff().iloc[-1], 2), delta_color="inverse")

if __name__ == "__main__":
    run_app()
