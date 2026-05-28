import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import glob
import os

# 1. การตั้งค่าหน้าจอแบบ Wide-screen
st.set_page_config(layout="wide", page_title="My Stock Portfolio")

st.title("📊 My Custom Stock Terminal")

# 🔍 ค้นหาไฟล์ Excel ในโปรเจกต์อัตโนมัติ
@st.cache_resource
def find_excel_file():
    excel_files = glob.glob("My portfolio_*.xlsx") + glob.glob("portfolio.xlsx")
    if excel_files:
        return excel_files[0]
    return "portfolio.xlsx"  # ถ้าไม่เจอเลย ให้ใช้ชื่อนี้เป็นตัวตั้งต้น

EXCEL_FILE = find_excel_file()

# 📦 ฟังก์ชันสำหรับโหลดข้อมูลจาก Excel สดใหม่ทุกครั้ง (ไม่ใช้ Cache ค้างใน Session ยาวๆ เพื่อลดบั๊กตอนรีเฟรช)
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

# ดึงอัตราแลกเปลี่ยนเงินตราปัจจุบัน (USDTHB)
@st.cache_data(ttl=3600)
def get_fx_rate():
    try: 
        return yf.Ticker("USDTHB=X").fast_info['last_price']
    except: 
        return 36.5

fx_rate = get_fx_rate()

# ==============================================================================
# SIDEBAR: หน้าต่างจัดการธุรกรรม (UI สำหรับ Add / Delete ลงไฟล์ Excel โดยตรง)
# ==============================================================================
st.sidebar.header("⚙️ Portfolio Management")
show_manager = st.sidebar.checkbox("เปิดเมนูจัดการธุรกรรม (Add/Delete)")

if show_manager:
    st.markdown("---")
    st.subheader("🛠️ การจัดการธุรกรรมหุ้น")
    
    # ส่วนฟอร์มสำหรับเพิ่มข้อมูลธุรกรรมใหม่ (ADD)
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
                # บันทึกเป็นคอลัมน์ดั้งเดิมตามรูปแบบของ Excel ของผู้ใช้
                new_row = pd.DataFrame([{
                    'Symbol': str(sym).upper().strip(),
                    'Side': str(side),
                    'Qty': float(qty),
                    'Fill Price': float(price),       # ใช้ชื่อคอลัมน์ดั้งเดิมเพื่อเซฟลง Excel
                    'Commission': float(comm),
                    'Closing Time': str(date)         # ใช้ชื่อคอลัมน์ดั้งเดิมเพื่อเซฟลง Excel
                }])
                
                # โหลดข้อมูลดิบล่าสุดจากไฟล์มาต่อแถวเพื่อป้องกันการบันทึกทับซ้ำซ้อน
                df_raw_excel = pd.read_excel(EXCEL_FILE) if os.path.exists(EXCEL_FILE) else pd.DataFrame()
                df_updated = pd.concat([df_raw_excel, new_row], ignore_index=True)
                
                # สั่งเซฟลงไฟล์ Excel ทันที! ข้อมูลจะอยู่ถาวร
                df_updated.to_excel(EXCEL_FILE, index=False)
                st.success(f"บันทึกข้อมูล {sym.upper()} ลงไฟล์ Excel เรียบร้อยและถาวรแล้ว!")
                st.rerun()

    # ส่วนตารางรายการล่าสุดเพื่อกดลบออก (DELETE)
    if os.path.exists(EXCEL_FILE) and not df_current.empty:
        with st.expander("🗑️ ลบธุรกรรมที่บันทึกไว้ (Delete Transaction)"):
            st.write("กดปุ่ม 'ลบ' ท้ายรายการที่ต้องการเอาออกจาก Excel:")
            for idx in reversed(df_current.index):
                item = df_current.loc[idx]
                col_item, col_btn = st.columns([4, 1])
                col_item.write(f"รายการ {idx}: **{item['Symbol']}** | {item['Side']} | Qty: {item['Qty']:,} | ราคา: {item['Fill_Price']:,}")
                if col_btn.button("ลบ", key=f"del_item_{idx}"):
                    # โหลดข้อมูลดิบมาลบแถวออกและเซฟกลับซ้ำ
                    df_raw_excel = pd.read_excel(EXCEL_FILE)
                    df_raw_excel = df_raw_excel.drop(idx).reset_index(drop=True)
                    df_raw_excel.to_excel(EXCEL_FILE, index=False)
                    st.success(f"ลบรายการลำดับที่ {idx} ออกจาก Excel สำเร็จ!")
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
        
        # 🏎️ ปรับระบบดึงราคาเป็นแบบสุ่มตรวจดึงเดี่ยววนรอบเพื่อแก้ปัญหา Timezone บนหน้าคลาวด์หลุดเป็น 0
        with st.spinner('กำลังดึงข้อมูลราคาสดจากตลาดหุ้น...'):
            prices = []
            for s in portfolio['YF_Symbol']:
                last_price = 0
                try:
                    ticker_obj = yf.Ticker(s)
                    # ใช้ fast_info เป็นหลัก ถ้าไม่ได้ให้ถอยไปใช้ประวัติวันล่าสุด
                    last_price = ticker_obj.fast_info['last_price']
                    if pd.isna(last_price) or last_price <= 0:
                        last_price = ticker_obj.history(period="1d")['Close'].iloc[-1]
                except:
                    last_price = 0
                prices.append(last_price)
                
            portfolio['Current_Price'] = prices

        portfolio['Current_Value'] = portfolio['Qty'] * portfolio['Current_Price']
        
        portfolio['Value_THB'] = portfolio.apply(lambda x: x['Current_Value'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Current_Value'], axis=1)
        portfolio['Cost_THB'] = portfolio.apply(lambda x: x['Total_Cost'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Total_Cost'], axis=1)
        portfolio['Dividend_THB'] = portfolio.apply(lambda x: x['Total_Dividend'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Total_Dividend'], axis=1)
        
        portfolio['PL_THB'] = portfolio['Value_THB'] - portfolio['Cost_THB']
        portfolio['PL_Percent'] = (portfolio['PL_THB'] / portfolio['Cost_THB']) * 100 if portfolio['Cost_THB'].sum() > 0 else 0
        
        total_val_thb = portfolio['Value_THB'].sum()
        total_cost_thb = portfolio['Cost_THB'].sum()
        total_pl_thb = portfolio['PL_THB'].sum()
        total_pl_percent = (total_pl_thb / total_cost_thb) * 100 if total_cost_thb > 0 else 0
        total_dist_div_thb = portfolio['Dividend_THB'].sum()
        
        total_val_usd = total_val_thb / fx_rate
        total_pl_usd = total_pl_thb / fx_rate
        total_dist_div_usd = total_dist_div_thb / fx_rate
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39;"><p style="color: #cfd4e0; font-size: 14px; margin: 0; text-transform: uppercase;">Total Equity (มูลค่าพอร์ตปัจจุบัน)</p><p style="color: #ffffff; font-size: 30px; font-weight: 700; margin: 10px 0 0 0;">฿{total_val_thb:,.2f}</p><p style="color: #787b86; font-size: 18px; margin: 2px 0 0 0;">${total_val_usd:,.2f} <span style="font-size: 14px;">USD</span></p></div>', unsafe_allow_html=True)
        with col2:
            pl_color = "#089981" if total_pl_thb >= 0 else "#f23645"
            st.markdown(f'<div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39;"><p style="color: #cfd4e0; font-size: 14px; margin: 0; text-transform: uppercase;">Total Profit/Loss (กำไร/ขาดทุนรวม)</p><p style="color: {pl_color}; font-size: 30px; font-weight: 700; margin: 10px 0 0 0;">฿{total_pl_thb:,.2f} <span style="font-size: 18px; font-weight: 500;">({total_pl_percent:+.2f}%)</span></p><p style="color: {pl_color}; opacity: 0.8; font-size: 18px; margin: 2px 0 0 0;">${total_pl_usd:,.2f} <span style="font-size: 14px;">USD</span></p></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39;"><p style="color: #cfd4e0; font-size: 14px; margin: 0; text-transform: uppercase;">Total Dividends (ปันผลรับรวม)</p><p style="color: #ffffff; font-size: 30px; font-weight: 700; margin: 10px 0 0 0;">฿{total_dist_div_thb:,.2f}</p><p style="color: #787b86; font-size: 18px; margin: 2px 0 0 0;">${total_dist_div_usd:,.2f} <span style="font-size: 14px;">USD</span></p></div>', unsafe_allow_html=True)
        
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