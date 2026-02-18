import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# ========================================================
# [설정] 기본 세팅
# ========================================================
st.set_page_config(page_title="ETF 정복(김도현)", page_icon="🦅", layout="wide")

# 배포 및 로컬 겸용 경로
DB_PATH = "stocks.db" if os.path.exists("stocks.db") else os.path.join(os.path.expanduser("~"), "Desktop", "Stock_Data", "stocks.db")

if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

# ========================================================
# [DB 함수]
# ========================================================
def load_data():
    if not os.path.exists(DB_PATH): return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM etf_data", conn)
    conn.close()
    df['배당수_num'] = pd.to_numeric(df['배당수'], errors='coerce').fillna(0)
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
    cur.execute("INSERT INTO etf_data (티커, 이름, 국가, 운용사, 내용, 배당수) VALUES (?, ?, ?, ?, '', '0')",
                (ticker, name, country, manager))
    conn.commit()
    conn.close()

def delete_ticker(ticker):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM etf_data WHERE 티커 = ?", (ticker,))
    conn.commit()
    conn.close()

def handle_editor_change():
    changes = st.session_state["main_editor"]["edited_rows"]
    if changes:
        df_page = st.session_state["df_page_static"]
        for row_idx, updated_cols in changes.items():
            ticker = df_page.iloc[row_idx]["티커"]
            for col_name, new_val in updated_cols.items():
                update_db(ticker, col_name, new_val)
        st.toast("💾 자동 저장 완료!")

# ========================================================
# [메인 화면]
# ========================================================
def main():
    st.title("🦅 ETF 정복(김도현)")

    df_raw = load_data()
    if df_raw.empty:
        st.error("DB 파일을 찾을 수 없습니다.")
        return

    # --- 🌟 정밀 검색창 (Expander) ---
    with st.expander("🔍 정밀 검색창 열기/닫기"):
        c1, c2 = st.columns(2)
        with c1:
            country_options = ["전체", "미국", "한국"]
            selected_countries = st.multiselect("국가 필터", options=country_options, default=["전체"])
            search_ticker = st.text_input("🎯 티커 검색", placeholder="예: TSLA").strip().upper()
        
        with c2:
            search_kw = st.text_input("📝 키워드 검색", placeholder="이름/운용사/내용")
            
            # 🌟 [수정] 모바일 친화적 배당 필터 (숫자 입력 방식)
            st.write("💰 배당 횟수 필터 (연)")
            max_val = int(df_raw['배당수_num'].max())
            
            # 가로로 배치 (모바일에서도 버튼이 잘 보임)
            n1, n2 = st.columns(2)
            with n1:
                min_div = st.number_input("최소", min_value=0, max_value=max_val, value=0, step=1)
            with n2:
                max_div = st.number_input("최대", min_value=0, max_value=max_val, value=max_val, step=1)
        
        if st.button("🔄 검색 조건 초기화", use_container_width=True):
            st.session_state.current_page = 1
            st.rerun()

    # --- 필터링 로직 ---
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
    
    # 🌟 [수정] 입력된 최소/최대 값으로 필터링 적용
    df = df[(df['배당수_num'] >= min_div) & (df['배당수_num'] <= max_div)]

    # --- 페이징 처리 ---
    items_per_page = 30 
    total_items = len(df)
    total_pages = max(1, (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0))
    if st.session_state.current_page > total_pages: st.session_state.current_page = 1

    start_idx = (st.session_state.current_page - 1) * items_per_page
    df_page = df.iloc[start_idx : start_idx + items_per_page].reset_index(drop=True)
    st.session_state["df_page_static"] = df_page

    st.write(f"📊 **{total_items}**개 종목 (현재 {st.session_state.current_page}/{total_pages}P)")

    # --- 메인 에디터 ---
    st.data_editor(
        df_page[['티커', '이름', '국가', '배당수', '내용']], 
        column_config={
            "티커": st.column_config.TextColumn("티커", disabled=True),
            "이름": st.column_config.TextColumn("종목명", disabled=True, width="small"),
            "국가": st.column_config.TextColumn("국가", width="small"),
            "배당수": st.column_config.TextColumn("배당", width="small"),
            "내용": st.column_config.TextColumn("내용", width="large"),
        },
        use_container_width=True, hide_index=True, key="main_editor",
        on_change=handle_editor_change
    )

    # --- 하단 페이지 이동 버튼 ---
    st.markdown("---")
    col_prev, col_num, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.session_state.current_page > 1:
            if st.button("⬅️ 이전", use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
    with col_num:
        p_start = max(1, st.session_state.current_page - 1)
        p_end = min(total_pages, p_start + 2)
        p_range = range(p_start, p_end + 1)
        btn_cols = st.columns(len(p_range))
        for idx, p in enumerate(p_range):
            if btn_cols[idx].button(f"{p}", type="primary" if p == st.session_state.current_page else "secondary", use_container_width=True):
                st.session_state.current_page = p
                st.rerun()
    with col_next:
        if st.session_state.current_page < total_pages:
            if st.button("다음 ➡️", use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()

    # --- 관리 기능 ---
    st.markdown("---")
    with st.expander("🛠️ 데이터 관리 (추가/삭제/백업)"):
        c_add, c_del = st.columns(2)
        with c_add:
            st.write("**[종목 추가]**")
            new_sym = st.text_input("티커").upper()
            new_name = st.text_input("이름")
            new_country = st.selectbox("국가", ["미국", "한국"])
            if st.button("DB 추가"):
                if new_sym: add_ticker(new_sym, new_name, new_country, ""); st.rerun()
        with c_del:
            st.write("**[종목 삭제]**")
            del_sym = st.text_input("삭제 티커").upper()
            if st.button("데이터 영구 삭제", type="primary"):
                delete_ticker(del_sym); st.rerun()
        
        st.write("---")
        if st.button("📥 현재 DB를 엑셀로 백업", use_container_width=True):
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            df_raw.to_excel(f"DB_Backup_{now}.xlsx", index=False)
            st.success(f"백업 완료 (DB_Backup_{now}.xlsx)")

if __name__ == "__main__":
    main()
