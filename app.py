import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import datetime

# ========================================================
# [설정] 기본 세팅
# ========================================================
st.set_page_config(page_title="ETF 정복(김도현)", page_icon="🦅", layout="wide")

DB_PATH = "stocks.db" if os.path.exists("stocks.db") else os.path.join(os.path.expanduser("~"), "Desktop", "Stock_Data", "stocks.db")

if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

# ========================================================
# [DB 함수]
# ========================================================
def load_data():
    if not os.path.exists(DB_PATH): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM etf_data", conn)
    except:
        return pd.DataFrame()
    conn.close()
    
    df['배당수_num'] = pd.to_numeric(df['배당수'], errors='coerce').fillna(0)
    
    # 링크 생성
    df["url"] = df.apply(
        lambda row: f"https://finance.yahoo.com/quote/{row['티커']}" if row['국가'] == "미국" 
        else f"https://m.stock.naver.com/item/main.nhn?code={row['티커']}", 
        axis=1
    )
    return df

def update_db(ticker, field, new_value):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE etf_data SET {field} = ? WHERE 티커 = ?", (new_value, ticker))
        conn.commit()
    except: pass
    conn.close()

def add_ticker(ticker, name, country, manager):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) FROM etf_data WHERE 티커 = ?", (ticker,))
    if cur.fetchone()[0] > 0:
        conn.close()
        return False, f"❌ '{ticker}'는 이미 DB에 있습니다!"
    
    try:
        cur.execute("INSERT INTO etf_data (티커, 이름, 국가, 운용사, 내용, 배당수) VALUES (?, ?, ?, ?, '', '0')",
                    (ticker, name, country, manager))
        conn.commit()
        conn.close()
        return True, f"✅ {ticker} 추가 완료!"
    except Exception as e:
        conn.close()
        return False, f"오류: {e}"

def delete_ticker(ticker):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM etf_data WHERE 티커 = ?", (ticker,))
        conn.commit()
    except: pass
    conn.close()

def handle_editor_change():
    changes = st.session_state["main_editor"]["edited_rows"]
    if changes:
        df_page = st.session_state["df_page_static"]
        for row_idx, updated_cols in changes.items():
            ticker = df_page.iloc[row_idx]["티커"]
            for col_name, new_val in updated_cols.items():
                update_db(ticker, col_name, new_val)
        st.toast("✅ 수정 내용 저장 완료!", icon="💾")

# ========================================================
# [메인 화면]
# ========================================================
def main():
    st.title("🦅 ETF 정복(김도현)")

    df_raw = load_data()
    if df_raw.empty:
        st.error("DB 파일을 찾을 수 없습니다.")
        return

    # --- 1. 상단 검색창 ---
    with st.expander("🔍 종목 검색 및 화면 설정 (클릭해서 열기/닫기)"):
        # 🌟 [추가됨] 화면에 보여줄 컬럼 선택 기능 (숨기기 유지용)
        st.write("👁️ **표시할 항목 선택 (체크 해제하면 숨겨집니다)**")
        
        # 전체 가능한 컬럼 목록
        all_columns = ['티커', 'url', '이름', '국가', '운용사', '배당수', '내용']
        # 기본적으로 보여줄 컬럼들
        default_columns = ['티커', 'url', '이름', '국가', '배당수', '내용']
        
        # 멀티 셀렉트로 사용자 선택 받기
        selected_cols = st.multiselect(
            "보여줄 컬럼을 선택하세요:",
            options=all_columns,
            default=default_columns,
            label_visibility="collapsed"
        )
        
        st.markdown("---") # 구분선

        c1, c2 = st.columns(2)
        with c1:
            country_options = ["전체", "미국", "한국"]
            selected_countries = st.multiselect("국가 선택", options=country_options, default=["전체"])
            search_ticker = st.text_input("🎯 티커 검색", placeholder="예: TSLA").strip().upper()
        
        with c2:
            search_kw = st.text_input("📝 키워드 검색", placeholder="이름/내용 등")
            
            st.write("💰 배당 횟수 (연)")
            max_val = int(df_raw['배당수_num'].max()) if not df_raw.empty else 12
            
            n_col1, n_col2 = st.columns(2)
            with n_col1:
                min_div = st.number_input("최소", min_value=0, max_value=max_val, value=0, step=1)
            with n_col2:
                max_div = st.number_input("최대", min_value=0, max_value=max_val, value=max_val, step=1)
        
        if st.button("🔄 검색 조건 초기화", use_container_width=True):
            st.session_state.current_page = 1
            st.rerun()

    # --- 2. 데이터 필터링 ---
    df = df_raw.copy()
    if "전체" not in selected_countries and selected_countries:
        df = df[df['국가'].isin(selected_countries)]
    if search_ticker:
        df = df[df['티커'].str.contains(search_ticker, case=False, na=False)]
    if search_kw:
        kw = search_kw.upper()
        mask = (df['이름'].str.contains(kw, case=False, na=False)) | \
               (df['운용사'].str.contains(kw, case=False, na=False)) | \
               (df['내용'].str.contains(kw, case=False, na=False))
        df = df[mask]
    df = df[(df['배당수_num'] >= min_div) & (df['배당수_num'] <= max_div)]

    # --- 3. 페이징 ---
    items_per_page = 30 
    total_items = len(df)
    total_pages = max(1, (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0))
    if st.session_state.current_page > total_pages: st.session_state.current_page = 1

    start_idx = (st.session_state.current_page - 1) * items_per_page
    df_page = df.iloc[start_idx : start_idx + items_per_page].reset_index(drop=True)
    st.session_state["df_page_static"] = df_page

    st.write(f"📊 조회된 종목: **{total_items}**개 (현재 {st.session_state.current_page} / {total_pages} 페이지)")

    # --- 4. 메인 표 (사용자 선택 컬럼만 표시) ---
    # 사용자가 선택한 컬럼이 하나도 없으면 경고 방지용으로 티커는 보여줌
    if not selected_cols:
        selected_cols = ['티커']

    st.data_editor(
        df_page[selected_cols],  # 🌟 여기서 선택한 컬럼만 잘라서 보여줍니다!
        column_config={
            "티커": st.column_config.TextColumn("티커", disabled=True, width="small"),
            "url": st.column_config.LinkColumn("정보", help="이동", validate="^https://.*", max_chars=100, display_text="🔗", width="small"),
            "이름": st.column_config.TextColumn("종목명", disabled=True, width="small"),
            "국가": st.column_config.TextColumn("국가", width="small"),
            "운용사": st.column_config.TextColumn("운용사", width="small"),
            "배당수": st.column_config.TextColumn("배당", width="small"),
            "내용": st.column_config.TextColumn("메모/내용", width="large"),
        },
        use_container_width=True, 
        hide_index=True, 
        key="main_editor",
        on_change=handle_editor_change
    )

    # --- 5. 페이지 버튼 ---
    st.markdown("---")
    col_prev, col_num, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.session_state.current_page > 1:
            if st.button("◀ 이전", use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
    with col_num:
        p_start = max(1, st.session_state.current_page - 1)
        p_end = min(total_pages, p_start + 2)
        p_cols = st.columns(len(range(p_start, p_end + 1)))
        for idx, p in enumerate(range(p_start, p_end + 1)):
            if p_cols[idx].button(f"{p}", type="primary" if p == st.session_state.current_page else "secondary", use_container_width=True):
                st.session_state.current_page = p
                st.rerun()
    with col_next:
        if st.session_state.current_page < total_pages:
            if st.button("다음 ▶", use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()

    # --- 6. 관리 및 다운로드 ---
    st.markdown("---")
    with st.expander("🛠️ 데이터 관리 도구 (추가/삭제/다운로드)"):
        tab1, tab2 = st.tabs(["➕ 종목 추가/삭제", "📥 엑셀 다운로드"])
        
        with tab1:
            c_add, c_del = st.columns(2)
            with c_add:
                st.caption("신규 종목 추가 (중복 시 빨간색 경고)")
                new_sym = st.text_input("티커 입력").upper()
                new_name = st.text_input("종목명 입력")
                new_country = st.selectbox("국가", ["미국", "한국"])
                
                if st.button("DB에 추가하기"):
                    if new_sym: 
                        success, msg = add_ticker(new_sym, new_name, new_country, "")
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            with c_del:
                st.caption("종목 삭제")
                del_sym = st.text_input("삭제할 티커").upper()
                if st.button("삭제하기", type="primary"):
                    if del_sym:
                        delete_ticker(del_sym)
                        st.warning(f"{del_sym} 삭제됨!")
                        st.rerun()

        with tab2:
            st.caption("데이터 엑셀 다운로드")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_raw.drop(columns=['url', '배당수_num'], errors='ignore').to_excel(writer, index=False)
            st.download_button(
                label="📥 엑셀 파일 다운로드 (클릭)",
                data=buffer.getvalue(),
                file_name=f"Stock_DB_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

if __name__ == "__main__":
    main()
