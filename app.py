import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import re
import os
import json
from openai import OpenAI 

# ================= 配置区 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "Total_Words.xlsx")
HISTORY_FILE = os.path.join(BASE_DIR, "student_print_history.csv")

# API Key 配置逻辑 (优先读取 Secrets，失败则留空允许手动填)
try:
    DEFAULT_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except:
    DEFAULT_API_KEY = ""

DEFAULT_BASE_URL = "https://api.deepseek.com"

# ================= 数据与AI函数 =================

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
        # 强制转为字符串，防止纯数字列报错
        return pd.read_excel(DATA_FILE).astype(str)

def save_new_words_to_excel(new_words_list):
    """
    【核心修复】将 AI 生成的新词追加到本地 Excel
    增加了列对齐逻辑，防止 KeyError
    """
    if not new_words_list: return
    
    current_df = load_or_create_data()
    new_df = pd.DataFrame(new_words_list)
    
    # === 修复 KeyError 的关键步骤 ===
    # 1. 补全 new_df 缺失的列 (比如 Excel 有 'Note' 但 AI 没生成)
    for col in current_df.columns:
        if col not in new_df.columns:
            new_df[col] = ""
            
    # 2. 过滤 new_df 多余的列，并确保顺序一致
    new_df = new_df[current_df.columns]
    # ==============================
    
    # 合并并去重
    combined = pd.concat([current_df, new_df], ignore_index=True)
    
    if 'Word' in combined.columns:
        combined['Word_Lower_Temp'] = combined['Word'].astype(str).str.lower()
        combined.drop_duplicates(subset=['Word_Lower_Temp'], keep='last', inplace=True)
        combined.drop(columns=['Word_Lower_Temp'], inplace=True)
    
    combined.to_excel(DATA_FILE, index=False)

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
    """提取纯英文部分 (遇到第一个中文字符截止)"""
    if not isinstance(sentence, str): return ""
    match = re.search(r'[\u4e00-\u9fa5]', sentence)
    if match:
        return sentence[:match.start()].strip()
    return sentence

# === AI 核心生成逻辑 ===
def generate_words_by_ai(words_list, api_key, base_url):
    """
    调用大模型为缺失单词生成内容
    """
    if not words_list: return []
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # 【优化 Prompt】强制要求 Example 包含中文翻译，以便后续做中英分离
    prompt = f"""
    You are an English teacher. 
    I will give you a list of words: {words_list}.
    Generate a JSON response. The structure must be a list of objects with these exact keys:
    - "Word": The word itself (lowercase).
    - "Phonetic": IPA phonetic symbol.
    - "Meaning": Concise Chinese meaning (part of speech + meaning).
    - "Example": One English sentence containing the word, FOLLOWED IMMEDIATELY by its Chinese translation. (Format: English Sentence. Chinese Translation.)
    - "Collocation": One or two common phrases (English only).
    
    Output ONLY valid JSON.
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # 或 gpt-3.5-turbo
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        st.error(f"AI 生成失败: {e}")
        return []

# ================= HTML 生成逻辑 (省纸版 + 中英分离) =================
def generate_clean_html(words_data, student_info, for_printing=False):
    auto_print_script = """<script>window.onload = function() { setTimeout(function(){ window.print(); }, 800); }</script>""" if for_printing else ""
    
    header_msg = f"""
    <div class="no-print" style="text-align:center; padding: 10px; background:#e6fffa; color:#2c7a7b; border-bottom:1px solid #b2f5ea; font-size:13px;">
        💡 <strong>提示：</strong> 请选择 A4 纸打印，勾选“背景图形”。<br>左侧有中文提示，右侧为纯英文。
    </div>
    <div class="print-header" style="text-align:center; margin-bottom: 10px; font-size: 12px; color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px;">
        班级: <strong>{student_info['class_name']}</strong> | 姓名: <strong>{student_info['name']}</strong> | List: <strong>{student_info['list_num']}</strong> | 日期: {datetime.now().strftime('%Y-%m-%d')}
    </div>
    """
    
    html_content = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>复习卡_{student_info['name']}</title>
    <style>
        body {{ font-family: "Helvetica Neue", Arial, sans-serif; background-color: {'#ffffff' if for_printing else '#f9f9f9'}; margin: 0; padding: {'0' if for_printing else '10px'}; color: #333; font-size: 13px; }}
        .card-container {{ width: 100%; max-width: 700px; margin: 0 auto; }}
        
        /* === 卡片样式 (A4省纸紧凑版) === */
        .card-wrapper {{ display: flex; background: white; border: 1px dashed #999; margin-bottom: 12px; page-break-inside: avoid; position: relative; height: auto; min-height: 40mm; }}
        .card-wrapper::after {{ content: '✂️ Cut'; position: absolute; bottom: -13px; right: 0; font-size: 10px; color: #bbb; background: white; padding: 0 4px; }}
        
        /* 左右分栏 + 垂直分布 */
        .card-front, .card-back {{ flex: 1; padding: 10px 14px; display: flex; flex-direction: column; justify-content: space-between; }}
        .card-front {{ border-right: 1px solid #eee; }} .card-back {{ background-color: #fcfcfc; }}
        .content-top {{ flex-grow: 1; }}
        
        h2 {{ margin: 0 0 6px 0; font-size: 16px; color: #2c3e50; line-height: 1.2; }} h3 {{ margin: 0 0 4px 0; font-size: 20px; color: #000; line-height: 1.1; }}
        .cloze-box {{ background: #f0f2f6; padding: 8px; border-radius: 5px; font-style: italic; line-height: 1.4; font-size: 13px; border: 1px solid #ebedf0; margin-bottom: 5px; }}
        
        .meta-section {{ margin-top: 8px; padding-top: 6px; border-top: 1px dotted #eee; font-size: 11px; color: #555; }}
        .check-row {{ display: flex; align-items: center; margin-bottom: 3px; }} .check-label {{ margin-right: 6px; font-weight: bold; width: 60px; }}
        .box {{ display: inline-block; width: 12px; height: 12px; border: 1px solid #444; margin-right: 3px; border-radius: 2px; }} .box-text {{ margin-right: 8px; font-size: 10px; }}
        
        .phonetic {{ color: #777; font-family: "Times New Roman", serif; margin-bottom: 8px; font-size: 13px; }}
        .label {{ font-weight: bold; font-size: 10px; color: #999; text-transform: uppercase; margin-top: 8px; display:block; }}
        .text-content {{ font-size: 13px; color: #333; line-height: 1.3; }}
        
        @media print {{ @page {{ margin: 10mm; size: A4; }} body {{ background: white; padding: 0; -webkit-print-color-adjust: exact; }} .no-print {{ display: none !important; }} .print-header {{ display: block !important; margin-bottom: 15px; }} .card-container {{ max-width: 100%; width: 100%; }} .card-wrapper {{ border-color: #888; margin-bottom: 12px; border-style: dashed; }} .card-wrapper::after {{ display: none; }} }}
    </style></head><body>{header_msg}<div class="card-container">{_generate_cards_body(words_data)}</div>{auto_print_script}</body></html>
    """
    return html_content

def _generate_cards_body(words_data):
    cards_html = ""
    for _, row in words_data.iterrows():
        # 安全获取字段
        full_example = str(row.get('Example', ''))
        word_text = str(row.get('Word', ''))
        meaning_text = str(row.get('Meaning', ''))
        phonetic_text = str(row.get('Phonetic', ''))
        collocation_text = str(row.get('Collocation', ''))

        # 核心逻辑：左侧中英挖空，右侧纯英提取
        masked_full = get_masked_sentence(full_example, word_text)
        english_only = extract_english_only(full_example)
        
        cards_html += f"""
        <div class="card-wrapper">
            <div class="card-front">
                <div class="content-top"><h2>🇨🇳 {meaning_text}</h2><div class="cloze-box">"{masked_full}"</div></div>
                <div class="meta-section"><div class="check-row"><span class="check-label">📅 Ebb:</span><span class="box"></span><span class="box-text">1</span><span class="box"></span><span class="box-text">2</span><span class="box"></span><span class="box-text">4</span><span class="box"></span><span class="box-text">7</span><span class="box"></span><span class="box-text">15</span></div><div class="check-row"><span class="check-label">🗂 Box:</span><span class="box"></span><span class="box-text">New</span><span class="box"></span><span class="box-text">Blur</span><span class="box"></span><span class="box-text">Done</span></div></div>
            </div>
            <div class="card-back">
                <div class="content-top"><h3>{word_text}</h3><div class="phonetic">{phonetic_text}</div><span class="label">Collocation</span><div class="text-content">{collocation_text}</div><span class="label">Sentence (EN)</span><div class="text-content" style="color:#666;">{english_only}</div></div>
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
    # 优先使用配置的 Key，否则显示输入框
    if DEFAULT_API_KEY:
        api_key = DEFAULT_API_KEY
    else:
        api_key = st.text_input("DeepSeek Key:", type="password", help="未配置Secrets时手动输入")
    
    student_class = st.text_input("班级:", key="class", placeholder="Grade 3")
    student_name = st.text_input("姓名:", key="name", placeholder="Tom")
    list_num = st.text_input("List编号:", key="list", placeholder="List 5")
    
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
    st.info("💡 提示：输入任意单词。如果本地词库没有，AI 会自动为你生成！")
    
    user_input = st.text_area("输入单词:", height=150, placeholder="例如: ambition, serendipity")
    
    if st.button("✨ 智能查找与生成", type="primary"):
        if not user_input:
            st.warning("请输入单词")
        elif not api_key:
            st.error("缺少 API Key，无法调用 AI。")
        else:
            input_words = [w.strip().lower() for w in re.split(r'[,\s\n]+', user_input) if w.strip()]
            master_db['Word_Lower'] = master_db['Word'].astype(str).str.lower()
            
            found_words = [] 
            missing_words = [] 
            
            # 1. 查本地
            for w in input_words:
                match = master_db[master_db['Word_Lower'] == w]
                if not match.empty:
                    found_words.append(match.iloc[0].to_dict())
                else:
                    missing_words.append(w)
            
            # 2. 查 AI
            ai_generated_words = []
            if missing_words:
                with st.status(f"🤖 正在呼叫 AI 生成: {', '.join(missing_words)} ...", expanded=True) as status:
                    # 使用当前获取到的 api_key
                    ai_result = generate_words_by_ai(missing_words, api_key, DEFAULT_BASE_URL)
                    
                    if ai_result:
                        save_new_words_to_excel(ai_result) # 自动入库
                        master_db = load_or_create_data() # 刷新缓存
                        ai_generated_words = ai_result
                        status.update(label="✅ AI 生成完毕！", state="complete", expanded=False)
                    else:
                        status.update(label="❌ AI 生成失败", state="error")
            
            # 3. 汇总加入打印列表 (去重)
            total_added = 0
            all_new_items = found_words + ai_generated_words
            current_print_words = [x['Word'] for x in st.session_state.print_data]
            
            for item in all_new_items:
                if item['Word'] not in current_print_words:
                    st.session_state.print_data.append(item)
                    total_added += 1
            
            msg = f"已添加 {total_added} 个单词。"
            if ai_generated_words:
                msg += f" (含 {len(ai_generated_words)} 个 AI 生成新词)"
            st.success(msg)

# --- 右侧: 预览与下载 ---
with col2:
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