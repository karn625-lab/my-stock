import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import glob
import os

# 1. การตั้งค่าหน้าจอแบบ Wide-screen ให้สวยงามสไตล์ Terminal
st.set_page_config(layout="wide", page_title="My Stock Portfolio")

st.title("📊 My Custom Stock Terminal")

# 🔍 ค้นหาไฟล์ Excel ในโปรเจกต์อัตโนมัติ (เป็นค่าตั้งต้น)
@st.cache_resource
def find_excel_file():
    excel_files = glob.glob("My portfolio_*.xlsx") + glob.glob("portfolio.xlsx")
    if excel_files:
        return excel_files[0]
    return "portfolio.xlsx"

DEFAULT_EXCEL_FILE = find_excel_file()

# 📦 ระบบโหลดข้อมูลจากไฟล์ Excel หลักในโปรเจกต์เข้าสู่ Session State เพื่อความลื่นไหลในการใช้งาน
if 'df_portfolio' not in st.session_state:
    if os.path.exists(DEFAULT_EXCEL_FILE):
        try:
            df = pd.read_excel(DEFAULT_EXCEL_FILE)
            df = df.rename(columns={'Fill Price': 'Fill_Price', 'Closing Time': 'Closing_Time'})
            if 'Symbol' in df.columns:
                df['Symbol'] = df['Symbol'].astype(str).str.strip()
            st.session_state.df_portfolio = df
        except:
            st.session_state.df_portfolio = pd.DataFrame(columns=['Symbol', 'Side', 'Qty', 'Fill_Price', 'Commission', 'Closing_Time'])
    else:
        st.session_state.df_portfolio = pd.DataFrame(columns=['Symbol', 'Side', 'Qty', 'Fill_Price', 'Commission', 'Closing_Time'])

# 💱 ดึงอัตราแลกเปลี่ยนเงินตราปัจจุบัน (USDTHB) พร้อม Cache 1 ชั่วโมง
@st.cache_data(ttl=3600)
def get_fx_rate():
    try: 
        return yf.Ticker("USDTHB=X").fast_info['last_price']
    except: 
        return 36.5

fx_rate = get_fx_rate()

# 🏎️ ฟังก์ชันดึงราคาหุ้นกลุ่มความเร็วสูง พร้อมระบบ Cache 5 นาที ป้องกันราคาเป็น 0
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

# 📈 ฟังก์ชันสำหรับคำนวณและสร้างเทคนิคอลกราฟ (EMA / RSI) แบบยืดหยุ่นตามเวลาที่เลือก
def draw_technical_chart(symbol, period_choice):
    try:
        stock = yf.Ticker(symbol)
        df_hist = stock.history(period=period_choice)
        if df_hist.empty or len(df_hist) < 20:
            st.warning(f"ข้อมูลหุ้น {symbol} มีไม่เพียงพอสำหรับการคำนวณเส้นเทคนิคอลในกรอบเวลานี้")
            return

        # คำนวณเส้นอินดิเคเตอร์เชิงเทคนิค
        df_hist['EMA_20'] = df_hist['Close'].ewm(span=20, adjust=False).mean()
        delta = df_hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df_hist['RSI_14'] = 100 - (100 / (1 + rs))

        # สร้างกราฟสองชั้น (Row 1 ราคา + EMA / Row 2 ดัชนี RSI)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
        
        # วาดกราฟแท่งเทียน Candlestick
        fig.add_trace(go.Candlestick(x=df_hist.index, open=df_hist['Open'], high=df_hist['High'], low=df_hist['Low'], close=df_hist['Close'], name="Candlestick"), row=1, col=1)
        # วาดเส้นเฉลี่ยเคลื่อนที่ EMA 20
        fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['EMA_20'], mode='lines', line=dict(color='#ff9900', width=1.5), name='EMA (20)'), row=1, col=1)
        # วาดดัชนี RSI
        fig.add_trace(go.Scatter(x=df_hist.index, y=df_hist['RSI_14'], mode='lines', line=dict(color='#9b5de5', width=1.5), name='RSI (14)'), row=2, col=1)
        
        # ลากเส้นบอกโซน Overbought (70) และ Oversold (30) ของ RSI
        fig.add_hline(y=70, line_dash="dash", line_color="#ff3b30", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#00b074", opacity=0.5, row=2, col=1)

        # ตกแต่งหน้าตากราฟให้เข้ากับ Dark Theme สไตล์ TradingView
        fig.update_layout(
            title=f"📈 กราฟเทคนิคอลเรียลไทม์: {symbol} ({period_choice})", 
            xaxis_rangeslider_visible=False, 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='#131722', 
            yaxis=dict(gridcolor='#2a2e39', title="ราคาหุ้น"), 
            yaxis2=dict(gridcolor='#2a2e39', title="RSI", range=[10, 90]), 
            xaxis=dict(gridcolor='#2a2e39'), 
            height=500, 
            showlegend=True, 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลกราฟของหุ้น {symbol} ได้ในขณะนี้: {e}")

# ==============================================================================
# SIDEBAR: ศูนย์จัดการธุรกรรมหุ้นและปุ่มดาวน์โหลด Backup ล่าสุด
# ==============================================================================
st.sidebar.header("⚙️ Portfolio Data Center")

show_manager = st.sidebar.checkbox("เปิดเมนูจัดการธุรกรรม (Add/Delete)")

if show_manager:
    st.markdown("---")
    st.subheader("🛠️ การจัดการธุรกรรมหุ้น")
    
    # ฟอร์มสำหรับกรอกเพิ่มหุ้น/ปันผลใหม่ลงพอร์ต
    with st.expander("➕ เพิ่มธุรกรรมใหม่ (Add Transaction)", expanded=False):
        with st.form("add_form", clear_on_submit=True):
            sym = st.text_input("สัญลักษณ์หุ้น (เช่น SET:PTT หรือ NASDAQ:AAPL)").strip()
            side = st.selectbox("ประเภทธุรกรรม (Side)", ["Buy", "Dividend"])
            qty = st.number_input("จำนวนหุ้น / เงินปันผลรวมที่ได้รับ (Qty)", min_value=0.0, step=0.000001, format="%.6f")
            price = st.number_input("ราคาต่อหน่วย (Fill Price) *กรณีปันผลให้ใส่ 0*", min_value=0.0, step=0.01)
            comm = st.number_input("ค่าธรรมเนียม / คอมมิชชั่น (Commission)", min_value=0.0, step=0.01)
            date = st.date_input("วันที่ทำรายการ")
            
            submit_btn = st.form_submit_button("บันทึกข้อมูลธุรกรรม")
            if submit_btn and sym:
                new_row = pd.DataFrame([{
                    'Symbol': str(sym).upper().strip(),
                    'Side': str(side),
                    'Qty': float(qty),
                    'Fill_Price': float(price),       
                    'Commission': float(comm),
                    'Closing_Time': str(date)         
                }])
                st.session_state.df_portfolio = pd.concat([st.session_state.df_portfolio, new_row], ignore_index=True)
                
                # เขียนบันทึกลงดิสก์จำลองหลังบ้าน
                df_to_save = st.session_state.df_portfolio.rename(columns={'Fill_Price': 'Fill Price', 'Closing_Time': 'Closing Time'})
                df_to_save.to_excel(DEFAULT_EXCEL_FILE, index=False)
                st.cache_data.clear() 
                st.success(f"บันทึกข้อมูลหุ้น {sym.upper()} เรียบร้อย!")
                st.rerun()

    # รายการแสดงสำหรับกดลบธุรกรรมที่เลือกเอาออก
    if not st.session_state.df_portfolio.empty:
        with st.expander("🗑️ ลบธุรกรรมที่บันทึกไว้ (Delete Transaction)"):
            st.write("กดปุ่ม 'ลบ' ท้ายรายการธุรกรรมที่คุณต้องการนำออก:")
            for idx in reversed(st.session_state.df_portfolio.index):
                item = st.session_state.df_portfolio.loc[idx]
                col_item, col_btn = st.columns([4, 1])
                col_item.write(f"รายการ {idx}: **{item['Symbol']}** | {item['Side']} | Qty: {item['Qty']:,}")
                if col_btn.button("ลบ", key=f"del_item_{idx}"):
                    st.session_state.df_portfolio = st.session_state.df_portfolio.drop(idx).reset_index(drop=True)
                    df_to_save = st.session_state.df_portfolio.rename(columns={'Fill_Price': 'Fill Price', 'Closing_Time': 'Closing Time'})
                    df_to_save.to_excel(DEFAULT_EXCEL_FILE, index=False)
                    st.cache_data.clear()
                    st.success(f"ลบรายการลำดับที่ {idx} สำเร็จ!")
                    st.rerun()
                    
    # 💾 ระบบดาวน์โหลดไฟล์สำรองถาวร (ใช้เอนจิ้น openpyxl ที่รองรับ Cloud 100%)
    st.markdown("---")
    st.subheader("💾 Backup ข้อมูลพอร์ตล่าสุด")
    df_download_ready = st.session_state.df_portfolio.rename(columns={'Fill_Price': 'Fill Price', 'Closing_Time': 'Closing Time'})
    
    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_download_ready.to_excel(writer, index=False, sheet_name='Portfolio')
    
    st.sidebar.download_button(
        label="💾 ดาวน์โหลดไฟล์ Excel เพื่อนำไปอัปเดตลง GitHub",
        data=buffer.getvalue(),
        file_name="portfolio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.sidebar.caption("💡 แนะนำ: หลังจากพพี่ยอด เพิ่ม/ลบ หุ้นในหน้านี้เสร็จแล้ว ให้กดปุ่มดาวน์โหลดไฟล์นี้ไปเซฟทับตัวเก่าในเครื่องคอม แล้วสั่ง Git Push ขึ้น GitHub ได้ทันทีครับ ข้อมูลจะอยู่ถาวรตลอดไปครับ")
    st.markdown("---")

# ==============================================================================
# MAIN DASHBOARD: คำนวณสถิติทางการเงินและวิเคราะห์สัดส่วนพอร์ต
# ==============================================================================
df_raw = st.session_state.df_portfolio.copy()

if not df_raw.empty:
    df_buy = df_raw[df_raw['Side'] == 'Buy'].copy()
    df_div = df_raw[df_raw['Side'] == 'Dividend'].copy()
    
    # แปลงสัญลักษณ์ของหุ้นให้สอดคล้องกับ Yahoo Finance
    def convert_symbol(symbol):
        sym_clean = str(symbol).upper().strip()
        if sym_clean.startswith('SET:'): 
            return sym_clean.replace('SET:', '').strip() + '.BK'
        return sym_clean.replace('NASDAQ:', '').replace('NYSE:', '').strip()

    if not df_buy.empty:
        df_buy['YF_Symbol'] = df_buy['Symbol'].apply(convert_symbol)
        df_buy['Total_Cost'] = (df_buy['Qty'] * df_buy['Fill_Price']) + df_buy['Commission']
        
        # รวมกลุ่มธุรกรรมรายหุ้นหาต้นทุนเฉลี่ย
        portfolio = df_buy.groupby('YF_Symbol').agg({
            'Qty': 'sum',
            'Total_Cost': 'sum',
            'Symbol': 'first'
        }).reset_index()
        
        portfolio['Avg_Price'] = portfolio['Total_Cost'] / portfolio['Qty']
        
        # คำนวณเงินปันผลสะสมรายหุ้น
        div_summary = df_div.groupby('Symbol')['Qty'].sum().reset_index() if not df_div.empty else pd.DataFrame(columns=['Symbol', 'Total_Dividend'])
        div_summary.columns = ['Symbol', 'Total_Dividend']
        
        portfolio = portfolio.merge(div_summary, on='Symbol', how='left')
        portfolio['Total_Dividend'] = portfolio['Total_Dividend'].fillna(0)
        
        # ยิงเรียกราคาตลาดปัจจุบันผ่าน yfinance อัตโนมัติ
        with st.spinner('กำลังเชื่อมต่อข้อมูลราคาสดส่งตรงจากตลาดทุน...'):
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
        
        # คำนวณปรับค่าเงิน (แปลงดอลลาร์สหรัฐ เป็นเงินบาทไทยกรณีหุ้นนอก)
        portfolio['Value_THB'] = portfolio.apply(lambda x: x['Current_Value'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Current_Value'], axis=1)
        portfolio['Cost_THB'] = portfolio.apply(lambda x: x['Total_Cost'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Total_Cost'], axis=1)
        portfolio['Dividend_THB'] = portfolio.apply(lambda x: x['Total_Dividend'] * fx_rate if ".BK" not in x['YF_Symbol'] else x['Total_Dividend'], axis=1)
        
        portfolio['PL_THB'] = portfolio['Value_THB'] - portfolio['Cost_THB']
        portfolio['PL_Percent'] = (portfolio['PL_THB'] / portfolio['Cost_THB']) * 100 if portfolio['Cost_THB'].sum() > 0 else 0
        
        # 📊 คำนวณสรุปตัวเลขรวมหน้าพอร์ต (TradingView Style KPI)
        total_val_thb = portfolio['Value_THB'].sum()
        total_cost_thb = portfolio['Cost_THB'].sum()
        unrealized_pl_thb = portfolio['PL_THB'].sum()
        unrealized_pl_percent = (unrealized_pl_thb / total_cost_thb) * 100 if total_cost_thb > 0 else 0
        total_dist_div_thb = portfolio['Dividend_THB'].sum()
        realized_pl_thb = total_dist_div_thb 
        all_pl_thb = unrealized_pl_thb + realized_pl_thb
        all_pl_percent = (all_pl_thb / total_cost_thb) * 100 if total_cost_thb > 0 else 0
        
        total_val_usd = total_val_thb / fx_rate
        unrealized_pl_usd = unrealized_pl_thb / fx_rate
        realized_pl_usd = realized_pl_thb / fx_rate
        all_pl_usd = all_pl_thb / fx_rate

        # 🎨 แสดงผล 4 กล่องการเงินสรุปภาพรวมด้านบนสุดของแอป
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">มูลค่าพอร์ตโฟลิโอ (Equity)</p><p style="color: #ffffff; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">฿{total_val_thb:,.2f}</p><p style="color: #848e9c; font-size: 15px; margin: 2px 0 0 0;">${total_val_usd:,.2f} <span style="font-size: 12px;">USD</span></p></div>', unsafe_allow_html=True)
        with col2:
            unreal_color = "#00b074" if unrealized_pl_thb >= 0 else "#ff3b30"
            unreal_sign = "+" if unrealized_pl_thb >= 0 else ""
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">กำไรที่ยังไม่รับรู้ (Unrealized P/L)</p><p style="color: {unreal_color}; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">{unreal_sign}฿{unrealized_pl_thb:,.2f}</p><p style="color: {unreal_color}; opacity: 0.9; font-size: 15px; margin: 2px 0 0 0;">{unreal_sign}{unrealized_pl_percent:+.2f}% (${unrealized_pl_usd:,.2f})</p></div>', unsafe_allow_html=True)
        with col3:
            real_color = "#00b074" if realized_pl_thb > 0 else "#848e9c"
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">กำไรที่รับรู้แล้ว (Realized P/L)</p><p style="color: {real_color}; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">฿{realized_pl_thb:,.2f}</p><p style="color: {real_color}; opacity: 0.9; font-size: 15px; margin: 2px 0 0 0;">+100.00% (${realized_pl_usd:,.2f})</p></div>', unsafe_allow_html=True)
        with col4:
            all_color = "#00b074" if all_pl_thb >= 0 else "#ff3b30"
            all_sign = "+" if all_pl_thb >= 0 else ""
            st.markdown(f'<div style="background-color: #1c2030; padding: 18px; border-radius: 8px; border: 1px solid #2d3247;"><p style="color: #848e9c; font-size: 13px; margin: 0; font-weight: 500;">กำไรทั้งหมด (Total P/L)</p><p style="color: {all_color}; font-size: 26px; font-weight: 700; margin: 8px 0 0 0;">{all_sign}฿{all_pl_thb:,.2f}</p><p style="color: {all_color}; opacity: 0.9; font-size: 15px; margin: 2px 0 0 0;">{all_sign}{all_pl_percent:+.2f}% (${all_pl_usd:,.2f})</p></div>', unsafe_allow_html=True)
        
        st.write("---")

        # 📋 ตารางแจกแจงรายละเอียดหุ้นในพอร์ตแบบมีสีสันไฮไลท์แดงเขียว
        st.subheader("📋 รายละเอียดหุ้นในพอร์ตโฟลิโอ")
        table_show = portfolio[['Symbol', 'Qty', 'Avg_Price', 'Current_Price', 'Value_THB', 'PL_THB', 'PL_Percent', 'Dividend_THB']].copy()
        table_show.columns = ['Symbol', 'Qty', 'Avg Price', 'Last Price', 'Current Value', 'P/L (THB)', 'P/L %', 'Dividends Received']
        
        def style_pl(val): return f"color: {'#089981' if val >= 0 else '#f23645'}; font-weight: bold;"
        st.dataframe(table_show.style.format({'Qty': '{:,.6f}', 'Avg Price': '{:,.2f}', 'Last Price': '{:,.2f}', 'Current Value': '฿{:,.2f}', 'P/L (THB)': '฿{:,.2f}', 'P/L %': '{:+.2f}%', 'Dividends Received': '฿{:,.2f}'}).map(style_pl, subset=['P/L (THB)', 'P/L %']), use_container_width=True)

        st.write("---")
        
        # 🎯 PHASE 3: INTERACTIVE CHARTS & TECHNICAL ANALYTICS
        st.subheader("🎯 การวิเคราะห์ทางเทคนิครายหุ้น (Interactive Technical Charts)")
        chart_col1, chart_col2 = st.columns([2, 2])
        with chart_col1:
            available_stocks = portfolio['YF_Symbol'].tolist()
            selected_stock = st.selectbox("🔍 เลือกหุ้นในพอร์ตที่ต้องการเปิดกราฟเทคนิคอล:", available_stocks)
        with chart_col2:
            time_period = st.selectbox("📅 เลือกช่วงเวลาข้อมูลย้อนหลัง (Time Horizon):", ["3mo", "6mo", "1y", "2y", "1mo"], index=0)
            
        if selected_stock:
            draw_technical_chart(selected_stock, time_period)
            
        st.write("---")
        # 🥧 กราฟพายสัดส่วนการกระจายความเสี่ยงของเงินลงทุน (Portfolio Allocation)
        st.subheader("🥧 สัดส่วนการลงทุน (Portfolio Allocation)")
        fig_pie = px.pie(portfolio, values='Value_THB', names='Symbol', hole=0.4)
        fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)
else:
    st.info("💡 ไม่พบข้อมูลธุรกรรมในพอร์ต กรุณาคลิกเลือก 'เปิดเมนูจัดการธุรกรรม' ที่เมนูด้านซ้ายเพื่อเริ่มต้นบันทึกหุ้นตัวแรกของคุณครับ")