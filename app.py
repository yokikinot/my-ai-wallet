import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import datetime

# ==========================================
# 1. バックエンド（脳と記憶）
# ==========================================

class DatabaseManager:
    def __init__(self, db_name="wallet.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                item_name TEXT,
                amount INTEGER,
                category TEXT,
                merchant TEXT
            )
        """)
        self.conn.commit()

    def add_transaction(self, item_name, amount, category, merchant):
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("INSERT INTO transactions (date, item_name, amount, category, merchant) VALUES (?, ?, ?, ?, ?)", 
                            (date, item_name, amount, category, merchant))
        self.conn.commit()

    def get_all_data(self):
        # PandasのDataFrameとしてデータを取得（グラフ化しやすくするため）
        return pd.read_sql("SELECT * FROM transactions", self.conn)

# AIロジック（簡易版）
def get_ai_advice(category, merchant, amount):
    advice = {"tax": "", "payment": ""}
    
    # 税金アドバイス
    if category == "medical":
        advice["tax"] = "💊 これは『医療費控除』の対象です。領収書を保存しました。"
    elif category == "business":
        advice["tax"] = "💼 副業の『経費』として計上します。"
    elif category == "furusato":
        advice["tax"] = "🎁 ふるさと納税です。住民税の控除対象になります。"
    else:
        advice["tax"] = "🛒 通常の消費支出です。"

    # 決済ルートアドバイス
    if merchant == "Amazon":
        advice["payment"] = "おすすめ決済: Amazon Prime Card (2.5%)"
    elif merchant == "Rakuten":
        advice["payment"] = "おすすめ決済: Rakuten Card (3.0%)"
    else:
        advice["payment"] = "おすすめ決済: Main Card (1.0%)"
        
    return advice

# ==========================================
# 2. フロントエンド（見た目・Webアプリ）
# ==========================================

# ページ設定
st.set_page_config(page_title="My Personal CFO", layout="wide")
st.title("🤖 AI Wallet: My Personal CFO")

# DB接続
db = DatabaseManager()

# --- サイドバー：入力フォーム ---
st.sidebar.header("📝 新しい支出を入力")
with st.sidebar.form("input_form"):
    item_name = st.text_input("商品名（例：風邪薬）")
    amount = st.number_input("金額（円）", min_value=0, step=100)
    category = st.selectbox("カテゴリー", ["food", "medical", "business", "furusato", "private"])
    merchant = st.selectbox("購入場所", ["Amazon", "Rakuten", "SevenEleven", "DrugStore", "Other"])
    
    submitted = st.form_submit_button("AIに相談して登録")

# --- メインエリア：ロジック実行 ---
if submitted:
    # 1. データベースに保存
    db.add_transaction(item_name, amount, category, merchant)
    
    # 2. AIアドバイス生成
    advice = get_ai_advice(category, merchant, amount)
    
    # 3. 結果表示（派手な通知）
    st.success(f"登録完了: {item_name} ({amount}円)")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**税務AI**: {advice['tax']}")
    with col2:
        st.warning(f"**決済AI**: {advice['payment']}")

# --- ダッシュボードエリア ---
st.markdown("---")
st.header("📊 財務ダッシュボード")

# データの読み込み
df = db.get_all_data()

if not df.empty:
    # KPI（重要指標）の表示
    total_spent = df["amount"].sum()
    medical_spent = df[df["category"]=="medical"]["amount"].sum()
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("総支出額", f"¥{total_spent:,}")
    kpi2.metric("医療費控除 対象額", f"¥{medical_spent:,}", delta=f"{medical_spent - 100000}円 (閾値比)")
    kpi3.metric("データ件数", f"{len(df)}件")

    # グラフ描画エリア
    chart1, chart2 = st.columns(2)
    
    with chart1:
        st.subheader("支出の内訳")
        # カテゴリごとの集計
        category_sum = df.groupby("category")["amount"].sum()
        fig1, ax1 = plt.subplots()
        ax1.pie(category_sum, labels=category_sum.index, autopct='%1.1f%%', startangle=90)
        st.pyplot(fig1)

    with chart2:
        st.subheader("医療費控除の進捗 (目標10万円)")
        # バーチャート
        progress = min(medical_spent / 100000, 1.0)
        st.progress(progress)
        st.caption(f"現在: {medical_spent:,}円 / 目標: 100,000円")
        if medical_spent > 100000:
            st.error("✨ 控除ライン突破！確定申告の準備をしましょう！")

    # 履歴データの表示
    st.subheader("📜 最近の取引履歴")
    st.dataframe(df.sort_values("id", ascending=False).head(5))

else:
    st.info("👈 左のサイドバーから、最初の支出データを入力してください。")