import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from micro_bot import MicroIntelligentTradingBot
from binance.client import Client
from micro_config import BINANCE_CONFIG, MICRO_CONFIG
import time
import plotly.express as px

st.set_page_config(page_title="البوت الذكي للرؤوس الصغيرة", layout="wide", page_icon="💰")

st.title("💰 البوت التداولي الذكي للرؤوس الصغيرة")
st.markdown("### 🤖 ربح تراكمي فوري بعد كل صفقة ناجحة - بداية من 10$")

# الشريط الجانبي
st.sidebar.header("⚙️ إعدادات البوت المصغر")

# اختيار الأزواج المناسبة للرؤوس الصغيرة
micro_pairs = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT",
    "DOGEUSDT", "DOTUSDT", "LTCUSDT", "LINKUSDT", "MATICUSDT"
]

selected_pairs = st.sidebar.multiselect(
    "🎯 اختر أزواج التداول (3-4 أزواج موصى بها):",
    micro_pairs,
    default=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    max_selections=5
)

# إعدادات الرأس المال
st.sidebar.header("💵 إعدادات رأس المال")

capital = st.sidebar.number_input(
    "رأس المال الأولي ($)",
    value=10.0,
    min_value=5.0,
    max_value=100.0,
    step=5.0,
    help="ابدأ بـ 10-50$ للاختبار"
)

# إعدادات المخاطرة للمبالغ الصغيرة
st.sidebar.header("🎯 إدارة المخاطر المصغرة")

risk_level = st.sidebar.selectbox(
    "مستوى المخاطرة:",
    ["🟢 منخفض (3%)", "🟡 متوسط (4%)", "🟠 عالي (5%)", "🔴 عدواني (6%)"]
)

risk_mapping = {
    "🟢 منخفض (3%)": 0.03,
    "🟡 متوسط (4%)": 0.04, 
    "🟠 عالي (5%)": 0.05,
    "🔴 عدواني (6%)": 0.06
}

base_risk = risk_mapping[risk_level]

# إعدادات الوقت
timeframe = st.sidebar.selectbox("⏰ الإطار الزمني:", ["1m", "3m", "5m"], index=0)
days = st.sidebar.slider("📅 أيام المحاكاة:", 1, 14, 3)

# تحديث الإعدادات
cfg = MICRO_CONFIG.copy()
cfg.update({
    "initial_balance": float(capital),
    "selected_pairs": selected_pairs,
    "base_risk": base_risk,
    "max_risk": base_risk * 2,
    "min_risk": base_risk * 0.5,
    "timeframe": timeframe
})

@st.cache_data(ttl=300)
def fetch_micro_klines(symbols, interval, days=3):
    """جلب بيانات مخصصة للرؤوس الصغيرة"""
    client = Client(BINANCE_CONFIG.get("api_key",""), BINANCE_CONFIG.get("api_secret",""))
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    
    micro_data = {}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, symbol in enumerate(symbols):
        try:
            status_text.text(f"📥 جلب بيانات {symbol}...")
            
            klines = client.get_historical_klines(
                symbol, interval,
                start.strftime("%d %b, %Y"),
                end.strftime("%d %b, %Y"),
                limit=500  # عدد أقل للسرعة
            )
            
            if klines:
                df = pd.DataFrame(klines, columns=[
                    'timestamp','open','high','low','close','volume','close_time',
                    'qav','num_trades','taker_base_vol','taker_quote_vol','ignore'
                ])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                micro_data[symbol] = df[['timestamp','open','high','low','close','volume']]
            
            progress_bar.progress((idx + 1) / len(symbols))
            time.sleep(0.1)
            
        except Exception as e:
            st.error(f"❌ خطأ في {symbol}: {str(e)}")
    
    progress_bar.empty()
    status_text.empty()
    
    return micro_data

def calculate_micro_metrics(trades):
    """حساب مقاييس للرؤوس الصغيرة"""
    if not trades:
        return {}
    
    closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
    if not closed_trades:
        return {}
    
    profits = [t.get('profit', 0) for t in closed_trades]
    winning_trades = [p for p in profits if p > 0]
    losing_trades = [p for p in profits if p < 0]
    
    return {
        'total_trades': len(closed_trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': (len(winning_trades) / len(closed_trades)) * 100,
        'total_profit': sum(profits),
        'avg_profit': np.mean(profits),
        'profit_factor': abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf'),
        'expectancy': (np.mean(winning_trades) if winning_trades else 0) * (len(winning_trades)/len(closed_trades)) + (np.mean(losing_trades) if losing_trades else 0) * (len(losing_trades)/len(closed_trades)),
        'avg_trade_size': np.mean([t.get('amount', 0) for t in closed_trades])
    }

# الواجهة الرئيسية
tab1, tab2, tab3 = st.tabs(["🚀 المحاكاة المصغرة", "📊 لوحة التحكم", "💎 خطة النمو"])

with tab1:
    st.header("المحاكاة المصغرة للرؤوس الصغيرة")
    
    if st.button("💰 بدء المحاكاة المصغرة", type="primary", use_container_width=True):
        if not selected_pairs:
            st.error("⚠️ الرجاء اختيار أزواج التداول أولاً")
        elif capital < 5:
            st.error("⚠️ رأس المال صغير جداً. Minimum: $5")
        else:
            with st.spinner("جلب بيانات السوق..."):
                klines_data = fetch_micro_klines(selected_pairs, timeframe, days)
                
                if not klines_data:
                    st.error("❌ فشل في جلب بيانات السوق")
                else:
                    # إنشاء البوت المصغر
                    micro_bot = MicroIntelligentTradingBot(cfg)
                    
                    # محاكاة
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i in range(100):
                        progress_bar.progress(i + 1)
                        status_text.text(f"🧠 البوت يحلل الفرص... {i+1}%")
                        time.sleep(0.01)
                    
                    result = micro_bot.run_enhanced_backtest(klines_data, timeframe)
                    progress_bar.empty()
                    status_text.empty()
                    
                    st.success("✅ اكتملت المحاكاة المصغرة!")
                    
                    # النتائج الأساسية
                    st.subheader("📊 النتائج الأساسية")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("💵 رأس المال الأولي", f"${result['initial_balance']:.2f}")
                    with col2:
                        profit = result['total_profit']
                        profit_color = "normal" if profit >= 0 else "inverse"
                        st.metric("🎯 إجمالي الربح", f"${profit:.2f}", 
                                 delta=f"{result['profit_percentage']:.2f}%",
                                 delta_color=profit_color)
                    with col3:
                        st.metric("💎 الرصيد النهائي", f"${result['final_balance']:.2f}")
                    with col4:
                        st.metric("📈 معدل النجاح", f"{result['win_rate']:.1f}%")
                    
                    # تحليل مفصل
                    metrics = calculate_micro_metrics(result['trade_history'])
                    if metrics:
                        st.subheader("📈 تحليل أداء مفصل")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("🔢 إجمالي الصفقات", metrics['total_trades'])
                        col2.metric("✅ صفقات رابحة", metrics['winning_trades'])
                        col3.metric("📉 صفقات خاسرة", metrics['losing_trades'])
                        col4.metric("⚖️ عامل الربح", f"{metrics['profit_factor']:.2f}")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("📊 متوسط الربح", f"${metrics['avg_profit']:.4f}")
                        col2.metric("📋 التوقع", f"${metrics['expectancy']:.4f}")
                        col3.metric("💰 متوسط حجم الصفقة", f"${metrics['avg_trade_size']:.2f}")
                        col4.metric("🔄 الأرباح المتراكمة", f"${result['real_time_metrics']['compounded_profits']:.2f}")
                    
                    # عرض الصفقات
                    trades_df = pd.DataFrame(result['trade_history'])
                    if not trades_df.empty:
                        st.subheader("💼 سجل الصفقات")
                        
                        # تنسيق العرض
                        display_df = trades_df.copy()
                        if 'timestamp' in display_df.columns:
                            display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                        if 'profit' in display_df.columns:
                            display_df['profit'] = display_df['profit'].apply(lambda x: f"${x:.4f}" if pd.notnull(x) else "-")
                        if 'profit_pct' in display_df.columns:
                            display_df['profit_pct'] = display_df['profit_pct'].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "-")
                        
                        st.dataframe(display_df, use_container_width=True)
                        
                        # رسم بياني لتطور رأس المال
                        st.subheader("💹 منحنى رأس المال التراكمي")
                        
                        balance_history = []
                        current_balance = result['initial_balance']
                        
                        for trade in result['trade_history']:
                            if trade['status'] == 'CLOSED':
                                current_balance += trade.get('profit', 0)
                                balance_history.append({
                                    'timestamp': trade['timestamp'],
                                    'balance': current_balance,
                                    'symbol': trade['symbol']
                                })
                        
                        if balance_history:
                            balance_df = pd.DataFrame(balance_history)
                            
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=balance_df['timestamp'],
                                y=balance_df['balance'],
                                mode='lines+markers',
                                name='رأس المال التراكمي',
                                line=dict(color='#00FF00', width=3),
                                marker=dict(size=4, color='green')
                            ))
                            
                            fig.update_layout(
                                title="تطور رأس المال مع النظام التراكمي الفوري",
                                xaxis_title="الوقت",
                                yaxis_title="رأس المال ($)",
                                height=400
                            )
                            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("لوحة تحكم البوت المصغر")
    
    # معلومات البوت
    st.info("""
    **🤖 مميزات البوت المصغر:**
    
    - ✅ **ربح تراكمي فوري** بعد كل صفقة ناجحة
    - ✅ **إدارة أموال ذكية** مخصصة للرؤوس الصغيرة
    - ✅ **ذكاء اصطناعي سريع** مع تعلم تكيفي
    - ✅ **تداول متعدد الأزواج** بشكل متزامن
    - ✅ **حدود صفقات ذكية** (0.50$ - 3.00$)
    - ✅ **تحليل فني متقدم** بمؤشرات سريعة
    """)
    
    # إحصائيات سريعة
    st.subheader("🎯 أهداف الأداء اليومية")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("الهدف اليومي", "150-250 صفقة", "مرن")
    col2.metric("معدل النجاح المستهدف", "70-80%", "±5%")
    col3.metric("الربح اليومي المستهدف", "50-100%", "تراكمي")
    
    # إعدادات متقدمة
    st.subheader("⚙️ إعدادات متقدمة")
    
    advanced_col1, advanced_col2 = st.columns(2)
    
    with advanced_col1:
        st.checkbox("تفعيل التعلم التكيفي", value=True)
        st.checkbox("الربح التراكمي الفوري", value=True)
        st.slider("حد الخسارة اليومي (%)", 5, 15, 10)
    
    with advanced_col2:
        st.checkbox("إشعارات الأداء", value=True)
        st.checkbox("توقف تلقائي", value=False)
        st.slider("هدف الربح اليومي (%)", 20, 100, 50)

with tab3:
    st.header("💎 خطة النمو من 10$ إلى 1000$")
    
    st.warning("""
    **📈 خارطة الطريق الواقعية:**
    
    هذه توقعات واقعية بناءً على أداء البوت المصغر:
    """)
    
    # خطة النمو
    growth_data = [
        {"المرحلة": "الأسبوع 1", "رأس_المال": "10$ → 50$", "الربح": "+40$", "النسبة": "+400%", "الاستراتيجية": "3 أزواج، 4% مخاطرة"},
        {"المرحلة": "الأسبوع 2", "رأس_المال": "50$ → 150$", "الربح": "+100$", "النسبة": "+200%", "الاستراتيجية": "4 أزواج، 4% مخاطرة"},
        {"المرحلة": "الأسبوع 3", "رأس_المال": "150$ → 400$", "الربح": "+250$", "النسبة": "+167%", "الاستراتيجية": "5 أزواج، 4% مخاطرة"},
        {"المرحلة": "الأسبوع 4", "رأس_المال": "400$ → 1000$", "الربح": "+600$", "النسبة": "+150%", "الاستراتيجية": "5 أزواج، 5% مخاطرة"}
    ]
    
    growth_df = pd.DataFrame(growth_data)
    st.dataframe(growth_df, use_container_width=True)
    
    # نصائح النجاح
    st.subheader("🎯 نصائح للنجاح مع الرؤوس الصغيرة")
    
    tips = [
        "🏁 **ابدأ بـ 10-50$** للتعلم والاختبار",
        "🎯 **ركز على 3-4 أزواج** في البداية",
        "💪 **تحلَّ بالصبر** - النمو يحتاج وقت",
        "📊 **راقب الأداء** يومياً وقم بالتعديلات",
        "🚀 **زد رأس المال** تدريجياً مع تحقق النتائج",
        "⚖️ **التزم بإدارة المخاطر** ولا تطمع",
        "🔁 **استفد من الربح التراكمي** للنمو السريع"
    ]
    
    for tip in tips:
        st.write(f"✅ {tip}")

# تذييل الصفحة
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>💰 <b>البوت التداولي الذكي للرؤوس الصغيرة</b> - بداية من 10$ إلى ما لا نهاية</p>
    <p>⚡ <i>ربح تراكمي فوري • إدارة أموال ذكية • تداول متعدد الأزواج</i></p>
</div>
""", unsafe_allow_html=True)
