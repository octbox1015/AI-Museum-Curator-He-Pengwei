# app.py
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import base64
import os
from typing import List, Dict

# New OpenAI client style
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ----------------- Config -----------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ----------------- Constants -----------------
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

# Path to course PDF (developer-provided). Kept here as link in UI.
COURSE_PDF_PATH = "/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf"

# ----------------- MET helpers -----------------
def met_search_ids(query: str, max_results: int = 60) -> List[int]:
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=10)
        r.raise_for_status()
        ids = r.json().get("objectIDs") or []
        return ids[:max_results]
    except Exception as e:
        st.error(f"MET search error: {e}")
        return []

def met_get_object(object_id: int) -> Dict:
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to fetch MET object {object_id}: {e}")
        return {}

def fetch_image_from_metadata(meta: Dict):
    """Robust image loader: try primaryImageSmall, primaryImage, additionalImages."""
    candidates = []
    if meta.get("primaryImageSmall"):
        candidates.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"):
        candidates.append(meta["primaryImage"])
    if meta.get("additionalImages"):
        candidates.extend(meta["additionalImages"])
    # try each URL
    for url in candidates:
        try:
            r = requests.get(url, timeout=10)
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
    aliases += [f"{name} Greek", f"{name} myth", f"{name} deity"]
    return list(dict.fromkeys(aliases))

# ----------------- OpenAI client & wrappers (new SDK) -----------------
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

def image_generate(client, prompt_text: str, size: str = "1024x1024"):
    if client is None:
        return None, "OpenAI client not configured."
    try:
        # try images.generate, fallback to images.create
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

# Prompt wrappers
def expand_bio_ai(client, name: str, base_bio: str):
    system = "You are an expert in Greek mythology and museum interpretation. Produce a concise, museum-friendly 3-paragraph introduction."
    user = f"Expand the short bio about {name} into three paragraphs: who they are; key myths; common artistic depictions and exhibition notes.\n\nShort bio:\n{base_bio}"
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=500)

def generate_curator_analysis(client, metadata: Dict):
    system = "You are a professional museum curator. Write an accessible but scholarly label and short essay with labeled sections."
    title = metadata.get("title") or metadata.get("objectName") or "Untitled"
    artist = metadata.get("artistDisplayName") or "Unknown"
    date = metadata.get("objectDate") or "Unknown"
    medium = metadata.get("medium") or "Unknown"
    url = metadata.get("objectURL") or ""
    user = f"""Analyze this artwork. Provide labeled sections: Identification; Overview; Historical & Artistic Context; Artistic Features; Iconography & Myth Interpretation; Exhibition Notes.
Metadata:
Title: {title}
Artist: {artist}
Date: {date}
Medium: {medium}
URL: {url}
"""
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=900)

def ai_answer_detail(client, question: str, metadata: Dict):
    system = "You are a museum educator answering a visitor's close-looking question."
    user = f"Visitor asked: '{question}' about artwork titled '{metadata.get('title')}'. Provide a concise curator response, mention if interpretation is speculative."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=350)

def ai_style_match(client, note: str):
    system = "You are an art historian specialized in ancient Mediterranean art."
    user = f"User describes a sketch/photo: '{note}'. Explain distinguishing features for Archaic black-figure, Classical marble, Hellenistic composition; provide visual checks."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=500)

def ai_myth_identifier(client, desc: str):
    system = "You are an expert in Greek myth and iconography."
    user = f"Identify which Greek deity/hero/creature best matches this: '{desc}'. Explain visual cues and suggest two MET search terms."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=400)

def ai_personality_archetype(client, answers: Dict):
    system = "You are a cultural analyst mapping short quiz answers to Jungian archetypes within Greek myth."
    user = f"Map these answers to a best-fit Greek myth archetype and explain: {answers}. Provide: 1) archetype & deity; 2) short psych explanation; 3) 3 recommended artwork themes."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=500)

# ----------------- Layout (tabs) -----------------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone"])

# ---- HOME ----
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
**What this app does:**  
Explore Greek gods, heroes, and mythic creatures via MET collections, and receive curator-level AI interpretations.
    """)
    st.subheader("Quick guide (short & clear)")
    st.markdown("""
1. Open **Greek Deities** and choose a figure.  
2. Expand the short bio with AI (optional).  
3. Fetch related works from MET.  
4. Go to **Works & Analysis**, select an object, then generate curator analysis.  
5. Use **Interactive Art Zone** for close-looking, sketch-style analysis, myth ID, archetype quiz, or image generation.
    """)
    st.subheader("OpenAI API Key (session only)")
    key = st.text_input("Paste your OpenAI API Key (sk-...):", type="password")
    if st.button("Save API Key"):
        if not key:
            st.warning("Please paste a valid API key.")
        else:
            st.session_state["OPENAI_API_KEY"] = key
            st.success("API Key saved to session. AI features enabled.")
    if OpenAI is None:
        st.warning("OpenAI SDK not installed correctly. Make sure package 'openai' in requirements is available.")

# ---- GREEK DEITIES ----
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
    if st.button("Fetch related works from MET"):
        all_ids = []
        for alias in generate_aliases(selected):
            ids = met_search_ids(alias, max_results=40)
            for i in ids:
                if i not in all_ids:
                    all_ids.append(i)
        if not all_ids:
            st.info("No works found.")
        else:
            st.success(f"Found {len(all_ids)} candidate works (may include different object types).")
            st.session_state["related_ids"] = all_ids

# ---- WORKS & ANALYSIS ----
with tabs[2]:
    st.header("Works & Analysis — Structured View")
    if "related_ids" not in st.session_state:
        st.info("No related works yet. Go to 'Greek Deities' and fetch related works.")
    else:
        ids = st.session_state["related_ids"]
        st.subheader("Gallery — click to select an object")
        cols = st.columns(4)
        for idx, oid in enumerate(ids):
            meta = met_get_object(oid)
            title = meta.get("title") or meta.get("objectName") or f"Object {oid}"
            img = fetch_image_from_metadata(meta)
            if img:
                with cols[idx % 4]:
                    st.image(img.resize((220,220)), caption=f"{title} ({oid})")
                    if st.button(f"Select {oid}", key=f"sel_{oid}"):
                        st.session_state["selected_artwork"] = oid

        if "selected_artwork" in st.session_state:
            art_id = st.session_state["selected_artwork"]
            meta = met_get_object(art_id)
            st.markdown("---")
            # Structured museum-like wall text (auto-expanded)
            st.subheader(f"{meta.get('title') or meta.get('objectName')}  —  Object ID {art_id}")

            # Identification
            st.markdown("#### Identification")
            st.write(f"**Object Name:** {meta.get('objectName')}")
            st.write(f"**Title:** {meta.get('title')}")
            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
            st.write(f"**Date:** {meta.get('objectDate')}")
            st.write(f"**Medium:** {meta.get('medium')}")
            st.write(f"**Classification:** {meta.get('classification')}")
            st.write(f"**Culture:** {meta.get('culture')}")
            st.write(f"**Department:** {meta.get('department')}")
            st.write(f"**Accession Number:** {meta.get('accessionNumber')}")
            st.markdown(f"[View on MET]({meta.get('objectURL')})")

            # Overview (auto expanded)
            st.markdown("#### Overview")
            overview_client = get_openai_client()
            if overview_client:
                with st.spinner("Generating museum-style overview..."):
                    # a short overview prompt
                    msg = [{"role":"system","content":"You are a museum curator."},
                           {"role":"user","content":f"Write a 3-sentence public-facing overview for the artwork titled '{meta.get('title')}'. Use metadata to ground it."}]
                    overview = chat_complete(overview_client, msg, max_tokens=200)
                    st.write(overview)
            else:
                st.write("Overview: (enable OpenAI API key to auto-generate)")

            # Historical & Artistic Context (auto expanded)
            st.markdown("#### Historical & Artistic Context")
            if overview_client:
                with st.spinner("Generating context..."):
                    msg = [{"role":"system","content":"You are an art historian."},
                           {"role":"user","content":f"Using metadata: {meta}. Provide 4-6 sentences about the artwork's historical and artistic context."}]
                    ctx = chat_complete(overview_client, msg, max_tokens=400)
                    st.write(ctx)
            else:
                st.write("Context: (enable OpenAI API key)")

            # Artistic Features
            st.markdown("#### Artistic Features")
            st.write("Material, technique, composition, and notable stylistic features will be described here when AI is enabled.")

            # Iconography & Myth Interpretation
            st.markdown("#### Iconography & Myth Interpretation")
            if overview_client:
                with st.spinner("Analyzing iconography..."):
                    msg = [{"role":"system","content":"You are an iconography specialist."},
                           {"role":"user","content":f"Analyze the iconography for metadata: {meta}. What mythic elements or symbols are present and what might they mean?"}]
                    ico = chat_complete(overview_client, msg, max_tokens=400)
                    st.write(ico)
            else:
                st.write("Iconography: (enable OpenAI API key)")

            # Exhibition Notes
            st.markdown("#### Exhibition Notes")
            st.write("Suggested placement, wall text length, and related objects (AI will generate when API enabled).")

# ---- INTERACTIVE ART ZONE (Art-based / Myth-based) ----
with tabs[3]:
    st.header("Interactive Art Zone")
    choice = st.radio("Category:", ["Art-based", "Myth-based"])

    client = get_openai_client()

    if choice == "Art-based":
        st.subheader("Detail & Symbolism — Ask about a visual detail")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork first in Works & Analysis.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            q = st.text_input("Ask about a visual detail (e.g., 'What does the owl mean?'):")
            if st.button("Ask detail"):
                if client is None:
                    st.error("OpenAI client not configured.")
                else:
                    with st.spinner("Answering..."):
                        ans = ai_answer_detail(client, q, meta)
                        st.write(ans)

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
                    resp = ai_style_match(client, note or "User sketch")
                    st.write(resp)

    else:
        st.subheader("Myth Identifier — one-sentence description")
        desc = st.text_input("Describe a scene or motif:")
        if st.button("Identify myth"):
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                with st.spinner("Identifying..."):
                    r = ai_myth_identifier(client, desc)
                    st.write(r)

        st.markdown("---")
        st.subheader("Myth Archetype Matcher — (Jungian-style)")
        st.write("Answer a few short questions; the AI will map your responses to a mythic archetype and recommend artwork themes.")
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
                    profile = ai_personality_archetype(client, answers)
                    st.markdown("### Your Myth Archetype")
                    st.write(profile)

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

# End of app
