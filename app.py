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

# ---------------- UI Layout (tabs) ----------------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone"])

# ---------------- HOME ----------------
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
**What this app does:**  
Explore Greek gods, heroes, and mythic creatures via the MET Museum collections and receive curator-level AI interpretations (optional).

**Quick guide**
1. Open **Greek Deities**, browse deities and see most famous related works.  
2. Click a thumbnail to select an artwork → switch to **Works & Analysis** to see details.  
3. Use **Interactive Art Zone** for close-looking, sketch analysis, myth ID, archetype quiz, or image generation (requires OpenAI key).  
    """)
    st.subheader("OpenAI API Key (session only)")
    key = st.text_input("Paste your OpenAI API Key (sk-...):", type="password", key="home_api_input")
    if st.button("Save API Key", key="save_api_btn"):
        if key:
            st.session_state["OPENAI_API_KEY"] = key
            st.success("API Key saved to session. AI features enabled.")
        else:
            st.warning("Please paste a valid API key.")

# ---------------- GREEK DEITIES ----------------
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    selected = st.selectbox("Choose a figure:", MYTH_LIST, key="deity_select")
    base_bio = FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth with diverse visual representations.")
    st.subheader(f"Short description — {selected}")
    st.write(base_bio)

    client = get_openai_client()
    if st.button("Expand description with AI", key="expand_bio_btn"):
        if client:
            with st.spinner("Expanding..."):
                expanded = expand_bio_ai(client, selected, base_bio)
                st.session_state["expanded_bio"] = expanded
                st.session_state["last_bio_for"] = selected
                st.markdown("### AI Expanded Introduction")
                st.write(expanded)
        else:
            st.error("OpenAI client not configured. Enter API key on Home.")

    if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for")==selected:
        st.markdown("### AI Expanded Introduction (cached)")
        st.write(st.session_state["expanded_bio"])

    st.markdown("#### Related search aliases")
    st.write(generate_aliases(selected))
    st.markdown("---")
    st.write("Most famous works related to Greek Mythology (art, manuscripts, books, and artifacts).")

    max_results = 40
    if "greek_myth_objects" not in st.session_state:
        all_ids = met_search_ids("Greek Mythology", max_results)
        thumbs = []
        for oid in all_ids:
            meta = met_get_object_cached(oid)
            if meta:
                img = fetch_image_from_meta(meta)
                thumbs.append((oid, meta, img))
        st.session_state["greek_myth_objects"] = thumbs

    thumbs = st.session_state.get("greek_myth_objects", [])
    per_page = st.number_input("Thumbnails per page (Greek Myth Gallery)", min_value=8, max_value=48, value=24, step=4, key="greek_myth_per_page")
    pages = math.ceil(len(thumbs)/per_page)
    page = st.number_input("Gallery page", min_value=1, max_value=max(1,pages), value=1, key="greek_myth_gallery_page")
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
                        st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                    else:
                        st.write(f"{meta.get('title') or meta.get('objectName')} ({oid})")
                    if st.button("Select", key=f"deity_select_{oid}"):
                        st.session_state["selected_artwork"] = oid
                        st.success(f"Selected {oid}. Switch to Works & Analysis to view details.")

# ---------------- WORKS & ANALYSIS ----------------
with tabs[2]:
    st.header("Works & Analysis — Greek Mythology Highlights")
    client = get_openai_client()
    # 默认加载希腊神话相关作品
    if "selected_artwork" not in st.session_state:
        thumbs = st.session_state.get("greek_myth_objects", [])
        if thumbs:
            st.session_state["selected_artwork"] = thumbs[0][0]  # 默认第一件

    if "selected_artwork" in st.session_state:
        art_id = st.session_state["selected_artwork"]
        meta = met_get_object_cached(art_id)
        left, right = st.columns([0.5,0.5])

        with left:
            img = fetch_image_from_meta(meta)
            if img:
                max_w = 700
                w,h = img.size
                if w > max_w:
                    img = img.resize((max_w, int(h*(max_w/w))))
                st.image(img, use_column_width=False)
            else:
                st.info("No image available.")

        with right:
            st.subheader("Artwork Information")
            st.markdown(f"### **{meta.get('title') or meta.get('objectName') or 'Untitled'}**")
            st.write(f"**Object ID:** {art_id}")
            st.write(f"**Artist / Author:** {meta.get('artistDisplayName') or meta.get('creditLine') or 'Unknown'}")
            st.write(f"**Culture:** {meta.get('culture') or '—'}")
            st.write(f"**Department:** {meta.get('department') or '—'}")
            st.write(f"**Date:** {meta.get('objectDate') or '—'}")
            st.write(f"**Medium / Type:** {meta.get('medium') or meta.get('objectName') or '—'}")
            st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
            st.write(f"**Classification:** {meta.get('classification') or '—'}")
            st.write(f"**Accession Number:** {meta.get('accessionNumber') or '—'}")
            if meta.get("objectURL"):
                st.markdown(f"🔗 [View on The MET Website]({meta.get('objectURL')})")

            st.markdown("---")
            st.markdown("### AI-generated Curator Notes")
            if client:
                with st.spinner("Generating overview..."):
                    st.write(generate_overview(client, meta))
                with st.spinner("Generating context..."):
                    st.write(generate_context(client, meta))
                with st.spinner("Analyzing iconography..."):
                    st.write(generate_iconography(client, meta))
            else:
                st.write("(Enable OpenAI API Key to generate curator notes.)")
    else:
        st.info("No works available.")

# ---------------- INTERACTIVE ART ZONE ----------------
with tabs[3]:
    st.header("Interactive Art Zone")
    client = get_openai_client()

    tab_mode = st.radio("Category:", ["Art-based","Myth-based"], key="interactive_mode")
    if tab_mode == "Art-based":
        st.subheader("Detail & Symbolism — Ask about a visual detail")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork first in Works & Analysis.")
        else:
            meta = met_get_object_cached(st.session_state["selected_artwork"])
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
