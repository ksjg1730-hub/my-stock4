import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="24H 매크로 주도주 위기 감지 시스템", layout="wide")

# 2. 종목 설정 (기본 색상)
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
    
    # 이평선 계산 (10MA 삭제)
    final_df['MA30'] = raw_energy.rolling(window=30, min_periods=1).mean()
    final_df['MA60'] = raw_energy.rolling(window=60, min_periods=1).mean()
    
    return final_df, current_stats

def run_app():
    st.title("🚨 매크로 주도주 & 에너지 음전 동기화 분석")
    st.markdown("##### 💡 **MA 음전(초록) 시 1등 종목 분홍색 전환** | 10MA 제거 완료 | 은: 노랑")

    df, stats = get_performance_data()
    if df is None:
        st.info("데이터를 불러오는 중입니다...")
        return

    # 1등 종목 찾기 (현재 수익률 기준)
    top_ticker = max(stats, key=lambda k: stats[k]['ret'])
    
    fig = go.Figure()

    # 에너지 음전 상태 계산 (MA30 또는 MA60 둘 중 하나라도 하락 중이면 위기로 간주)
    ma30_diff = df['MA30'].diff().fillna(0)
    ma60_diff = df['MA60'].diff().fillna(0)
    is_crisis = (ma30_diff < 0) | (ma60_diff < 0)

    # 1. 개별 자산 수익률 (1등 종목 가변 색상 로직 적용)
    for sym, info in tickers_info.items():
        if sym in df.columns:
            line_color = info['color']
            line_width = info['width']
            
            # 1등 종목인데 위기(음전) 상황이면 분홍색으로 변경
            if sym == top_ticker:
                line_width = 4  # 주도주 강조
                
                # 시계열 색상 변화를 위해 구간별로 그림
                df_top_normal = df[sym].copy()
                df_top_normal[is_crisis] = np.nan
                
                df_top_crisis = df[sym].copy()
                df_top_crisis[~is_crisis] = np.nan
                
                # 정상 구간 (기본색)
                fig.add_trace(go.Scatter(
                    x=df.index, y=df_top_normal,
                    name=f"⭐ {info['name']} (주도주)",
                    line=dict(color=info['color'], width=line_width),
                    connectgaps=False
                ))
                # 위기 구간 (분홍색)
                fig.add_trace(go.Scatter(
                    x=df.index, y=df_top_crisis,
                    name=f"⚠️ {info['name']} (위기-분홍)",
                    line=dict(color='#FF69B4', width=line_width + 1),
                    connectgaps=False
                ))
            else:
                # 일반 종목
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[sym],
                    name=f"{info['name']} ({stats[sym]['ret']:+.2f}%)",
                    line=dict(color=line_color, width=line_width),
                    opacity=0.6,
                    connectgaps=True 
                ))

    # 2. 가변형 이평선 (음전 시 초록)
    def add_adaptive_ma(ma_col, name, width, dash=None):
        diff = df[ma_col].diff().fillna(0)
        
        # 기본 검은색 선
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma_col], name=name,
            line=dict(color='black', width=width, dash=dash),
            opacity=0.3,
            showlegend=True
        ))
        
        # 하락(음전) 구간 초록색 강조
        df_down = df[ma_col].copy()
        df_down[diff >= 0] = np.nan
        
        fig.add_trace(go.Scatter(
            x=df_down.index, y=df_down,
            name=f"{name} (하락감지)",
            line=dict(color='#27AE60', width=width + 1, dash=dash),
            showlegend=False,
            connectgaps=False
        ))

    if 'MA30' in df.columns:
        add_adaptive_ma('MA30', '상승에너지 MA 30', 3)
        add_adaptive_ma('MA60', '상승에너지 MA 60', 4, 'dot')

    # 레이아웃 설정
    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(tickformat="%m/%d %H:%M", rangebreaks=[dict(bounds=["sat", "mon"])]),
        yaxis=dict(title="수익률 / 상승 에너지 (%)", range=[-12, 12], ticksuffix="%", zeroline=True, zerolinecolor='black'),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 하단 메트릭
    cols = st.columns(len(tickers_info) + 2)
    for i, sym in enumerate(tickers_info.keys()):
        if sym in stats:
            label = f"⭐ {tickers_info[sym]['name']}" if sym == top_ticker else tickers_info[sym]['name']
            cols[i].metric(label, f"{stats[sym]['price']:,.2f}", f"{stats[sym]['ret']:.2f}%")
    
    if 'MA30' in df.columns:
        cols[-2].metric("BULL MA 30", f"{df['MA30'].iloc[-1]:.2f}%", 
                        delta=round(df['MA30'].diff().iloc[-1], 2), delta_color="inverse")
        cols[-1].metric("BULL MA 60", f"{df['MA60'].iloc[-1]:.2f}%", 
                        delta=round(df['MA60'].diff().iloc[-1], 2), delta_color="inverse")

if __name__ == "__main__":
    run_app()
