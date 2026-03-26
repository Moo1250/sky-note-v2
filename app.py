import streamlit as st
import cv2
import os
import requests
import pandas as pd
from deepface import DeepFace
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime, timedelta
import tempfile
import qrcode
from io import BytesIO
import random
import math
import glob

# ==========================================
# 1. إعدادات التصميم والواجهة الاحترافية
# ==========================================
st.set_page_config(page_title="SkyNote - Smart Attendance", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .stApp { background-color: #0e1117; color: #ffffff; } 
    p, label, .stMarkdown { color: #e0e0e0 !important; font-size: 16px; }
    
    div[data-testid="stButton"] > button {
        background-color: #0ea5e9 !important; 
        color: #ffffff !important; 
        border-radius: 8px !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: 0.3s;
    }
    div[data-testid="stButton"] > button:hover {
        background-color: #0284c7 !important;
        transform: translateY(-2px);
    }
    
    h1, h2, h3, h4, h5 { color: #38bdf8 !important; text-align: center; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. إدارة اللغات (عربي / English)
# ==========================================
if 'lang' not in st.session_state: st.session_state['lang'] = 'AR'

col_lang1, col_lang2 = st.columns([8, 2])
with col_lang2:
    if st.button("🌐 عربي / English"):
        st.session_state['lang'] = 'EN' if st.session_state['lang'] == 'AR' else 'AR'
        st.rerun()

def t(en, ar): return en if st.session_state['lang'] == 'EN' else ar

# ==========================================
# 3. محرك قاعدة البيانات Firebase
# ==========================================
DB_URL = 'https://skynote10-c7743-default-rtdb.firebaseio.com'

def get_db(path):
    try: return requests.get(f"{DB_URL}{path}.json").json()
    except: return None

def set_db(path, data):
    try: requests.put(f"{DB_URL}{path}.json", json=data)
    except: pass

def push_db(path, data):
    try: requests.post(f"{DB_URL}{path}.json", json=data)
    except: pass

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # نصف قطر الأرض بالمتر
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R * c)

if 'page' not in st.session_state: st.session_state['page'] = 'Home'
if 'doc_id' not in st.session_state: st.session_state['doc_id'] = None

# ==========================================
# 4. مسار الطالب (عبر الباركود)
# ==========================================
query_params = st.query_params
student_session_doc = query_params.get("session", None)

if student_session_doc:
    doc_id = student_session_doc
    active = get_db(f'/active_sessions/{doc_id}')
    
    st.markdown(f"<h1>⚡ {t('SkyNote Student Portal', 'بوابة الطالب')}</h1>", unsafe_allow_html=True)
    
    if not active or active['mode'] == "Standby (Closed)":
        st.info(t("⏳ System is closed. Please wait for the Doctor.", "⏳ النظام مغلق. يرجى انتظار الدكتور."))
    else:
        safe_cls = active['class_name']
        display_name = active['display_name']
        current_mode = active['mode']
        expires_at_str = active.get('expires_at', "2030-01-01 00:00:00")
        doc_lat = active.get('doc_lat', 0.0)
        doc_lon = active.get('doc_lon', 0.0)
        allowed_radius = active.get('allowed_radius', 100) 
        
        st.markdown(f"### 🏛️ {t('Class', 'الكلاس')}: {display_name}")
        st.write("---")

        is_expired = datetime.now() > datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")

        if current_mode == "Registration (New Students)":
            st.markdown(f"#### 📝 {t('Cloud Registration', 'التسجيل السحابي')}")
            sid = st.text_input(t("Enter Student ID", "أدخل رقمك الجامعي"))
            face = st.camera_input(t("Frame your face", "التقط صورة واضحة لوجهك"))
            
            if st.button(t("Register Identity", "تسجيل البيانات")):
                if not sid or face is None:
                    st.warning(t("⚠️ Please enter ID and capture photo first.", "⚠️ يرجى إدخال الرقم والتقاط الصورة أولاً."))
                else:
                    with st.spinner(t("Validating face...", "جاري التحقق من الوجه...")):
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            tmp.write(face.getvalue()); tmp_p = tmp.name
                        try:
                            # نبقيها صارمة في التسجيل لضمان جودة الصورة المرجعية
                            DeepFace.extract_faces(img_path=tmp_p, enforce_detection=True)
                            os.remove(tmp_p)
                            folder = f"registered_faces/{doc_id}_{safe_cls}"
                            os.makedirs(folder, exist_ok=True)
                            with open(f"{folder}/{sid}.jpg", "wb") as f: f.write(face.getbuffer())
                            st.success(t("✅ Registered Successfully!", "✅ تم التسجيل بنجاح!"))
                        except ValueError:
                            os.remove(tmp_p)
                            st.error(t("❌ Face not clear! Please capture a clear photo.", "❌ الوجه غير واضح! يرجى تصوير وجهك بوضوح لتسجيلك."))

        elif current_mode == "Attendance (Live)":
            if is_expired:
                st.error(t("⏳ Time is up! Session closed.", "⏳ انتهى وقت التحضير! أُغلقت الجلسة."))
            else:
                st.markdown(f"#### 🎓 {t('Mark Attendance', 'تسجيل الحضور')}")
                sid = st.text_input(t("Your Registered ID", "رقمك الجامعي المسجل"))
                
                c1, c2 = st.columns(2)
                with c1: 
                    student_img = st.camera_input(t("Live Selfie Verification", "التحقق من الوجه"))
                with c2:
                    st.markdown(f"**📍 {t('Confirm Your Location', 'تأكيد موقعك')}**")
                    c_gps_btn, c_empty = st.columns([1, 4])
                    with c_gps_btn:
                        loc = streamlit_geolocation()
                    if loc['latitude']: st.success(t("GPS Lock 📍", "تم تحديد الموقع 📍"))
                
                if st.button(t("Confirm Attendance", "تأكيد الحضور")):
                    if not sid or student_img is None or not loc['latitude']:
                        st.warning(t("⚠️ Complete all steps (ID, Photo, GPS).", "⚠️ يرجى إكمال كل الخطوات (الرقم، الصورة، الموقع)."))
                    else:
                        reg_p = f"registered_faces/{doc_id}_{safe_cls}/{sid}.jpg"
                        if not os.path.exists(reg_p):
                            st.error(t("❌ ID Not Found in this class!", "❌ رقمك غير مسجل في هذا الكلاس!"))
                        else:
                            with st.spinner(t("Analyzing with Facenet AI...", "جاري التحليل المعمق...")):
                                student_distance = calculate_distance(doc_lat, doc_lon, loc['latitude'], loc['longitude'])
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                    tmp.write(student_img.getvalue()); tmp_p = tmp.name
                                try:
                                    # الحل الجذري: استخدام نموذج Facenet الموثوق وإلغاء الاكتشاف الإجباري في التحضير
                                    res = DeepFace.verify(img1_path=tmp_p, img2_path=reg_p, model_name="Facenet", enforce_detection=False)
                                    os.remove(tmp_p)
                                    
                                    if not res['verified']:
                                        st.error(t("❌ Face Mismatch! (Check your photo)", "❌ الوجه لا يتطابق مع الرقم الجامعي!"))
                                    else:
                                        if student_distance <= allowed_radius:
                                            st.balloons(); st.success(t("✅ Attendance Marked.", "✅ تم تسجيل حضورك بنجاح."))
                                            push_db(f"/attendance/{doc_id}_{safe_cls}", {
                                                "id": sid, "date": datetime.now().strftime("%Y-%m-%d"),
                                                "time": datetime.now().strftime("%I:%M %p"),
                                                "distance": f"{student_distance} m",
                                                "status": "✅ Present (Valid)", "method": "Self-Scan"
                                            })
                                        else:
                                            st.error(f"❌ {t('Out of bounds!', 'أنت بعيد عن القاعة!')} {student_distance}m")
                                            push_db(f"/attendance/{doc_id}_{safe_cls}", {
                                                "id": sid, "date": datetime.now().strftime("%Y-%m-%d"),
                                                "time": datetime.now().strftime("%I:%M %p"),
                                                "distance": f"{student_distance} m",
                                                "status": "❌ Rejected (Wrong Location)", "method": "Self-Scan"
                                            })
                                except Exception:
                                    os.remove(tmp_p)
                                    st.error(t("❌ Image Error. Capture again.", "❌ حدث خطأ في معالجة الصورة، التقطها بوضوح وحاول مرة أخرى."))

# ==========================================
# 5. مسار الدكتور ولوحة التحكم
# ==========================================
else:
    if not st.session_state['doc_id']:
        if st.session_state['page'] == 'Home':
            st.markdown(f"<h1>⚡ {t('SkyNote Cloud Architecture', 'نظام سكاي نوت السحابي')}</h1>", unsafe_allow_html=True)
            st.write("---")
            st.markdown(f"<h3>{t('Select Your Role', 'اختر صفتك للبدء')}</h3>", unsafe_allow_html=True)
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135755.png", width=140)
                if st.button(t("👨‍🎓 Student Portal", "👨‍🎓 بوابة الطالب")):
                    st.session_state['page'] = 'Student_Info'; st.rerun()
            with c2:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135810.png", width=140)
                if st.button(t("👨‍🏫 Professor Portal", "👨‍🏫 بوابة الدكتور")):
                    st.session_state['page'] = 'Doctor_Auth'; st.rerun()

        elif st.session_state['page'] == 'Doctor_Auth':
            if st.button(t("🔙 Back to Home", "🔙 العودة للرئيسية")): st.session_state['page'] = 'Home'; st.rerun()
            st.markdown(f"<h2>👨‍🏫 {t('Professor Portal', 'بوابة الدكتور')}</h2>", unsafe_allow_html=True)
            tab_login, tab_reg = st.tabs([t("🔒 Secure Login", "🔒 تسجيل الدخول"), t("📝 Setup Account", "📝 إنشاء حساب")])
            with tab_login:
                log_email = st.text_input(t("Email Address", "البريد الإلكتروني"), key="log_e").lower().strip()
                log_pwd = st.text_input(t("Password", "كلمة المرور"), type="password", key="log_p")
                if st.button(t("Login", "دخول")):
                    doc_safe_id = log_email.replace(".", "_").replace("@", "_")
                    db_pwd = get_db(f'/doctors/{doc_safe_id}/password')
                    if db_pwd and str(db_pwd) == str(log_pwd):
                        st.session_state['doc_id'] = doc_safe_id; st.rerun()
                    else: st.error(t("❌ Invalid Credentials", "❌ بيانات الدخول خاطئة"))
            with tab_reg:
                reg_email = st.text_input(t("Email", "البريد الإلكتروني الجديد"), key="reg_e").lower().strip()
                reg_pwd = st.text_input(t("Password", "كلمة المرور"), type="password", key="reg_p")
                reg_name = st.text_input(t("Dr. Name", "اسم الدكتور"), key="reg_n")
                if st.button(t("Create Account", "إنشاء الحساب")):
                    if reg_email and reg_pwd and reg_name:
                        doc_safe_id = reg_email.replace(".", "_").replace("@", "_")
                        set_db(f'/doctors/{doc_safe_id}', {"password": reg_pwd, "name": reg_name})
                        st.success(t("✅ Account Created! Login now.", "✅ تم إنشاء الحساب! سجل دخولك الآن."))
    
    else:
        doc_id = st.session_state['doc_id']
        doc_info = get_db(f'/doctors/{doc_id}')
        doc_name = doc_info.get('name', '') if doc_info else 'Professor'
        
        c_title, c_log = st.columns([8,2])
        with c_title: st.title(f"👨‍🏫 {t('Dr.', 'د.')} {doc_name}'s {t('Control', 'لوحة التحكم')}")
        with c_log:
            if st.button(t("🚪 Logout", "🚪 خروج")):
                st.session_state['doc_id'] = None; st.session_state['page'] = 'Home'; st.rerun()
        
        tabs = st.tabs([t("⚙️ Operations", "⚙️ العمليات"), t("📸 Batch Processing", "📸 تصوير القاعة"), t("📋 Live KPIs", "📋 السجلات")])
        
        with tabs[0]:
            saved_classes = get_db(f'/doctors/{doc_id}/classes') or []
            c1, c2 = st.columns([3, 1])
            with c1: new_c = st.text_input(t("Add Class", "أضف كلاس جديد"))
            with c2:
                st.write(""); st.write("")
                if st.button(t("Save", "حفظ")):
                    if new_c and new_c not in saved_classes:
                        saved_classes.append(new_c)
                        set_db(f'/doctors/{doc_id}/classes', saved_classes); st.rerun()
            
            if saved_classes:
                st.markdown(f"### 📍 {t('Geofencing Setup', 'إعدادات الموقع')}")
                selected_class = st.selectbox(t("Select Course:", "اختر الكلاس:"), saved_classes)
                mode = st.radio(t("Student Action:", "حالة الطلاب:"), ["Standby (Closed)", "Registration (New Students)", "Attendance (Live)"])
                dur = st.slider(t("⏱️ Timer (Minutes)", "⏱️ مدة التحضير"), 1, 60, 5)
                
                doc_loc = streamlit_geolocation()
                
                if st.button(t("🚀 GO LIVE", "🚀 تفعيل الجلسة")):
                    lat_val = doc_loc['latitude'] if doc_loc['latitude'] else 0.0
                    expires_at = (datetime.now() + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M:%S")
                    set_db(f'/active_sessions/{doc_id}', {
                        "class_name": selected_class.replace(" ", "_"), "display_name": selected_class,
                        "mode": mode, "expires_at": expires_at, "doc_lat": lat_val,
                        "doc_lon": doc_loc['longitude'] if doc_loc['longitude'] else 0.0, "allowed_radius": 100
                    })
                    st.success(f"✅ {t('Active until', 'مفعل حتى')} {expires_at}")
                
                # تحديث رابط الباركود ليشير إلى السيرفر الجديد
                smart_url = f"https://sky-note-v2-qmfaubuyvyndbdukcrwwjw.streamlit.app/?session={doc_id}"
                qr = qrcode.make(smart_url)
                buf = BytesIO(); qr.save(buf, format="PNG")
                st.image(buf.getvalue(), width=200, caption=t("Scan this QR", "امسح هذا الباركود"))

        with tabs[1]:
            active = get_db(f'/active_sessions/{doc_id}')
            if active and active['mode'] != "Standby (Closed)":
                safe_cls = active['class_name']
                st.subheader(f"{t('AI Batch Marking:', 'التحضير الذكي لـ:')} {active['display_name']}")
                doc_cam = st.camera_input(t("Capture Classroom", "التقط صورة للقاعة"))
                
                if doc_cam:
                    with st.spinner(t("DeepFace Analyzing...", "جاري التحليل...")):
                        recognized = set()
                        folder = f"registered_faces/{doc_id}_{safe_cls}"
                        os.makedirs(folder, exist_ok=True)
                        
                        # الحل الجذري لمسح الذاكرة القديمة للدكتور
                        for pkl_file in glob.glob(os.path.join(folder, "*.pkl")):
                            try: os.remove(pkl_file)
                            except: pass
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            tmp.write(doc_cam.getvalue()); tmp_p = tmp.name
                        try:
                            res = DeepFace.find(img_path=tmp_p, db_path=folder, model_name="Facenet", enforce_detection=False)
                            for r in res:
                                if not r.empty:
                                    sid = os.path.basename(r.iloc[0]['identity']).split('.')[0]
                                    recognized.add(sid)
                        except: pass
                        os.remove(tmp_p)
                        
                        for sid in recognized:
                            push_db(f'/attendance/{doc_id}_{safe_cls}', {
                                "id": sid, "date": datetime.now().strftime("%Y-%m-%d"),
                                "time": datetime.now().strftime("%I:%M %p"), "status": "✅ Present (Doc)", "method": "Batch"
                            })
                        if recognized: st.success(f"Found IDs: {list(recognized)}")
                        else: st.warning("No faces matched.")

        with tabs[2]:
            active = get_db(f'/active_sessions/{doc_id}')
            if active:
                safe_cls = active['class_name']
                data = get_db(f"/attendance/{doc_id}_{safe_cls}")
                if data:
                    df = pd.DataFrame.from_dict(data, orient='index')
                    st.dataframe(df, use_container_width=True)
                    st.download_button("Export CSV", df.to_csv().encode('utf-8'), "Report.csv")
