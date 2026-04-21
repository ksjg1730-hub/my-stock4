import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np

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
def get_final_data():
    combined_list = []
    current_stats = {}
    
    for sym, info in TICKERS_INFO.items():
        try:
            # 데이터 로드 (최신 yfinance 인덱스 대응)
            raw = yf.download(sym, period='1mo', interval='15m', progress=False)
            if raw.empty: continue
            
            # Close 데이터 추출 로직 보강
            if isinstance(raw.columns, pd.MultiIndex):
                if 'Close' in raw.columns.levels[0]:
                    df_close = raw['Close'].iloc[:, 0]
                else:
                    df_close = raw.xs('Close', axis=1, level=0).iloc[:, 0]
            else:
                df_close = raw['Close']

            # KST 변환
            if df_close.index.tz is None:
                df_close.index = df_close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                df_close.index = df_close.index.tz_convert('Asia/Seoul')
            
            df_close = df_close.dropna()

            # --- 금요일 14:00 기준 수익률 계산 ---
            year_week = df_close.index.strftime('%Y-%U')
            
            def find_friday_base(group):
                week_start = group.index[0]
                prior_data = df_close[df_close.index < week_start]
                target = prior_data[(prior_data.index.weekday == 4) & (prior_data.index.hour == 14)]
                return target.iloc[-1] if not target.empty else group.iloc[0]

            base_map = df_close.groupby(year_week).apply(find_friday_base, include_groups=False)
            
            rets = []
            for wk in year_week.unique():
                wk_data = df_close[year_week == wk]
                base_val = base_map[wk]
                rets.append((wk_data - base_val) / base_val * 100)
            
            final_ret = pd.concat(rets)
            if sym == 'DX-Y.NYB': final_ret *= 5
                
            final_ret.name = sym
            combined_list.append(final_ret)
            current_stats[sym] = {'price': df_close.iloc[-1], 'ret': final_ret.iloc[-1]}
            
        except Exception as e:
            continue

    if not combined_list: return None, None
    
    # 데이터 통합
    full_df = pd.concat(combined_list, axis=1)
    
    # [수정 포인트] 최신 Pandas 방식의 ffill 사용 (에러 해결)
    full_df = full_df.ffill()
    
    return full_df, current_stats

def main():
    st.title("📊 삼성전자 및 주요 지수 수익률 비교")
    st.markdown("##### 💡 기준: **전주 금요일 14:00 (0%)**")

    df_ret, stats = get_final_data()

    if df_ret is None:
        st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    fig = go.Figure()
    render_order = ['CL=F', 'DX-Y.NYB', 'SI=F', '005930.KS']

    for sym in render_order:
        if sym in df_ret.columns:
            info = TICKERS_INFO[sym]
            s_info = stats[sym]
            
            fig.add_trace(go.Scatter(
                x=df_ret.index,
                y=df_ret[sym],
                name=f"{info['name']} ({s_info['price']:,.0f} | {s_info['ret']:+.2f}%)",
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True
            ))

    # 그래프 레이아웃
    fig.update_layout(
        height=750,
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
        xaxis=dict(
            tickformat="%m/%d\n%H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
                dict(bounds=[15.5, 9], pattern="hour"),
            ]
        ),
        yaxis=dict(title="수익률 (%)", zeroline=True, zerolinewidth=2, range=[-15, 15])
    )

    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
