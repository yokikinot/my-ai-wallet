import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
import datetime
import re
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. 基本設定
# ==========================================
st.set_page_config(page_title="AI Wallet: High-Quality OCR", layout="wide")
st.title("🤖 AI Wallet: Personal CFO (高精度版)")

# ==========================================
# 2. クラウドDB連携 (Google Sheets)
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        # シートから最新データを取得（キャッシュなし）
        df = conn.read(ttl=0)
        return df
    except:
        return pd.DataFrame(columns=["date", "item_name", "amount", "category", "merchant"])

def add_data(item_name, amount, category, merchant):
    df = get_data()
    new_row = pd.DataFrame([{
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "item_name": item_name,
        "amount": amount,
        "category": category,
        "merchant": merchant
    }])
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(data=updated_df)
    return updated_df

# ==========================================
# 3. 最強のOCR処理ロジック
# ==========================================
def parse_receipt(image_file):
    """
    画像を読み取りやすく加工してからOCRにかける
    """
    try:
        # 1. 画像を読み込んで白黒（グレースケール）化
        img = Image.open(image_file).convert('L')
        
        # 2. コントラストを上げて文字をクッキリさせる
        img = ImageOps.autocontrast(img)
        
        # 3. シャープネス（鋭さ）を強化
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        
        # --- OCR実行 ---
        # --psm 6: ひとまとまりのテキストとして読む
        # --oem 3: デフォルトのニューラルネットワークを使用
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, lang='jpn', config=custom_config)
        
        # --- 情報抽出 (Regex) ---
        data = {"merchant": "不明な店", "amount": 0, "category": "private"}
        
        # 金額（合計 または ¥ などの後の数字を探す）
        amount_match = re.search(r'(合計|¥|￥|支払)\s*([\d,]+)', text)
        if amount_match:
            data["amount"] = int(amount_match.group(2).replace(',', ''))
            
        # カテゴリ推測キーワード
        if any(kw in text for kw in ["セブン", "ローソン", "ファミマ", "コンビニ"]):
            data["merchant"], data["category"] = "ConvenienceStore", "food"
        elif any(kw in text for kw in ["ドラッグ", "薬", "マツモトキヨシ"]):
            data["merchant"], data["category"] = "DrugStore", "medical"
        elif "Amazon" in text:
            data["merchant"], data["category"] = "Amazon", "private"
            
        return text, data
    except Exception as e:
        return f"解析エラー: {e}", {}

# ==========================================
# 4. メイン画面 (UI)
# ==========================================
tab1, tab2 = st.tabs(["📸 レシート取込", "📊 財務ダッシュボード"])

with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1. レシートを読み込む")
        
        # 【重要】画質を落とさないための選択肢
        input_type = st.radio("入力方法", ["高画質ファイルをアップロード (推奨)", "今すぐカメラで撮る"])
        
        if input_type == "今すぐカメラで撮る":
            input_image = st.camera_input("撮影")
        else:
            # スマホのカメラアプリで撮った「本気の一枚」を選べる
            input_image = st.file_uploader("レシートの写真を選択（高画質）", type=['jpg', 'jpeg', 'png'])

        extracted_info = {}
        if input_image:
            with st.spinner("AIが画質を調整して読み取り中..."):
                raw_text, extracted_info = parse_receipt(input_image)
                
                # 読み取り結果が不安な場合のために生データを表示
                with st.expander("AIが読み取った生データを確認"):
                    st.text(raw_text)

    with col2:
        st.subheader("2. 登録内容の最終確認")
        with st.form("input_form"):
            # OCRの結果がここに入る
            item_name = st.text_input("品名", value="レシート読取商品" if input_image else "")
            
            # OCRが失敗しても手動で直せるようにする
            def_amt = extracted_info.get("amount", 0)
            amount = st.number_input("金額 (円)", min_value=0, step=1, value=def_amt)
            
            # カテゴリ選択
            cats = ["food", "medical", "business", "furusato", "private"]
            def_cat = extracted_info.get("category", "private")
            cat_idx = cats.index(def_cat) if def_cat in cats else 4
            category = st.selectbox("カテゴリー", cats, index=cat_idx)
            
            merchant = st.text_input("購入場所", value=extracted_info.get("merchant", ""))
            
            submitted = st.form_submit_button("クラウドへ保存")
            
            if submitted:
                add_data(item_name, amount, category, merchant)
                st.balloons()
                st.success("✅ Googleスプレッドシートへの保存が完了しました！")

with tab2:
    st.subheader("リアルタイム財務分析")
    df = get_data()
    
    if not df.empty:
        # 数値計算
        total = df["amount"].astype(int).sum()
        medical = df[df["category"]=="medical"]["amount"].astype(int).sum()
        
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("総支出額", f"¥{total:,}")
        m_col2.metric("医療費控除進捗", f"¥{medical:,}", f"{medical-100000}円")
        
        # グラフ
        fig, ax = plt.subplots()
        df.groupby("category")["amount"].sum().plot.pie(autopct='%1.1f%%', ax=ax)
        ax.set_ylabel('')
        st.pyplot(fig)
        
        st.subheader("最新の履歴")
        st.dataframe(df.sort_index(ascending=False))
    else:
        st.info("データがまだありません。")
