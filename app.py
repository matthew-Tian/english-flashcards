import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import re
import os
import base64

# ================= 配置区 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "Total_Words.xlsx")
HISTORY_FILE = os.path.join(BASE_DIR, "student_print_history.csv")

# ================= 数据处理函数 =================

def load_or_create_data():
    if not os.path.exists(DATA_FILE):
        # 初始演示数据
        data = {
            "Word": ["ambition"],
            "Phonetic": ["/æmˈbɪʃn/"],
            "Meaning": ["n. 雄心，抱负"],
            "Example": ["She has a great ambition to become a doctor. 她有一个成为医生的宏大抱负。"],
            "Collocation": ["great ambition"]
        }
        df = pd.DataFrame(data)
        df.to_excel(DATA_FILE, index=False)
        return df
    else:
        return pd.read_excel(DATA_FILE)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame(columns=["Student", "Class", "List_Num", "Word", "Print_Date"])
    else:
        return pd.read_csv(HISTORY_FILE)

def save_history(df):
    df.to_csv(HISTORY_FILE, index=False)

def get_masked_sentence(sentence, word):
    if not isinstance(sentence, str): return ""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub("_______", sentence)

def extract_english_only(sentence):
    """
    核心辅助函数：从 '英文+中文' 的字符串中提取 '英文'
    逻辑：找到第一个中文字符，截取它之前的所有内容。
    """
    if not isinstance(sentence, str): return ""
    match = re.search(r'[\u4e00-\u9fa5]', sentence)
    if match:
        return sentence[:match.start()].strip()
    return sentence

# ================= 生成 HTML (含中英分离逻辑) =================

def generate_clean_html(words_data, student_info, for_printing=False):
    
    auto_print_script = """
    <script>
        window.onload = function() { setTimeout(function(){ window.print(); }, 800); }
    </script>
    """ if for_printing else ""
    
    header_msg = f"""
    <div class="no-print" style="text-align:center; padding: 10px; background:#e6fffa; color:#2c7a7b; border-bottom:1px solid #b2f5ea; font-size:13px;">
        💡 <strong>提示：</strong> A4 纸打印，请勾选“背景图形”。<br>
        左侧包含中英例句（挖空），右侧仅包含英文例句。
    </div>
    <div class="print-header" style="text-align:center; margin-bottom: 15px; font-size: 12px; color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px;">
        班级: <strong>{student_info['class_name']}</strong> | 
        姓名: <strong>{student_info['name']}</strong> | 
        List: <strong>{student_info['list_num']}</strong> | 
        日期: {datetime.now().strftime('%Y-%m-%d')}
    </div>
    """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>复习卡_{student_info['name']}</title>
        <style>
            body {{
                font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
                background-color: {'#ffffff' if for_printing else '#f9f9f9'};
                margin: 0;
                padding: {'0' if for_printing else '10px'};
                color: #333;
                font-size: 13px;
            }}
            .card-container {{ width: 100%; max-width: 700px; margin: 0 auto; }}

            /* 卡片外框 */
            .card-wrapper {{
                display: flex;
                background: white;
                border: 1px dashed #999;
                margin-bottom: 12px;
                page-break-inside: avoid;
                position: relative;
                height: auto; 
                min-height: 40mm; /* 高度压缩版 */
            }}
            
            .card-wrapper::after {{
                content: '✂️ Cut';
                position: absolute;
                bottom: -13px;
                right: 0;
                font-size: 10px;
                color: #bbb;
                background: white;
                padding: 0 4px;
            }}

            /* 左右布局 + 垂直分布 */
            .card-front, .card-back {{
                flex: 1;
                padding: 10px 14px;
                display: flex;
                flex-direction: column; 
                justify-content: space-between;
            }}

            .card-front {{ border-right: 1px solid #eee; }}
            .card-back {{ background-color: #fcfcfc; }}

            .content-top {{ flex-grow: 1; }}

            h2 {{ margin: 0 0 6px 0; font-size: 16px; color: #2c3e50; line-height: 1.2; }}
            h3 {{ margin: 0 0 4px 0; font-size: 20px; color: #000; line-height: 1.1; }}
            
            .cloze-box {{
                background: #f0f2f6;
                padding: 8px;
                border-radius: 5px;
                font-style: italic;
                line-height: 1.4;
                font-size: 13px;
                border: 1px solid #ebedf0;
                margin-bottom: 5px;
            }}

            .meta-section {{
                margin-top: 8px;
                padding-top: 6px;
                border-top: 1px dotted #eee;
                font-size: 11px;
                color: #555;
            }}
            .check-row {{ display: flex; align-items: center; margin-bottom: 3px; }}
            .check-label {{ margin-right: 6px; font-weight: bold; width: 60px; }}
            .box {{ display: inline-block; width: 12px; height: 12px; border: 1px solid #444; margin-right: 3px; border-radius: 2px; }}
            .box-text {{ margin-right: 8px; font-size: 10px; }}

            .phonetic {{ color: #777; font-family: "Times New Roman", serif; margin-bottom: 8px; font-size: 13px; }}
            .label {{ font-weight: bold; font-size: 10px; color: #999; text-transform: uppercase; margin-top: 8px; display:block; }}
            .text-content {{ font-size: 13px; color: #333; line-height: 1.3; }}

            @media print {{
                @page {{ margin: 10mm; size: A4; }}
                body {{ background: white; padding: 0; -webkit-print-color-adjust: exact; }}
                .no-print {{ display: none !important; }}
                .print-header {{ display: block !important; margin-bottom: 15px; }}
                .card-container {{ max-width: 100%; width: 100%; }}
                .card-wrapper {{ border-color: #888; margin-bottom: 12px; border-style: dashed; }}
                .card-wrapper::after {{ display: none; }}
            }}
        </style>
    </head>
    <body>
        {header_msg}
        <div class="card-container">
            {_generate_cards_body(words_data)}
        </div>
        {auto_print_script}
    </body>
    </html>
    """
    return html_content

def _generate_cards_body(words_data):
    cards_html = ""
    for _, row in words_data.iterrows():
        # 获取原始的完整例句 (含中文)
        full_example = str(row['Example'])
        
        # 1. 左侧：使用完整例句，但挖空目标词 (中文不受影响)
        masked_full = get_masked_sentence(full_example, row['Word'])
        
        # 2. 右侧：提取纯英文例句 (无挖空)
        english_only = extract_english_only(full_example)
        cards_html += f"""
        <div class="card-wrapper">
            <div class="card-front">
                <div class="content-top">
                    <h2>🇨🇳 {row['Meaning']}</h2>
                    <div class="cloze-box">"{masked_full}"</div>
                </div>
                
                <div class="meta-section">
                    <div class="check-row">
                        <span class="check-label">📅 Ebb:</span>
                        <span class="box"></span><span class="box-text">1</span>
                        <span class="box"></span><span class="box-text">2</span>
                        <span class="box"></span><span class="box-text">4</span>
                        <span class="box"></span><span class="box-text">7</span>
                        <span class="box"></span><span class="box-text">15</span>
                    </div>
                    <div class="check-row">
                        <span class="check-label">🗂 Box:</span>
                        <span class="box"></span><span class="box-text">New</span>
                        <span class="box"></span><span class="box-text">Blur</span>
                        <span class="box"></span><span class="box-text">Done</span>
                    </div>
                </div>
            </div>
            <div class="card-back">
                <div class="content-top">
                    <h3>{row['Word']}</h3>
                    <div class="phonetic">{row['Phonetic']}</div>
                    
                    <span class="label">Collocation</span>
                    <div class="text-content">{row['Collocation']}</div>
                    
                    <span class="label">Sentence (EN)</span>
                    <div class="text-content" style="color:#666;">{english_only}</div>
                </div>
            </div>
        </div>"""
    return cards_html

# ================= UI 页面 =================
st.set_page_config(page_title="AI 智能单词卡", layout="wide")
st.title("🤖 AI 智能单词卡生成器")

# Session State
if 'print_data' not in st.session_state: st.session_state.print_data = []

# --- Sidebar: 配置 ---
with st.sidebar:
    st.header("Step 1: 信息录入")
    student_class = st.text_input("班级:", key="class_input", placeholder="YS1800")
    student_name = st.text_input("姓名:", key="name_input", placeholder="张三")
    list_num = st.text_input("List编号:", key="list_input", placeholder="List1")
    
    if student_class and student_name and list_num:
        st.success(f"Hi, {student_name}!")
        master_db = load_or_create_data()
        history_df = load_history()
    else:
        st.warning("请补全信息")
        st.stop()

col1, col2 = st.columns([1, 1.5])

# --- 左侧: 智能输入 ---
with col1:
    st.subheader("Step 2: 录入错词")
    user_input = st.text_area("输入错词 (用空格/逗号隔开):", height=200)
    
    if 'print_list' not in st.session_state:
        st.session_state.print_list = []

    if st.button("⬇️ 添加到列表", type="primary"):
        if user_input:
            input_words = [w.strip().lower() for w in re.split(r'[,\s\n]+', user_input) if w.strip()]
            master_db['Word_Lower'] = master_db['Word'].astype(str).str.lower()
            
            count = 0
            for w in input_words:
                match = master_db[master_db['Word_Lower'] == w]
                if not match.empty:
                    real_word = match.iloc[0]['Word']
                    if real_word not in st.session_state.print_list:
                        st.session_state.print_list.append(real_word)
                        count += 1
            if count > 0:
                st.success(f"已添加 {count} 个词")

with col_preview:
    st.subheader("Step 3: 预览与下载")
    if st.session_state.print_data:
        if st.button("🗑️ 清空列表"):
            st.session_state.print_data = []
            st.rerun()
            
        df_print = pd.DataFrame(st.session_state.print_data)
        student_info = {"name": student_name, "class_name": student_class, "list_num": list_num}
        
        # 预览
        html_view = generate_clean_html(df_print, student_info, False)
        components.html(html_view, height=500, scrolling=True)
        
        # 下载
        html_print = generate_clean_html(df_print, student_info, True)
        clean_name = re.sub(r'[\\/*?:"<>|]', "", f"{student_class}_{student_name}_{list_num}")
        
        if st.download_button("📥 下载打印文件", html_print, f"Cards_{clean_name}.html", "text/html", type="primary"):
            # 记录历史
            new_recs = [{"Student":student_name, "Class":student_class, "List_Num":list_num, "Word":row['Word'], "Print_Date":datetime.now().strftime("%Y-%m-%d")} for _, row in df_print.iterrows()]
            save_history(pd.concat([history_df, pd.DataFrame(new_recs)], ignore_index=True))
            st.toast("下载成功！")
    else:
        st.info("👈 列表为空")