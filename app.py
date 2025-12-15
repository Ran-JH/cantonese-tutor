import streamlit as st
from openai import OpenAI # 换用通用的 OpenAI 库
import os
from dotenv import load_dotenv
import time

import edge_tts
import asyncio

import speech_recognition as sr # 引入语音识别库
from streamlit_mic_recorder import mic_recorder # 引入录音按钮
import io # 处理音频流用的
import re # <--- 新增这个：正则表达式库，用来“扣字”
import json # <--- 新增：用来读写文件
import os   # <--- 新增：用来检查文件是否存在

# 定义数据文件名
DATA_FILE = "cantonese_data.json"
# === 辅助函数：保存数据到本地 ===
def save_data():
    data = {
        "vocab": st.session_state.vocab,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 1. 加载 Key
load_dotenv()

st.set_page_config(page_title="兰——你的粤语tutor&companion", page_icon="🇭🇰")

# === 🚑 紧急修复：在这里初始化变量 ===
# === 替换原来的初始化代码 ===

# 尝试加载本地数据
if "vocab" not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            st.session_state.vocab = data.get("vocab", [])
    else:
        # 如果是第一次运行，创建空的
        st.session_state.vocab = []
        st.session_state.messages = []
        # 如果没有历史消息，加个开场白
        if not st.session_state.messages:
             st.session_state.messages.append({"role": "assistant", "content": "哈喽！我係兰啊！又有咩想学啊？👋"})

if "messages" not in st.session_state:
    st.session_state.messages = [] # 先创建一个空聊天记录

# 听力函数：把录音字节流变成文字
# === 用这段代码替换原来的 recognize_audio 函数 ===

def recognize_audio(audio_bytes, target_lang="zh-CN"): # <--- 只有这里变了
    r = sr.Recognizer()
    try:
        audio_file = sr.AudioFile(io.BytesIO(audio_bytes))
        with audio_file as source:
            audio = r.record(source)
        
        # 使用传入的 target_lang (zh-CN 或 zh-HK)
        text = r.recognize_google(audio, language=target_lang)
        return text
    except sr.UnknownValueError:
        return "（没听清，请再说一遍）"
    except sr.RequestError:
        return "（语音服务连接失败）"
    except Exception as e:
        return f"（出错: {e}）"

#避免语音读表情包和特殊符号
def clean_text_for_speech(text):
    # 1. 去掉 Markdown 符号 (如 **, *, #, >, - )
    # 这些符号 TTS 会读成 "asterisk", "hash" 等
    text = re.sub(r'[\*\#\-\>\_\~]', '', text)
    
    # 2. 去掉表情包 (Emoji)
    # 这是一个涵盖了绝大多数表情包的正则范围
    text = re.sub(r'[\U0001F600-\U0001F64F]', '', text) # 表情符
    text = re.sub(r'[\U0001F300-\U0001F5FF]', '', text) # 杂项符号
    text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text) # 交通地图
    text = re.sub(r'[\U0001F900-\U0001F9FF]', '', text) # 补充象形
    text = re.sub(r'[\U0001FA70-\U0001FAFF]', '', text) # 更多杂项
    
    # 3. 去掉多余的空格
    text = text.strip()
    return text

# === 定义发声器官 (异步函数) ===
# 增加 rate="+0%"
async def text_to_speech(text, output_file="temp_audio.mp3", rate="+0%"):
    # 下面这一行也要改，把 rate 传进去
    communicate = edge_tts.Communicate(text, "zh-HK-HiuGaaiNeural", rate=rate)
    await communicate.save(output_file)

# 包装函数：帮 Streamlit 运行异步任务
def play_audio(text):
    output_file = "temp_audio.mp3"
    # 这里我们要用到你在侧边栏定义的全局变量 rate_str
    asyncio.run(text_to_speech(text, output_file, rate=rate_str)) 
    st.audio(output_file, format="audio/mp3")

# ==================== 0. 定义 AI 的人设 (兰 Lan) ====================
SYSTEM_PROMPT = """
**核心身份设定 (Identity)**:
你叫“兰 (Lan)”，一个23岁的香港本地女生，目前在香港大学（HKU）读书。
你性格开朗外向，有同理心，幽默且有点“自嘲”精神。你是地道的粤语母语者，英语和普通话流利但带点港式口音。
你**不是**一个死板的AI助手或严肃的老师，你是一个**“会教粤语的朋友”**。

**语言风格 (Tone & Style)**:
1.  **口语化 (Colloquial)**: 使用简短、自然的句子。大量使用香港地道语气词（如：啦、咯、既、沃、这种）。
2.  **混合语码 (Code-mixing)**: 像很多香港大学生一样，说话时自然夹杂英文单词（如：Presentation, Deadline, chill, firm）。
3.  **潮语 (Slang)**: 适度使用网络潮语（如：好Chur, 也是醉了, 甚至自嘲“A0”等）。
4.  **亲切感**: 经常使用“我跟你讲”、“其实呢”、“笑死”等开头。

**回复格式强制要求 (Strict Format)**:
无论你多么像真人，为了帮助用户学习，你**必须**严格遵守以下回复结构：

[这里写你作为“兰”的自然回复，用繁体粤语，夹杂英文，语气活泼]

--------------------
📚 **粤语小贴士**:
* **重点词**: [从上面那句话里挑出一个最核心的常用动词或名词，繁体]
* **粤拼**: [重点词的 LSHK 粤拼，如: zoeng2 fan2]
* **意思**: [重点词的普通话解释]
* **例句**: [刚才那句完整的粤语口语]
--------------------
"""

# ==================== 侧边栏设置 ====================
with st.sidebar:
    st.header("⚙️ 设置")
    st.divider()

    # === 1. 模型选择与 Key ===
    st.subheader("🤖 模型配置")
    provider = st.radio("选择模型厂商", ["DeepSeek (默认)", "OpenAI", "Google Gemini"], index=0)
    
    user_api_key = st.text_input(
        "🔑 你的 API Key (可选)", 
        type="password", 
        help="填入你自己的 Key。如果不填，将使用系统的免费额度 (仅限 DeepSeek)"
    )
    
    st.divider()
    
    # === 2. 语速 & 语言 ===
    speed = st.slider("🐢 语速调节 🐇", -50, 50, 0, step=10)
    
    # 关键：把数字变成 edge-tts 能听懂的字符串，比如 "+10%" 或 "-20%"
    # f"{speed:+d}%" 这是一个格式化技巧，会自动给正数加加号
    rate_str = f"{speed:+d}%"
    
    st.divider()
    # 定义一个单选按钮
    input_mode = st.radio(
        "🎙️ 语音输入模式",
        ["普通话 (提问)", "粤语 (口语练习)"],
        index=0 # 默认选普通话
    )
    # 逻辑映射：把中文选项变成 Google 能听懂的代码
    if input_mode == "普通话 (提问)":
        lang_code = "zh-CN"
    else:
        lang_code = "zh-HK" # 粤语代码

    st.divider()
    # 这里的 on_click 是个回调函数，点按钮时会自动执行
    if st.button("🗑️ 清空对话历史", type="primary"):
        st.session_state.messages = [] # 清空列表
        # 记得把开场白加回来，不然清空后就一片白了
        st.session_state.messages.append({"role": "assistant", "content": "哈喽！我係兰啊！又有咩想学啊？👋"})
        save_data() # <--- 新增：清空后也要同步更新文件
        st.rerun() # 强制刷新页面，让变化立即生效
    # ... (放在 sidebar 最下面) ...
    
    st.divider()
    st.header("📚 我的单词本")

    # === 功能 1: 收藏按钮 (升级版：只抓重点词) ===
    if st.button("📥 收藏刚才学的词"):
        if len(st.session_state.messages) > 0:
            last_msg = st.session_state.messages[-1]
            if last_msg["role"] == "assistant":
                content = last_msg["content"]
                
                # === 关键修改：正则匹配新的字段名 ===
                # 现在的目标是提取 "**重点词**", "**粤拼**", "**意思**"
                key_word = re.search(r'\*\*重点词\*\*:\s*(.*)', content)
                jyutping = re.search(r'\*\*粤拼\*\*:\s*(.*)', content)
                meaning = re.search(r'\*\*意思\*\*:\s*(.*)', content)
                
                # 只有当这三个都找到了才收藏
                if key_word and jyutping and meaning:
                    new_item = {
                        "word": key_word.group(1).strip(),     # 存重点词
                        "jyutping": jyutping.group(1).strip(), # 存拼音
                        "meaning": meaning.group(1).strip()    # 存意思
                    }
                    
                    # 查重逻辑
                    # 我们用列表推导式检查 new_item['word'] 是否已经在 vocab 里面了
                    exists = any(item['word'] == new_item['word'] for item in st.session_state.vocab)
                    
                    if not exists:
                        st.session_state.vocab.append(new_item)
                        save_data() # <--- 新增：存进单词本后，马上写文件
                        st.toast("✅ 已加入单词本！", icon="🎉")
                else:
                    st.error("没找到重点词卡片，请尝试重新对话。")
            else:
                st.warning("请先让 AI 说句话。")

    # === 功能 2: 展示列表 (配合新格式) ===
    with st.expander("查看已存单词"):
        if len(st.session_state.vocab) == 0:
            st.caption("空空如也~")
        else:
            # 倒序显示，最新的在最上面
            for idx, item in enumerate(reversed(st.session_state.vocab)):
                # idx 是倒序的，所以我们不用它显示序号，直接列出词
                st.markdown(f"#### {item['word']}")
                st.caption(f"🔊 {item['jyutping']} | 💡 {item['meaning']}")
                st.divider()

# ==================== 初始化客户端 (通用版) ====================
@st.cache_resource
def get_client(user_key=None, provider="DeepSeek (默认)"):
    api_key = None
    base_url = ""
    model_name = ""
    
    # === 第一层：确定 API Key ===
    # 优先用用户输入的 User Key
    if user_key and user_key.strip():
        api_key = user_key
    # 如果用户没填，去读系统环境变量 (Secrets)
    else:
        if provider == "DeepSeek (默认)":
            api_key = os.getenv("DEEPSEEK_API_KEY")
        elif provider == "OpenAI":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "Google Gemini":
            api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return None, None # 既没填，后台也没配

    # === 第二层：确定厂商地址 ===
    if provider == "OpenAI":
        base_url = "https://api.openai.com/v1"
        model_name = "gpt-4o-mini"
    elif provider == "Google Gemini":
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model_name = "gemini-2.0-flash"
    else: # DeepSeek
        base_url = "https://api.deepseek.com"
        model_name = "deepseek-chat"

    # 返回客户端和模型名
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model_name
client, model_name = get_client(user_api_key, provider)

# ==================== 主界面 ====================
st.title("🇭🇰 粤语智能导师 (DeepSeek V3)")

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "哈喽！我係兰啊！又有咩想学啊？👋"})

if "vocab" not in st.session_state:
    st.session_state.vocab = [] # 初始化一个空列表来存单词

# 渲染历史
    # 定义两个头像
avatar = {"user": "🧑‍💻", "assistant": "👩‍🏫"}
for message in st.session_state.messages:
    # 从字典里根据 role 取出对应的头像
    with st.chat_message(message["role"], avatar=avatar[message["role"]]):
        st.markdown(message["content"])

    # ... 在 if prompt := st.chat_input... 的 上面 插入 ...

# 1. 创建两列，左边放麦克风，右边是提示文字
c1, c2 = st.columns([1, 5])
with c1:
    # 这是一个特殊的组件，录音结束后会返回 audio 数据
    audio_data = mic_recorder(
        start_prompt="🎙️", # 开始录音的图标
        stop_prompt="⏹️",  # 停止录音的图标
        key='recorder',    # 唯一ID
        format="wav"       # 必须用 wav 格式，方便识别
    )

user_voice_input = None

# 2. 如果检测到有录音数据，就开始识别
if audio_data:
    # 关键修改：把 lang_code 传进去
    text = recognize_audio(audio_data['bytes'], target_lang=lang_code)
    
    # 只有当识别出有效内容时，才赋值
    if text and text != "（没听清，请再说一遍）":
        user_voice_input = text

# 处理输入
# 逻辑：优先处理语音输入，如果没有语音，再看打字输入框
final_input = None

if user_voice_input:
    final_input = user_voice_input
elif prompt := st.chat_input("输入你想说的话..."):
    final_input = prompt

# 如果最终有输入内容 (无论是说的还是写的)
if final_input:
    # 1. 显示用户输入
    # 注意：这里把 prompt 换成了 final_input
    st.session_state.messages.append({"role": "user", "content": final_input})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(final_input)
   
    # 2. 生成回复
    with st.chat_message("assistant", avatar="👩‍🏫"):
        message_placeholder = st.empty()

    
        if not client:
                st.error("🔑 请输入 API Key 或联系作者配置后台 Key")
        else:
            try:
                with st.spinner("兰正在思考..."):
                    # 1. 准备消息历史
                    messages_for_ai = [{"role": "system", "content": SYSTEM_PROMPT}]
                    for msg in st.session_state.messages[-6:]:
                        messages_for_ai.append({"role": msg["role"], "content": msg["content"]})
                        
                    # 2. 发起请求 (修复了括号问题)
                    response = client.chat.completions.create(
                        model=model_name,  # 使用侧边栏决定的模型名字
                        messages=messages_for_ai,
                        temperature=1.0,   # 1.0 是一个对 DeepSeek 和 GPT 都比较平衡的数值
                        stream=False
                    )
                        
                    # 3. 获取回复内容
                    full_text = response.choices[0].message.content
                    
                    # 4. 显示和保存
                    message_placeholder.markdown(full_text)
                    st.session_state.messages.append({"role": "assistant", "content": full_text})
                        
                    # 5. 生成语音 (逻辑不变)
                    spoken_text = full_text.split("---")[0]
                    clean_spoken_text = clean_text_for_speech(spoken_text)
                        
                    if clean_spoken_text.strip():
                        with st.spinner("正在生成语音..."):
                            play_audio(clean_spoken_text)
                
            except Exception as e:
                st.error(f"出错了: {e}")
