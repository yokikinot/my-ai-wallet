import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import pytesseract
import datetime
import re
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 設定・OCRエンジン準備
# ==========================================
st.set_page_config(page_title="AI Wallet: Cloud & OCR", layout="wide")
st.title("🤖 AI Wallet: Personal CFO (Cloud Ver.)")

# ==========================================
# 2. データベース機能 (Google Sheets)
# ==========================================
# スプレッドシートへの接続を作成
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    # シートからデータを読み込む（キャッシュを使わない設定）
    try:
        df = conn.read(ttl=0)
        return df
    except:
        # シートが空の場合の初期データ
        return pd.DataFrame(columns=["date", "item_name", "amount", "category", "merchant"])

def add_data(item_name, amount, category, merchant):
    # 現在のデータを取得
    df = get_data()
    # 新しい行を作成
    new_row = pd.DataFrame([{
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "item_name": item_name,
        "amount": amount,
        "category": category,
        "merchant": merchant
    }])
    # 結合して保存
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)
    return updated_df

# ==========================================
# 3. AIロジック (OCR & 判定)
# ==========================================
def parse_receipt(image):
    """ レシート画像から文字を読み取る """
    try:
        # 日本語モデルでOCR実行
        text = pytesseract.image_to_string(image, lang='jpn')
        
        # 簡易的な情報抽出ロジック
        data = {"merchant": "Unknown", "amount": 0, "category": "private"}
        
        # 金額を探す（¥1,000 や 1,000円）
        amount_match = re.search(r'(合計|¥|￥)\s*([\d,]+)', text)
        if amount_match:
            data["amount"] = int(amount_match.group(2).replace(',', ''))
            
        # 店名・カテゴリ推測
        if "セブン" in text or "Seven" in text:
            data["merchant"] = "SevenEleven"
            data["category"] = "food"
        elif "Amazon" in text:
            data["merchant"] = "Amazon"
            data["category"] = "private"
        elif "薬" in text or "ドラッグ" in text:
            data["merchant"] = "DrugStore"
            data["category"] = "medical"
            
        return text, data
    except Exception as e:
        return f"Error: {e}", {}

# ==========================================
# 4. アプリ画面 (UI)
# ==========================================

# --- タブで機能を分ける ---
tab1, tab2 = st.tabs(["📸 入力・カメラ", "📊 分析ダッシュボード"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. レシートを撮影")
        # カメラ機能
        camera_image = st.camera_input("レシートを撮ってください")
        
        extracted_info = {}
        if camera_image:
            # 画像を処理できる形式に変換
            img = Image.open(camera_image)
            st.image(img, caption="撮影画像", width=200)
            
            # OCR実行
            with st.spinner("AIがレシートを読んでいます..."):
                raw_text, extracted_info = parse_receipt(img)
                st.info(f"読み取った金額: {extracted_info.get('amount', 0)}円")

    with col2:
        st.subheader("2. 内容の確認と登録")
        # フォーム（OCR結果があれば自動入力）
        with st.form("input_form"):
            item_name = st.text_input("商品名", value="レシート読取品" if camera_image else "")
            
            # OCRで金額が取れていればそれを初期値にする
            default_amount = extracted_info.get("amount", 0)
            amount = st.number_input("金額", min_value=0, step=10, value=default_amount)
            
            # OCRでカテゴリが取れていればそれを初期値にする
            cat_index = 0
            cats = ["food", "medical", "business", "furusato", "private"]
            if extracted_info.get("category") in cats:
                cat_index = cats.index(extracted_info.get("category"))
                
            category = st.selectbox("カテゴリー", cats, index=cat_index)
            merchant = st.text_input("購入場所", value=extracted_info.get("merchant", ""))
            
            submitted = st.form_submit_button("クラウドに保存")

            if submitted:
                add_data(item_name, amount, category, merchant)
                st.success("✅ スプレッドシートに保存しました！")

with tab2:
    st.subheader("クラウド上の財務データ")
    
    # データを再読み込み
    df = get_data()
    
    if not df.empty:
        # データ表示
        st.dataframe(df.sort_index(ascending=False).head(5))
        
        # グラフ化
        st.write("---")
        total = df["amount"].sum()
        medical = df[df["category"]=="medical"]["amount"].sum()
        
        kpi1, kpi2 = st.columns(2)
        kpi1.metric("総支出", f"¥{total:,}")
        kpi2.metric("医療費控除 対象額", f"¥{medical:,}", delta=f"{medical-100000}")
        
        # 円グラフ
        fig, ax = plt.subplots()
        df.groupby("category")["amount"].sum().plot.pie(autopct='%1.1f%%', ax=ax)
        st.pyplot(fig)
    else:
        st.info("まだデータがありません。")
