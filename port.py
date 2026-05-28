import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import glob
import os

# 1. การตั้งค่าหน้าจอแบบ Wide-screen
st.set_page_config(layout="wide", page_title="Karn Stock Portfolio")

st.title("📊 My Custom Stock Terminal")

# 🔍 ค้นหาไฟล์ Excel ในโปรเจกต์อัตโนมัติ
@st.cache_resource
def find_excel_file():
    excel_files = glob.glob("My portfolio_*.xlsx") + glob.glob("portfolio.xlsx")
    if excel_files:
        return excel_files[0]
    return "portfolio.xlsx"

EXCEL_FILE = find_excel_file()

# 📦 ฟังก์ชันสำหรับโหลดข้อมูลจาก Excel สดใหม่
def load_data_from_excel():
    if os.path.exists(EXCEL_FILE):
        try:
            df = pd.read_excel(EXCEL_FILE)
            df = df.rename(columns={'Fill Price': 'Fill_Price', 'Closing Time': 'Closing_Time'})
            if 'Symbol' in df.columns:
                df['Symbol'] = df['Symbol'].astype(str).str.strip()
            return df
        except Exception as e:
            st.sidebar.error(f"อ่านไฟล์ Excel ไม่สำเร็จ: {e}")
            return pd.DataFrame(columns=['Symbol', 'Side', 'Qty', 'Fill_Price', 'Commission', 'Closing_Time'])
    else:
        return pd.DataFrame(columns=['Symbol', 'Side', 'Qty', 'Fill_Price', 'Commission', 'Closing_Time'])

# โหลดข้อมูลจริงขึ้นมาทำงาน
df_current = load_data_from_excel()

# 💱 ดึงอัตราแลกเปลี่ยนเงินตราปัจจุบัน (USDTHB) พร้อม Cache 1 ชั่วโมง
@st.cache_data(ttl=3600)
def get_fx_rate():
    try: 
        return yf.Ticker("USDTHB=X").fast_info['last_price']
    except: 
        return 36.5

fx_rate = get_fx_rate()

# 🏎️ ฟังก์ชันดึงราคาหุ้นกลุ่มความเร็วสูง พร้อมระบบ Cache ป้องกันราคาเป็น 0 (จำค่า 5 นาที)
@st.cache_data(ttl=300)
def fetch_stock_prices(symbol_list):
    prices_dict = {}
    if not symbol_list:
        return prices_dict
        
    try:
        tickers_group = yf.Tickers(" ".join(symbol_list))
        for s in symbol_list:
            try:
                last_price = tickers_group.tickers[s].fast_info['last_price']
                if pd.isna(last_price) or last_price <= 0:
                    last_price = tickers_group.tickers[s].history(period="1d")['Close'].iloc[-1]
            except:
                try:
                    last_price = yf.Ticker(s).fast_info['last_price']
                except:
                    last_price = 0
            
            prices_dict[s] = last_price if (not pd.isna(last_price) and last_price > 0) else 0
    except:
        for s in symbol_list:
            try:
                p = yf.Ticker(s).fast_info['last_price']
                prices_dict[s] = p if p > 0 else 0
            except:
                prices_dict[s] = 0
                
    return prices_dict

# ==============================================================================
# SIDEBAR: หน้าต่างจัดการธุรกรรม
# ==============================================================================
st.sidebar.header("⚙️ Portfolio Management")
show_manager = st.sidebar.checkbox("เปิดเมนูจัดการธุรกรรม (Add/Delete)")

if show_manager:
    st.markdown("---")
    st.subheader("🛠️ การจัดการธุรกรรมหุ้น")
    
    with st.expander("➕ เพิ่มธุรกรรมใหม่ (Add Transaction)", expanded=False):
        with st.form("add_form", clear_on_submit=True):
            sym = st.text_input("สัญลักษณ์หุ้น (เช่น SET:PTT หรือ NASDAQ:AAPL)").strip()
            side = st.selectbox("ประเภทธุรกรรม (Side)", ["Buy", "Dividend"])
            qty = st.number_input("จำนวนหุ้น / จำนวนเงินปันผลที่ได้รับ (Qty)", min_value=0.0, step=0.000001, format="%.6f")
            price = st.number_input("ราคาต่อหน่วย (Fill Price) *ใส่ 0 ถ้าเป็นเงินปันผล*", min_value=0.0, step=0.01)
            comm = st.number_input("ค่าธรรมเนียม / คอมมิชชั่น (Commission)", min_value=0.0, step=0.01)
            date = st.date_input("วันที่ทำรายการ")
            
            submit_btn = st.form_submit_button("บันทึกข้อมูลธุรกรรม")
            if submit_btn and sym:
                new_row = pd.DataFrame([{
                    'Symbol': str(sym).upper().strip(),
                    'Side': str(side),
                    'Qty': float(qty),
                    'Fill Price': float(price),       
                    'Commission': float(comm),
                    'Closing Time': str(date)         
                }])
                
                df_raw_excel = pd.read_excel(EXCEL_FILE) if os.path.exists(EXCEL_FILE) else pd.DataFrame()
                df_updated = pd.concat([df_raw_excel, new_row], ignore_index=True)
                df_updated.to_excel(EXCEL_FILE, index=False)
                
                st.cache_data.clear() # ล้างแคชเพื่อให้ราคาหุ้นตัวใหม่อัปเดตทันที
                st.success(f"บันทึกข้อมูล {sym.upper()} ลงไฟล์ Excel เรียบร้อยแล้ว!")
                st.rerun()

    if os.path.exists(EXCEL_FILE) and not df_current.empty:
        with st.expander("🗑️ ลบธุรกรรมที่บันทึกไว้ (Delete Transaction)"):
            st.write("กดปุ่ม 'ลบ' ท้ายรายการที่ต้องการเอาออกจาก Excel:")
            for idx in reversed(df_current.index):
                item = df_current.loc[idx]
                col_item, col_btn = st.columns([4, 1])
                col_item.write(f"รายการ {idx}: **{item['Symbol']}** | {item['Side']} | Qty: {item['Qty']:,} | ราคา: {item['Fill_Price']:,}")
                if col_btn.button("ลบ", key=f"del_item_{idx}"):
                    df_raw_excel = pd.read_excel(EXCEL_FILE)
                    df_raw_excel = df_raw_excel.drop(idx).reset_index(drop=True)
                    df_raw_excel.to_excel(EXCEL_FILE, index=False)
                    st.cache_data.clear()
                    st.success(f"ลบรายการลำดับที่ {idx} สำเร็จ!")
                    st.rerun()
    st.markdown("---")

# ==============================================================================
# MAIN DASHBOARD: คำนวณผลและแสดงกราฟหน้าจอหลัก
# ==============================================================================
df_raw = df_current.copy()

if not df_raw.empty:
    df_buy = df_raw[df_raw['Side'] == 'Buy'].copy()
    df_div = df_raw[df_raw['Side'] == 'Dividend'].copy()
    
    def convert_symbol(symbol):
        sym_clean = str(symbol).upper().strip()
        if sym_clean.startswith('SET:'): 
            return sym_clean.replace('SET:', '').strip() + '.BK'
        return sym_clean.replace('NASDAQ:', '').replace('NYSE:', '').strip()

    if not df_buy.empty:
        df_buy['YF_Symbol'] = df_buy['Symbol'].apply(convert_symbol)
        df_buy['Total_Cost'] = (df_buy['Qty'] * df_buy['Fill_Price']) + df_buy['Commission']
        
        portfolio = df_buy.groupby('YF_Symbol').agg({
            'Qty': 'sum',
            'Total_Cost': 'sum',
            'Symbol': 'first'
        }).reset_index()
        
        portfolio['Avg_Price'] = portfolio['Total_Cost'] / portfolio['Qty']
        
        div_summary = df_div.groupby('Symbol')['Qty'].sum().reset_index() if not df_div.empty else pd.DataFrame(columns=['Symbol', 'Total_Dividend'])
        div_summary.columns = ['Symbol', 'Total_Dividend']
        
        portfolio = portfolio.merge(div_summary, on='Symbol', how='left')
        portfolio['Total_Dividend'] = portfolio['Total_Dividend'].fillna(0)
        
        with st.spinner('กำลังโหลดข้อมูลราคาสดจากตลาดหุ้น...'):
            symbol_list = portfolio['YF_Symbol'].tolist()
            cached_prices = fetch_stock_prices(symbol_list)
            
            prices = []
            for s in symbol_list:
                p_val = cached_prices.get(s, 0)
                if p_val <= 0:
                    p_val = portfolio[portfolio['YF_Symbol'] == s]['Avg_Price'].values[0]
                prices.append(p_val)
                
            portfolio['Current_Price'] = prices

        portfolio['Current_Value'] = portfolio['Qty'] * portfolio['Current_Price']
        
        portfolio['Value_THB'] = portfolio.apply(lambda x: x['Current_Value'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Current_Value'], axis=1)
        portfolio['Cost_THB'] = portfolio.apply(lambda x: x['Total_Cost'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Total_Cost'], axis=1)
        portfolio['Dividend_THB'] = portfolio.apply(lambda x: x['Total_Dividend'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Total_Dividend'], axis=1)
        
        portfolio['PL_THB'] = portfolio['Value_THB'] - portfolio['Cost_THB']
        portfolio['PL_Percent'] = (portfolio['PL_THB'] / portfolio['Cost_THB']) * 100 if portfolio['Cost_THB'].sum() > 0 else 0
        
        # 📊 คำนวณตัวเลขสำหรับ 4 กล่องสไตล์ TradingView
        total_val_thb = portfolio['Value_THB'].sum()
        total_cost_thb = portfolio['Cost_THB'].sum()
        
        # 1. กำไรที่ยังไม่รับรู้ (Unrealized P/L) วิ่งตามราคากลางตลาด ณ ตอนนั้น
        unrealized_pl_thb = portfolio['PL_THB'].sum()
        unrealized_pl_percent = (unrealized_pl_thb / total_cost_thb) * 100 if total_cost_thb > 0 else 0
        
        # 2. กำไรที่รับรู้แล้ว (Realized P/L) ในระบบนี้คือปันผลที่เข้าบัญชีชัวร์ๆ แล้ว
        total_dist_div_thb = portfolio['Dividend_THB'].sum()
        realized_pl_thb = total_dist_div_thb 
        
        # 3. กำไรทั้งหมดรวม (Total P/L) = กำไรหุ้น + ปันผล
        all_pl_thb = unrealized_pl_thb + realized_pl_thb
        all_pl_percent = (all_pl_thb / total_cost_thb) * 100 if total_cost_thb > 0 else 0
        
        # แปลงค่าเป็นหน่วย USD แถวสอง
        total_val_usd = total_val_thb / fx_rate
        unrealized_pl_usd = unrealized_pl_thb / fx_rate
        realized_pl_usd = realized_pl_thb / fx_rate
        all_pl_usd = all_pl_thb / fx_rate

        # 🎨 สร้าง 4 กล่องสไตล์แดชบอร์ด TradingView (Responsive UI ลื่นๆ)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">มูลค่าพอร์ตโฟลิโอ (Equity)</p><p style="color: #ffffff; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">฿{total_val_thb:,.2f}</p><p style="color: #848e9c; font-size: 15px; margin: 2px 0 0 0;">${total_val_usd:,.2f} <span style="font-size: 12px;">USD</span></p></div>', unsafe_allow_html=True)
        
        with col2:
            unreal_color = "#00b074" if unrealized_pl_thb >= 0 else "#ff3b30"
            unreal_sign = "+" if unrealized_pl_thb >= 0 else ""
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">กำไรที่ยังไม่รับรู้ (Unrealized P/L)</p><p style="color: {unreal_color}; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">{unreal_sign}฿{unrealized_pl_thb:,.2f}</p><p style="color: {unreal_color}; opacity: 0.9; font-size: 15px; margin: 2px 0 0 0;">{unreal_sign}{unrealized_pl_percent:+.2f}% (${unrealized_pl_usd:,.2f})</p></div>', unsafe_allow_html=True)
        
        with col3:
            # ยอดปันผลสะสมเข้ากระเป๋า ถือเป็นกำไรที่ล็อกเข้าพอร์ตชัวร์ๆ แล้ว (Realized)
            real_color = "#00b074" if realized_pl_thb > 0 else "#848e9c"
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">กำไรที่รับรู้แล้ว (Realized P/L)</p><p style="color: {real_color}; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">฿{realized_pl_thb:,.2f}</p><p style="color: {real_color}; opacity: 0.9; font-size: 15px; margin: 2px 0 0 0;">+100.00% (${realized_pl_usd:,.2f})</p></div>', unsafe_allow_html=True)
        
        with col4:
            all_color = "#00b074" if all_pl_thb >= 0 else "#ff3b30"
            all_sign = "+" if all_pl_thb >= 0 else ""
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">กำไรทั้งหมด (Total P/L)</p><p style="color: {all_color}; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">{all_sign}฿{all_pl_thb:,.2f}</p><p style="color: {all_color}; opacity: 0.9; font-size: 15px; margin: 2px 0 0 0;">{all_sign}{all_pl_percent:+.2f}% (${all_pl_usd:,.2f})</p></div>', unsafe_allow_html=True)
        
        st.write("---")

        st.subheader("📋 รายละเอียดหุ้นในพอร์ตโฟลิโอ")
        table_show = portfolio[['Symbol', 'Qty', 'Avg_Price', 'Current_Price', 'Value_THB', 'PL_THB', 'PL_Percent', 'Dividend_THB']].copy()
        table_show.columns = ['Symbol', 'Qty', 'Avg Price', 'Last Price', 'Current Value', 'P/L (THB)', 'P/L %', 'Dividends Received']
        
        def style_pl(val): return f"color: {'#089981' if val >= 0 else '#f23645'}; font-weight: bold;"
        st.dataframe(table_show.style.format({'Qty': '{:,.6f}', 'Avg Price': '{:,.2f}', 'Last Price': '{:,.2f}', 'Current Value': '฿{:,.2f}', 'P/L (THB)': '฿{:,.2f}', 'P/L %': '{:+.2f}%', 'Dividends Received': '฿{:,.2f}'}).map(style_pl, subset=['P/L (THB)', 'P/L %']), use_container_width=True)

        st.write("---")
        st.subheader("🎯 สัดส่วนการลงทุน (Portfolio Allocation)")
        fig = px.pie(portfolio, values='Value_THB', names='Symbol', hole=0.4)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 ไม่พบข้อมูลธุรกรรมในพอร์ต กรุณาคลิกเลือก 'เปิดเมนูจัดการธุรกรรม' ที่เมนูด้านซ้ายเพื่อเริ่มต้นบันทึกหุ้นตัวแรกของคุณครับ")