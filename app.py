import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# ========================================================
# [설정] 기본 세팅
# ========================================================
st.set_page_config(page_title="ETF 정복(김도현)", page_icon="🦅", layout="wide")

# 배포용 경로 설정 (GitHub 환경 고려)
DB_PATH = "stocks.db" if os.path.exists("stocks.db") else os.path.join(os.path.expanduser("~"), "Desktop", "Stock_Data", "stocks.db")

# 페이지 세션 상태 초기화
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
        st.toast("✅ 자동 저장 완료!", icon="💾")

# ========================================================
# [메인 화면]
# ========================================================
def main():
    st.title("🦅 ETF 정복(김도현)")

    df_raw = load_data()
    if df_raw.empty:
        st.error("DB 파일을 찾을 수 없습니다.")
        return

    # --- 사이드바: 검색 및 필터만 배치 ---
    with st.sidebar:
        st.header("🔍 정밀 검색")
        country_options = ["전체", "미국", "한국"]
        selected_countries = st.multiselect("국가 필터", options=country_options, default=["전체"])
        
        search_ticker = st.text_input("🎯 티커 검색", placeholder="예: TSLA, 005930").strip().upper()
        search_kw = st.text_input("📝 키워드 검색", placeholder="이름/운용사/내용")
        
        max_div = int(df_raw['배당수_num'].max())
        div_range = st.slider("배당 횟수 필터 (연)", 0, max_div, (0, max_div))
        
        if st.button("🔄 검색 초기화", use_container_width=True):
            st.session_state.current_page = 1
            st.rerun()

    # --- 데이터 필터링 로직 ---
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
    df = df[(df['배당수_num'] >= div_range[0]) & (df['배당수_num'] <= div_range[1])]

    # --- 페이징 처리 ---
    items_per_page = 50 # 모바일 부하를 줄이기 위해 페이지당 개수를 50개로 하향 조정
    total_items = len(df)
    total_pages = max(1, (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0))
    
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = 1

    start_idx = (st.session_state.current_page - 1) * items_per_page
    df_page = df.iloc[start_idx : start_idx + items_per_page].reset_index(drop=True)
    st.session_state["df_page_static"] = df_page

    st.write(f"📊 종목: **{total_items}**개 (현재 {st.session_state.current_page}/{total_pages}P)")

    # --- 메인 에디터 ---
    st.data_editor(
        df_page[['티커', '이름', '국가', '배당수', '내용']], # 모바일 화면을 고려해 컬럼 축소
        column_config={
            "티커": st.column_config.TextColumn("티커", disabled=True),
            "이름": st.column_config.TextColumn("종목명", disabled=True, width="small"),
            "내용": st.column_config.TextColumn("내용", width="medium"),
        },
        use_container_width=True, hide_index=True, key="main_editor",
        on_change=handle_editor_change
    )

    # --- 하단 페이지 이동 버튼 (모바일 최적화) ---
    # 버튼이 아래로 밀리지 않도록 개수를 줄임
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.session_state.current_page > 1:
            if st.button("⬅️ 이전", use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
    
    with col2:
        # 현재 페이지 주변 3개만 표시하여 밀림 방지
        page_range = range(max(1, st.session_state.current_page - 1), min(total_pages, st.session_state.current_page + 1) + 1)
        btn_cols = st.columns(len(page_range))
        for idx, p in enumerate(page_range):
            if btn_cols[idx].button(f"{p}", type="primary" if p == st.session_state.current_page else "secondary", use_container_width=True):
                st.session_state.current_page = p
                st.rerun()

    with col3:
        if st.session_state.current_page < total_pages:
            if st.button("다음 ➡️", use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()

    # --- 하단 관리 메뉴 (모바일 배려: 사이드바 대신 메인 하단으로) ---
    st.markdown("---")
    st.subheader("🛠️ 관리 및 백업")
    m_col1, m_col2 = st.columns(2)
    
    with m_col1:
        with st.expander("➕ 종목 추가"):
            new_sym = st.text_input("추가 티커").upper()
            new_name = st.text_input("추가 이름")
            new_country = st.selectbox("추가 국가", ["미국", "한국"])
            if st.button("DB 추가"):
                if new_sym:
                    add_ticker(new_sym, new_name, new_country, "")
                    st.rerun()
                    
    with m_col2:
        with st.expander("🗑️ 종목 삭제"):
            del_sym = st.text_input("삭제 티커").upper()
            if st.button("DB 삭제", type="primary"):
                delete_ticker(del_sym)
                st.rerun()

    if st.button("📥 엑셀 백업 파일 생성", use_container_width=True):
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        df_raw.to_excel(f"DB_Backup_{now}.xlsx", index=False)
        st.success("바탕화면 혹은 서버 폴더에 백업 되었습니다.")

if __name__ == "__main__":
    main()
