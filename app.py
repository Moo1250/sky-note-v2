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
# 1. إعدادات التصميم (Dark Glassmorphism & Enhanced UI)
# ==========================================
st.set_page_config(page_title="SkyNote SaaS", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* 1. صورة خلفية لقاعة جامعية مع تظليل داكن (Dark Overlay) لبروز المحتوى */
    .stApp { 
        background: linear-gradient(rgba(10, 15, 30, 0.75), rgba(10, 15, 30, 0.85)), 
                    url("https://images.unsplash.com/photo-1562774053-701939374585?q=80&w=2000&auto=format&fit=crop");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    
    /* 2. التأثير الزجاجي (Glassmorphism) مع وضوح عالي للقراءة */
    .main .block-container {
        background-color: rgba(15, 23, 42, 0.65); /* شفافية مدروسة */
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        margin-top: 2rem;
        margin-bottom: 2rem;
    }

    /* 3. توضيح النصوص وتناسق الألوان مع إضافة ظلال للقراءة المريحة */
    p, label, .stMarkdown, .stText, li { 
        color: #f1f5f9 !important; 
        font-size: 16.5px; 
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5); 
    }
    h1, h2, h3, h4, h5 { 
        color: #38bdf8 !important; 
        text-align: center; 
        font-weight: 800; 
        text-shadow: 2px 2px 4px rgba(0,0,0,0.8); 
    }
    
    /* 4. تصميم الأزرار الحديث (تدرج لوني 3D متناسق مع النمط الزجاجي) */
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%) !important; 
        color: #ffffff !important; 
        border-radius: 12px !important;
        font-weight: 900 !important;
        font-size: 16px !important;
        height: 3.5em !important;
        width: 100% !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);
        transition: all 0.3s ease;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(14, 165, 233, 0.6);
    }
    
    /* 5. تجميل الجداول وخانات الإدخال لتتناسب مع الخلفية المظللة */
    [data-testid="stDataFrame"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. نظام اللغات
# ==========================================
if 'lang' not in st.session_state: st.session_state['lang'] = 'EN'

col_lang1, col_lang2 = st.columns([8, 2])
with col_lang2:
    if st.button("🌐 عربي / English"):
        st.session_state['lang'] = 'AR' if st.session_state['lang'] == 'EN' else 'EN'
        st.rerun()

def t(en, ar): return en if st.session_state['lang'] == 'EN' else ar

# ==========================================
# 3. محرك قاعدة البيانات ومعادلة المسافة
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
    R = 6371000  
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R * c)

if 'page' not in st.session_state: st.session_state['page'] = 'Home'
if 'doc_id' not in st.session_state: st.session_state['doc_id'] = None

# ==========================================
# التوجيه الذكي (نظام الطالب)
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
                            DeepFace.extract_faces(img_path=tmp_p, enforce_detection=True)
                            os.remove(tmp_p)
                            folder = f"registered_faces/{doc_id}_{safe_cls}"
                            os.makedirs(folder, exist_ok=True)
                            with open(f"{folder}/{sid}.jpg", "wb") as f: f.write(face.getbuffer())
                            st.success(t("✅ Registered Successfully!", "✅ تم التسجيل بنجاح!"))
                        except ValueError:
                            os.remove(tmp_p)
                            st.error(t("❌ No face detected! Please capture a clear photo of your face.", "❌ لم يتم العثور على وجه! يرجى تصوير وجهك بوضوح لتسجيلك."))

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
                            with st.spinner(t("Analyzing with SFace AI...", "جاري التحليل السريع والمطابقة...")):
                                student_distance = calculate_distance(doc_lat, doc_lon, loc['latitude'], loc['longitude'])
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                    tmp.write(student_img.getvalue()); tmp_p = tmp.name
                                try:
                                    res = DeepFace.verify(img1_path=tmp_p, img2_path=reg_p, model_name="SFace", enforce_detection=False)
                                    if os.path.exists(tmp_p): os.remove(tmp_p)
                                    
                                    if not res['verified']:
                                        st.error(t("❌ Face Mismatch! (Or blurry photo)", "❌ الوجه لا يتطابق مع الرقم الجامعي، أو أنك تحاول تمرير صورة فارغة!"))
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
                                except Exception as e:
                                    if os.path.exists(tmp_p): os.remove(tmp_p)
                                    st.error(f"❌ رسالة العطل من السيرفر (الطالب): {str(e)}")

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

        elif st.session_state['page'] == 'Student_Info':
            if st.button(t("🔙 Back to Home", "🔙 العودة للرئيسية")): st.session_state['page'] = 'Home'; st.rerun()
            st.markdown(f"<h2>📱 {t('Accessing Your Class', 'كيف تدخل كلاسك')}</h2>", unsafe_allow_html=True)
            st.info(t("Scan the Magic QR Code displayed by your Professor.", "لتسجيل حضورك، امسح الباركود الذي يعرضه الدكتور ليتم توجيهك."))

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
                        st.success(t("✅ Account Created! You can login now.", "✅ تم إنشاء الحساب! سجل دخولك الآن."))
    
    else:
        doc_id = st.session_state['doc_id']
        doc_info = get_db(f'/doctors/{doc_id}')
        doc_name = doc_info.get('name', '') if doc_info else 'Professor'
        
        c_title, c_log = st.columns([8,2])
        with c_title: st.title(f"👨‍🏫 {t('Dr.', 'د.')} {doc_name}'s {t('Command Center', 'لوحة التحكم')}")
        with c_log:
            if st.button(t("🚪 Logout", "🚪 خروج")):
                st.session_state['doc_id'] = None; st.session_state['page'] = 'Home'; st.rerun()
        
        tabs = st.tabs([
            t("⚙️ Operations", "⚙️ العمليات"), 
            t("📸 Batch Processing", "📸 تصوير القاعة"), 
            t("📋 Live KPIs", "📋 السجلات والغياب"),
            t("👥 Registered", "👥 المسجلين")
        ])
        
        with tabs[0]:
            saved_classes = get_db(f'/doctors/{doc_id}/classes') or []
            c1, c2 = st.columns([3, 1])
            with c1: new_c = st.text_input(t("Add Class (e.g., ostim Univ - AI)", "أضف كلاس جديد"))
            with c2:
                st.write(""); st.write("")
                if st.button(t("Save Course", "حفظ الكلاس")):
                    if new_c and new_c not in saved_classes:
                        saved_classes.append(new_c)
                        set_db(f'/doctors/{doc_id}/classes', saved_classes)
                        st.rerun()
            
            st.write("---")
            if saved_classes:
                st.markdown(f"### 📍 {t('Geofencing Setup', 'إعدادات الموقع (السياج الجغرافي)')}")
                selected_class = st.selectbox(t("Select Course:", "اختر الكلاس:"), saved_classes)
                mode = st.radio(t("Student Action:", "حالة الطلاب:"), ["Standby (Closed)", "Registration (New Students)", "Attendance (Live)"])
                dur = st.slider(t("⏱️ Timer Window (Minutes)", "⏱️ مدة فتح التحضير (بالدقائق)"), 1, 60, 5)
                
                c_geo1, c_geo2 = st.columns(2)
                with c_geo1:
                    allowed_rad = st.number_input(t("Allowed Distance (Meters)", "المسافة المسموحة (بالأمتار)"), min_value=10, max_value=5000, value=100)
                with c_geo2:
                    st.markdown(f"**📍 {t('Capture Classroom Location', 'تحديد موقع القاعة الحالي')}**")
                    c_gps_doc, c_empty_doc = st.columns([1, 4])
                    with c_gps_doc:
                        doc_loc = streamlit_geolocation()
                    if doc_loc['latitude']:
                         st.success(t("Location captured!", "تم تحديد الموقع بنجاح!"))
                
                if st.button(t("🚀 GO LIVE", "🚀 تفعيل الجلسة للطلاب")):
                    lat_val = doc_loc['latitude'] if doc_loc and doc_loc.get('latitude') else 0.0
                    lon_val = doc_loc['longitude'] if doc_loc and doc_loc.get('longitude') else 0.0
                    
                    if mode == "Attendance (Live)" and lat_val == 0.0:
                        st.warning(t("Please capture location first!", "يرجى تحديد موقع القاعة قبل التفعيل!"))
                    else:
                        expires_at = (datetime.now() + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M:%S")
                        set_db(f'/active_sessions/{doc_id}', {
                            "class_name": selected_class.replace(" ", "_").replace("/", "_"),
                            "display_name": selected_class,
                            "mode": mode, "expires_at": expires_at,
                            "doc_lat": lat_val,
                            "doc_lon": lon_val,
                            "allowed_radius": allowed_rad
                        })
                        st.success(f"✅ {t('Session Active until', 'الجلسة مفعلة حتى')} {expires_at}")
                
                st.write("---")
                st.markdown(f"### 📱 {t('Magic QR Code', 'باركود التوجيه الذكي')}")
                smart_url = f"https://sky-note-v2-qmfaubuyvyndbdukcrwwjw.streamlit.app/?session={doc_id}"
                qr = qrcode.make(smart_url)
                buf = BytesIO(); qr.save(buf, format="PNG")
                st.image(buf.getvalue(), width=200)

        with tabs[1]:
            active = get_db(f'/active_sessions/{doc_id}')
            if active and active['mode'] != "Standby (Closed)":
                safe_cls = active['class_name']
                st.subheader(f"{t('AI Batch Marking:', 'التحضير الذكي لـ:')} {active['display_name']}")
                
                c_cam, c_up = st.columns(2)
                
                with c_cam:
                    st.markdown(f"**📷 {t('Live Camera (Auto-Process)', 'كاميرا التحضير (تحليل فوري وتلقائي)')}**")
                    doc_cam = st.camera_input(t("Take photo", "التقط الصورة"))
                    
                    if doc_cam is not None:
                        with st.spinner(t("AI is processing the photo instantly...", "الذكاء الاصطناعي يحلل الصورة فوراً...")):
                            recognized = set()
                            folder = f"registered_faces/{doc_id}_{safe_cls}"
                            os.makedirs(folder, exist_ok=True)
                            
                            for pkl_file in glob.glob(os.path.join(folder, "*.pkl")):
                                try: os.remove(pkl_file)
                                except: pass
                            
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                tmp.write(doc_cam.getvalue()); tmp_p = tmp.name
                            try:
                                res = DeepFace.find(img_path=tmp_p, db_path=folder, model_name="SFace", enforce_detection=False)
                                for r in res:
                                    if not r.empty:
                                        sid = os.path.basename(r.iloc[0]['identity']).split('.')[0]
                                        recognized.add(sid)
                            except Exception as e: 
                                st.error(f"❌ رسالة العطل من السيرفر (كاميرا الدكتور): {str(e)}")
                            if os.path.exists(tmp_p): os.remove(tmp_p)
                            
                            for sid in recognized:
                                push_db(f'/attendance/{doc_id}_{safe_cls}', {
                                    "id": sid, "date": datetime.now().strftime("%Y-%m-%d"),
                                    "time": datetime.now().strftime("%I:%M %p"), 
                                    "distance": "0 m (Doctor)", "status": "✅ Present", "method": "Doctor Camera"
                                })
                            if recognized:
                                st.success(f"{t('Successfully processed IDs:', 'تم تحضير الأرقام بنجاح:')} {list(recognized)}")
                            else:
                                st.warning(t("No matching faces found in this photo.", "لم يتم التعرف على أي وجه مسجل في هذه الصورة."))

                with c_up:
                    st.markdown(f"**📂 {t('Upload Photos', 'رفع صور من الجهاز')}**")
                    imgs = st.file_uploader(t("Upload and Process", "ارفع الصور ثم اضغط الزر بالأسفل"), accept_multiple_files=True)
                    
                    if st.button(t("Process Uploaded Photos", "تحليل الصور المرفوعة")):
                        if not imgs:
                            st.warning(t("Please upload a photo first.", "يرجى رفع صور أولاً."))
                        else:
                            with st.spinner(t("AI is extracting faces...", "الذكاء الاصطناعي يحلل الوجوه...")):
                                recognized = set()
                                folder = f"registered_faces/{doc_id}_{safe_cls}"
                                os.makedirs(folder, exist_ok=True)
                                
                                for pkl_file in glob.glob(os.path.join(folder, "*.pkl")):
                                    try: os.remove(pkl_file)
                                    except: pass
                                
                                for img in imgs[:10]:
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                        tmp.write(img.getvalue()); tmp_p = tmp.name
                                    try:
                                        res = DeepFace.find(img_path=tmp_p, db_path=folder, model_name="SFace", enforce_detection=False)
                                        for r in res:
                                            if not r.empty:
                                                sid = os.path.basename(r.iloc[0]['identity']).split('.')[0]
                                                recognized.add(sid)
                                    except Exception as e:
                                        st.error(f"❌ رسالة العطل من السيرفر (رفع صور الدكتور): {str(e)}")
                                    if os.path.exists(tmp_p): os.remove(tmp_p)
                                
                                for sid in recognized:
                                    push_db(f'/attendance/{doc_id}_{safe_cls}', {
                                        "id": sid, "date": datetime.now().strftime("%Y-%m-%d"),
                                        "time": datetime.now().strftime("%I:%M %p"), 
                                        "distance": "0 m (Doctor)", "status": "✅ Present", "method": "Batch Upload"
                                    })
                                if recognized:
                                    st.success(f"{t('Successfully processed IDs:', 'تم تحضير الأرقام بنجاح:')} {list(recognized)}")
                                else:
                                    st.warning(t("No matching faces found in the uploaded photos.", "لم يتم التعرف على أي وجه مسجل في الصور المرفوعة."))
            else: st.warning(t("Activate a session in Operations first.", "قم بتفعيل كلاس من العمليات أولاً."))
            
        with tabs[2]:
            active = get_db(f'/active_sessions/{doc_id}')
            if active:
                safe_cls = active['class_name']
                data = get_db(f"/attendance/{doc_id}_{safe_cls}")
                if data:
                    df = pd.DataFrame.from_dict(data, orient='index')
                    cols_to_show = ["date", "time", "id", "status", "distance", "method"]
                    df = df[[c for c in cols_to_show if c in df.columns]]
                    
                    st.markdown(f"### 📅 {t('Filter by Date', 'تصفية السجلات حسب اليوم')}")
                    unique_dates = df['date'].unique().tolist()
                    unique_dates.sort(reverse=True)
                    
                    selected_date = st.selectbox(t("Select Date:", "اختر اليوم لعرض الغياب والحضور:"), ["All (عرض الكل)"] + unique_dates)
                    
                    if selected_date != "All (عرض الكل)":
                        df_filtered = df[df['date'] == selected_date]
                    else:
                        df_filtered = df
                        
                    st.dataframe(df_filtered, use_container_width=True)
                    csv_filename = f"Report_{selected_date.replace('/', '-')}.csv" if selected_date != "All (عرض الكل)" else "Full_Report.csv"
                    st.download_button(t(f"Export CSV", f"تحميل سجل ({selected_date}) كملف إكسيل"), data=df_filtered.to_csv().encode('utf-8'), file_name=csv_filename)
                else: 
                    st.info(t("Database is empty.", "لا يوجد سجلات حتى الآن."))

        with tabs[3]:
            active = get_db(f'/active_sessions/{doc_id}')
            if active:
                safe_cls = active['class_name']
                folder = f"registered_faces/{doc_id}_{safe_cls}"
                st.markdown(f"### 👥 {t('Registered Students Overview', 'إحصائيات الطلاب المسجلين (البصمة الوجهية)')}")
                
                if os.path.exists(folder):
                    registered_files = glob.glob(os.path.join(folder, "*.jpg"))
                    sids = [os.path.basename(f).replace('.jpg', '') for f in registered_files]
                    
                    st.success(f"**📈 {t('Total Registered', 'إجمالي المسجلين في هذا الكلاس')}: {len(sids)} {t('Students', 'طالب / طالبة')}**")
                    
                    if sids:
                        df_sids = pd.DataFrame(sids, columns=[t("Student ID", "الرقم الجامعي المسجل")])
                        df_sids.index += 1
                        st.dataframe(df_sids, use_container_width=True)
                else:
                    st.warning(t("No students have registered their faces for this class yet.", "لا يوجد أي طلاب مسجلين في هذا الكلاس حتى الآن. يرجى تفعيل وضع Registration للطلاب."))
            else:
                st.info(t("Activate a session in Operations first to see registered students.", "قم بتفعيل كلاس من العمليات أولاً لعرض إحصائيات الطلاب."))
