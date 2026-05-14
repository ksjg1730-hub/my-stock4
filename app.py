# --- [기존 get_performance_data 내 로직에 추가] ---
# 변동성 합계의 이동평균선 계산 (수축/팽창 흐름 파악용)
final_df['Energy_MA'] = final_df['Scaled_Abs_Sum'].rolling(window=5).mean()

# --- [run_app 내 차트 그리기 부분 수정] ---
# 변동성 합계 (검은 점선)
if 'Scaled_Abs_Sum' in df.columns:
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Scaled_Abs_Sum'],
        name="실시간 에너지",
        line=dict(color='rgba(0,0,0,0.3)', width=2, dash='dot'),
        hovertemplate="현재 에너지: %{y:.2f}%<extra></extra>"
    ))
    
    # 에너지 이동평균선 (굵은 실선으로 수축/팽창 가이드)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Energy_MA'],
        name="에너지 흐름(MA)",
        line=dict(color='black', width=4),
        hovertemplate="평균 에너지: %{y:.2f}%<extra></extra>"
    ))
