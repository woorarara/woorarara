# --- [수정된 정밀 검색창 부분] ---
with st.expander("🔍 정밀 검색창 열기/닫기"):
    c1, c2 = st.columns(2)
    with c1:
        country_options = ["전체", "미국", "한국"]
        selected_countries = st.multiselect("국가 필터", options=country_options, default=["전체"])
        search_ticker = st.text_input("🎯 티커 검색", placeholder="예: TSLA, 005930").strip().upper()
    
    with c2:
        search_kw = st.text_input("📝 키워드 검색", placeholder="이름/운용사/내용")
        
        # 🌟 [수정] 슬라이더 대신 숫자 입력기로 변경 (모바일 조작성 향상)
        st.write("💰 배당 횟수 필터 (연)")
        max_div_val = int(df_raw['배당수_num'].max())
        
        # 가로로 나란히 최소/최대 입력칸 배치
        div_col1, div_col2 = st.columns(2)
        with div_col1:
            min_div = st.number_input("최소", min_value=0, max_value=max_div_val, value=0, step=1)
        with div_col2:
            max_div = st.number_input("최대", min_value=0, max_value=max_div_val, value=max_div_val, step=1)
    
    if st.button("🔄 검색 조건 초기화", use_container_width=True):
        st.session_state.current_page = 1
        st.rerun()

# --- [필터링 로직 부분] ---
# ... 기존 코드 동일 ...
# 배당 필터 적용 (슬라이더 변수 대신 입력기 변수 사용)
df = df[(df['배당수_num'] >= min_div) & (df['배당수_num'] <= max_div)]
