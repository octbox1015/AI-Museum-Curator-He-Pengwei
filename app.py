# app.py
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import base64
import os
from typing import List, Dict, Tuple
import math
import time
import tempfile
import re

# visualization libs
import networkx as nx
from pyvis.network import Network
import plotly.express as px

# OpenAI new SDK client (optional)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ---------- Page config ----------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------- Constants ----------
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

MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

COURSE_PDF_PATH = "/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf"

# ---------- Helpers: MET ----------
@st.cache_data(show_spinner=False)
def met_search_ids(query: str, max_results: int = 120) -> List[int]:
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        ids = data.get("objectIDs") or []
        return ids[:max_results]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def met_get_object_cached(object_id: int) -> Dict:
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def met_get_object(object_id: int) -> Dict:
    return met_get_object_cached(object_id)

def fetch_image_from_metadata(meta: Dict) -> Image.Image | None:
    if not meta:
        return None
    candidates = []
    if meta.get("primaryImageSmall"):
        candidates.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"):
        candidates.append(meta["primaryImage"])
    if meta.get("additionalImages"):
        try:
            candidates.extend(meta.get("additionalImages"))
        except Exception:
            pass
    # unique urls
    seen = set()
    urls = []
    for u in candidates:
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    for url in urls:
        try:
            r = requests.get(url, timeout=12)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")
        except Exception:
            continue
    return None

def generate_aliases(name: str) -> List[str]:
    aliases = [name]
    mapping = {
        "Athena": ["Pallas Athena", "Minerva"],
        "Zeus": ["Jupiter"],
        "Aphrodite": ["Venus"],
        "Hermes": ["Mercury"],
        "Medusa": ["Gorgon"],
        "Heracles": ["Hercules"],
        "Dionysus": ["Bacchus"]
    }
    if name in mapping:
        aliases.extend(mapping[name])
    aliases.extend([f"{name} Greek", f"{name} myth", f"{name} deity"])
    return list(dict.fromkeys(aliases))

# ---------- OpenAI client helpers ----------
def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    if OpenAI is None:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        try:
            return OpenAI()
        except Exception:
            return None

def chat_complete(client, messages, model="gpt-4o-mini", max_tokens=700, temperature=0.2):
    if client is None:
        return "OpenAI client not configured."
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"

def image_generate(client, prompt_text, size="1024x1024"):
    if client is None:
        return None, "OpenAI key missing"
    try:
        try:
            resp = client.images.generate(prompt=prompt_text, size=size, n=1)
            b64 = resp.data[0].b64_json
        except Exception:
            resp = client.images.create(prompt=prompt_text, size=size, n=1)
            b64 = resp.data[0].b64_json
        img = Image.open(BytesIO(base64.b64decode(b64)))
        return img, None
    except Exception as e:
        return None, str(e)

# ---------- Prompts ----------
def expand_bio_ai(client, name, base):
    system = "You are an expert in Greek mythology and museum interpretation."
    user = f"Expand the short bio of {name} into 3 museum-style paragraphs. Short bio: {base}"
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=450)

def generate_overview(client, meta):
    msg = [{"role":"system","content":"You are a museum curator."},
           {"role":"user","content":f"Write a 3-sentence public-facing overview for '{meta.get('title')}'. Use metadata to ground it."}]
    return chat_complete(client, msg, max_tokens=220)

def generate_context(client, meta):
    msg = [{"role":"system","content":"You are an art historian."},
           {"role":"user","content":f"Using metadata: {meta}. Provide 4–6 sentences on historical & artistic context."}]
    return chat_complete(client, msg, max_tokens=380)

def generate_iconography(client, meta):
    msg = [{"role":"system","content":"You are an iconography specialist."},
           {"role":"user","content":f"Analyze the mythic iconography for metadata: {meta}."}]
    return chat_complete(client, msg, max_tokens=400)

# wrappers for some interactive AI features
def ai_answer_detail(client, q, meta):
    msg = [
        {"role":"system","content":"You are a museum educator."},
        {"role":"user","content":f"Question: {q}. Metadata: {meta}"}
    ]
    return chat_complete(client, msg, max_tokens=300)

def ai_style_match(client, note):
    msg = [
        {"role":"system","content":"You are an art historian."},
        {"role":"user","content":f"Explain visual style cues for: {note}"}
    ]
    return chat_complete(client, msg, max_tokens=400)

def ai_myth_identifier(client, desc):
    msg = [
        {"role":"system","content":"You are an expert in Greek myth."},
        {"role":"user","content":f"Identify the most likely Greek figure for this: '{desc}'."}
    ]
    return chat_complete(client, msg, max_tokens=350)

def ai_personality_archetype(client, answers):
    msg = [
        {"role":"system","content":"You are a Jungian analyst of Greek myth."},
        {"role":"user","content":f"Map answers {answers} to a mythic archetype + explanation + artwork themes."}
    ]
    return chat_complete(client, msg, max_tokens=450)

# ---------- UI Tabs ----------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone","Mythology Network","Artwork Timeline"])

# ---------------- HOME ----------------
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
Explore Greek gods, heroes, and creatures through MET artworks with curator-grade AI interpretations.

**Quick steps**
1. Go to **Greek Deities**, pick a figure and fetch related works.
2. Click thumbnail to view full analysis in **Works & Analysis** (left–right layout).
3. Use **Interactive Art Zone** for detail questions, sketch analysis, myth ID, archetype matcher, and image generation.
4. Explore relationship graph and timeline in the right tabs.
    """)
    st.markdown("---")
    st.subheader("OpenAI API Key (session)")
    key = st.text_input("Enter your OpenAI API Key (sk-...)", type="password", key="home_api_input")
    if st.button("Save API Key", key="save_api_btn"):
        if key:
            st.session_state["OPENAI_API_KEY"] = key
            st.success("API Key saved to session.")
        else:
            st.warning("Please enter a valid key.")
    if OpenAI is None:
        st.warning("OpenAI SDK not available. Install 'openai' in requirements if you want AI features.")
    st.markdown("---")
    st.markdown("Course slides (reference):")
    st.markdown(f"[Open course PDF]({COURSE_PDF_PATH})")

# ---------------- GREEK DEITIES ----------------
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    selected = st.selectbox("Choose a figure:", MYTH_LIST, key="deity_select")
    base = FIXED_BIOS.get(selected, f"{selected} is an important figure in Greek mythology.")
    st.subheader(f"Short description — {selected}")
    st.write(base)

    client = get_openai_client()
    if st.button("Expand description with AI", key="expand_bio_btn"):
        if client is None:
            st.error("OpenAI client not configured. Add key on Home.")
        else:
            with st.spinner("Expanding..."):
                expanded = expand_bio_ai(client, selected, base)
                st.session_state["expanded_bio"] = expanded
                st.session_state["last_bio_for"] = selected
                st.markdown("### AI Expanded Introduction")
                st.write(expanded)

    if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for") == selected:
        st.markdown("### AI Expanded Introduction (cached)")
        st.write(st.session_state["expanded_bio"])

    st.markdown("#### Related search aliases")
    st.write(generate_aliases(selected))
    st.markdown("---")
    st.write("Fetch accessible artworks related to this figure. Only artworks with downloadable images will be shown.")

    max_results = st.slider("Max MET results to try", 40, 400, 120, 20, key="deity_max_results")
    if st.button("Fetch related works from MET", key="fetch_deity_btn"):
        all_ids = []
        for alias in generate_aliases(selected):
            ids = met_search_ids(alias, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
        if not all_ids:
            st.info("No works found.")
            st.session_state.pop("related_ids", None)
            st.session_state.pop("thumbs_data", None)
        else:
            st.success(f"Found {len(all_ids)} candidate works — loading images (only show those with images).")
            thumbs = []
            progress = st.progress(0)
            total = max(1, len(all_ids))
            for i, oid in enumerate(all_ids):
                meta = met_get_object(oid)
                if meta:
                    img = fetch_image_from_metadata(meta)
                    if img:
                        thumbs.append((oid, meta, img))
                progress.progress(min(100, int((i+1)/total*100)))
                time.sleep(0.02)
            progress.empty()
            if not thumbs:
                st.info("Found candidates but none had accessible images.")
                st.session_state["related_ids"] = []
                st.session_state.pop("thumbs_data", None)
            else:
                # store only the ones we have images for
                st.session_state["related_ids"] = [t[0] for t in thumbs]
                st.session_state["thumbs_data"] = thumbs
                st.success(f"Loaded {len(thumbs)} artworks with downloadable images.")
                # pagination UI for this tab (unique key)
                per_page = st.number_input("Thumbnails per page (deity gallery)", min_value=8, max_value=48, value=24, step=4, key="deity_per_page")
                pages = math.ceil(len(thumbs)/per_page)
                page = st.number_input("Gallery page (Deity)", min_value=1, max_value=max(1,pages), value=1, key="deity_gallery_page")
                start = (page-1)*per_page
                # display in a grid using rows of 4
                page_items = thumbs[start:start+per_page]
                rows = math.ceil(len(page_items)/4)
                for r in range(rows):
                    cols = st.columns(4)
                    for c in range(4):
                        idx = r*4 + c
                        if idx < len(page_items):
                            oid, meta, img = page_items[idx]
                            with cols[c]:
                                st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                                if st.button("Select", key=f"deity_select_{oid}"):
                                    st.session_state["selected_artwork"] = oid
                                    st.success(f"Selected {oid}. Switch to Works & Analysis tab.")

# ---------------- WORKS & ANALYSIS ----------------
with tabs[2]:
    st.header("Works & Analysis — Selected Artwork View (left: image; right: structured text)")
    if "selected_artwork" in st.session_state:
        art_id = st.session_state["selected_artwork"]
        meta = met_get_object(art_id)
        left_col, right_col = st.columns([0.5, 0.5])
        with left_col:
            img = fetch_image_from_metadata(meta)
            if img:
                max_w = 650
                w, h = img.size
                if w > max_w:
                    img = img.resize((max_w, int(h*(max_w/w))))
                st.image(img, use_column_width=False)
            else:
                st.info("No image available.")
            if st.button("Back to Gallery", key="back_to_gallery"):
                st.session_state.pop("selected_artwork", None)
                st.rerun()
        with right_col:
            st.subheader(f"{meta.get('title') or meta.get('objectName')} — ID {art_id}")
            st.markdown("#### Identification")
            st.write(f"**Object Name:** {meta.get('objectName')}")
            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
            st.write(f"**Date:** {meta.get('objectDate')}")
            st.write(f"**Medium:** {meta.get('medium')}")
            st.write(f"**Classification:** {meta.get('classification')}")
            st.write(f"**Culture:** {meta.get('culture')}")
            st.write(f"**Department:** {meta.get('department')}")
            st.markdown(f"[View on MET]({meta.get('objectURL')})")

            client = get_openai_client()
            st.markdown("#### Overview")
            if client:
                with st.spinner("Generating overview..."):
                    st.write(generate_overview(client, meta))
            else:
                st.write("(Enable OpenAI API Key on Home)")

            st.markdown("#### Historical & Artistic Context")
            if client:
                with st.spinner("Generating context..."):
                    st.write(generate_context(client, meta))
            else:
                st.write("(Enable OpenAI API Key on Home)")

            st.markdown("#### Artistic Features")
            st.write("Material, technique, composition — AI will expand when API is enabled.")

            st.markdown("#### Iconography & Myth Interpretation")
            if client:
                with st.spinner("Analyzing iconography..."):
                    st.write(generate_iconography(client, meta))
            else:
                st.write("(Enable API Key to generate iconography notes)")

            st.markdown("#### Exhibition Notes")
            st.write("Placement recommendation, related works, and label length suggestions (AI when enabled).")

    else:
        st.info("No artwork selected. Go to Greek Deities and fetch/select works. You can also use the gallery below if available.")
        thumbs = st.session_state.get("thumbs_data", [])
        if thumbs:
            per_page = st.number_input("Thumbnails per page (works & analysis gallery)", min_value=8, max_value=48, value=24, step=4, key="wa_per_page")
            pages = math.ceil(len(thumbs)/per_page)
            page = st.number_input("Gallery page (Works)", min_value=1, max_value=max(1,pages), value=1, key="wa_gallery_page")
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
                            st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                            if st.button("Select", key=f"wa_select_{oid}"):
                                st.session_state["selected_artwork"] = oid
                                st.rerun()

# ---------------- INTERACTIVE ART ZONE ----------------
with tabs[3]:
    st.header("Interactive Art Zone")
    mode = st.radio("Category:", ["Art-based", "Myth-based"], key="interactive_mode")
    client = get_openai_client()

    if mode == "Art-based":
        st.subheader("Detail question about selected artwork")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork in Works & Analysis first.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            q = st.text_input("Ask about a visual detail (e.g., 'What does the owl mean?')", key="interactive_q")
            if st.button("Ask", key="ask_detail"):
                if client:
                    with st.spinner("Answering..."):
                        st.write(ai_answer_detail(client, q, meta))
                else:
                    st.error("OpenAI API Key not configured.")

        st.markdown("---")
        st.subheader("Style Analyzer — upload a sketch/photo")
        uploaded = st.file_uploader("Upload sketch/photo", type=["png","jpg","jpeg"], key="style_upload")
        note = st.text_input("Describe the sketch (lines, pose, mood)", key="style_note")
        if uploaded and st.button("Analyze sketch", key="analyze_sketch"):
            if client:
                image = Image.open(BytesIO(uploaded.getvalue())).convert("RGB")
                st.image(image, caption="Uploaded")
                with st.spinner("Analyzing..."):
                    st.write(ai_style_match(client, note or "User sketch"))
            else:
                st.error("OpenAI API Key not configured.")

    else:
        st.subheader("Myth Identifier")
        desc = st.text_input("Describe a scene or motif", key="myth_desc")
        if st.button("Identify myth", key="identify_myth"):
            if client:
                with st.spinner("Identifying..."):
                    st.write(ai_myth_identifier(client, desc))
            else:
                st.error("OpenAI API Key not configured.")

        st.markdown("---")
        st.subheader("Myth Archetype Matcher (Jungian-style)")
        a1 = st.selectbox("Preferred role in a team:", ["Leader","Supporter","Strategist","Creator"], key="arch_role")
        a2 = st.selectbox("Which drives you most:", ["Duty","Fame","Pleasure","Wisdom"], key="arch_drive")
        a3 = st.selectbox("You respond to crisis by:", ["Plan","Fight","Flee","Negotiate"], key="arch_crisis")
        a4 = st.selectbox("Which image appeals most:", ["Eagle","Owl","Serpent","Laurel"], key="arch_image")
        if st.button("Get my archetype", key="get_archetype"):
            if client:
                answers = {"role":a1,"drive":a2,"crisis":a3,"image":a4}
                with st.spinner("Mapping archetype..."):
                    st.write(ai_personality_archetype(client, answers))
            else:
                st.error("OpenAI API Key not configured.")

# ---------------- MYTHOLOGY NETWORK (Network Graph) ----------------
with tabs[4]:
    st.header("Mythology Relationship Graph")
    st.markdown("Interactive network of selected mythological relationships. Drag nodes to explore connections.")

    relations = [
        ("Zeus","Hera","married"),
        ("Zeus","Athena","father"),
        ("Zeus","Apollo","father"),
        ("Zeus","Artemis","father"),
        ("Zeus","Ares","father"),
        ("Hades","Persephone","husband"),
        ("Perseus","Medusa","slays"),
        ("Apollo","Artemis","twin"),
        ("Poseidon","Theseus","father"),
        ("Zeus","Heracles","father"),
        ("Demeter","Persephone","mother"),
        ("Odysseus","Athena","favored_by"),
        ("Aphrodite","Eros","mother"),
    ]

    G = nx.DiGraph()
    for a,b,rel in relations:
        G.add_node(a)
        G.add_node(b)
        G.add_edge(a,b, label=rel)

    net = Network(height="600px", width="100%", directed=True, notebook=False)
    net.from_nx(G)
    net.repulsion(node_distance=180, spring_length=120)

    # Generate HTML safely (no show(), no write_html())
    html_str = net.generate_html(notebook=False)
    from streamlit.components.v1 import html
    html(html_str, height=640, scrolling=True)

# ---------------- ARTWORK TIMELINE ----------------
with tabs[5]:
    st.header("Artwork Timeline & Date Distribution")
    st.markdown("Timeline (scatter) and histogram of object begin dates from currently loaded gallery.")
    thumbs = st.session_state.get("thumbs_data", [])
    # collect normalized years from metadata
    years = []
    titles = []
    for (oid, meta, img) in thumbs:
        y = meta.get("objectBeginDate")
        if isinstance(y, int):
            years.append(y)
            titles.append(meta.get("title") or meta.get("objectName") or str(oid))
        else:
            od = meta.get("objectDate") or ""
            parsed = None
            try:
                m = re.search(r"-?\d{1,4}", od)
                if m:
                    parsed = int(m.group(0))
            except Exception:
                parsed = None
            if parsed:
                years.append(parsed)
                titles.append(meta.get("title") or meta.get("objectName") or str(oid))

    if not years:
        st.info("No date information available for the current gallery. Select a deity and fetch works with images.")
    else:
        df = {"year": years, "title": titles}
        fig = px.scatter(df, x="year", y=[1]*len(years), hover_data=["title"], labels={"x":"Year"})
        fig.update_yaxes(visible=False)
        st.plotly_chart(fig, use_container_width=True)
        hist = px.histogram(df, x="year", nbins=20, title="Distribution of object begin dates")
        st.plotly_chart(hist, use_container_width=True)

# End of app

