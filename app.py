def run_app():
    st.title("📈 주간 수익률 분석 (기준: 전주 금요일 14:00)")
    st.markdown("##### 🟦 삼성전자 강조 | 🟥 빨간 실선: 월요일 09:00 개장 시점 | 🥈 은(Silver) 수익률 2배")

    df, stats = get_weekly_performance_data()
    if df is None:
        st.error("데이터 로딩 실패")
        return

    fig = go.Figure()
    plot_order = ['132030.KS', '261240.KS', '144600.KS', '005930.KS']
    
    for sym in plot_order:
        if sym in df.columns:
            info = tickers_info[sym]
            curr = stats.get(sym, {'price': 0, 'ret': 0})
            display_name = f"{info['name']} [{curr['price']:,.0f} | {curr['ret']:+.2f}%]"
            
            fig.add_trace(go.Scatter(
                x=df.index, y=df[sym],
                name=display_name,
                line=dict(color=info['color'], width=info['width']),
                connectgaps=True,
                hovertemplate=f"<b>{info['name']}</b><br>수익률: %{{y:.2f}}%<extra></extra>"
            ))

    # --- [수정된 붉은색 세로줄 로직] ---
    # 정확히 09:00이 아니더라도 9시 정각 데이터를 포함하는 날짜를 찾아 세로줄을 긋습니다.
    # 월요일(weekday 0)이면서 시(hour)가 9인 데이터의 날짜들을 추출
    monday_open_times = df.index[(df.index.weekday == 0) & (df.index.hour == 9)]
    
    # 중복 날짜를 제거하고 각 월요일 아침마다 줄 생성
    unique_mondays = pd.Series(monday_open_times).dt.normalize().unique()
    
    for m_day in unique_mondays:
        # 해당 날짜의 오전 9시 정각 시점을 타겟팅
        target_time = pd.Timestamp(m_day).replace(hour=9, minute=0)
        fig.add_vline(
            x=target_time, 
            line_width=3,          # 더 두껍게
            line_color="red",      # 붉은색
            line_dash="solid",     # 실선으로 변경하여 더 잘 보이게 함
            opacity=0.8            # 약간의 투명도
        )

    fig.update_layout(
        hovermode="x unified", height=800, template="plotly_white",
        xaxis=dict(
            tickformat="%m/%d %H:%M",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
                dict(bounds=[15.5, 9], pattern="hour"),
            ]
        ),
        yaxis=dict(
            title="상승률 (%)", 
            range=[-15, 15], 
            ticksuffix="%", 
            zeroline=True, 
            zerolinewidth=2, 
            zerolinecolor='black'
        ),
        legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
    )

    st.plotly_chart(fig, use_container_width=True)
