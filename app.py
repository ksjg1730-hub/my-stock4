@st.cache_data(ttl=30)
def get_weekly_performance_data():
    combined_df_list = []
    current_stats = {}
    
    for sym, info in tickers_info.items():
        try:
            df = yf.download(sym, period='1mo', interval='15m', progress=False)
            if df.empty: continue
            
            if isinstance(df.columns, pd.MultiIndex):
                close = df['Close'][sym].copy()
            else:
                close = df['Close'].copy()
            
            if close.index.tz is None:
                close.index = close.index.tz_localize('UTC').tz_convert('Asia/Seoul')
            else:
                close.index = close.index.tz_convert('Asia/Seoul')

            # --- [수정 핵심] 월요일 기준가 산출 로직 강화 ---
            # 1. 연도-주차 생성
            year_week = close.index.strftime('%Y-%U')
            
            # 2. 각 주차별로 '월요일 09:00'에 가장 가까운 첫 데이터를 기준가로 선정
            def get_strict_monday_open(group):
                # 월요일 데이터만 필터링 시도
                monday_data = group[group.index.weekday == 0]
                if not monday_data.empty:
                    return monday_data.dropna().iloc[0] # 월요일의 첫 가격
                else:
                    return group.dropna().iloc[0] # 월요일 데이터가 없으면 해당 주의 첫 가격

            # 주차별 기준가 계산
            base_prices = close.groupby(year_week).apply(get_strict_monday_open)
            
            # 3. 수익률 계산 (Mapping 방식 사용으로 정확도 향상)
            ret = close.copy()
            for wk in year_week.unique():
                mask = (year_week == wk)
                ret[mask] = ((close[mask] - base_prices[wk]) / base_prices[wk] * 100)
            
            if sym == 'DX-Y.NYB': ret *= 5
            
            latest_val = close.dropna().iloc[-1]
            latest_ret = ret.dropna().iloc[-1]
            current_stats[sym] = {'price': latest_val, 'ret': latest_ret}

            ret.name = sym
            combined_df_list.append(ret)
        except: continue
    
    if not combined_df_list: return None, None
        
    # 데이터 통합 및 전방 채우기 (ffill)
    final_df = pd.concat(combined_df_list, axis=1)
    
    # [중요] 삼성전자 개장 전 시간대를 '이번 주 시작가(0%)'로 강제 고정
    final_df = final_df.ffill().fillna(0) 
    
    return final_df, current_stats
