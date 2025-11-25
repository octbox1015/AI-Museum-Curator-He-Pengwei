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
def met_get_object(object_id: int):
    """安全获取 MET 作品信息，失败返回空字典"""
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data or data.get("objectID") is None:
            return {}
        return data
    except requests.exceptions.HTTPError as e:
        st.warning(f"作品 {object_id} 请求失败（HTTPError {getattr(r,'status_code','?')}）")
        return {}
    except requests.exceptions.RequestException as e:
        st.warning(f"作品 {object_id} 请求异常：{e}")
        return {}
    except Exception as e:
        st.warning(f"作品 {object_id} 未知错误：{e}")
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

# ---------------- UI Layout (tabs) ----------------
tabs = st.tabs(["Home","Greek Deities & Works","Interactive Art Zone"])

# ---------------- HOME ----------------
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
**What this app does:**  
Explore Greek gods, heroes, and mythic creatures via MET collections and get curator-level insights.

**Quick guide**
1. Open **Greek Deities & Works**, choose a figure, fetch artworks/books related to them.  
2. By default, the most famous Greek myth-related works are displayed even without selection.  
3. Click **View Details** on any item to see metadata, AI-generated overview, historical context, and iconography.  
4. Use **Interactive Art Zone** to ask detailed visual questions or identify myths.  

**Note:** AI features require OpenAI API key.
    """)
    st.subheader("OpenAI API Key (session only)")
    key = st.text_input("Paste your OpenAI API Key (sk-...):", type="password", key="home_api_input")
    if st.button("Save API Key", key="save_api_btn"):
        if key:
            st.session_state["OPENAI_API_KEY"] = key
            st.success("API Key saved to session. AI features enabled.")
        else:
            st.warning("Please paste a valid API key.")

# ---------------- GREEK DEITIES & WORKS ----------------
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures & Works")
    client = get_openai_client()

    selected = st.selectbox("Choose a figure (optional):", MYTH_LIST, key="deity_select")
    base_bio = FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth with diverse visual representations.")
    st.subheader(f"Short description — {selected}")
    st.write(base_bio)

    if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for")==selected:
        st.markdown("### AI Expanded Introduction")
        st.write(st.session_state["expanded_bio"])

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

    st.markdown("#### Related search aliases")
    st.write(generate_aliases(selected))
    st.markdown("---")

    # 通过 MET API 获取最著名作品
    st.subheader("Famous Works & Related Items (Art, Books, Manuscripts)")
    max_results = st.slider("Max results to try", 40, 300, 120, 20, key="deity_max_results")

    all_ids = []
    aliases = generate_aliases(selected)
    for alias in aliases:
        ids = met_search_ids(alias, max_results)
        for oid in ids:
            if oid not in all_ids:
                all_ids.append(oid)

    thumbs = []
    progress = st.progress(0)
    total = max(1, len(all_ids))
    for i, oid in enumerate(all_ids):
        meta = met_get_object(oid)
        if meta:
            img = fetch_image_from_meta(meta)
            thumbs.append((oid, meta, img))
        progress.progress(min(100, int((i+1)/total*100)))
        time.sleep(0.01)
    progress.empty()

    if thumbs:
        per_page = st.number_input("Items per page", min_value=4, max_value=24, value=12, step=2, key="deity_per_page")
        pages = math.ceil(len(thumbs)/per_page)
        page = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="deity_gallery_page")
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
                        with st.expander("View Details"):
                            st.write(f"**Object ID:** {oid}")
                            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
                            st.write(f"**Culture:** {meta.get('culture') or '—'}")
                            st.write(f"**Department:** {meta.get('department') or '—'}")
                            st.write(f"**Date:** {meta.get('objectDate') or '—'}")
                            st.write(f"**Medium:** {meta.get('medium') or '—'}")
                            st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
                            st.write(f"**Classification:** {meta.get('classification') or '—'}")
                            st.write(f"**Accession Number:** {meta.get('accessionNumber') or '—'}")
                            if meta.get("objectURL"):
                                st.markdown(f"🔗 [View on MET Website]({meta.get('objectURL')})")
                            if client:
                                with st.spinner("Generating overview..."):
                                    st.markdown("**Overview:**")
                                    st.write(generate_overview(client, meta))
                                with st.spinner("Generating context..."):
                                    st.markdown("**Context:**")
                                    st.write(generate_context(client, meta))
                                with st.spinner("Analyzing iconography..."):
                                    st.markdown("**Iconography:**")
                                    st.write(generate_iconography(client, meta))
    else:
        st.info("No works found for this figure.")

# ---------------- INTERACTIVE ART ZONE ----------------
with tabs[2]:
    st.header("Interactive Art Zone")
    client = get_openai_client()
    tab_mode = st.radio("Category:", ["Art-based","Myth-based"], key="interactive_mode")
    if tab_mode == "Art-based":
        st.info("Art-based interactive mode temporarily disabled.")
    else:
        st.subheader("Myth Identifier — one-sentence description")
        desc = st.text_input("Describe a scene or motif:", key="myth_desc")
        if st.button("Identify myth", key="identify_myth_btn"):
            if client:
                with st.spinner("Identifying..."):
                    st.write(ai_answer_detail(client, desc, {"title": "User Input"}))
            else:
                st.error("OpenAI client not configured. Enter API key on Home.")
