import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf

# 1. 페이지 설정
st.set_page_config(page_title="Silver Real-time Strategy & Vol", layout="wide")
st.title("🏆 은(Silver) 실전 릴레이 및 주간 변동성 분석")

# 2. 데이터 수집 (상태 메시지 추가)
@st.cache_data(ttl=600)
def get_silver_data():
    try:
        with st.spinner('데이터를 불러오는 중...'):
            silver = yf.Ticker("SI=F")
            # 15분봉은 최근 60일까지만 제공되므로 안전하게 1mo 사용
            df = silver.history(period="1mo", interval="15m")
            
            if df is None or df.empty:
                st.warning("⚠️ 데이터를 가져오지 못했습니다. 시장 휴장일이거나 yfinance API 일시적 오류일 수 있습니다.")
                return None
                
            df = df.reset_index()
            df = df[['Datetime', 'Close']].rename(columns={'Datetime': 'Time', 'Close': 'Price'})
            df['Time'] = df['Time'].dt.tz_convert('Asia/Seoul')
            df = df[df['Time'].dt.weekday < 5].copy()
            return df
    except Exception as e:
        st.error(f"❌ 데이터 로딩 중 오류 발생: {e}")
        return None

# [핵심 엔진 및 시각화 로직은 이전과 동일하되, 데이터 체크 추가]
df = get_silver_data()

if df is not None and len(df) > 20:
    # 3. 통합 엔진 실행 (이전 코드의 run_integrated_engine 함수 내용)
    # [코드의 간결함을 위해 실행부만 명시합니다. 이전 전체 코드의 엔진 함수를 그대로 쓰세요]
    try:
        from app_logic import run_integrated_engine # 혹은 엔진 함수를 여기에 위치
        equity, signals, ids, vix, plot_df = run_integrated_engine(df)
        
        # 그래프 출력부...
        # (이전의 시각화 코드 삽입)
        st.success("✅ 분석이 완료되었습니다.")
        
    except Exception as e:
        st.error(f"❌ 분석 엔진 실행 중 오류: {e}")
else:
    if df is not None:
        st.info("데이터 양이 충분하지 않습니다. (최소 20개 이상의 봉 필요)")
