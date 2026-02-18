import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# ========================================================
# [설정] 기본 세팅
# ========================================================
st.set_page_config(page_title="ETF 정복(김도현)", page_icon="🦅", layout="wide")

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
BASE_FOLDER = os.path.join(desktop_path, "Stock_Data")
DB_PATH = "stocks.db"

# 폴더가 없으면 생성
if not os.path.exists(BASE_FOLDER):
    os.makedirs(BASE_FOLDER)

# 페이지 및 세션 상태 초기화
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

# ========================================================
# [핵심] 자동 저장 핸들러
# ========================================================
def handle_editor_change():
    changes = st.session_state["main_editor"]["edited_rows"]
    if changes:
        df_page = st.session_state["df_page_static"]
        for row_idx, updated_cols in changes.items():
            ticker = df_page.iloc[row_idx]["티커"]
            for col_name, new_val in updated_cols.items():
                update_db(ticker, col_name, new_val)
        st.toast("✅ 수정사항이 DB에 자동 저장되었습니다.", icon="💾")

# ========================================================
# [메인 화면]
# ========================================================
def main():
    st.title("🦅 ETF 정복(김도현)")

    df_raw = load_data()
    if df_raw.empty:
        st.error("DB 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        return

    # --- 사이드바 ---
    with st.sidebar:
        st.header("💾 데이터 백업")
        # 🌟 엑셀 백업 버튼 추가
        if st.button("📥 현재 DB를 엑셀로 백업", use_container_width=True):
            try:
                now = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"DB_Backup_{now}.xlsx"
                backup_path = os.path.join(BASE_FOLDER, backup_filename)
                
                # 전체 데이터를 엑셀로 저장
                df_raw.drop(columns=['배당수_num'], errors='ignore').to_excel(backup_path, index=False)
                st.success(f"✅ 백업 완료!\n{backup_filename}")
                os.startfile(BASE_FOLDER) # 폴더 바로 열어주기
            except Exception as e:
                st.error(f"❌ 백업 실패: {e}")

        st.markdown("---")
        st.header("➕ 종목 관리")
        with st.expander("신규 종목 추가"):
            new_sym = st.text_input("티커 추가").upper()
            new_name = st.text_input("종목명")
            new_country = st.selectbox("국가 선택", ["미국", "한국"])
            new_mgr = st.text_input("운용사")
            if st.button("DB에 추가"):
                if new_sym:
                    add_ticker(new_sym, new_name, new_country, new_mgr)
                    st.success(f"{new_sym} 추가 완료!")
                    st.rerun()

        with st.expander("종목 삭제"):
            del_sym = st.text_input("삭제할 티커").upper()
            if st.button("데이터 영구 삭제"):
                delete_ticker(del_sym)
                st.warning(f"{del_sym} 삭제됨")
                st.rerun()

        st.markdown("---")
        st.header("🔍 정밀 검색")
        country_options = ["전체", "미국", "한국"]
        selected_countries = st.multiselect("국가 필터", options=country_options, default=["전체"])
        search_ticker = st.text_input("🎯 티커 검색", placeholder="티커 입력").strip().upper()
        search_kw = st.text_input("📝 내용/이름/운용사 검색", placeholder="2글자 이상 입력")
        
        max_div = int(df_raw['배당수_num'].max())
        div_range = st.slider("배당 횟수 필터 (연)", 0, max_div, (0, max_div))
        
        if st.button("검색 초기화"):
            st.session_state.current_page = 1
            st.rerun()

    # --- 필터링 로직 ---
    df = df_raw.copy()
    if "전체" not in selected_countries and selected_countries:
        df = df[df['국가'].isin(selected_countries)]
    if search_ticker:
        if len(search_ticker) <= 2:
            df = df[df['티커'].str.startswith(search_ticker, na=False)]
        else:
            df = df[df['티커'].str.contains(search_ticker, case=False, na=False)]
    if search_kw and len(search_kw.strip()) >= 2:
        kw = search_kw.strip().upper()
        mask = (df['이름'].str.contains(kw, case=False, na=False)) | \
               (df['운용사'].str.contains(kw, case=False, na=False)) | \
               (df['내용'].str.contains(kw, case=False, na=False))
        df = df[mask]
    df = df[(df['배당수_num'] >= div_range[0]) & (df['배당수_num'] <= div_range[1])]

    # --- 페이징 및 출력 ---
    items_per_page = 100
    total_items = len(df)
    total_pages = max(1, (total_items // items_per_page) + (1 if total_items % items_per_page > 0 else 0))
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = 1
    start_idx = (st.session_state.current_page - 1) * items_per_page
    df_page = df.iloc[start_idx : start_idx + items_per_page].reset_index(drop=True)
    st.session_state["df_page_static"] = df_page

    st.write(f"📊 조회된 종목: **{total_items}**개 (현재 {st.session_state.current_page} / {total_pages} 페이지)")

    # --- 메인 에디터 (자동 저장) ---
    display_cols = ['티커', '이름', '국가', '운용사', '배당수', '내용']
    st.data_editor(
        df_page[display_cols],
        column_config={
            "티커": st.column_config.TextColumn("티커", disabled=True),
            "이름": st.column_config.TextColumn("종목명", disabled=True, width="medium"),
            "내용": st.column_config.TextColumn("투자포인트/내용", width="large"),
        },
        use_container_width=True, hide_index=True, key="main_editor",
        on_change=handle_editor_change
    )

    st.markdown("---")

    # --- 하단 페이지 이동 버튼 ---
    p_cols = st.columns(min(total_pages + 2, 15))
    if st.session_state.current_page > 1:
        if p_cols[0].button("이전"):
            st.session_state.current_page -= 1
            st.rerun()
    start_p = max(1, st.session_state.current_page - 4)
    end_p = min(total_pages, start_p + 9)
    for i, p in enumerate(range(start_p, end_p + 1)):
        if p_cols[i+1].button(f"{p}", type="primary" if p == st.session_state.current_page else "secondary"):
            st.session_state.current_page = p
            st.rerun()
    if st.session_state.current_page < total_pages:
        if p_cols[-1].button("다음"):
            st.session_state.current_page += 1
            st.rerun()

if __name__ == "__main__":

    main()
