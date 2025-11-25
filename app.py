# app.py
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import time

# Optional AI client
try:
    import openai
except Exception:
    openai = None

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------------- Constants ----------------
MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

COURSE_PDF_PATH = "/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf"

MYTH_LIST = [
    "Zeus","Hera","Athena","Apollo","Artemis","Aphrodite","Hermes","Dionysus","Ares","Hephaestus",
    "Poseidon","Hades","Demeter","Persephone","Hestia","Heracles","Perseus","Achilles","Odysseus",
    "Theseus","Jason","Medusa","Minotaur","Sirens","Cyclops","Centaur","Prometheus","Orpheus",
    "Eros","Nike","The Muses","The Fates","The Graces","Hecate","Atlas","Pandora"
]

FIXED_BIOS = {
    "Zeus": "Zeus is the king of the Olympian gods, ruler of the sky and thunder. Often shown with a thunderbolt and eagle.",
    "Athena": "Athena (Pallas Athena) is goddess of wisdom, craft, and strategic warfare. Often shown armored with an owl as symbol.",
    "Medusa": "Medusa is one of the Gorgons whose gaze could turn viewers to stone; a complex symbol in ancient and modern art.",
    "Perseus": "Perseus is the hero who beheaded Medusa and rescued Andromeda; often shown with winged sandals and reflecting shield."
}

# ---------------- Helpers: MET ----------------
@st.cache_data(show_spinner=False)
def met_search_ids(query: str, max_results: int = 100):
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=10)
        r.raise_for_status()
        ids = r.json().get("objectIDs") or []
        return ids[:max_results]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def met_get_object_cached(object_id: int):
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def met_get_object(object_id: int):
    return met_get_object_cached(object_id)

def fetch_image_from_meta(meta):
    candidates = []
    if meta.get("primaryImageSmall"):
        candidates.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"):
        candidates.append(meta["primaryImage"])
    if meta.get("additionalImages"):
        try:
            for u in meta["additionalImages"]:
                candidates.append(u)
        except Exception:
            pass
    for url in candidates:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")
        except Exception:
            continue
    return None

def generate_aliases(name: str):
    mapping = {
        "Athena": ["Pallas Athena", "Minerva"],
        "Zeus": ["Jupiter"],
        "Aphrodite": ["Venus"],
        "Hermes": ["Mercury"],
        "Medusa": ["Gorgon"],
        "Heracles": ["Hercules"],
        "Dionysus": ["Bacchus"],
        "Persephone": ["Proserpina"]
    }
    aliases = [name]
    if name in mapping:
        aliases += mapping[name]
    aliases += [f"{name} Greek", f"{name} myth", f"{name} deity"]
    return list(dict.fromkeys(aliases))

# ---------------- OpenAI wrappers (optional) ----------------
def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or openai is None:
        return None
    try:
        openai.api_key = key
        return openai
    except Exception:
        return None

def chat_complete(client, prompt, max_tokens=400, temperature=0.2, system="You are a museum curator."):
    if client is None:
        return "OpenAI client not configured. Paste your API key on Home."
    try:
        resp = client.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"

def expand_bio_ai(client, name, base):
    prompt = f"Expand the short bio about {name} into a concise, museum-friendly 3-paragraph introduction.\n\nShort bio:\n{base}"
    return chat_complete(client, prompt, max_tokens=500)

def generate_overview(client, meta):
    title = meta.get("title") or meta.get("objectName") or "Untitled"
    prompt = f"Write a 3-sentence public-facing overview for the artwork titled '{title}', using metadata: {meta}."
    return chat_complete(client, prompt, max_tokens=220)

def generate_context(client, meta):
    prompt = f"Using metadata: {meta}. Provide 4-6 sentences about the artwork's historical and artistic context."
    return chat_complete(client, prompt, max_tokens=350)

def generate_iconography(client, meta):
    prompt = f"Analyze iconography for this artwork using metadata: {meta}. Mention mythic elements and symbols."
    return chat_complete(client, prompt, max_tokens=350)

def ai_answer_detail(client, question, meta):
    prompt = f"Visitor asked: '{question}' about artwork titled '{meta.get('title')}'. Provide a concise curator response and note uncertainty if speculative."
    return chat_complete(client, prompt, max_tokens=250)

def ai_style_match(client, note):
    prompt = f"User sketch/photo described as: '{note}'. Explain distinguishing features for Archaic black-figure, Classical marble, and Hellenistic composition; give visual checks."
    return chat_complete(client, prompt, max_tokens=300)

def ai_myth_identifier(client, desc):
    prompt = f"Identify which Greek deity/hero/creature best matches this description: '{desc}'. Explain visual cues and suggest two MET search terms."
    return chat_complete(client, prompt, max_tokens=300)

def ai_personality_archetype(client, answers):
    prompt = f"Map these quiz answers to a Greek myth archetype and explain: {answers}. Provide archetype, short psych explanation, and three recommended artwork themes."
    return chat_complete(client, prompt, max_tokens=400)

# ---------------- UI Layout ----------------
tabs = st.tabs(["Home","Greek Myth Works & Deities","Interactive Art Zone"])

# ---------------- HOME ----------------
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
**What this app does:**  
Explore Greek gods, heroes, mythic creatures, and related works from The MET, including artworks, manuscripts, and books. Receive curator-level AI interpretations (optional).  

**Quick guide**  
1. Open **Greek Myth Works & Deities**, choose a figure or browse top works.  
2. Click **View Details** on a card to expand artwork metadata, historical context, and AI-generated analysis.  
3. Use **Interactive Art Zone** for sketch analysis, myth identification, or archetype quizzes.  

**Notes:**  
- Top famous works are shown by default per figure.  
- Detailed info appears in **expandable sections**, keeping the interface clean.  
- AI features require an OpenAI API key.
    """)
    st.subheader("OpenAI API Key (session only)")
    key = st.text_input("Paste your OpenAI API Key (sk-...):", type="password", key="home_api_input")
    if st.button("Save API Key", key="save_api_btn"):
        if key:
            st.session_state["OPENAI_API_KEY"] = key
            st.success("API Key saved to session. AI features enabled.")
        else:
            st.warning("Please paste a valid API key.")

# ---------------- GREEK MYTH WORKS & DEITIES ----------------
with tabs[1]:
    st.header("Greek Myth Works & Deities")
    selected = st.selectbox("Choose a figure (optional):", ["Top Famous Works"] + MYTH_LIST, key="deity_select")
    client = get_openai_client()

    # Fetch IDs
    if st.button("Fetch Works", key="fetch_deity_btn"):
        if selected == "Top Famous Works":
            aliases = ["Greek Myth"]  # search for top famous works
        else:
            aliases = generate_aliases(selected)
        all_ids = []
        for alias in aliases:
            ids = met_search_ids(alias, 100)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
        if not all_ids:
            st.info("No works found.")
            st.session_state.pop("thumbs_data", None)
        else:
            thumbs = []
            progress = st.progress(0)
            total = max(1, len(all_ids))
            for i, oid in enumerate(all_ids):
                meta = met_get_object(oid)
                if meta:
                    img = fetch_image_from_meta(meta)
                    if img:
                        thumbs.append((oid, meta, img))
                progress.progress(min(100, int((i+1)/total*100)))
                time.sleep(0.01)
            progress.empty()
            if not thumbs:
                st.info("Found works but none had accessible images.")
                st.session_state["thumbs_data"] = []
            else:
                st.session_state["thumbs_data"] = thumbs
                st.success(f"Loaded {len(thumbs)} artworks with images.")

    # Display cards
    thumbs = st.session_state.get("thumbs_data", [])
    if thumbs:
        per_page = st.number_input("Thumbnails per page", min_value=8, max_value=48, value=24, step=4)
        pages = math.ceil(len(thumbs)/per_page)
        page = st.number_input("Gallery page", min_value=1, max_value=max(1,pages), value=1)
        start = (page-1)*per_page
        page_items = thumbs[start:start+per_page]

        rows = math.ceil(len(page_items)/4)
        for r in range(rows):
            cols = st.columns(4)
            for c in range(4):
                idx = r*4 + c
                if idx < len(page_items):
                    oid, meta, img = page_items[idx]
                    with cols[c]:
                        if img:
                            st.image(img.resize((220,220)))
                        st.markdown(f"**{meta.get('title') or 'Untitled'}**")
                        st.markdown(f"*{meta.get('artistDisplayName') or 'Unknown'}*")
                        if st.button("View Details", key=f"detail_{oid}"):
                            st.session_state.setdefault("expanded_items", []).append(oid)

        # Expander for details
        for oid in st.session_state.get("expanded_items", []):
            meta = met_get_object(oid)
            img = fetch_image_from_meta(meta)
            with st.expander(f"{meta.get('title') or 'Untitled'} — Details", expanded=True):
                if img:
                    st.image(img.resize((400,400)))
                st.markdown(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
                st.markdown(f"**Date:** {meta.get('objectDate') or '—'}")
                st.markdown(f"**Medium:** {meta.get('medium') or '—'}")
                st.markdown(f"**Dimensions:** {meta.get('dimensions') or '—'}")
                if meta.get("objectURL"):
                    st.markdown(f"🔗 [View on MET]({meta.get('objectURL')})")
                if client:
                    st.markdown("#### Overview")
                    st.write(generate_overview(client, meta))
                    st.markdown("#### Historical & Artistic Context")
                    st.write(generate_context(client, meta))
                    st.markdown("#### Iconography & Myth Interpretation")
                    st.write(generate_iconography(client, meta))

# ---------------- INTERACTIVE ART ZONE ----------------
with tabs[2]:
    st.header("Interactive Art Zone")
    client = get_openai_client()

    tab_mode = st.radio("Category:", ["Art-based","Myth-based"], key="interactive_mode")
    if tab_mode == "Art-based":
        st.subheader("Detail & Symbolism — Ask about a visual detail")
        if "expanded_items" not in st.session_state or not st.session_state["expanded_items"]:
            st.info("Select an artwork first from the gallery.")
        else:
            # choose first expanded artwork for demo
            meta = met_get_object(st.session_state["expanded_items"][-1])
            q = st.text_input("Ask about a visual detail (e.g., 'What does the owl mean?')", key="detail_q")
            if st.button("Ask detail", key="ask_detail_btn"):
                if client:
                    with st.spinner("Answering..."):
                        st.write(ai_answer_detail(client, q, meta))
                else:
                    st.error("OpenAI client not configured. Enter API key on Home.")

        st.markdown("---")
        st.subheader("Style Analyzer — Upload sketch or photo")
        uploaded = st.file_uploader("Upload sketch/photo", type=["png","jpg","jpeg"], key="style_upload")
        note = st.text_input("Describe sketch (lines, shapes, pose)...", key="style_note")
        if uploaded and st.button("Analyze sketch", key="analyze_sketch_btn"):
            if client:
                image = Image.open(BytesIO(uploaded.getvalue())).convert("RGB")
                st.image(image, caption="Uploaded")
                with st.spinner("Analyzing style..."):
                    st.write(ai_style_match(client, note or "User sketch"))
            else:
                st.error("OpenAI client not configured. Enter API key on Home.")

    else:
        st.subheader("Myth Identifier — one-sentence description")
        desc = st.text_input("Describe a scene or motif:", key="myth_desc")
        if st.button("Identify myth", key="identify_myth_btn"):
            if client:
                with st.spinner("Identifying..."):
                    st.write(ai_myth_identifier(client, desc))
            else:
                st.error("OpenAI client not configured. Enter API key on Home.")

        st.markdown("---")
        st.subheader("Myth Archetype Matcher — (Jungian-style)")
        a1 = st.selectbox("Preferred role in a team:", ["Leader","Supporter","Strategist","Creator"], key="arch_q1")
        a2 = st.selectbox("Which drives you most:", ["Duty","Fame","Pleasure","Wisdom"], key="arch_q2")
        a3 = st.selectbox("You respond to crisis by:", ["Plan","Fight","Flee","Negotiate"], key="arch_q3")
        a4 = st.selectbox("Which image appeals most:", ["Eagle","Owl","Serpent","Laurel"], key="arch_q4")
        if st.button("Get my archetype", key="get_archetype_btn"):
            if client:
                answers = {"role":a1,"drive":a2,"crisis":a3,"image":a4}
                with st.spinner("Mapping archetype..."):
                    st.write(ai_personality_archetype(client, answers))
            else:
                st.error("OpenAI client not configured. Enter API key on Home.")

