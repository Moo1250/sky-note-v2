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

# ==========================================
# 1. إعدادات التصميم (صافية وواضحة)
# ==========================================
st.set_page_config(page_title="SkyNote SaaS", page_icon="⚡", layout="wide")

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
    div[data-testid="stText"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. نظام اللغات
# ==========================================
if 'lang' not in st.session_state: st.session_state['lang'] = 'EN'

col_lang1, col_lang2 = st.columns([8, 2])
with col_lang2:
    if st.button("🌐 عربي / English", key="lang_btn"):
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
            sid = st.text_input(t("Enter Student ID", "أدخل رقمك الجامعي"), key="reg_id")
            # مفتاح الذاكرة لحماية الكاميرا
            face = st.camera_input(t("Frame your face", "التقط صورة واضحة لوجهك"), key="reg_cam")
            
            if st.button(t("Register Identity", "تسجيل البيانات"), key="reg_btn"):
                if not sid or face is None:
                    st.warning(t("⚠️ Please enter ID and capture photo first.", "⚠️ يرجى إدخال الرقم والتقاط الصورة أولاً."))
                else:
                    with st.spinner(t("Validating face...", "جاري التحقق من الوجه...")):
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            tmp.write(face.getvalue()); tmp_p = tmp.name
                        try:
                            # 🛡️ وضع حماية الطالب (صارم)
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
                sid = st.text_input(t("Your Registered ID", "رقمك الجامعي المسجل"), key="att_id")
                
                c1, c2 = st.columns(2)
                with c1: 
                    # مفتاح الذاكرة لحماية الكاميرا
                    student_img = st.camera_input(t("Live Selfie Verification", "التحقق من الوجه"), key="att_cam")
                with c2:
                    st.markdown(f"**📍 {t('Confirm Your Location', 'تأكيد موقعك')}**")
                    c_gps_btn, c_empty = st.columns([1, 4])
                    with c_gps_btn:
                        loc = streamlit_geolocation()
                    if loc['latitude']: st.success(t("GPS Lock 📍", "تم تحديد الموقع 📍"))
                
                if st.button(t("Confirm Attendance", "تأكيد الحضور"), key="att_btn"):
                    if not sid or student_img is None or not loc['latitude']:
                        st.warning(t("⚠️ Complete all steps (ID, Photo, GPS).", "⚠️ يرجى إكمال كل الخطوات (الرقم، الصورة، الموقع)."))
                    else:
                        reg_p = f"registered_faces/{doc_id}_{safe_cls}/{sid}.jpg"
                        if not os.path.exists(reg_p):
                            st.error(t("❌ ID Not Found in this class!", "❌ رقمك غير مسجل في هذا الكلاس!"))
                        else:
                            with st.spinner(t("Analyzing...", "جاري التحليل...")):
                                student_distance = calculate_distance(doc_lat, doc_lon, loc['latitude'], loc['longitude'])
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                    tmp.write(student_img.getvalue()); tmp_p = tmp.name
                                try:
                                    # 🛡️ وضع حماية الطالب (صارم)
                                    res = DeepFace.verify(img1_path=tmp_p, img2_path=reg_p, enforce_detection=True)
                                    os.remove(tmp_p)
                                    if not res['verified']:
                                        st.error(t("❌ Face Mismatch Alert!", "❌ الوجه لا يتطابق مع الرقم الجامعي!"))
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
                                except ValueError:
                                    os.remove(tmp_p)
                                    st.error(t("❌ No face detected in the picture! Stop trying to cheat.", "❌ لم يتم التعرف على وجه في الصورة! يرجى تصوير وجهك بوضوح."))

else:
    # -----------------------------------------------------
    # مسار الزوار والدكاترة 
    # -----------------------------------------------------
    if not st.session_state['doc_id']:
        if st.session_state['page'] == 'Home':
            st.markdown(f"<h1>⚡ {t('SkyNote Cloud Architecture', 'نظام سكاي نوت السحابي')}</h1>", unsafe_allow_html=True)
            st.write("---")
            st.markdown(f"<h3>{t('Select Your Role', 'اختر صفتك للبدء')}</h3>", unsafe_allow_html=True)
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135755.png", width=140)
                if st.button(t("👨‍🎓 Student Portal", "👨‍🎓 بوابة الطالب"), key="home_stu_btn"):
                    st.session_state['page'] = 'Student_Info'; st.rerun()
            with c2:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135810.png", width=140)
                if st.button(t("👨‍🏫 Professor Portal", "👨‍🏫 بوابة الدكتور"), key="home_doc_btn"):
                    st.session_state['page'] = 'Doctor_Auth'; st.rerun()

        elif st.session_state['page'] == 'Student_Info':
            if st.button(t("🔙 Back to Home", "🔙 العودة للرئيسية"), key="back_btn_stu"): st.session_state['page'] = 'Home'; st.rerun()
            st.markdown(f"<h2>📱 {t('Accessing Your Class', 'كيف تدخل كلاسك')}</h2>", unsafe_allow_html=True)
            st.info(t("Scan the Magic QR Code displayed by your Professor.", "لتسجيل حضورك، امسح الباركود الذي يعرضه الدكتور ليتم توجيهك."))

        elif st.session_state['page'] == 'Doctor_Auth':
            if st.button(t("🔙 Back to Home", "🔙 العودة للرئيسية"), key="back_btn_doc"): st.session_state['page'] = 'Home'; st.rerun()
            st.markdown(f"<h2>👨‍🏫 {t('Professor Portal', 'بوابة الدكتور')}</h2>", unsafe_allow_html=True)
            tab_login, tab_reg = st.tabs([t("🔒 Secure Login", "🔒 تسجيل الدخول"), t("📝 Setup Account", "📝 إنشاء حساب")])
            with tab_login:
                log_email = st.text_input(t("Email Address", "البريد الإلكتروني"), key="log_e").lower().strip()
                log_pwd = st.text_input(t("Password", "كلمة المرور"), type="password", key="log_p")
                if st.button(t("Login", "دخول"), key="login_btn"):
                    doc_safe_id = log_email.replace(".", "_").replace("@", "_")
                    db_pwd = get_db(f'/doctors/{doc_safe_id}/password')
                    if db_pwd and str(db_pwd) == str(log_pwd):
                        st.session_state['doc_id'] = doc_safe_id; st.rerun()
                    else: st.error(t("❌ Invalid Credentials", "❌ بيانات الدخول خاطئة"))
            with tab_reg:
                reg_email = st.text_input(t("Email", "البريد الإلكتروني الجديد"), key="reg_e").lower().strip()
                reg_pwd = st.text_input(t("Password", "كلمة المرور"), type="password", key="reg_p")
                reg_name = st.text_input(t("Dr. Name", "اسم الدكتور"), key="reg_n")
                if st.button(t("Create Account", "إنشاء الحساب"), key="reg_acc_btn"):
                    if reg_email and reg_pwd and reg_name:
                        doc_safe_id = reg_email.replace(".", "_").replace("@", "_")
                        set_db(f'/doctors/{doc_safe_id}', {"password": reg_pwd, "name": reg_name})
                        st.success(t("✅ Account Created! You can login now.", "✅ تم إنشاء الحساب! سجل دخولك الآن."))
    
    # -----------------------------------------------------
    # لوحة تحكم الدكتور 
    # -----------------------------------------------------
    else:
        doc_id = st.session_state['doc_id']
        doc_info = get_db(f'/doctors/{doc_id}')
        doc_name = doc_info.get('name', '') if doc_info else 'Professor'
        
        c_title, c_log = st.columns([8,2])
        with c_title: st.title(f"👨‍🏫 {t('Dr.', 'د.')} {doc_name}'s {t('Command Center', 'لوحة التحكم')}")
        with c_log:
            if st.button(t("🚪 Logout", "🚪 خروج"), key="logout_btn"):
                st.session_state['doc_id'] = None; st.session_state['page'] = 'Home'; st.rerun()
        
        tabs = st.tabs([t("⚙️ Operations", "⚙️ العمليات"), t("📸 Batch Processing", "📸 تصوير القاعة"), t("📋 Live KPIs", "📋 السجلات والغياب")])
        
        with tabs[0]:
            saved_classes = get_db(f'/doctors/{doc_id}/classes') or []
            c1, c2 = st.columns([3, 1])
            with c1: new_c = st.text_input(t("Add Class (e.g., Sana'a Univ - AI)", "أضف كلاس جديد"), key="new_class")
            with c2:
                st.write(""); st.write("")
                if st.button(t("Save Course", "حفظ الكلاس"), key="save_class_btn"):
                    if new_c and new_c not in saved_classes:
                        saved_classes.append(new_c)
                        set_db(f'/doctors/{doc_id}/classes', saved_classes)
                        st.rerun()
            
            st.write("---")
            if saved_classes:
                selected_class = st.selectbox(t("Select Course:", "اختر الكلاس:"), saved_classes, key="sel_class")
                mode = st.radio(t("Student Action:", "حالة الطلاب:"), ["Standby (Closed)", "Registration (New Students)", "Attendance (Live)"], key="mode_rad")
                dur = st.slider(t("⏱️ Timer Window (Minutes)", "⏱️ مدة فتح التحضير (بالدقائق)"), 1, 60, 5, key="dur_slider")
                
                c_geo1, c_geo2 = st.columns(2)
                with c_geo1:
                    allowed_rad = st.number_input(t("Allowed Distance (Meters)", "المسافة المسموحة (بالأمتار)"), min_value=10, max_value=5000, value=100, key="dist_input")
                with c_geo2:
                    st.markdown(f"**📍 {t('Capture Classroom Location', 'تحديد موقع القاعة الحالي')}**")
                    c_gps_doc, c_empty_doc = st.columns([1, 4])
                    with c_gps_doc:
                        doc_loc = streamlit_geolocation()
                    if doc_loc['latitude']:
                         st.success(t("Location captured!", "تم تحديد الموقع بنجاح!"))
                
                if st.button(t("🚀 GO LIVE", "🚀 تفعيل الجلسة للطلاب"), key="golive_btn"):
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
                smart_url = f"https://mow3lid-skynote-attendance.hf.space/?embed=true&session={doc_id}"
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
                    st.markdown(f"**📷 {t('Live Camera', 'كاميرا التحضير المباشر')}**")
                    # مفتاح الذاكرة لحماية كاميرا الدكتور من المسح
                    doc_cam = st.camera_input(t("Take photo", "التقط الصورة"), key="doc_batch_cam")
                    
                with c_up:
                    st.markdown(f"**📂 {t('Upload Photos', 'رفع صور من الجهاز')}**")
                    imgs = st.file_uploader(t("Upload and Process", "ارفع الصور"), accept_multiple_files=True, key="doc_uploads")
                    
                # زر معالجة موحد يعالج الصور المرفوعة والكاميرا في نفس الوقت بدون فقدان البيانات
                if st.button(t("Process via AI Engine", "تحليل وتحضير الطلاب"), key="doc_process_btn"):
                    images_to_process = []
                    if imgs: images_to_process.extend(imgs)
                    if doc_cam is not None: images_to_process.append(doc_cam)

                    if len(images_to_process) == 0:
                        st.warning(t("⚠️ Please capture or upload a photo first.", "⚠️ يرجى التقاط أو رفع صورة أولاً."))
                    else:
                        with st.spinner(t("AI is extracting faces...", "الذكاء الاصطناعي يحلل الوجوه في القاعة...")):
                            recognized = set()
                            folder = f"registered_faces/{doc_id}_{safe_cls}"
                            os.makedirs(folder, exist_ok=True)
                            
                            for img in images_to_process[:10]:
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                                    tmp.write(img.getvalue()); tmp_p = tmp.name
                                try:
                                    # 🛡️ وضع البانوراما للدكتور (مرن ليسمح بقراءة الوجوه الصغيرة أو القاعات)
                                    res = DeepFace.find(img_path=tmp_p, db_path=folder, enforce_detection=False)
                                    for r in res:
                                        if not r.empty:
                                            sid = os.path.basename(r.iloc[0]['identity']).split('.')[0]
                                            recognized.add(sid)
                                except: pass
                                os.remove(tmp_p)
                            
                            for sid in recognized:
                                push_db(f'/attendance/{doc_id}_{safe_cls}', {
                                    "id": sid, "date": datetime.now().strftime("%Y-%m-%d"),
                                    "time": datetime.now().strftime("%I:%M %p"), 
                                    "distance": "0 m (Doctor)", "status": "✅ Present", "method": "Doctor Camera/Batch"
                                })
                            if recognized:
                                st.success(f"{t('Successfully processed IDs:', 'تم تحضير الأرقام بنجاح:')} {list(recognized)}")
                            else:
                                st.warning(t("No matching faces found in the images.", "لم يتم التعرف على أي وجه مسجل في هذه الصور."))
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
                    st.dataframe(df, use_container_width=True)
                    st.download_button(t("Export Cloud CSV", "تحميل السجل (CSV)"), data=df.to_csv().encode('utf-8'), file_name="Report.csv", key="csv_btn")
                else: st.info(t("Database is empty.", "لا يوجد سجلات حتى الآن."))
