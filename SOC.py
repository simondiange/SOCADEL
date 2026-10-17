"""
⚡ SOCADEL Outage Communication System — Complete App (cascading fix)
=====================================================================
Roles: Admin · Supervisor · Client
Location: Region → Division → Sub-division — cascades instantly (not inside a form)
Photos: Opt-in — Camera / Upload / No photos
Filtering: Clients & Supervisors see outages in their sub-division by default,
           with a "Search another area" option.
Notifications: In-app popup · Email (SMTP) · WhatsApp (Twilio or wa.me links)

RUN:     pip install -r requirements.txt && streamlit run SOC.py
DEPLOY:  Push to GitHub → Streamlit Cloud redeploys automatically.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import uuid
import smtplib
import urllib.parse
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

try:
    from supabase import create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

# ============================================
# CONFIG
# ============================================
LOCAL_FILE = "socadel_outages_data.json"
DEFAULT_ADMIN_PASSWORD = "socadel2024"
DEFAULT_SUPERVISOR_CODE = "field2024"
FORCE_POPUP_FRESH_MINUTES = 10
MAX_WA_PER_DISPATCH = 30
MAX_IMAGES_PER_REPORT = 3

# ============================================
# CAMEROON — OFFICIAL ADMINISTRATIVE STRUCTURE
# ============================================
CAMEROON_LOCATIONS = {
    "Adamawa": {
        "Djérem": ["Tibati", "Ngaoundal"],
        "Faro-et-Déo": ["Tignère", "Galim-Tignère", "Mayo-Baléo"],
        "Mayo-Banyo": ["Banyo", "Bankim", "Mayo-Darlé"],
        "Mbéré": ["Meiganga", "Djohong", "Dir", "Ngaoui"],
        "Vina": ["Ngaoundéré I", "Ngaoundéré II", "Ngaoundéré III",
                 "Nganha", "Nyambaka", "Martap", "Mbé", "Bélel"],
    },
    "Centre": {
        "Haute-Sanaga": ["Nanga-Eboko", "Mbandjock", "Minta", "Nkoteng"],
        "Lekié": ["Monatélé", "Obala", "Okola", "Sa'a", "Elig-Mfomo",
                  "Evodoula", "Ebebda", "Bot-Makak"],
        "Mbam-et-Inoubou": ["Bafia", "Bokito", "Ndikiniméki", "Deuk",
                            "Ombessa", "Makénéné", "Kiiki", "Kon-Yambetta"],
        "Mbam-et-Kim": ["Ntui", "Ngambè-Tikar", "Ngoro", "Yoko",
                        "Mbangassina"],
        "Méfou-et-Afamba": ["Mfou", "Esse", "Awae", "Soa", "Nkolafamba",
                            "Edzendouan", "Assamba"],
        "Méfou-et-Akono": ["Ngoumou", "Akono", "Mbankomo", "Bikok"],
        "Mfoundi": ["Yaoundé I", "Yaoundé II", "Yaoundé III", "Yaoundé IV",
                    "Yaoundé V", "Yaoundé VI", "Yaoundé VII"],
        "Nyong-et-Kellé": ["Eséka", "Bot-Makak", "Makak", "Messondo",
                           "Ngog-Mapubi", "Matomb", "Dibang",
                           "Nguibassal", "Bondjock", "Biyouha"],
        "Nyong-et-Mfoumou": ["Akonolinga", "Ayos", "Endom", "Mengang",
                             "Nyakombo", "Kobdombo"],
        "Nyong-et-So'o": ["Mbalmayo", "Akoeman", "Dzeng", "Ngomedzap",
                          "Mengueme", "Olanguina", "Zoétélé"],
    },
    "East": {
        "Boumba-et-Ngoko": ["Yokadouma", "Moloundou", "Salapoumbé",
                            "Gari-Gombo"],
        "Haut-Nyong": ["Abong-Mbang", "Doumé", "Messamena",
                       "Nguelemendouka", "Lomié", "Dimako", "Dja",
                       "Doumaintang", "Mboanz", "Mboma", "Messok",
                       "Ngoyla", "Somalomo"],
        "Kadey": ["Batouri", "Kentzou", "Ndelele", "Kette", "Mbang",
                  "Bombé", "Mbotoro", "Ndem-Nam"],
        "Lom-et-Djérem": ["Bertoua I", "Bertoua II", "Mandjou",
                          "Bétaré-Oya", "Bélabo", "Diang",
                          "Garoua-Boulaï", "Ngoura"],
    },
    "Far North": {
        "Diamaré": ["Maroua I", "Maroua II", "Maroua III", "Bogo",
                    "Dargala", "Gazawa", "Meri", "Ndoukoula", "Petté"],
        "Logone-et-Chari": ["Kousséri", "Logone-Birni", "Makary",
                            "Waza", "Blangoua", "Fotokol", "Goulfey",
                            "Hile-Alifa", "Zina", "Darak"],
        "Mayo-Danay": ["Yagoua", "Guéré", "Kalfou", "Kar-Hay",
                       "Maga", "Meye", "Tchatibali", "Wina",
                       "Datcheka", "Gobo", "Kai-Kai", "Vele"],
        "Mayo-Kani": ["Kaélé", "Guidiguis", "Mindif", "Moulvoudaye",
                      "Moutourwa", "Taïbong", "Porhi"],
        "Mayo-Sava": ["Mora", "Tokombéré", "Kolofata"],
        "Mayo-Tsanaga": ["Mokolo", "Bourha", "Koza", "Hina",
                         "Mayo-Moskota", "Mogodé", "Soulédé-Roua"],
    },
    "Littoral": {
        "Moungo": ["Nkongsamba I", "Nkongsamba II", "Nkongsamba III",
                   "Mbanga", "Dibombari", "Manjo", "Melong", "Loum",
                   "Baré-Bakem", "Nlonako", "Njombe-Penja", "Fiko",
                   "Mombo"],
        "Nkam": ["Yabassi", "Yingui", "Nkondjock", "Nord-Makombé"],
        "Sanaga-Maritime": ["Edéa I", "Edéa II", "Ngambé", "Pouma",
                            "Ndom", "Dizangué", "Mouanko", "Dibamba",
                            "Ngwei", "Massock-Songloulou", "Nyanon"],
        "Wouri": ["Douala I", "Douala II", "Douala III", "Douala IV",
                  "Douala V", "Douala VI"],
    },
    "North": {
        "Bénoué": ["Garoua I", "Garoua II", "Garoua III", "Mayo-Hourna",
                   "Bibémi", "Pitoa", "Lagdo", "Dembo", "Tchéboa",
                   "Baschéo", "Demsa", "Touroua"],
        "Faro": ["Poli", "Béka", "Mayo-Oulo"],
        "Mayo-Louti": ["Guider", "Figuil"],
        "Mayo-Rey": ["Tcholliré", "Rey-Bouba", "Touboro", "Madingring"],
    },
    "North West": {
        "Boyo": ["Fundong", "Bum", "Belo", "Njinikom"],
        "Bui": ["Kumbo", "Jakiri", "Mbven", "Oku", "Noni", "Nkum"],
        "Donga-Mantung": ["Nkambé", "Nwa", "Ako", "Ndu", "Misaje"],
        "Menchum": ["Wum", "Furu-Awa", "Fungom", "Menchum Valley"],
        "Mezam": ["Bamenda I", "Bamenda II", "Bamenda III", "Bali",
                  "Tubah", "Bafut", "Santa"],
        "Momo": ["Mbengwi", "Batibo", "Njikwa", "Ngie", "Widikum"],
        "Ngo-Ketunjia": ["Ndop", "Babessi", "Balikumbat"],
    },
    "South": {
        "Dja-et-Lobo": ["Sangmélima", "Bengbis", "Zoétélé",
                        "Meyomessala", "Mvangan", "Djoum", "Mintom"],
        "Mvila": ["Ebolowa I", "Ebolowa II", "Efoulan",
                  "Biwong-Bulu", "Meyomesi", "Mengong"],
        "Océan": ["Kribi I", "Kribi II", "Lokoundjé", "Akom II",
                  "Campo", "Lolodorf", "Mvengue", "Niété"],
        "Vallée-du-Ntem": ["Ambam", "Ma'an", "Kyé-Ossi", "Olamze"],
    },
    "South West": {
        "Fako": ["Limbe I", "Limbe II", "Limbe III", "Tiko", "Buea",
                 "Muyuka", "West Coast"],
        "Koupé-Manengouba": ["Bangem", "Tombel", "Nguti"],
        "Lebialem": ["Menji", "Alou", "Wabane"],
        "Manyu": ["Mamfe", "Akwaya", "Eyumojock", "Upper Banyang"],
        "Meme": ["Kumba I", "Kumba II", "Kumba III", "Mbonge"],
        "Ndian": ["Mundemba", "Ekondo-Titi", "Bamusso", "Isangele",
                  "Kombo-Itindi", "Idabato", "Kombo-Abedimo",
                  "Dikome-Balue", "Toko"],
    },
    "West": {
        "Bamboutos": ["Mbouda", "Batcham", "Galim", "Babadjou"],
        "Haut-Nkam": ["Bafang", "Bakou", "Bana", "Bandja", "Kékem"],
        "Hauts-Plateaux": ["Baham", "Bamougoum", "Bangou"],
        "Koung-Khi": ["Bandjoun", "Bayangam", "Demdeng"],
        "Menoua": ["Dschang", "Pennebaken", "Santchou", "Fokoué",
                   "Fongo-Tongo", "Nkong-Ni"],
        "Mifi": ["Bafoussam I", "Bafoussam II", "Bafoussam III"],
        "Ndé": ["Bangangté", "Bazou", "Tonga", "Bangou"],
        "Noun": ["Foumban", "Bamendjou", "Kouoptamo", "Malantouen",
                 "Massangam", "Njimom", "Koutaba"],
    },
}

# ============================================
# SECRETS
# ============================================
def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except (KeyError, FileNotFoundError, AttributeError):
        return default

ADMIN_PASSWORD  = get_secret("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
SUPERVISOR_CODE = get_secret("SUPERVISOR_CODE", DEFAULT_SUPERVISOR_CODE)

# ============================================
# NOTIFICATION CHANNELS
# ============================================
def get_email_config():
    return {
        "host":      get_secret("SMTP_HOST", ""),
        "port":      int(get_secret("SMTP_PORT", 587)),
        "user":      get_secret("SMTP_USER", ""),
        "password":  get_secret("SMTP_PASSWORD", ""),
        "from":      get_secret("SMTP_FROM", get_secret("SMTP_USER", "")),
        "from_name": get_secret("SMTP_FROM_NAME", "SOCADEL Outage Alerts"),
    }

def get_wa_config():
    return {
        "sid":   get_secret("TWILIO_ACCOUNT_SID", ""),
        "token": get_secret("TWILIO_AUTH_TOKEN", ""),
        "from":  get_secret("TWILIO_WHATSAPP_FROM", ""),
    }

def is_email_configured():
    c = get_email_config()
    return bool(c["host"] and c["user"] and c["password"] and c["from"])

def is_whatsapp_configured():
    c = get_wa_config()
    return bool(c["sid"] and c["token"] and c["from"])

def normalize_phone(phone):
    if not phone:
        return ""
    s = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if not s:
        return ""
    if not s.startswith("+"):
        s = "+237" + s.lstrip("0")
    return s

def send_email_broadcast(emails, subject, body):
    cfg = get_email_config()
    if not is_email_configured():
        return False, "Email not configured"
    clean = [e.strip() for e in emails if e and "@" in e]
    if not clean:
        return False, "No valid email addresses"
    if len(clean) > 100:
        clean = clean[:100]
    msg = MIMEMultipart()
    msg["From"]    = f'{cfg["from_name"]} <{cfg["from"]}>'
    msg["To"]      = cfg["from"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=25) as s:
            s.ehlo(); s.starttls()
            s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from"], clean, msg.as_string())
        return True, f"Sent to {len(clean)} recipient(s)"
    except Exception as e:
        return False, str(e)

def send_whatsapp_twilio(phone, message):
    cfg = get_wa_config()
    if not is_whatsapp_configured():
        return False, "WhatsApp (Twilio) not configured"
    to = normalize_phone(phone)
    if not to:
        return False, "Invalid phone"
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['sid']}/Messages.json"
        r = requests.post(url,
            data={"From": cfg["from"], "To": f"whatsapp:{to}",
                  "Body": message[:1600]},
            auth=(cfg["sid"], cfg["token"]), timeout=15)
        if r.status_code in (200, 201):
            return True, "Sent"
        return False, f"HTTP {r.status_code}: {r.text[:160]}"
    except Exception as e:
        return False, str(e)

def generate_wa_links(recipients, message):
    enc = urllib.parse.quote(message)
    out = []
    for name, phone in recipients:
        p = normalize_phone(phone)
        if p:
            out.append((name, p, f"https://wa.me/{p.lstrip('+')}?text={enc}"))
    return out

def dispatch_to_channels(data, message, subject, send_email_flag, send_wa_flag):
    recipients = get_all_recipients(data)
    out = {"email": [], "whatsapp": [], "wa_links": [],
           "recipients_count": len(recipients)}
    if send_email_flag and is_email_configured():
        emails = [r["email"] for r in recipients if r.get("email")]
        if emails:
            ok, msg = send_email_broadcast(emails, subject, message)
            out["email"].append((ok, msg, len(emails)))
        else:
            out["email"].append((False, "No email recipients on file", 0))
    if send_wa_flag:
        phones = [(r["name"], r["phone"]) for r in recipients if r.get("phone")]
        if not phones:
            out["whatsapp"].append(("—", "—", False, "No phone numbers on file"))
        elif is_whatsapp_configured():
            for name, phone in phones[:MAX_WA_PER_DISPATCH]:
                ok, msg = send_whatsapp_twilio(phone, message)
                out["whatsapp"].append((name, phone, ok, msg))
            if len(phones) > MAX_WA_PER_DISPATCH:
                out["whatsapp"].append(("—", "—", False,
                    f"{len(phones) - MAX_WA_PER_DISPATCH} more not sent (batch limit)"))
        else:
            out["wa_links"] = generate_wa_links(phones, message)
    return out

def render_dispatch_report(report):
    if report["email"]:
        for ok, msg, count in report["email"]:
            (st.success if ok else st.error)(f"📧 Email: {msg}")
    if report["whatsapp"]:
        with st.expander(f"💬 WhatsApp results ({len(report['whatsapp'])})"):
            for name, phone, ok, msg in report["whatsapp"]:
                (st.success if ok else st.error)(
                    f"{'✅' if ok else '❌'} {name} — {phone}" +
                    ("" if ok else f": {msg}"))
    if report["wa_links"]:
        st.info("⚠️ Twilio not configured — click each link to send via your own WhatsApp.")
        for name, phone, url in report["wa_links"]:
            st.markdown(f"- **{name}** ({phone}) — [💬 Send on WhatsApp]({url})")

# ============================================
# LOCATION HELPERS
# ============================================
def format_location(loc):
    if isinstance(loc, dict):
        parts = [
            (loc.get("quarter") or "").strip(),
            (loc.get("subdivision") or "").strip(),
            (loc.get("division") or "").strip(),
            (loc.get("region") or "").strip(),
        ]
        return ", ".join([p for p in parts if p]) or "—"
    return (loc or "").strip() or "—"

def location_inputs(prefix, defaults=None):
    if not isinstance(defaults, dict):
        defaults = {}
    c1, c2, c3, c4 = st.columns(4)

    region_list = list(CAMEROON_LOCATIONS.keys())
    default_region = defaults.get("region", "Centre") or "Centre"
    try:
        region_idx = region_list.index(default_region)
    except ValueError:
        region_idx = 1
    region = c1.selectbox("Region", region_list, index=region_idx,
                          key=f"{prefix}_region")

    divisions = list(CAMEROON_LOCATIONS.get(region, {}).keys())
    default_div = defaults.get("division", divisions[0] if divisions else "")
    try:
        div_idx = divisions.index(default_div)
    except (ValueError, IndexError):
        div_idx = 0
    division = c2.selectbox("Division", divisions, index=div_idx,
                            key=f"{prefix}_division")

    subdivisions = CAMEROON_LOCATIONS.get(region, {}).get(division, [])
    if subdivisions:
        options = subdivisions + ["Other (specify)"]
        default_sub = defaults.get("subdivision", subdivisions[0])
        try:
            sub_idx = options.index(default_sub)
        except ValueError:
            sub_idx = 0
        sel = c3.selectbox("Sub-division", options, index=sub_idx,
                           key=f"{prefix}_subdivision")
        if sel == "Other (specify)":
            subdivision = c3.text_input(
                "Specify sub-division",
                value=defaults.get("subdivision", ""),
                key=f"{prefix}_subdivision_custom")
        else:
            subdivision = sel
    else:
        subdivision = c3.text_input(
            "Sub-division", value=defaults.get("subdivision", ""),
            key=f"{prefix}_subdivision_custom")

    quarter = c4.text_input("Quarter", value=defaults.get("quarter", ""),
                            key=f"{prefix}_quarter",
                            placeholder="e.g. Mvog-Mbi")

    return {
        "region": region.strip(),
        "division": division.strip(),
        "subdivision": subdivision.strip(),
        "quarter": quarter.strip(),
    }

def current_user_location():
    return {
        "region": st.session_state.get("region", ""),
        "division": st.session_state.get("division", ""),
        "subdivision": st.session_state.get("subdivision", ""),
        "quarter": st.session_state.get("quarter", ""),
    }

# ============================================
# OUTAGE FILTERING
# ============================================
def filter_outages_for_viewer(outages, viewer_location, search_location=None):
    if not outages:
        return []
    target = search_location if search_location else viewer_location
    target_region = (target.get("region") or "").strip().lower()
    target_div    = (target.get("division") or "").strip().lower()
    target_sub    = (target.get("subdivision") or "").strip().lower()

    filtered = []
    for o in outages:
        loc = o.get("location", {})
        o_region = (loc.get("region") or "").strip().lower()
        o_div    = (loc.get("division") or "").strip().lower()
        o_sub    = (loc.get("subdivision") or "").strip().lower()

        if target_sub and o_sub:
            if target_sub == o_sub:
                filtered.append(o)
        elif target_div and o_div:
            if target_div == o_div:
                filtered.append(o)
        elif target_region and o_region:
            if target_region == o_region:
                filtered.append(o)
    return filtered

def outage_area_selector(data, prefix, viewer_location):
    st.markdown("**🔍 View outages in:**")
    mode = st.radio(
        "Area",
        ["My sub-division (default)", "Search another area"],
        key=f"{prefix}_area_mode",
        horizontal=True,
    )
    if mode == "My sub-division (default)":
        return viewer_location
    st.markdown("**Search area**")
    return location_inputs(f"{prefix}_search", defaults=viewer_location)

# ============================================
# IMAGE HANDLING — opt-in only
# ============================================
def capture_images(prefix):
    st.markdown("**📸 Attach photos (optional — up to 3)**")
    method = st.radio(
        "How would you like to attach photos?",
        ["🚫 No photos", "📷 Take a photo", "🖼️ Upload from gallery"],
        key=f"{prefix}_method",
        horizontal=True,
        index=0,
    )
    images = []
    if method == "📷 Take a photo":
        photo = st.camera_input("Take a live picture",
                                key=f"{prefix}_camera")
        if photo:
            images.append(base64.b64encode(photo.getvalue()).decode("utf-8"))
    elif method == "🖼️ Upload from gallery":
        uploaded = st.file_uploader(
            "Upload images", type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True, key=f"{prefix}_upload")
        if uploaded:
            for f in uploaded[:MAX_IMAGES_PER_REPORT]:
                images.append(base64.b64encode(f.getvalue()).decode("utf-8"))
    return images[:MAX_IMAGES_PER_REPORT]

def render_images(images, prefix=""):
    if not images:
        return
    st.markdown("**📸 Attached photos**")
    cols = st.columns(min(len(images), 3))
    for i, b64 in enumerate(images):
        try:
            img_bytes = base64.b64decode(b64)
            with cols[i % len(cols)]:
                st.image(img_bytes, use_container_width=True)
        except Exception:
            pass

# ============================================
# STORAGE
# ============================================
def default_data():
    return {
        "active_outages": [], "past_outages": [], "reports": [],
        "notifications": [], "clients": {}, "contacts": {},
        "next_outage_id": 1, "next_notif_id": 1, "next_report_id": 1,
    }

def _ensure_fields(d):
    for k, v in default_data().items():
        d.setdefault(k, v)
    return d

class LocalStorage:
    def load(self):
        try:
            with open(LOCAL_FILE, "r") as f:
                d = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            d = {}
        return _ensure_fields(d)
    def save(self, data):
        with open(LOCAL_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    def backend_name(self):
        return "💾 Local JSON — add Supabase to sync."

class SupabaseStorage:
    TABLE = "socadel_state"; ROW_ID = "main"
    def __init__(self, url, key):
        self.client = create_client(url, key)
    def load(self):
        try:
            r = self.client.table(self.TABLE).select("data").eq("id", self.ROW_ID).execute()
            d = (r.data[0]["data"] if r.data else {}) or {}
        except Exception as e:
            st.error(f"Supabase load error: {e}"); d = {}
        return _ensure_fields(d)
    def save(self, data):
        try:
            self.client.table(self.TABLE).upsert({
                "id": self.ROW_ID, "data": data,
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception as e:
            st.error(f"Supabase save error: {e}")
    def backend_name(self):
        return "☁️ Supabase (shared)"

def get_storage():
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY") or get_secret("SUPABASE_KEY")
    if url and key and HAS_SUPABASE:
        try:
            return SupabaseStorage(url, key)
        except Exception as e:
            st.warning(f"Supabase unavailable ({e}). Using local JSON.")
    return LocalStorage()

# ============================================
# DATA HELPERS
# ============================================
def add_notification(data, message, force_popup=False, outage_id=0):
    n = {"id": data["next_notif_id"], "outage_id": outage_id,
         "message": message,
         "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "force_popup": force_popup}
    data["next_notif_id"] += 1
    data["notifications"].append(n)
    return n

def create_report(data, role, name, issue, description, severity, location, images=None):
    r = {"id": data["next_report_id"],
         "reporter_id": st.session_state.client_id,
         "reporter_name": name, "reporter_role": role,
         "issue": issue, "description": description,
         "severity": severity, "location": location,
         "images": images or [],
         "status": "pending",
         "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "admin_note": "", "outage_id": None}
    data["next_report_id"] += 1
    data["reports"].append(r)
    return r

def register_contact(data, cid, name, role, email, phone, location, worker_id=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = data["contacts"].get(cid, {})
    data["contacts"][cid] = {
        "name": name, "role": role,
        "email": (email or "").strip(),
        "phone": (phone or "").strip(),
        "location": location, "worker_id": worker_id,
        "registered_at": existing.get("registered_at", now),
        "last_updated": now,
    }

def touch_user(data, role, name):
    cid = st.session_state.client_id
    entry = data["clients"].get(cid, {})
    entry.update({"name": name, "role": role,
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "location": current_user_location()})
    if role == "supervisor":
        entry["worker_id"] = st.session_state.get("worker_id", "")
    data["clients"][cid] = entry
    return data

def cleanup_clients(data, max_age_minutes=30):
    now = datetime.now(); stale = []
    for cid, entry in list(data["clients"].items()):
        try:
            last = datetime.strptime(entry.get("last_seen", ""), "%Y-%m-%d %H:%M:%S")
            if (now - last).total_seconds() > max_age_minutes * 60:
                stale.append(cid)
        except Exception:
            stale.append(cid)
    for cid in stale:
        del data["clients"][cid]

def get_all_recipients(data):
    out = []
    for cid, c in data.get("contacts", {}).items():
        if c.get("email") or c.get("phone"):
            out.append({"client_id": cid, "name": c.get("name", ""),
                "role": c.get("role", ""), "email": c.get("email", ""),
                "phone": c.get("phone", "")})
    return out

# ============================================
# PAGE CONFIG & STYLES
# ============================================
st.set_page_config(page_title="SOCADEL Outage System", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.main-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px; }
.role-card { border: 2px solid #e0e6ed; border-radius: 12px; padding: 24px;
    text-align: center; background: white; }
.role-card h3 { margin-top: 0; }
.stButton > button { border-radius: 8px; font-weight: 600; }
.loc-badge { display: inline-block; background: #eef2ff; color: #4338ca;
    padding: 4px 10px; border-radius: 12px; font-size: 12px;
    font-weight: 600; margin-bottom: 8px; }
.chan-badge { display: inline-block; padding: 3px 10px; border-radius: 10px;
    font-size: 11px; font-weight: 700; margin-right: 6px; }
.chan-on  { background: #d1fae5; color: #065f46; }
.chan-off { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

for key, val in {
    "role": None, "client_id": f"user_{uuid.uuid4().hex[:8]}",
    "display_name": "", "worker_id": "", "email": "", "phone": "",
    "region": "", "division": "", "subdivision": "", "quarter": "",
    "_shown_force_notifs": set(), "_active_force_notif": None,
}.items():
    st.session_state.setdefault(key, val)

def do_logout():
    for k in ["role","display_name","worker_id","email","phone",
              "region","division","subdivision","quarter"]:
        st.session_state[k] = "" if k != "role" else None
    st.session_state._shown_force_notifs = set()
    st.session_state._active_force_notif = None
    st.rerun()

# ============================================
# FORCE POPUP
# ============================================
@st.dialog("🚨 SOCADEL EMERGENCY ALERT", width="large")
def force_popup_dialog():
    n = st.session_state.get("_active_force_notif")
    if not n: return
    up = n["message"].upper()
    if "CRITICAL" in up or "EMERGENCY" in up or "URGENT" in up:
        st.error(f"### ⚠️ {n['message']}")
    elif "HIGH" in up:
        st.warning(f"### ⚠️ {n['message']}")
    else:
        st.info(f"### 📢 {n['message']}")
    st.caption(f"🕐 {n['timestamp']}")
    st.markdown("---")
    if st.button("✅ Acknowledge", type="primary", use_container_width=True):
        st.session_state._shown_force_notifs.add(n["id"])
        st.session_state._active_force_notif = None
        st.rerun()

def check_force_popup(data):
    now = datetime.now()
    for n in data.get("notifications", []):
        if not n.get("force_popup"): continue
        if n["id"] in st.session_state._shown_force_notifs: continue
        try:
            ts = datetime.strptime(n["timestamp"], "%Y-%m-%d %H:%M:%S")
            if (now - ts) > timedelta(minutes=FORCE_POPUP_FRESH_MINUTES): continue
        except Exception:
            continue
        st.session_state._active_force_notif = n
        force_popup_dialog()
        return True
    return False

# ============================================
# LANDING
# ============================================
def show_landing():
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">⚡ SOCADEL Outage Communication System</h1>
        <p style="margin:5px 0 0 0; opacity:0.9;">Real-Time Electricity Outage Management — Cameroon</p>
        <p style="margin:5px 0 0 0; opacity:0.8; font-size:13px;">Société Camerounaise de Distribution d'Électricité</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("## 👋 Welcome — choose your role")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown("""<div class="role-card"><div style="font-size:48px;">👨‍💼</div>
        <h3>Administrator</h3><p>Full control: dashboard, outages, convert reports, broadcast alerts.</p></div>""",
        unsafe_allow_html=True)
        st.write("")
        if st.button("🔐 Login as Admin", type="primary", use_container_width=True, key="btn_admin"):
            st.session_state.role = "admin_login"; st.rerun()
    with c2:
        st.markdown("""<div class="role-card"><div style="font-size:48px;">👷</div>
        <h3>Supervisor</h3><p>SOCADEL field worker: report issues with photos, view all field reports.</p></div>""",
        unsafe_allow_html=True)
        st.write("")
        if st.button("🔐 Login as Supervisor", type="primary", use_container_width=True, key="btn_sup"):
            st.session_state.role = "supervisor_login"; st.rerun()
    with c3:
        st.markdown("""<div class="role-card"><div style="font-size:48px;">🏠</div>
        <h3>Client / Consumer</h3><p>View power status, report outages with photos, track submissions.</p></div>""",
        unsafe_allow_html=True)
        st.write("")
        if st.button("👀 Continue as Client", type="primary", use_container_width=True, key="btn_cli"):
            st.session_state.role = "client_login"; st.rerun()

# ============================================
# LOGIN SCREENS  (location OUTSIDE forms — cascade works)
# ============================================
def show_admin_login():
    st.markdown("## 🔐 Administrator Login")
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("admin_login_form"):
            pwd = st.text_input("Administrator password", type="password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.role = "admin"; st.rerun()
                else:
                    st.error("Incorrect password")
        if st.button("← Back to role selection", use_container_width=True, key="admin_back"):
            st.session_state.role = None; st.rerun()

def show_supervisor_login():
    st.markdown("## 👷 Supervisor Login")
    st.caption("For SOCADEL field workers only.")
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        r1c1, r1c2 = st.columns(2)
        name = r1c1.text_input("Full name", key="sup_login_name")
        wid  = r1c2.text_input("Worker ID", placeholder="e.g. SOC-1234",
                               key="sup_login_wid")
        r2c1, r2c2 = st.columns(2)
        email = r2c1.text_input("Email", placeholder="you@example.com",
                                key="sup_login_email")
        phone = r2c2.text_input("WhatsApp number", placeholder="+237 6XX XXX XXX",
                                key="sup_login_phone")
        code  = st.text_input("Supervisor access code", type="password",
                              key="sup_login_code")
        st.markdown("**Base location** *(pick region first → divisions cascade)*")
        loc = location_inputs("sup_login_loc")
        st.caption(f"Selected: **{format_location(loc)}**")
        if st.button("Enter Field Portal", type="primary",
                     use_container_width=True, key="sup_login_btn"):
            if not (name and wid and code):
                st.error("Please fill name, worker ID and access code.")
            elif code != SUPERVISOR_CODE:
                st.error("Invalid supervisor access code.")
            else:
                st.session_state.role = "supervisor"
                st.session_state.display_name = name
                st.session_state.worker_id = wid
                st.session_state.email = email.strip()
                st.session_state.phone = phone.strip()
                st.session_state.region = loc["region"]
                st.session_state.division = loc["division"]
                st.session_state.subdivision = loc["subdivision"]
                st.session_state.quarter = loc["quarter"]
                st.rerun()
        if st.button("← Back to role selection", use_container_width=True, key="sup_back"):
            st.session_state.role = None; st.rerun()

def show_client_login():
    st.markdown("## 🏠 Client / Consumer Access")
    st.caption("Enter your name, contact and location — no password needed.")
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        r1c1, r1c2 = st.columns(2)
        name = r1c1.text_input("Your name", key="cli_login_name")
        email = r1c2.text_input("Email", placeholder="you@example.com",
                                key="cli_login_email")
        phone = st.text_input("WhatsApp number", placeholder="+237 6XX XXX XXX",
                              key="cli_login_phone")
        st.markdown("**Your location** *(pick region first → divisions cascade)*")
        loc = location_inputs("cli_login_loc")
        st.caption(f"Selected: **{format_location(loc)}**")
        if st.button("Continue", type="primary",
                     use_container_width=True, key="cli_login_btn"):
            if not name:
                st.error("Please enter your name.")
            else:
                st.session_state.role = "client"
                st.session_state.display_name = name
                st.session_state.email = email.strip()
                st.session_state.phone = phone.strip()
                st.session_state.region = loc["region"]
                st.session_state.division = loc["division"]
                st.session_state.subdivision = loc["subdivision"]
                st.session_state.quarter = loc["quarter"]
                st.rerun()
        if st.button("← Back to role selection", use_container_width=True, key="cli_back"):
            st.session_state.role = None; st.rerun()

# ============================================
# ADMIN PORTAL
# ============================================
def show_admin():
    storage = get_storage(); data = storage.load(); cleanup_clients(data)
    with st.sidebar:
        st.markdown("### 🛠️ Admin Panel")
        st.caption("👤 Signed in as Administrator")
        email_ok = is_email_configured(); wa_ok = is_whatsapp_configured()
        st.markdown(
            f'<span class="chan-badge {"chan-on" if email_ok else "chan-off"}">'
            f'📧 Email {"ON" if email_ok else "OFF"}</span>'
            f'<span class="chan-badge {"chan-on" if wa_ok else "chan-off"}">'
            f'💬 WA {"ON" if wa_ok else "OFF"}</span>',
            unsafe_allow_html=True)
        pending = len([r for r in data["reports"] if r["status"] == "pending"])
        if pending:
            st.error(f"📥 {pending} new report(s) awaiting review")
        menu = st.radio("Navigation", [
            "📊 Dashboard", "📥 Reports Inbox", "📝 Create Outage",
            "📋 Manage Outages", "📢 Send Notification", "🔴 Force Popup",
            "📜 History", "👥 Users", "🔔 Notification Channels"])
        st.markdown("---")
        st.caption(storage.backend_name())
        if st.button("🔄 Refresh data", use_container_width=True):
            st.rerun()
        if st.button("🚪 Logout", use_container_width=True):
            do_logout()

    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">⚡ SOCADEL — Admin Dashboard</h1>
        <p style="margin:5px 0 0 0; opacity:0.9;">Real-Time Electricity Outage Management</p>
    </div>
    """, unsafe_allow_html=True)

    if   menu == "📊 Dashboard":             admin_dashboard(data)
    elif menu == "📥 Reports Inbox":         admin_reports_inbox(data, storage)
    elif menu == "📝 Create Outage":         admin_create_outage(data, storage)
    elif menu == "📋 Manage Outages":        admin_manage_outages(data, storage)
    elif menu == "📢 Send Notification":     admin_send_notification(data, storage)
    elif menu == "🔴 Force Popup":           admin_force_popup(data, storage)
    elif menu == "📜 History":               admin_history(data)
    elif menu == "👥 Users":                 admin_users(data)
    elif menu == "🔔 Notification Channels": admin_channels(data, storage)

def admin_dashboard(data):
    st.subheader("📊 Overview")
    pending_reports = len([r for r in data["reports"] if r["status"] == "pending"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🚨 Active Outages", len(data["active_outages"]))
    c2.metric("✅ Resolved", len(data["past_outages"]))
    c3.metric("📥 Pending Reports", pending_reports)
    c4.metric("📢 Notifications", len(data["notifications"]))
    c5.metric("💻 Users Online", len(data["clients"]))
    recipients = get_all_recipients(data)
    e_count = len([r for r in recipients if r.get("email")])
    p_count = len([r for r in recipients if r.get("phone")])
    st.caption(f"📇 Contacts: **{len(recipients)}** — 📧 {e_count} · 💬 {p_count}")
    if pending_reports:
        st.warning(f"📥 **{pending_reports} report(s)** waiting in the Reports Inbox.")
    st.markdown("---")
    st.subheader("🚨 Active Outages")
    if not data["active_outages"]:
        st.success("✅ No active outages — the power grid is stable.")
        return
    for o in data["active_outages"]:
        with st.expander(f"⚡ #{o['id']} — {o['issue']}  [{o['severity']}]", expanded=True):
            st.markdown(f'<div class="loc-badge">📍 {format_location(o.get("location"))}</div>',
                        unsafe_allow_html=True)
            st.write(f"**Description:** {o['description']}")
            st.write(f"**Additional affected areas:** {o.get('affected_services') or '—'}")
            st.write(f"**Started:** {o['start_time']}")
            st.write(f"**ETA:** {o['estimated_resolution']}")
            render_images(o.get("images", []))
            for u in o["updates"]:
                st.info(f"🕐 {u['timestamp']} — {u['message']}")

def channel_options_ui(data, key_prefix):
    recipients = get_all_recipients(data)
    e_count = len([r for r in recipients if r.get("email")])
    p_count = len([r for r in recipients if r.get("phone")])
    c1, c2 = st.columns(2)
    send_email = c1.checkbox(
        f"📧 Also send by Email ({e_count})", key=f"{key_prefix}_email_ck",
        disabled=not is_email_configured())
    send_wa = c2.checkbox(
        f"💬 Also send by WhatsApp ({p_count})", key=f"{key_prefix}_wa_ck")
    if not is_email_configured():
        c1.caption("⚠️ Email not configured")
    if send_wa and not is_whatsapp_configured():
        st.info("💡 Twilio not configured — WhatsApp shown as wa.me links after sending.")
    return send_email, send_wa

def admin_reports_inbox(data, storage):
    st.subheader("📥 Reports Inbox")
    pending = [r for r in data["reports"] if r["status"] == "pending"]
    if not pending:
        st.success("✅ No pending reports. All caught up.")
        return
    st.caption(f"{len(pending)} report(s) awaiting action")
    for r in pending:
        role_badge = "👷 Supervisor" if r["reporter_role"] == "supervisor" else "🏠 Client"
        with st.expander(f"#{r['id']} — {r['issue']}  ·  {role_badge} · {r['reporter_name']}",
                         expanded=True):
            st.markdown(f'<div class="loc-badge">📍 {format_location(r.get("location"))}</div>',
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Reporter:** {r['reporter_name']} ({role_badge})")
                st.write(f"**Issue:** {r['issue']}")
                st.write(f"**Severity:** {r['severity']}")
            with c2:
                st.write(f"**Submitted:** {r['created_at']}")
            st.write(f"**Description:** {r['description']}")
            render_images(r.get("images", []))
            st.markdown("---")
            tab1, tab2, tab3 = st.tabs(["✅ Convert", "📌 Add as Update", "🗑️ Dismiss"])
            with tab1:
                cc1, cc2 = st.columns(2)
                with cc1:
                    new_issue = st.text_input("Issue", value=r["issue"],
                                              key=f"cv_issue_{r['id']}")
                    new_desc = st.text_area("Description", value=r["description"],
                                            key=f"cv_desc_{r['id']}", height=90)
                with cc2:
                    sev_opts = ["Critical", "High", "Medium", "Low"]
                    new_sev = st.selectbox("Severity", sev_opts,
                        index=sev_opts.index(r["severity"]) if r["severity"] in sev_opts else 2,
                        key=f"cv_sev_{r['id']}")
                    new_eta = st.text_input("ETA", key=f"cv_eta_{r['id']}",
                                            placeholder="e.g. 3 hours")
                st.markdown("**Fault location** *(cascade works — pick region first)*")
                new_loc = location_inputs(f"cv_{r['id']}_loc",
                    defaults=r.get("location") if isinstance(r.get("location"), dict) else {})
                new_area = st.text_input("Additional affected areas",
                                         key=f"cv_area_{r['id']}")
                force = st.checkbox("🔴 Force popup", key=f"cv_force_{r['id']}")
                send_email, send_wa = channel_options_ui(data, f"cv_{r['id']}")
                if st.button("🚀 Convert to Active Outage", type="primary",
                             use_container_width=True, key=f"cv_btn_{r['id']}"):
                    outage = {"id": data["next_outage_id"], "issue": new_issue,
                              "description": new_desc, "severity": new_sev,
                              "affected_services": new_area, "location": new_loc,
                              "images": r.get("images", []),
                              "estimated_resolution": new_eta,
                              "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              "status": "active", "updates": []}
                    data["next_outage_id"] += 1
                    data["active_outages"].append(outage)
                    for rr in data["reports"]:
                        if rr["id"] == r["id"]:
                            rr["status"] = "converted"
                            rr["outage_id"] = outage["id"]
                            rr["admin_note"] = "Converted to active outage"
                    msg = (f"⚡ CONFIRMED OUTAGE — {new_issue}\n"
                           f"Severity: {new_sev}\n"
                           f"Location: {format_location(new_loc)}\n"
                           f"Description: {new_desc}\n"
                           f"Additional areas: {new_area}\nETA: {new_eta}")
                    add_notification(data, msg, force_popup=force,
                                     outage_id=outage["id"])
                    storage.save(data)
                    st.success(f"✅ Outage #{outage['id']} created from report #{r['id']}.")
                    if send_email or send_wa:
                        report = dispatch_to_channels(data, msg,
                            subject=f"⚡ SOCADEL Outage: {new_issue[:60]}",
                            send_email_flag=send_email, send_wa_flag=send_wa)
                        st.markdown("### 📤 Delivery results")
                        render_dispatch_report(report)
                    st.rerun()
            with tab2:
                if not data["active_outages"]:
                    st.info("No active outages to attach this report to.")
                else:
                    with st.form(f"update_form_{r['id']}"):
                        options = {f"#{o['id']} — {o['issue'][:50]}": o["id"]
                                   for o in data["active_outages"]}
                        pick = st.selectbox("Attach to outage", list(options.keys()),
                                            key=f"at_pick_{r['id']}")
                        note = st.text_area("Update message",
                            value=f"Field report from {r['reporter_name']} "
                                  f"({format_location(r.get('location'))}): {r['description']}",
                            key=f"at_note_{r['id']}", height=90)
                        if st.form_submit_button("📌 Add as Update",
                                                 use_container_width=True):
                            outage_id = options[pick]
                            for oo in data["active_outages"]:
                                if oo["id"] == outage_id:
                                    oo["updates"].append({
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "message": note})
                                    break
                            for rr in data["reports"]:
                                if rr["id"] == r["id"]:
                                    rr["status"] = "acknowledged"
                                    rr["outage_id"] = outage_id
                                    rr["admin_note"] = "Attached as update"
                            add_notification(data, f"📌 UPDATE: {note}",
                                             outage_id=outage_id)
                            storage.save(data)
                            st.success("Report attached as an update.")
                            st.rerun()
            with tab3:
                with st.form(f"dismiss_form_{r['id']}"):
                    reason = st.text_input("Reason (optional)",
                                           key=f"ds_reason_{r['id']}")
                    if st.form_submit_button("🗑️ Dismiss Report",
                                             use_container_width=True):
                        for rr in data["reports"]:
                            if rr["id"] == r["id"]:
                                rr["status"] = "dismissed"
                                rr["admin_note"] = reason or "Dismissed by admin"
                        storage.save(data)
                        st.success("Report dismissed.")
                        st.rerun()

def admin_create_outage(data, storage):
    st.subheader("📝 Create New Outage Report")
    c1, c2 = st.columns(2)
    with c1:
        issue = st.selectbox("Issue Type", [
            "Complete Power Outage (Blackout)",
            "Partial Power Outage", "Frequent Fluctuations",
            "Low Voltage", "High Voltage / Surge",
            "Transformer Failure", "Damaged / Downed Power Lines",
            "Fallen Electric Pole", "Vandalized Equipment",
            "Cable Theft", "Substation Fault", "Short Circuit",
            "Fire Hazard", "Meter Malfunction",
            "Meter Reading Dispute", "Illegal Connection",
            "Load Shedding", "Planned Maintenance",
            "Billing / Payment Issue", "Other"], key="ao_issue")
        description = st.text_area("Detailed Description", height=120,
                                   key="ao_description")
    with c2:
        severity = st.selectbox("Severity", ["Critical", "High", "Medium", "Low"],
                                key="ao_severity")
        eta = st.text_input("Estimated Restoration",
                            placeholder="e.g. 3 hours", key="ao_eta")
    st.markdown("**Fault location** *(region → division → sub-division cascade)*")
    loc = location_inputs("ao_loc")
    st.caption(f"Selected: **{format_location(loc)}**")
    affected = st.text_input("Additional affected areas / notes", key="ao_affected")
    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3: send_notif = st.checkbox("Send in-app notification", value=True,
                                      key="ao_send_notif")
    with c4: force_popup = st.checkbox("🔴 Force popup on all users", value=False,
                                       key="ao_force_popup")
    st.markdown("**External channels**")
    send_email, send_wa = channel_options_ui(data, "ao")
    images = capture_images("admin_outage")
    if st.button("🚀 Create Outage", type="primary",
                 use_container_width=True, key="ao_submit"):
        if not description:
            st.error("Please provide a description.")
        else:
            outage = {"id": data["next_outage_id"], "issue": issue,
                      "description": description, "severity": severity,
                      "affected_services": affected, "location": loc,
                      "images": images,
                      "estimated_resolution": eta,
                      "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      "status": "active", "updates": []}
            data["next_outage_id"] += 1
            data["active_outages"].append(outage)
            msg = (f"⚡ NEW OUTAGE — {issue}\nSeverity: {severity}\n"
                   f"Location: {format_location(loc)}\nDescription: {description}\n"
                   f"Additional areas: {affected}\nETA: {eta}")
            if send_notif:
                add_notification(data, msg, force_popup=force_popup,
                                 outage_id=outage["id"])
            storage.save(data)
            st.success(f"✅ Outage #{outage['id']} created.")
            if send_email or send_wa:
                report = dispatch_to_channels(data, msg,
                    subject=f"⚡ SOCADEL Outage: {issue[:60]}",
                    send_email_flag=send_email, send_wa_flag=send_wa)
                st.markdown("### 📤 Delivery results")
                render_dispatch_report(report)
            st.rerun()

def admin_manage_outages(data, storage):
    st.subheader("📋 Manage Active Outages")
    if not data["active_outages"]:
        st.info("No active outages to manage.")
        return
    for o in list(data["active_outages"]):
        with st.expander(f"#{o['id']} — {o['issue']}", expanded=True):
            st.markdown(f'<div class="loc-badge">📍 {format_location(o.get("location"))}</div>',
                        unsafe_allow_html=True)
            st.write(f"**Severity:** {o['severity']}")
            st.write(f"**Description:** {o['description']}")
            st.write(f"**Additional affected areas:** {o.get('affected_services') or '—'}")
            st.write(f"**Started:** {o['start_time']}")
            render_images(o.get("images", []))
            for u in o["updates"]:
                st.info(f"🕐 {u['timestamp']} — {u['message']}")
            st.markdown("---")
            update_msg = st.text_area("Add update", key=f"upd_{o['id']}")
            if st.button("📌 Post Update", key=f"btn_upd_{o['id']}"):
                if update_msg:
                    for oo in data["active_outages"]:
                        if oo["id"] == o["id"]:
                            oo["updates"].append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "message": update_msg})
                    add_notification(data,
                        f"📌 UPDATE on Outage #{o['id']}: {update_msg}",
                        outage_id=o["id"])
                    storage.save(data)
                    st.success("Update posted.")
                    st.rerun()
            st.markdown("---")
            resolution = st.text_area("Resolution message", key=f"res_{o['id']}")
            if st.button(f"✅ Resolve Outage #{o['id']}",
                         key=f"btn_res_{o['id']}", type="primary"):
                if resolution:
                    for oo in data["active_outages"]:
                        if oo["id"] == o["id"]:
                            oo["status"] = "resolved"
                            oo["resolution_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            oo["resolution_message"] = resolution
                            data["past_outages"].append(oo)
                            data["active_outages"].remove(oo)
                            break
                    msg = f"✅ POWER RESTORED — {resolution}"
                    add_notification(data, msg, outage_id=o["id"])
                    storage.save(data)
                    st.success("Outage resolved.")
                    st.markdown("### 📤 Broadcast resolution?")
                    with st.form(f"resolve_broadcast_{o['id']}"):
                        send_email, send_wa = channel_options_ui(data, f"res_{o['id']}")
                        if st.form_submit_button("Send resolution broadcast"):
                            report = dispatch_to_channels(data, msg,
                                subject=f"✅ Power Restored — Outage #{o['id']}",
                                send_email_flag=send_email, send_wa_flag=send_wa)
                            render_dispatch_report(report)
                    st.rerun()

def admin_send_notification(data, storage):
    st.subheader("📢 Send Notification")
    with st.form("send_notification_form"):
        c1, c2 = st.columns(2)
        with c1:
            ntype = st.selectbox("Type", ["General", "Maintenance", "Load Shedding",
                                          "Billing", "System Status", "Emergency"])
        with c2:
            severity = st.selectbox("Severity", ["Low", "Medium", "High", "Critical"])
        message = st.text_area("Message", height=150)
        force = st.checkbox("🔴 Force popup in-app on all users")
        st.markdown("**External channels**")
        send_email, send_wa = channel_options_ui(data, "sn")
        if st.form_submit_button("📤 Send", use_container_width=True):
            if not message:
                st.error("Please enter a message.")
            else:
                body = f"{ntype} [{severity}]: {message}"
                add_notification(data, body, force_popup=force)
                storage.save(data)
                st.success("✅ Sent in-app." + (" (FORCE POPUP)" if force else ""))
                if send_email or send_wa:
                    report = dispatch_to_channels(data, body,
                        subject=f"📢 SOCADEL: {ntype} [{severity}]",
                        send_email_flag=send_email, send_wa_flag=send_wa)
                    st.markdown("### 📤 Delivery results")
                    render_dispatch_report(report)
                st.rerun()

def admin_force_popup(data, storage):
    st.subheader("🔴 Force Emergency Popup")
    st.warning("⚠️ Full-screen alert on all connected users.")
    with st.form("force_popup_form"):
        title = st.text_input("Popup Title", "🚨 SOCADEL URGENT NOTIFICATION")
        message = st.text_area("Message", height=150)
        severity = st.selectbox("Severity",
                                ["Critical", "High", "Medium", "Low"], index=0)
        st.markdown("**External channels**")
        send_email, send_wa = channel_options_ui(data, "fp")
        if st.form_submit_button("🔴 SEND FORCE POPUP",
                                 type="primary", use_container_width=True):
            if not message:
                st.error("Please enter a message.")
            else:
                body = f"{title}\n\n{message}\n\nSeverity: {severity}"
                add_notification(data, body, force_popup=True)
                storage.save(data)
                st.error("🔴 FORCE POPUP SENT.")
                st.balloons()
                if send_email or send_wa:
                    report = dispatch_to_channels(data, body,
                        subject=f"🚨 SOCADEL URGENT: {title}",
                        send_email_flag=send_email, send_wa_flag=send_wa)
                    st.markdown("### 📤 Delivery results")
                    render_dispatch_report(report)

def admin_history(data):
    st.subheader("📜 Outage History")
    if data["past_outages"]:
        df = pd.DataFrame(data["past_outages"])
        keep = ["id", "issue", "severity", "start_time",
                "resolution_time", "resolution_message"]
        df = df[[c for c in keep if c in df.columns]]
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 Download CSV",
                           df.to_csv(index=False).encode("utf-8"),
                           f"socadel_history_{datetime.now().strftime('%Y%m%d')}.csv",
                           "text/csv", use_container_width=True)
    else:
        st.info("No resolved outages yet.")
    st.markdown("---")
    st.subheader("📥 All Reports")
    if data["reports"]:
        rows = [{"id": r["id"], "reporter": r["reporter_name"],
                 "role": r["reporter_role"], "issue": r["issue"],
                 "location": format_location(r.get("location")),
                 "status": r["status"], "created_at": r["created_at"],
                 "photos": len(r.get("images", [])),
                 "admin_note": r.get("admin_note", "")}
                for r in data["reports"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No reports submitted yet.")

def admin_users(data):
    st.subheader("👥 Users & Contacts")
    tab1, tab2 = st.tabs(["🟢 Online now", "📇 Registered contacts"])
    with tab1:
        st.metric("Total", len(data["clients"]))
        if data["clients"]:
            rows = [{"Name": v.get("name", ""), "Role": v.get("role", ""),
                     "Worker ID": v.get("worker_id", ""),
                     "Location": format_location(v.get("location")),
                     "Last seen": v.get("last_seen", "")}
                    for v in data["clients"].values()]
            st.dataframe(pd.DataFrame(rows).sort_values("Last seen", ascending=False),
                         use_container_width=True)
        else:
            st.info("No users currently online.")
    with tab2:
        contacts = get_all_recipients(data)
        st.metric("Total registered", len(contacts))
        if contacts:
            rows = [{"Name": c["name"], "Role": c["role"],
                     "Email": c["email"] or "—",
                     "WhatsApp": c["phone"] or "—",
                     "Email OK": "✅" if (c["email"] and "@" in c["email"]) else "—",
                     "Phone OK": "✅" if normalize_phone(c["phone"]) else "—"}
                    for c in contacts]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.download_button("📥 Export contacts CSV",
                               pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
                               "socadel_contacts.csv", "text/csv",
                               use_container_width=True)
        else:
            st.info("No contacts registered yet.")

def admin_channels(data, storage):
    st.subheader("🔔 Notification Channels")
    email_ok = is_email_configured(); wa_ok = is_whatsapp_configured()
    c1, c2 = st.columns(2)
    with c1:
        if email_ok:
            cfg = get_email_config()
            st.success(f"📧 **Email: ON**\n\nServer: `{cfg['host']}:{cfg['port']}`\n\n"
                       f"From: `{cfg['from']}`")
        else:
            st.error("📧 **Email: OFF**\n\nAdd `SMTP_HOST`, `SMTP_PORT`, "
                     "`SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` to Streamlit secrets.")
    with c2:
        if wa_ok:
            st.success("💬 **WhatsApp (Twilio): ON**")
        else:
            st.warning("💬 **WhatsApp: LINK MODE**\n\nAdd `TWILIO_ACCOUNT_SID`, "
                       "`TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` for auto-send.")
    st.markdown("---")
    st.subheader("🧪 Test channels")
    recipients = get_all_recipients(data)
    st.caption(f"{len(recipients)} registered contact(s).")
    t1, t2 = st.columns(2)
    with t1:
        with st.form("test_email_form"):
            test_to = st.text_input("Send test email to",
                                    value=st.session_state.get("email", ""))
            if st.form_submit_button("📧 Send Test Email"):
                if not is_email_configured():
                    st.error("Email not configured.")
                elif not test_to:
                    st.error("Enter an email address.")
                else:
                    ok, msg = send_email_broadcast([test_to],
                        "SOCADEL — Test Email",
                        "✅ Test email from your SOCADEL Outage System.")
                    (st.success if ok else st.error)(msg)
    with t2:
        with st.form("test_wa_form"):
            test_phone = st.text_input("Send test WhatsApp to",
                                       value=st.session_state.get("phone", ""))
            if st.form_submit_button("💬 Send Test WhatsApp"):
                if not test_phone:
                    st.error("Enter a phone number.")
                elif is_whatsapp_configured():
                    ok, msg = send_whatsapp_twilio(test_phone,
                        "✅ Test WhatsApp from SOCADEL Outage System.")
                    (st.success if ok else st.error)(msg)
                else:
                    p = normalize_phone(test_phone)
                    text = urllib.parse.quote(
                        "✅ Test WhatsApp from SOCADEL Outage System.")
                    st.info("Twilio not configured — open this link:")
                    st.markdown(f"[💬 Open WhatsApp test](https://wa.me/{p.lstrip('+')}?text={text})")
    st.markdown("---")
    st.subheader("📇 Registered contacts")
    if recipients:
        rows = [{"Name": r["name"], "Role": r["role"],
                 "Email": r["email"] or "—", "WhatsApp": r["phone"] or "—"}
                for r in recipients]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.info("No contacts yet.")
    st.markdown("---")
    with st.expander("🗑️ Danger zone — clear all contacts"):
        confirm = st.checkbox("I understand — clear all contacts permanently",
                              key="clr_contacts_ck")
        if st.button("Clear all contacts", type="primary", disabled=not confirm):
            data["contacts"] = {}; storage.save(data)
            st.success("All contacts cleared."); st.rerun()

# ============================================
# SUPERVISOR PORTAL
# ============================================
def show_supervisor():
    storage = get_storage(); data = storage.load(); cleanup_clients(data)
    touch_user(data, "supervisor", st.session_state.display_name)
    register_contact(data, st.session_state.client_id, st.session_state.display_name,
                     "supervisor", st.session_state.email, st.session_state.phone,
                     current_user_location(), st.session_state.worker_id)
    storage.save(data)
    popup_shown = check_force_popup(data)

    with st.sidebar:
        st.markdown("### 👷 Field Portal")
        st.caption(f"👤 {st.session_state.display_name} ({st.session_state.worker_id})")
        st.caption(f"📍 {format_location(current_user_location())}")
        if st.session_state.email: st.caption(f"📧 {st.session_state.email}")
        if st.session_state.phone: st.caption(f"💬 {st.session_state.phone}")
        menu = st.radio("Navigation", ["📊 Overview", "📝 Report Issue",
                                        "📋 My Reports", "📢 All Field Reports",
                                        "📢 Announcements", "👤 My Profile"])
        st.markdown("---")
        st.caption(storage.backend_name())
        if st.button("🚪 Logout", use_container_width=True): do_logout()

    if not popup_shown and HAS_AUTOREFRESH and menu in ("📊 Overview", "📢 Announcements", "📢 All Field Reports"):
        st_autorefresh(interval=5000, key="sup_autorefresh")

    st.markdown(f"""
    <div class="main-header">
        <h1 style="margin:0;">⚡ SOCADEL — Field Supervisor</h1>
        <p style="margin:5px 0 0 0; opacity:0.9;">Welcome, {st.session_state.display_name} · {st.session_state.worker_id}</p>
        <p style="margin:5px 0 0 0; opacity:0.8; font-size:13px;">📍 {format_location(current_user_location())}</p>
    </div>
    """, unsafe_allow_html=True)

    if   menu == "📊 Overview":          sup_overview(data)
    elif menu == "📝 Report Issue":      sup_report(data, storage)
    elif menu == "📋 My Reports":        sup_my_reports(data)
    elif menu == "📢 All Field Reports": sup_all_reports(data)
    elif menu == "📢 Announcements":     sup_announcements(data)
    elif menu == "👤 My Profile":        sup_profile(data, storage)

def sup_overview(data):
    st.subheader("📡 Current Power Status")
    viewer_loc = current_user_location()
    st.markdown("---")
    search_loc = outage_area_selector(data, "sup_overview", viewer_loc)
    st.caption(f"Showing outages in: **{format_location(search_loc)}**")
    st.markdown("---")

    visible = filter_outages_for_viewer(data["active_outages"], viewer_loc, search_loc)
    if visible:
        st.error(f"🔴 {len(visible)} active outage(s) in this area")
        for o in visible:
            with st.expander(f"⚡ {o['issue']}  [{o['severity']}]", expanded=True):
                st.markdown(f'<div class="loc-badge">📍 {format_location(o.get("location"))}</div>',
                            unsafe_allow_html=True)
                st.write(f"**Additional affected areas:** {o.get('affected_services') or '—'}")
                st.write(f"**Started:** {o['start_time']}")
                st.write(f"**ETA:** {o['estimated_resolution']}")
                st.write(f"**Description:** {o['description']}")
                render_images(o.get("images", []))
                for u in o["updates"][-3:]:
                    st.info(f"🕐 {u['timestamp']} — {u['message']}")
    else:
        st.success(f"✅ No active outages in {format_location(search_loc)}.")
    st.markdown("---")
    pending = [r for r in data["reports"] if r["status"] == "pending"]
    st.metric("📥 Reports awaiting admin review", len(pending))

def sup_report(data, storage):
    st.subheader("📝 Submit Field Report")
    c1, c2 = st.columns(2)
    with c1:
        issue = st.selectbox("Issue type", [
            "Blackout", "Partial outage", "Transformer failure",
            "Fallen pole", "Cable theft", "Low voltage",
            "Meter issue", "Other"], key="sup_rep_issue")
        description = st.text_area("What did you observe?", height=120,
                                   key="sup_rep_desc")
    with c2:
        severity = st.selectbox("Severity",
                                ["Critical", "High", "Medium", "Low"],
                                key="sup_rep_sev")
    st.markdown("**Location of the fault** *(defaults to your base — cascade works)*")
    loc = location_inputs("sup_rep_loc", defaults=current_user_location())
    images = capture_images("sup_report")
    if st.button("📤 Submit Report", type="primary",
                 use_container_width=True, key="sup_rep_submit"):
        if not description:
            st.error("Please describe the issue.")
        else:
            r = create_report(data, "supervisor", st.session_state.display_name,
                              issue, description, severity, loc, images=images)
            storage.save(data)
            st.success(f"✅ Report #{r['id']} submitted with {len(images)} photo(s).")
            st.rerun()

def sup_my_reports(data):
    st.subheader("📋 My Reports")
    mine = [r for r in data["reports"] if r["reporter_id"] == st.session_state.client_id]
    if not mine:
        st.info("You haven't submitted any reports yet."); return
    for r in reversed(mine):
        icon = {"pending": "🟡 Pending", "converted": "🟢 Converted",
                "acknowledged": "🔵 Acknowledged", "dismissed": "⚫ Dismissed"
                }.get(r["status"], r["status"])
        with st.expander(f"#{r['id']} — {r['issue']}  ·  {icon}"):
            st.markdown(f'<div class="loc-badge">📍 {format_location(r.get("location"))}</div>',
                        unsafe_allow_html=True)
            st.write(f"**Severity:** {r['severity']}")
            st.write(f"**Submitted:** {r['created_at']}")
            st.write(f"**Description:** {r['description']}")
            render_images(r.get("images", []))
            if r["admin_note"]: st.info(f"📌 Admin note: {r['admin_note']}")

def sup_all_reports(data):
    st.subheader("📢 All Field Reports")
    if not data["reports"]:
        st.info("No reports submitted yet."); return
    for r in reversed(data["reports"][-30:]):
        icon = "👷" if r["reporter_role"] == "supervisor" else "🏠"
        si = {"pending": "🟡", "converted": "🟢",
              "acknowledged": "🔵", "dismissed": "⚫"}.get(r["status"], "•")
        with st.expander(f"{si} #{r['id']} — {r['issue']}  ·  {icon} {r['reporter_name']}"):
            st.markdown(f'<div class="loc-badge">📍 {format_location(r.get("location"))}</div>',
                        unsafe_allow_html=True)
            st.write(f"**Severity:** {r['severity']}")
            st.write(f"**Submitted:** {r['created_at']}")
            st.write(f"**Description:** {r['description']}")
            render_images(r.get("images", []))
            if r["admin_note"]: st.caption(f"Admin: {r['admin_note']}")

def sup_announcements(data):
    st.subheader("📢 Announcements")
    if not data["notifications"]:
        st.info("No announcements yet."); return
    for n in reversed(data["notifications"][-15:]):
        if n.get("force_popup"):
            st.warning(f"🔴 **{n['timestamp']}** — {n['message']}")
        else:
            st.info(f"📢 **{n['timestamp']}** — {n['message']}")

def sup_profile(data, storage):
    st.subheader("👤 My Profile")
    with st.form("sup_profile_form"):
        name  = st.text_input("Full name", value=st.session_state.display_name)
        email = st.text_input("Email", value=st.session_state.email)
        phone = st.text_input("WhatsApp number", value=st.session_state.phone)
        if st.form_submit_button("💾 Save", type="primary"):
            st.session_state.display_name = name.strip()
            st.session_state.email = email.strip()
            st.session_state.phone = phone.strip()
            register_contact(data, st.session_state.client_id,
                             st.session_state.display_name, "supervisor",
                             st.session_state.email, st.session_state.phone,
                             current_user_location(), st.session_state.worker_id)
            storage.save(data)
            st.success("Profile updated."); st.rerun()

# ============================================
# CLIENT PORTAL
# ============================================
def show_client():
    storage = get_storage(); data = storage.load(); cleanup_clients(data)
    touch_user(data, "client", st.session_state.display_name)
    register_contact(data, st.session_state.client_id, st.session_state.display_name,
                     "client", st.session_state.email, st.session_state.phone,
                     current_user_location())
    storage.save(data)
    popup_shown = check_force_popup(data)

    with st.sidebar:
        st.markdown("### 🏠 Client Portal")
        st.caption(f"👤 {st.session_state.display_name}")
        st.caption(f"📍 {format_location(current_user_location())}")
        if st.session_state.email: st.caption(f"📧 {st.session_state.email}")
        if st.session_state.phone: st.caption(f"💬 {st.session_state.phone}")
        menu = st.radio("Navigation", ["📊 Power Status", "📝 Report Issue",
                                        "📋 My Reports", "📢 Announcements",
                                        "👤 My Profile"])
        st.markdown("---")
        st.caption(storage.backend_name())
        if st.button("🚪 Logout", use_container_width=True): do_logout()

    if not popup_shown and HAS_AUTOREFRESH and menu in ("📊 Power Status", "📢 Announcements"):
        st_autorefresh(interval=5000, key="cli_autorefresh")

    st.markdown(f"""
    <div class="main-header">
        <h1 style="margin:0;">⚡ SOCADEL — Power Status</h1>
        <p style="margin:5px 0 0 0; opacity:0.9;">Welcome, {st.session_state.display_name}</p>
        <p style="margin:5px 0 0 0; opacity:0.8; font-size:13px;">📍 {format_location(current_user_location())}</p>
    </div>
    """, unsafe_allow_html=True)

    if   menu == "📊 Power Status":  cli_status(data)
    elif menu == "📝 Report Issue":  cli_report(data, storage)
    elif menu == "📋 My Reports":    cli_my_reports(data)
    elif menu == "📢 Announcements": cli_announcements(data)
    elif menu == "👤 My Profile":    cli_profile(data, storage)

def cli_status(data):
    st.subheader("📡 Current Power Status")
    viewer_loc = current_user_location()
    st.markdown("---")
    search_loc = outage_area_selector(data, "cli_status", viewer_loc)
    st.caption(f"Showing outages in: **{format_location(search_loc)}**")
    st.markdown("---")

    visible = filter_outages_for_viewer(data["active_outages"], viewer_loc, search_loc)
    if visible:
        st.error(f"🔴 {len(visible)} active outage(s) in this area")
        for o in visible:
            with st.expander(f"⚡ {o['issue']}", expanded=True):
                st.markdown(f'<div class="loc-badge">📍 {format_location(o.get("location"))}</div>',
                            unsafe_allow_html=True)
                st.write(f"**Severity:** {o['severity']}")
                st.write(f"**Additional affected areas:** {o.get('affected_services') or '—'}")
                st.write(f"**Started:** {o['start_time']}")
                st.write(f"**ETA:** {o['estimated_resolution']}")
                st.write(f"**Description:** {o['description']}")
                render_images(o.get("images", []))
                if o["updates"]:
                    st.markdown("**Recent updates:**")
                    for u in o["updates"][-5:]:
                        st.info(f"🕐 {u['timestamp']} — {u['message']}")
    else:
        st.success(f"✅ **Power supply is normal** in {format_location(search_loc)} — no active outages.")

def cli_report(data, storage):
    st.subheader("📝 Report an Issue")
    c1, c2 = st.columns(2)
    with c1:
        issue = st.selectbox("What's the problem?", [
            "Blackout", "Partial outage", "Low voltage",
            "Transformer noise", "Fallen pole", "Meter problem", "Other"],
            key="cli_rep_issue")
        description = st.text_area("Describe the issue", height=120,
                                   key="cli_rep_desc")
    with c2:
        severity = st.selectbox("How bad is it?",
                                ["Critical", "High", "Medium", "Low"],
                                key="cli_rep_sev")
    st.markdown("**Location of the issue** *(defaults to your profile — cascade works)*")
    loc = location_inputs("cli_rep_loc", defaults=current_user_location())
    images = capture_images("cli_report")
    if st.button("📤 Submit Report", type="primary",
                 use_container_width=True, key="cli_rep_submit"):
        if not description:
            st.error("Please describe the issue.")
        else:
            r = create_report(data, "client", st.session_state.display_name,
                              issue, description, severity, loc, images=images)
            storage.save(data)
            st.success(f"✅ Report #{r['id']} submitted with {len(images)} photo(s).")
            st.rerun()

def cli_my_reports(data):
    st.subheader("📋 My Reports")
    mine = [r for r in data["reports"] if r["reporter_id"] == st.session_state.client_id]
    if not mine:
        st.info("You haven't reported any issues yet."); return
    for r in reversed(mine):
        icon = {"pending": "🟡 Pending review",
                "converted": "🟢 Confirmed by SOCADEL",
                "acknowledged": "🔵 Being handled",
                "dismissed": "⚫ Closed"}.get(r["status"], r["status"])
        with st.expander(f"#{r['id']} — {r['issue']}  ·  {icon}"):
            st.markdown(f'<div class="loc-badge">📍 {format_location(r.get("location"))}</div>',
                        unsafe_allow_html=True)
            st.write(f"**Submitted:** {r['created_at']}")
            st.write(f"**Description:** {r['description']}")
            render_images(r.get("images", []))
            if r["admin_note"]: st.info(f"📌 SOCADEL: {r['admin_note']}")

def cli_announcements(data):
    st.subheader("📢 Announcements")
    if not data["notifications"]:
        st.info("No announcements yet."); return
    for n in reversed(data["notifications"][-15:]):
        if n.get("force_popup"):
            st.warning(f"🔴 **{n['timestamp']}** — {n['message']}")
        else:
            st.info(f"📢 **{n['timestamp']}** — {n['message']}")

def cli_profile(data, storage):
    st.subheader("👤 My Profile")
    with st.form("cli_profile_form"):
        name  = st.text_input("Your name", value=st.session_state.display_name)
        email = st.text_input("Email", value=st.session_state.email)
        phone = st.text_input("WhatsApp number", value=st.session_state.phone)
        if st.form_submit_button("💾 Save", type="primary"):
            st.session_state.display_name = name.strip()
            st.session_state.email = email.strip()
            st.session_state.phone = phone.strip()
            register_contact(data, st.session_state.client_id,
                             st.session_state.display_name, "client",
                             st.session_state.email, st.session_state.phone,
                             current_user_location())
            storage.save(data)
            st.success("Profile updated."); st.rerun()

# ============================================
# ROUTER
# ============================================
r = st.session_state.role
if   r is None:                show_landing()
elif r == "admin_login":       show_admin_login()
elif r == "supervisor_login":  show_supervisor_login()
elif r == "client_login":      show_client_login()
elif r == "admin":             show_admin()
elif r == "supervisor":        show_supervisor()
elif r == "client":            show_client()