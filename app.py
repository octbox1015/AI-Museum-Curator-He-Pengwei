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

# OpenAI new SDK client
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

# Developer-provided course PDF path (deploy platform will expose this)
COURSE_PDF_PATH = "/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf"

# ---------- Helpers: MET ----------
@st.cache_data(show_spinner=False)
def met_search_ids(query: str, max_results: int = 120) -> List[int]:
    """Search MET for objectIDs (broad). Returns up to max_results IDs."""
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
    """Cached MET object fetch."""
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def met_get_object(object_id: int) -> Dict:
    return met_get_object_cached(object_id)

def fetch_image_from_metadata(meta: Dict) -> Image.Image | None:
    """Try multiple image fields and return a PIL Image or None."""
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
    # remove duplicates and empties
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

def chat_complete(client, messages: List[Dict], model: str = "gpt-4o-mini", max_tokens: int = 700, temperature: float = 0.2):
    if client is None:
        return "OpenAI client not configured. Enter API key on Home page."
    try:
        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
        return resp.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"

def image_generate(client, prompt_text, size: str = "1024x1024"):
    if client is None:
        return None, "OpenAI client not configured."
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

# ---------- Prompt wrappers ----------
def expand_bio_ai(client, name: str, base_bio: str):
    system = "You are an expert in Greek mythology and museum interpretation. Produce a concise, museum-friendly 3-paragraph introduction."
    user = f"Expand the short bio about {name} into three paragraphs: who they are; key myths; common artistic depictions and exhibition notes.\n\nShort bio:\n{base_bio}"
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=450)

def generate_overview(client, meta: Dict):
    msg = [{"role":"system","content":"You are a museum curator."},
           {"role":"user","content":f"Write a 3-sentence public-facing overview for the artwork titled '{meta.get('title')}'. Use metadata to ground it."}]
    return chat_complete(client, msg, max_tokens=220)

def generate_context(client, meta: Dict):
    msg = [{"role":"system","content":"You are an art historian."},
           {"role":"user","content":f"Using metadata: {meta}. Provide 4-6 sentences about the artwork's historical and artistic context."}]
    return chat_complete(client, msg, max_tokens=400)

def generate_iconography(client, meta: Dict):
    msg = [{"role":"system","content":"You are an iconography specialist."},
           {"role":"user","content":f"Analyze the iconography for metadata: {meta}. What mythic elements or symbols are present and what might they mean?"}]
    return chat_complete(client, msg, max_tokens=400)

def ai_answer_detail(client, question: str, metadata: Dict):
    system = "You are a museum educator answering a visitor's close-looking question."
    user = f"Visitor asked: '{question}' about artwork titled '{metadata.get('title')}'. Provide a concise curator response, mention if interpretation is speculative."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=350)

def ai_style_match(client, note: str):
    system = "You are an art historian specialized in ancient Mediterranean art."
    user = f"User describes a sketch/photo: '{note}'. Explain distinguishing features for Archaic black-figure, Classical marble, Hellenistic composition; provide visual checks."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=450)

def ai_myth_identifier(client, desc: str):
    system = "You are an expert in Greek myth and iconography."
    user = f"Identify which Greek deity/hero/creature best matches this: '{desc}'. Explain visual cues and suggest two MET search terms."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=350)

def ai_personality_archetype(client, answers: Dict):
    system = "You are a cultural analyst mapping short quiz answers to Jungian archetypes within Greek myth."
    user = f"Map these answers to a best-fit Greek myth archetype and explain: {answers}. Provide: 1) archetype & deity; 2) short psych explanation; 3) 3 recommended artwork themes."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=450)

# ---------- UI ----------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone"])

# --- HOME ---
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
Explore Greek gods, heroes, and creatures via MET collections with curator-level AI interpretations.

Quick steps:
1. Go to **Greek Deities**, pick a figure and (optionally) expand bio with AI.
2. Click **Fetch related works** — the gallery will show all accessible works (paginated).
3. Click any thumbnail to select it. Selected artwork page hides the gallery and shows a left–right detailed view.
4. Use **Interactive Art Zone** for close-looking and creative interactions.
    """)
    st.markdown("---")
    st.subheader("OpenAI API Key (session only)")
    key = st.text_input("Paste your OpenAI API Key (sk-...):", type="password")
    if st.button("Save API Key"):
        if not key:
            st.warning("Please paste a valid API key.")
        else:
            st.session_state["OPENAI_API_KEY"] = key
            st.success("API Key saved to session. AI features enabled.")
    if OpenAI is None:
        st.warning("OpenAI SDK not installed correctly (install 'openai' per requirements).")
    st.markdown("---")
    st.markdown("Course slides (reference):")
    st.markdown(f"[Download / View slides]({COURSE_PDF_PATH})")

# --- GREEK DEITIES ---
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    selected = st.selectbox("Choose a figure:", MYTH_LIST)
    base = FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth with diverse visual representations.")
    st.subheader(f"Short description — {selected}")
    st.write(base)

    client = get_openai_client()
    if st.button("Expand description with AI"):
        if client is None:
            st.error("OpenAI client not configured. Enter API key on Home.")
        else:
            with st.spinner("Expanding..."):
                expanded = expand_bio_ai(client, selected, base)
                st.markdown("### AI Expanded Introduction")
                st.write(expanded)
                st.session_state["expanded_bio"] = expanded
                st.session_state["last_bio_for"] = selected

    if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for") == selected:
        st.markdown("### AI Expanded Introduction (cached)")
        st.write(st.session_state["expanded_bio"])

    st.markdown("#### Related search aliases")
    st.write(generate_aliases(selected))

    st.markdown("---")
    st.write("Fetch all accessible artworks related to this figure (will try multiple aliases).")
    max_results = st.slider("Max results to try (bigger = slower, more results)", min_value=40, max_value=200, value=120, step=20)
    if st.button("Fetch related works from MET"):
        # gather ids from all aliases, deduplicate
        all_ids = []
        for alias in generate_aliases(selected):
            ids = met_search_ids(alias, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)

        if not all_ids:
            st.info("No works found for this figure.")
            st.session_state.pop("related_ids", None)
            st.session_state.pop("thumbs", None)
        else:
            st.success(f"Found {len(all_ids)} candidate works (trying to load images). This may take a moment.")
            thumbs: List[Tuple[int, Dict, Image.Image]] = []
            # progressive fetch with progress indicator
            progress = st.progress(0)
            total = len(all_ids)
            loaded = 0
            for idx, oid in enumerate(all_ids):
                meta = met_get_object(oid)
                if not meta:
                    continue
                img = fetch_image_from_metadata(meta)
                if img:
                    thumbs.append((oid, meta, img))
                loaded += 1
                if total:
                    progress.progress(min(100, int(100 * (idx + 1) / total)))
                # small sleep to be friendly to MET
                time.sleep(0.05)
            progress.empty()

            if not thumbs:
                st.info("Found works but none have accessible images. Try increasing network access or a different alias.")
                st.session_state["related_ids"] = all_ids
                st.session_state.pop("thumbs", None)
            else:
                # store results (ids and thumbnails metadata)
                st.session_state["related_ids"] = [t[0] for t in thumbs]  # only those with images
                st.session_state["thumbs_meta"] = [(t[0], t[1]) for t in thumbs]  # store meta for quick access
                st.session_state["thumb_images_b64"] = [base64.b64encode(BytesIO().getvalue()).decode() if False else None]  # placeholder (not used)
                st.success(f"Loaded {len(thumbs)} artworks with downloadable images.")
                # show first page of gallery
                per_page = 24
                pages = math.ceil(len(thumbs) / per_page)
                page = st.number_input("Gallery page", min_value=1, max_value=pages, value=1, step=1)
                start = (page - 1) * per_page
                end = start + per_page
                page_items = thumbs[start:end]
                st.markdown("### Gallery (click thumbnail to select)")
                cols = st.columns(4)
                for idx, (oid, meta, img) in enumerate(page_items):
                    with cols[idx % 4]:
                        st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                        if st.button(f"Select {oid}", key=f"thumb_select_{oid}"):
                            st.session_state["selected_artwork"] = oid
                            st.success(f"Selected {oid}. Switch to 'Works & Analysis' tab to view details.")

# --- WORKS & ANALYSIS ---
with tabs[2]:
    st.header("Works & Analysis — Selected Artwork View (Gallery hidden when an artwork is selected)")
    # If selected, show left-right layout; else show gallery (if available)
    if "selected_artwork" in st.session_state:
        art_id = st.session_state["selected_artwork"]
        meta = met_get_object(art_id)
        st.markdown("---")
        left_col, right_col = st.columns([0.5, 0.5])
        with left_col:
            img = fetch_image_from_metadata(meta)
            if img:
                max_w = 650
                w, h = img.size
                if w > max_w:
                    new_h = int(h * (max_w / w))
                    img = img.resize((max_w, new_h))
                st.image(img, use_column_width=False)
            else:
                st.info("Image not available for this object.")
            if st.button("Back to Gallery"):
                st.session_state.pop("selected_artwork", None)
                st.experimental_rerun()

        with right_col:
            st.subheader(f"{meta.get('title') or meta.get('objectName')}  —  Object ID {art_id}")
            st.markdown("#### Identification")
            st.write(f"**Object Name:** {meta.get('objectName')}")
            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
            st.write(f"**Date:** {meta.get('objectDate')}")
            st.write(f"**Medium:** {meta.get('medium')}")
            st.write(f"**Classification:** {meta.get('classification')}")
            st.write(f"**Culture:** {meta.get('culture')}")
            st.write(f"**Department:** {meta.get('department')}")
            st.write(f"**Accession Number:** {meta.get('accessionNumber')}")
            st.markdown(f"[View on MET]({meta.get('objectURL')})")

            client = get_openai_client()
            st.markdown("#### Overview")
            if client:
                with st.spinner("Generating overview..."):
                    st.write(generate_overview(client, meta))
            else:
                st.write("Overview: (enable OpenAI API key on Home page)")

            st.markdown("#### Historical & Artistic Context")
            if client:
                with st.spinner("Generating context..."):
                    st.write(generate_context(client, meta))
            else:
                st.write("Context: (enable OpenAI API key)")

            st.markdown("#### Artistic Features")
            st.write("Material, technique, composition, and notable stylistic features (AI-generated when API enabled).")

            st.markdown("#### Iconography & Myth Interpretation")
            if client:
                with st.spinner("Analyzing iconography..."):
                    st.write(generate_iconography(client, meta))
            else:
                st.write("Iconography: (enable OpenAI API key)")

            st.markdown("#### Exhibition Notes")
            st.write("Suggested placement and related objects (AI will generate when API enabled).")

    else:
        # No selection yet — show gallery from related_ids if exists
        if "related_ids" not in st.session_state:
            st.info("No related works yet. Go to 'Greek Deities' and fetch related works.")
        else:
            ids = st.session_state["related_ids"]
            st.subheader("Gallery — click a thumbnail to select an object")
            # we show a paginated gallery here too
            per_page = 24
            pages = math.ceil(len(ids) / per_page)
            page = st.number_input("Gallery page", min_value=1, max_value=pages, value=1, step=1)
            start = (page - 1) * per_page
            end = start + per_page
            cols = st.columns(4)
            shown_any = False
            for idx, oid in enumerate(ids[start:end]):
                meta = met_get_object(oid)
                img = fetch_image_from_metadata(meta)
                if img:
                    shown_any = True
                    with cols[idx % 4]:
                        st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                        if st.button(f"Select {oid}", key=f"sel_{oid}"):
                            st.session_state["selected_artwork"] = oid
                            st.experimental_rerun()
            if not shown_any:
                st.info("None of the fetched works have accessible images; try fetching again or select another figure.")

# --- INTERACTIVE ART ZONE ---
with tabs[3]:
    st.header("Interactive Art Zone")
    category = st.radio("Category:", ["Art-based", "Myth-based"])
    client = get_openai_client()

    if category == "Art-based":
        st.subheader("Detail & Symbolism — Ask about a visual detail")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork in Works & Analysis first.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            q = st.text_input("Ask about a visual detail (e.g., 'What does the owl mean?'):")
            if st.button("Ask detail"):
                if client is None:
                    st.error("OpenAI client not configured.")
                else:
                    with st.spinner("Answering..."):
                        st.write(ai_answer_detail(client, q, meta))

        st.markdown("---")
        st.subheader("Style Analyzer — Upload sketch or photo")
        uploaded = st.file_uploader("Upload sketch/photo", type=["png","jpg","jpeg"])
        note = st.text_input("Describe sketch (lines, shapes, pose)...")
        if uploaded and st.button("Analyze sketch"):
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                image = Image.open(BytesIO(uploaded.getvalue())).convert("RGB")
                st.image(image, caption="Uploaded", use_column_width=False)
                with st.spinner("Analyzing style (textual guidance)..."):
                    st.write(ai_style_match(client, note or "User sketch"))

    else:
        st.subheader("Myth Identifier — one-sentence description")
        desc = st.text_input("Describe a scene or motif:")
        if st.button("Identify myth"):
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                with st.spinner("Identifying..."):
                    st.write(ai_myth_identifier(client, desc))

        st.markdown("---")
        st.subheader("Myth Archetype Matcher — (Jungian-style)")
        a1 = st.selectbox("Preferred role in a team:", ["Leader","Supporter","Strategist","Creator"])
        a2 = st.selectbox("Which drives you most:", ["Duty","Fame","Pleasure","Wisdom"])
        a3 = st.selectbox("You respond to crisis by:", ["Plan","Fight","Flee","Negotiate"])
        a4 = st.selectbox("Which image appeals most:", ["Eagle","Owl","Serpent","Laurel"])
        if st.button("Get my archetype"):
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                answers = {"role":a1,"drive":a2,"crisis":a3,"image":a4}
                with st.spinner("Mapping archetype..."):
                    st.write(ai_personality_archetype(client, answers))

        st.markdown("---")
        st.subheader("Myth Image Generator — describe a scene")
        scene = st.text_area("Describe a myth scene (style, mood, color):", height=120)
        size = st.selectbox("Image size", ["512x512","1024x1024"])
        if st.button("Generate myth image"):
            if client is None:
                st.error("OpenAI client not configured.")
            elif not scene.strip():
                st.error("Provide a scene description.")
            else:
                with st.spinner("Generating image..."):
                    img, err = image_generate(client, scene, size=size)
                    if err:
                        st.error(f"Image generation error: {err}")
                    elif img:
                        st.image(img, use_column_width=True)
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        st.download_button("Download image", data=buf.getvalue(), file_name="myth_image.png", mime="image/png")

# End

