# 在文件顶部的导入部分添加新的导入
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import re
import os
import json
import random
from openai import OpenAI 
import difflib  # 添加这一行用于拼写检查

# ================= 基础配置 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "Total_Words.xlsx")
HISTORY_FILE = os.path.join(BASE_DIR, "student_print_history.csv")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")

st.set_page_config(page_title="雅睿途智能单词卡", layout="wide", page_icon="logo.png")

# ================= 状态初始化 =================
if 'print_data' not in st.session_state: 
    st.session_state.print_data = []
if 'current_user_info' not in st.session_state:
    st.session_state.current_user_info = {"class": "", "name": "", "list_num": ""}

# ================= API 配置 =================
try:
    DEFAULT_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except:
    DEFAULT_API_KEY = ""
DEFAULT_BASE_URL = "https://api.deepseek.com"

# ================= 按钮颜色 CSS（增强兼容版）=================
def inject_custom_css():
    st.markdown("""
    <style>
        /* =================== 按钮颜色精细控制 =================== */

        /* 1. 默认 Secondary 按钮 (灰色) - 对应【清空当前列表】 */
        /* 作用域：全局 Main 区域的 Secondary 按钮 */
        .stButton button[kind="secondary"] {
            background-color: #6c757d !important;
            border-color: #6c757d !important;
            color: white !important;
        }
        .stButton button[kind="secondary"]:hover {
            background-color: #5a6268 !important;
            border-color: #545b62 !important;
            color: white !important;
        }

        /* 2. 侧边栏 Secondary 按钮 (红色) - 对应【登出】 */
        /* 作用域：仅侧边栏，覆盖上面的灰色规则 */
        section[data-testid="stSidebar"] .stButton button[kind="secondary"] {
            background-color: #dc3545 !important;
            border-color: #dc3545 !important;
            color: white !important;
        }
        section[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
            background-color: #bb2d3b !important;
            border-color: #b02a37 !important;
            color: white !important;
        }

        /* 3. 普通 Primary 按钮 (蓝色) - 对应【智能查找与生成】 */
        /* 作用域：所有 st.button 的 primary 类型 */
        .stButton button[kind="primary"] {
            background-color: #0d6efd !important;
            border-color: #0d6efd !important;
            color: white !important;
        }
        .stButton button[kind="primary"]:hover {
            background-color: #0b5ed7 !important;
            border-color: #0a58ca !important;
            color: white !important;
        }

        /* 4. 下载按钮 (绿色) - 对应【下载打印文件】 */
        /* 作用域：st.download_button 特有类名 */
        .stDownloadButton button {
            background-color: #198754 !important;
            border-color: #198754 !important;
            color: white !important;
        }
        .stDownloadButton button:hover {
            background-color: #157347 !important;
            border-color: #146c43 !important;
            color: white !important;
        }
        
        /* 隐藏部署按钮 */
        .stDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# ================= 数据函数（保持不变）=================
def load_or_create_data():
    if not os.path.exists(DATA_FILE):
        data = {"Word": ["ambition"],"Phonetic": ["/æmˈbɪʃn/"],"Meaning": ["n. 雄心，抱负"],
                "Example": ["She has a great ambition to become a doctor. 她有一个成为医生的宏大抱负。"],
                "Collocation": ["great ambition"]}
        df = pd.DataFrame(data)
        df.to_excel(DATA_FILE, index=False)
        return df
    else:
        return pd.read_excel(DATA_FILE).astype(str)

def save_new_words_to_excel(new_words_list):
    if not new_words_list: return
    current_df = load_or_create_data()
    new_df = pd.DataFrame(new_words_list)
    for col in current_df.columns:
        if col not in new_df.columns: new_df[col] = ""
    new_df = new_df[current_df.columns]
    combined = pd.concat([current_df, new_df], ignore_index=True)
    if 'Word' in combined.columns:
        combined['Word_Lower'] = combined['Word'].astype(str).str.lower()
        combined.drop_duplicates(subset=['Word_Lower'], keep='last', inplace=True)
        combined.drop(columns=['Word_Lower'], inplace=True)
    combined.to_excel(DATA_FILE, index=False)

def load_history(): 
    return pd.read_csv(HISTORY_FILE) if os.path.exists(HISTORY_FILE) else pd.DataFrame(columns=["Student","Class","List_Num","Word","Print_Date"])

def save_history(df): df.to_csv(HISTORY_FILE, index=False)

def get_masked_sentence(sentence, word):
    if not isinstance(sentence, str): return ""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    return pattern.sub("_______", sentence)

def extract_english_only(sentence):
    if not isinstance(sentence, str): return ""
    match = re.search(r'[\u4e00-\u9fa5]', sentence)
    if match: return sentence[:match.start()].strip()
    return sentence

def generate_words_by_ai(words_list, api_key, base_url):
    if not words_list: return []
    client = OpenAI(api_key=api_key, base_url=base_url)
    system_prompt = """
    You are an English teacher. Output ONLY valid JSON.
    JSON format: [{"Word": "...", "Phonetic": "...", "Meaning": "...", "Example": "...", "Collocation": "..."}]
    1. "Meaning": MUST be in CHINESE only (n./v. + 中文意思)
    2. "Example": English sentence + Chinese translation (no extra space)
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":f"Words: {json.dumps(words_list)}"}],
            response_format={'type': 'json_object'},
            temperature=0.1
        )
        data = json.loads(response.choices[0].message.content)
        if isinstance(data, dict):
            for k in ["words","list","data"]:
                if k in data and isinstance(data[k], list): return data[k]
            return []
        return data if isinstance(data, list) else []
    except Exception as e:
        st.error(f"AI 生成失败: {e}")
        return []

# ================= HTML 生成=================
def generate_clean_html(words_data, student_info, for_printing=False):
    auto_print = """<script>window.onload=function(){setTimeout(()=>{window.print();},800)}</script>""" if for_printing else ""
    header_tip = '<div class="no-print" style="text-align:center;padding:10px;background:#e6fffa;color:#2c7a7b;font-size:13px;border-bottom:1px solid #b2f5ea;">打印提示：A4纸 + 勾选"背景图形"</div>' if not for_printing else ""

    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>单词卡_{student_info['name']}</title>
    <style>
        body {{margin:0;padding:0;font-family:"Helvetica Neue",Arial,sans-serif;background:white;color:#333;}}
        .page {{height:297mm;padding:11mm 13mm;box-sizing:border-box;page-break-after:always;display:flex;flex-direction:column;}}
        .page:last-child {{page-break-after:auto;}}
        .header {{text-align:center;font-size:13px;padding-bottom:6px;border-bottom:1px solid #eee;margin-bottom:12px;position:relative;}}
        .header .page-num {{position:absolute;right:0;top:0;font-size:12px;color:#666;}}
        .cards {{flex:1;display:flex;flex-direction:column;gap:8mm;}} /* 干净间距，无多余线 */
        .card {{display:flex;height:40mm;border:1px dashed #999;position:relative;flex-shrink:0;}}
        .card::before {{content:'';position:absolute;bottom:-7px;left:30%;right:30%;border-bottom:none;}} /* 移除虚线 */
        .card::after {{content:'✂️';position:absolute;bottom:-13px;right:8px;font-size:19px;color:#999;}}
        .left, .right {{flex:1;padding:7px 10px;display:flex;flex-direction:column;box-sizing:border-box;}}
        .right {{background:#fcfcfc;border-left:1px solid #eee;}}
        .cn-tag {{background:#333;color:white;padding:2px 6px;border-radius:4px;font-size:10.5px;align-self:flex-start;}}
        .meaning-line {{display:flex;align-items:center;gap:6px;font-size:14.5px;margin-bottom:5px;}}
        .cloze {{background:#f0f2f6;padding:6px 8px;border-radius:4px;font-style:italic;font-size:11.5px;line-height:1.4;
                 border:1px solid #ebedf0;flex-grow:1;overflow:hidden;display:flex;align-items:center;}}
        .meta {{font-size:9.5px;color:#666;margin-top:5px;padding-top:5px;border-top:1px dotted #ddd;}}
        .box {{display:inline-block;width:10px;height:10px;border:1px solid #444;margin-right:3px;}}
        .sentence {{font-size:12px;color:#666;line-height:1.4;flex-grow:1;overflow:hidden;}}
        .review {{margin-top:15px;padding:12px;border-top:3px dashed #ccc;background:#fdfdfd;font-size:11.5px;height:45mm;box-sizing:border-box;}} /* 增大上间距 */
        @media print {{
            @page {{margin:0;size:A4;}}
            body {{background:white;-webkit-print-color-adjust:exact;}}
            .no-print {{display:none !important;}}
        }}
    </style></head><body>
    {header_tip}
    {_generate_pages(words_data, student_info, for_printing)}
    {auto_print}
    </body></html>
    """
    return html

def _generate_pages(words_data, student_info, for_printing):
    html = ""
    cards_per_page = 5
    records = words_data.to_dict('records')
    total = len(records)
    pages = (total + cards_per_page - 1) // cards_per_page

    for i in range(0, total, cards_per_page):
        page_words = records[i:i+cards_per_page]
        page_num = i // cards_per_page + 1
        words_this_page = [r['Word'] for r in page_words]

        html += '<div class="page">'
        html += f'''
        <div class="header">
            班级: <strong>{student_info['class_name']}</strong> | 姓名: <strong>{student_info['name']}</strong> | List: <strong>{student_info['list_num']}</strong> | 日期: {datetime.now().strftime('%Y-%m-%d')}
            <span class="page-num">第 {page_num}/{pages} 页</span>
        </div>
        '''
        html += '<div class="cards">'
        for row in page_words:
            word = str(row.get('Word',''))
            example = str(row.get('Example',''))
            masked = get_masked_sentence(example, word)
            english_sentence = extract_english_only(example)
            html += f'''
            <div class="card">
                <div class="left">
                    <div class="meaning-line"><span class="cn-tag">中</span><span>{row.get('Meaning','')}</span></div>
                    <div class="cloze">"{masked}"</div>
                    <div class="meta">
                        <div>📅 Ebb: <span class="box"></span>1 <span class="box"></span>2 <span class="box"></span>4 <span class="box"></span>7 <span class="box"></span>15</div>
                        <div>🗂 Box: <span class="box"></span>New <span class="box"></span>Blur <span class="box"></span>Done</div>
                    </div>
                </div>
                <div class="right">
                    <h3 style="margin:0 0 4px;font-size:19px;">{word}</h3>
                    <div style="color:#666;font-family:'Times New Roman';font-size:13px;margin-bottom:5px">{row.get('Phonetic','')}</div>
                    <div style="font-size:10px;color:#999;font-weight:bold">COLLOCATION</div>
                    <div style="font-size:12px;line-height:1.3;margin-bottom:5px">{row.get('Collocation','')}</div>
                    <div style="font-size:10px;color:#999;font-weight:bold">SENTENCE</div>
                    <div class="sentence">{english_sentence}</div>
                </div>
            </div>
            '''
        html += '</div>'

        if for_printing and words_this_page:
            # 生成4行随机顺序
            lines = [words_this_page[:] for _ in range(4)]
            for line in lines:
                random.shuffle(line)
            html += f'''
            <div class="review" style="border-top: none !important;">  <!-- 移除虚线 -->
                <div style="font-weight:bold;color:#666;margin-bottom:10px;">📝 本页单词随机复习：</div>
                <div style="line-height:1.8;">
                    {" • ".join(lines[0])}<br>
                    {" • ".join(lines[1])}<br>
                    {" • ".join(lines[2])}<br>
                    {" • ".join(lines[3])}
                </div>
            </div>
            '''
        html += '</div>'
    return html

# ================= UI =================
inject_custom_css()

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    else:
        st.markdown("## 🎓 雅睿途")
    st.header("Step 1: 信息录入")
    api_key = DEFAULT_API_KEY if DEFAULT_API_KEY else st.text_input("DeepSeek Key:", type="password")
    student_class = st.text_input("班级:", key="class", placeholder="YS1800")
    student_name   = st.text_input("姓名:", key="name", placeholder="张三")
    list_num       = st.text_input("List编号:", key="list", placeholder="List 10")

    if student_class and student_name and list_num:
        st.divider()
        if st.button("🚪 登出", type="secondary", use_container_width=True):
            # 检查当前输入框的内容是否与已登录用户一致
            current = st.session_state.current_user_info
            input_info = {"class": student_class, "name": student_name, "list_num": list_num}
            
            if (current.get("class") == student_class and 
                current.get("name") == student_name and 
                current.get("list_num") == list_num):
                # 信息未变 -> 执行真正的登出（清空）
                for k in ["class", "name", "list", "word_input"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state.print_data = []
                st.session_state.current_user_info = {"class":"", "name":"", "list_num":""}
                st.rerun()
            else:
                # 信息已变 -> 执行切换用户
                st.session_state.print_data = []
                st.session_state.current_user_info = input_info
                # 清空Step2输入框
                if "word_input" in st.session_state:
                    st.session_state.word_input = ""
                # 设置提示信息
                st.session_state.flash_msg = f"已切换到 {student_name}（{student_class} List:{list_num}）"
                st.rerun()

st.title("雅睿途智能单词卡 powered by DeepSeek")
st.caption("自动补全生词 · 中英分离 · A4完美打印")

# === 消息提示区域 (屏幕中间显示) ===
if "flash_msg" in st.session_state and st.session_state.flash_msg:
    st.success(f"✅ {st.session_state.flash_msg}", icon="👋")
    # 显示一次后不再显示，清除消息但保持current_user_info
    del st.session_state.flash_msg

if not (student_class and student_name and list_num):
    st.info("请先在左侧填写信息")
    st.stop()

# 自动检测输入变化（非点击登出按钮的情况）
if (st.session_state.current_user_info.get("class") != student_class or
    st.session_state.current_user_info.get("name") != student_name or
    st.session_state.current_user_info.get("list_num") != list_num):
    
    st.session_state.print_data = []
    st.session_state.current_user_info = {"class": student_class, "name": student_name, "list_num": list_num}
    
    if "word_input" in st.session_state:
        st.session_state.word_input = ""
        
    st.session_state.flash_msg = f"已切换到 {student_name}（{student_class} List:{list_num}）"
    st.rerun()

master_db = load_or_create_data()
history_df = load_history()
col1, col2 = st.columns([1, 1.5])

# 在load_or_create_data函数之后添加新的函数
def find_similar_words(input_word, word_list, cutoff=0.8):
    """
    查找相似的单词，用于拼写检查
    :param input_word: 用户输入的单词
    :param word_list: 词库中的单词列表
    :param cutoff: 相似度阈值（0-1之间）
    :return: 最相似的单词列表
    """
    similar_words = difflib.get_close_matches(input_word.lower(), word_list, n=3, cutoff=cutoff)
    return similar_words

with col1:
    st.subheader("Step 2: 录入错词")
    user_input = st.text_area("输入单词（逗号/空格/换行分隔）", height=150, placeholder="aggressive extremely", key="word_input")
    
    # 添加一个占位符用于显示拼写检查结果
    spell_check_placeholder = st.empty()
    
    if st.button("✨ 智能查找与生成", type="primary", use_container_width=True):
        if not user_input:
            st.warning("请输入单词")
        elif not api_key:
            st.error("请填写 DeepSeek Key")
        else:
            words = [w.strip().lower() for w in re.split(r'[,\s\n]+', user_input) if w.strip()]
            master_db['low'] = master_db['Word'].str.lower()
            
            # 获取词库中的所有单词用于拼写检查
            word_list = master_db['low'].tolist()
            
            found = []
            missing = []
            corrections_made = []  # 记录所有纠正的单词
            corrected_words = {}   # 存储纠正的单词映射
            
            for w in words:
                row = master_db[master_db['low']==w]
                if not row.empty:
                    found.append(row.iloc[0].to_dict())
                else:
                    # 检查是否有拼写错误的单词
                    similar_words = find_similar_words(w, word_list, cutoff=0.8)
                    if similar_words:
                        # 如果找到相似单词，记录纠正信息
                        corrected_word = similar_words[0]  # 使用最相似的单词
                        corrections_made.append((w, corrected_word))  # 记录原始单词和纠正后的单词
                        corrected_words[w] = corrected_word
                    else:
                        missing.append(w)
            
            # 如果有拼写错误的单词，提示用户
            if corrections_made:
                # 显示纠正信息在按钮下方
                correction_messages = []
                for original, corrected in corrections_made:
                    correction_messages.append(f"'{original}' → '{corrected}'")
                
                correction_text = "已自动纠正以下拼写错误的单词：\n" + "\n".join([f"  • {msg}" for msg in correction_messages])
                spell_check_placeholder.info(correction_text)
                
                # 自动将纠正后的单词添加到found列表中
                for correct_word in corrected_words.values():
                    row = master_db[master_db['low']==correct_word]
                    if not row.empty:
                        found.append(row.iloc[0].to_dict())
            else:
                # 如果没有纠正，清空提示区域
                spell_check_placeholder.empty()
            
            if missing:
                with st.status(f"AI生成中：{', '.join(missing)}") as s:
                    new_words = generate_words_by_ai(missing, api_key, DEFAULT_BASE_URL)
                    if new_words:
                        save_new_words_to_excel(new_words)
                        found.extend(new_words)
                        s.update(label="生成成功", state="complete")
                    else:
                        s.update(label="生成失败", state="error")
            
            added = 0
            current_words = [x['Word'] for x in st.session_state.print_data]
            for item in found:
                if item.get('Word') and item['Word'] not in current_words:
                    st.session_state.print_data.append(item)
                    added += 1
            if added:
                st.success(f"成功添加 {added} 个单词")
                st.rerun()
            elif not corrections_made:
                st.info("已全部存在，无需重复添加")

with col2:
    st.subheader("Step 3: 预览与下载")
    if st.session_state.print_data:
        if st.button("🗑️ 清空当前列表", type="secondary", use_container_width=True):
            st.session_state.print_data = []
            st.rerun()

        df = pd.DataFrame(st.session_state.print_data)
        info = {"name": student_name, "class_name": student_class, "list_num": list_num}
        
        components.html(generate_clean_html(df, info, False), height=700, scrolling=True)
        
        if st.download_button(
            "📥 下载打印文件（自动打印）",
            data=generate_clean_html(df, info, True),
            file_name=f"单词卡_{student_class}_{student_name}_{list_num}.html",
            mime="text/html",
            type="primary",
            use_container_width=True
        ):
            new_rec = pd.DataFrame([{"Student": student_name, "Class": student_class, "List_Num": list_num,
                                     "Word": r['Word'], "Print_Date": datetime.now().strftime("%Y-%m-%d")} 
                                    for _, r in df.iterrows()])
            save_history(pd.concat([history_df, new_rec], ignore_index=True))
            st.toast("下载成功，打开HTML文件会自动打印~", icon="✅")
    else:
        st.info("等待录入单词...")