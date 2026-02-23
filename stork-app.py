import streamlit as st
import sqlite3
import pandas as pd
import os
import yfinance as yf
import math
import plotly.express as px

# ========================================================
# 🎨 1. 앱 기본 설정
# ========================================================
st.set_page_config(page_title="나만의 주식 스크리너 🚀", layout="wide")

DB_FILE = "Stock_Master.db"

# ========================================================
# 🧠 2. 상태 저장소(Session State) 초기화 세팅
# (초기화 버튼을 위해 슬라이더와 검색창의 기억 공간을 만듭니다)
# ========================================================
if 'page' not in st.session_state: st.session_state.page = 1
if 'search_keyword' not in st.session_state: st.session_state.search_keyword = ""
if 'min_div' not in st.session_state: st.session_state.min_div = 0.0
if 'max_per' not in st.session_state: st.session_state.max_per = 200.0
if 'max_pbr' not in st.session_state: st.session_state.max_pbr = 50.0
if 'min_roe' not in st.session_state: st.session_state.min_roe = -50.0
if 'max_psr' not in st.session_state: st.session_state.max_psr = 100.0

# ========================================================
# 💵 3. 실시간 환율 & 재무 데이터 불러오기
# ========================================================
@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        rate = yf.Ticker("KRW=X").fast_info['lastPrice']
        return round(rate, 2)
    except:
        return None

@st.cache_data(show_spinner=False, ttl=86400)
def get_financial_chart_data(ticker, market_choice, kr_market_type):
    try:
        if market_choice == "🇰🇷 한국 주식":
            yf_ticker = f"{ticker}.KS" if kr_market_type == 'KOSPI' else f"{ticker}.KQ"
        else:
            yf_ticker = ticker
            
        stock = yf.Ticker(yf_ticker)
        fin = stock.financials 
        
        if fin is None or fin.empty: return None
            
        def get_safe_row(df, possible_keys):
            for k in possible_keys:
                if k in df.index: return df.loc[k]
            return pd.Series([0]*len(df.columns), index=df.columns)

        rev = get_safe_row(fin, ['Total Revenue', 'Operating Revenue', 'Revenue'])
        op = get_safe_row(fin, ['Operating Income', 'Operating Profit'])
        ni = get_safe_row(fin, ['Net Income', 'Net Income Common Stockholders'])
        
        df_chart = pd.DataFrame({'매출액': rev, '영업이익': op, '당기순이익': ni})
        df_chart = df_chart.sort_index(ascending=True)
        df_chart.index = df_chart.index.strftime('%Y')
        return df_chart.tail(5)
    except:
        return None

# ========================================================
# 💾 4. DB 데이터 불러오기
# ========================================================
@st.cache_data
def load_data(market_choice):
    conn = sqlite3.connect(DB_FILE)
    if market_choice == "🇰🇷 한국 주식":
        df = pd.read_sql("SELECT 티커, 기업명, 시장, 섹터, 시가총액, 배당수익률, 배당주기, ROE, PER, PBR, PSR FROM korea_master", conn)
    else:
        df = pd.read_sql("SELECT 티커, 기업명, 'US' as 시장, 섹터, 시가총액, 배당수익률, 배당주기, ROE, PER, PBR, PSR FROM usa_master", conn)
    conn.close()

    for col in ['ROE', 'PER', 'PBR', 'PSR', '배당수익률']:
        df[col] = pd.to_numeric(df[col].replace(['-', '미확인'], pd.NA), errors='coerce')
    
    df['섹터'] = df['섹터'].fillna('기타').replace('', '기타')
    return df

# ========================================================
# 🎛️ 5. 사이드바 (조종석) & 초기화 버튼
# ========================================================
st.sidebar.title("🚀 주식 스크리너")
market = st.sidebar.radio("어느 시장을 볼까요?", ["🇰🇷 한국 주식", "🇺🇸 미국 주식"])

# 나라가 바뀔 때 해당 나라의 섹터 기억 공간도 세팅해 줍니다.
sector_key = f"sector_{market}"
if sector_key not in st.session_state: st.session_state[sector_key] = []

current_rate = get_exchange_rate()
if current_rate:
    st.sidebar.metric(label="🇺🇸 실시간 환율 (USD/KRW)", value=f"{current_rate:,.2f} 원")

st.sidebar.markdown("---")
df = load_data(market)

# 💡 대망의 [초기화 버튼]
if st.sidebar.button("🔄 검색 및 필터 초기화 (전체 보기)", use_container_width=True):
    st.session_state.search_keyword = ""
    st.session_state[sector_key] = []
    st.session_state.min_div = 0.0
    st.session_state.max_per = 200.0
    st.session_state.max_pbr = 50.0
    st.session_state.min_roe = -50.0
    st.session_state.max_psr = 100.0
    st.session_state.page = 1
    st.rerun() # 앱을 즉시 새로고침해서 비워버림

st.sidebar.subheader("🔍 상세 검색")
search_keyword = st.sidebar.text_input("티커 또는 기업명 검색", placeholder="예: 삼성전자, AAPL...", key="search_keyword")

all_sectors = sorted(df['섹터'].astype(str).unique().tolist())
selected_sectors = st.sidebar.multiselect("섹터(업종) 선택", options=all_sectors, key=sector_key)

st.sidebar.subheader("💰 재무 필터 (슬라이더)")
# 💡 슬라이더들이 session_state의 값을 바라보도록 key를 연결합니다.
min_div = st.sidebar.slider("최소 배당수익률 (%)", 0.0, 15.0, step=0.5, key="min_div")
max_per = st.sidebar.slider("최대 PER (수익대비 저평가)", 0.0, 200.0, step=1.0, key="max_per")
max_pbr = st.sidebar.slider("최대 PBR (자산대비 저평가)", 0.0, 50.0, step=0.5, key="max_pbr")
min_roe = st.sidebar.slider("최소 ROE (자본 수익성, %)", -50.0, 100.0, step=1.0, key="min_roe")
max_psr = st.sidebar.slider("최대 PSR (매출대비 저평가)", 0.0, 100.0, step=0.5, key="max_psr")

# ========================================================
# 🧠 6. 지능형 필터링 엔진 (빈칸 무시 기술)
# ========================================================
filtered_df = df.copy()

if search_keyword:
    filtered_df = filtered_df[
        filtered_df['티커'].str.contains(search_keyword, case=False, na=False) |
        filtered_df['기업명'].str.contains(search_keyword, case=False, na=False)
    ]

if selected_sectors:
    filtered_df = filtered_df[filtered_df['섹터'].isin(selected_sectors)]

# 💡 슬라이더가 최대/최소 끝에 있을 때는 아예 필터링을 하지 않음!
# (이렇게 해야 지표가 아예 없는 '우선주'나 '적자기업'도 필터 해제 시 화면에 뜹니다)
if min_div > 0.0: filtered_df = filtered_df[filtered_df['배당수익률'] >= min_div]
if max_per < 200.0: filtered_df = filtered_df[filtered_df['PER'] <= max_per]
if max_pbr < 50.0: filtered_df = filtered_df[filtered_df['PBR'] <= max_pbr]
if min_roe > -50.0: filtered_df = filtered_df[filtered_df['ROE'] >= min_roe]
if max_psr < 100.0: filtered_df = filtered_df[filtered_df['PSR'] <= max_psr]

# ========================================================
# 🧮 7. 100개 자르기 & 페이지 번호 계산
# ========================================================
ITEMS_PER_PAGE = 100
total_items = len(filtered_df)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

if st.session_state.page > total_pages: st.session_state.page = total_pages
if st.session_state.page < 1: st.session_state.page = 1

start_idx = (st.session_state.page - 1) * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE

display_df = filtered_df.iloc[start_idx:end_idx]
display_df = display_df.drop(columns=['시장']) if '시장' in display_df.columns else display_df

# ========================================================
# 🖥️ 8. 메인 화면 (데이터 표 & 페이지 버튼)
# ========================================================
st.title(f"{market} 검색 결과")
st.markdown(f"**🎯 검색 결과:** 총 `{total_items}`개 종목 (페이지 {st.session_state.page} / {total_pages})")

cap_format = "{:,.0f} 원" if market == "🇰🇷 한국 주식" else "$ {:,.0f}"

st.dataframe(
    display_df.style.format({
        "배당수익률": "{:.2f}%", "ROE": "{:.2f}%", "PER": "{:.2f}",
        "PBR": "{:.2f}", "PSR": "{:.2f}", "시가총액": cap_format
    }),
    use_container_width=True, height=400
)

cols = st.columns([1, 1, 2, 1, 1])
with cols[0]:
    if st.button("⏪ 처음으로"): st.session_state.page = 1
with cols[1]:
    if st.button("◀ 이전") and st.session_state.page > 1: st.session_state.page -= 1
with cols[2]:
    st.markdown(f"<div style='text-align: center; padding-top: 5px;'><b>{st.session_state.page} / {total_pages} Page</b></div>", unsafe_allow_html=True)
with cols[3]:
    if st.button("다음 ▶") and st.session_state.page < total_pages: st.session_state.page += 1
with cols[4]:
    if st.button("마지막 ⏩"): st.session_state.page = total_pages

# ========================================================
# 📊 9. 실시간 재무 차트 (Plotly 가로 정렬 적용)
# ========================================================
st.markdown("---")
st.subheader("📊 개별 종목 실적 분석 (최대 5년)")

if not filtered_df.empty:
    selected_corp = st.selectbox("실적을 확인할 기업을 선택하세요:", filtered_df['기업명'].tolist())
    
    if selected_corp:
        corp_data = filtered_df[filtered_df['기업명'] == selected_corp].iloc[0]
        selected_ticker = corp_data['티커']
        kr_market_type = corp_data.get('시장', 'US')
        
        with st.spinner(f"📡 야후에서 {selected_corp}의 실적을 가져오는 중..."):
            chart_data = get_financial_chart_data(selected_ticker, market, kr_market_type)
            
            if chart_data is not None and not chart_data.empty:
                unit = "원" if market == "🇰🇷 한국 주식" else "달러 (USD)"
                st.markdown(f"**{selected_corp} ({selected_ticker})**의 핵심 실적 (단위: {unit})")
                
                fig = px.bar(chart_data, barmode='group')
                fig.update_xaxes(tickangle=0) 
                fig.update_layout(
                    xaxis_title="", yaxis_title=f"금액 ({unit})",
                    legend_title_text="실적 지표", margin=dict(t=20, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"😢 야후 파이낸스에 {selected_corp}의 재무 차트 데이터가 없습니다.")
else:

    st.info("검색 조건에 맞는 종목이 없습니다.")
