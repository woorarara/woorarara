import streamlit as st
import pandas as pd
import sqlite3
import os
import io # 파일 폰 다운로드용 기능
from datetime import datetime

# ========================================================
# [설정] 기본 세팅
# ========================================================
st.set_page_config(page_title="ETF 정복(김도현)", page_icon="🦅", layout="wide")

# 배포(GitHub) 및 로컬(내컴퓨터) 경로 자동 설정
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
    
    # 🌟 [핵심] 링크 URL 컬럼 생성 (한국->네이버, 미국->야후)
    # 모바일 환경에 맞춰 네이버는 모바일 페이지(m.stock)로 연결합니다.
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
    try:
        cur.execute("INSERT INTO etf_data (티커, 이름, 국가, 운용사, 내용, 배당수) VALUES (?, ?, ?, ?, '', '0')",
                    (ticker, name, country, manager))
        conn.commit()
    except: pass
    conn.close()

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

    # --- 1. 상단 검색창 (접이식) ---
    with st.expander("🔍 종목 검색 및 필터 (클릭해서 열기/닫기)"):
        c1, c2 = st.columns(2)
        with c1:
            country_options = ["전체", "미국", "한국"]
            selected_countries = st.multiselect("국가 선택", options=country_options, default=["전체"])
            search_ticker = st.text_input("🎯 티커 검색", placeholder="예: TSLA").strip().upper()
        
        with c2:
            search_kw = st.text_input("📝 키워드 검색", placeholder="이름/내용 등")
            
            # [모바일 최적화] 슬라이더 대신 숫자 입력기 사용
            st.write("💰 배당 횟수 (연)")
            max_val = int(df_raw['배당수_num'].max()) if not df_raw.empty else 12
            n1, n2 = st.columns(2)
            with n1:
                min_div = st.number_input("최소", min_
