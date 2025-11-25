import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import time
import plotly.express as px
import matplotlib.pyplot as plt

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
        candidates += meta.get("additionalImages", [])
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
    aliases = [name] + mapping.get(name, [])
    aliases += [f"{name} Greek", f"{name} myth", f"{name} deity"]
    return list(dict.fromkeys(aliases))

# ---------------- OpenAI wrappers ----------------
def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or openai is None:
        return None
    openai.api_key = key
    return openai

def chat_complete(client, prompt, max_tokens=400, temperature=0.2, system="You are a museum curator."):
    if client is None:
        return "OpenAI client not configured."
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

def ai_myth_identifier(client, desc):
    prompt = f"Identify which Greek deity/hero/creature best matches this description: '{desc}'. Explain visual cues and suggest two MET search terms."
    return chat_complete(client, prompt, max_tokens=300)

def ai_personality_archetype(client, answers):
    prompt = f"Map these quiz answers to a Greek myth archetype and explain: {answers}. Provide archetype, short psych explanation, and three recommended artwork themes."
    return chat_complete(client, prompt, max_tokens=400)

# ---------------- HOME ----------------
st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
st.markdown("""
**Explore Greek gods, heroes, and mythic creatures via artworks, manuscripts, books, and cultural artifacts.**  

**Instructions:**
1. Go to **Greek Deities / Heroes / Creatures**. Search or select a figure.  
2. Default view shows the most famous related works. Click cards to expand details.  
3. AI-curated summaries appear inside each expanded card (overview, context, iconography).  
4. Use **Interactive Art Zone** for myth identification and personality archetype quiz.
""")
key = st.text_input("Paste your OpenAI API Key (sk-...):", type="password", key="home_api_input")
if st.button("Save API Key", key="save_api_btn"):
    if key:
        st.session_state["OPENAI_API_KEY"] = key
        st.success("API Key saved. AI features enabled.")
    else:
        st.warning("Please paste a valid API key.")

# ---------------- GREEK DEITIES ----------------
st.header("Greek Deities / Heroes / Creatures")
selected = st.selectbox("Choose a figure:", MYTH_LIST, key="deity_select")
base_bio = FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth.")
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
        st.error("OpenAI client not configured.")

if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for")==selected:
    st.markdown("### AI Expanded Introduction (cached)")
    st.write(st.session_state["expanded_bio"])

st.markdown("#### Related search aliases")
st.write(generate_aliases(selected))

st.markdown("---")
st.write("### Top related works")
aliases = generate_aliases(selected)
all_ids = []
for alias in aliases:
    all_ids += met_search_ids(alias, max_results=30)
all_ids = list(dict.fromkeys(all_ids))

thumbs = []
for oid in all_ids:
    meta = met_get_object_cached(oid)
    if not meta or meta.get("primaryImageSmall","")=="":
        continue
    img = fetch_image_from_meta(meta)
    if img:
        thumbs.append((oid, meta, img))
if not thumbs:
    st.info("No accessible works found for this figure.")
else:
    rows = math.ceil(len(thumbs)/4)
    for r in range(rows):
        cols = st.columns(4)
        for c in range(4):
            idx = r*4 + c
            if idx < len(thumbs):
                oid, meta, img = thumbs[idx]
                with cols[c]:
                    with st.expander(f"{meta.get('title') or meta.get('objectName')} ({oid})"):
                        st.image(img.resize((220,220)), use_column_width=False)
                        st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
                        st.write(f"**Date:** {meta.get('objectDate') or '—'}")
                        st.write(f"**Medium:** {meta.get('medium') or '—'}")
                        st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
                        if client:
                            with st.spinner("Generating overview..."):
                                st.markdown("**Overview:**")
                                st.write(generate_overview(client, meta))
                            with st.spinner("Generating context..."):
                                st.markdown("**Historical & Artistic Context:**")
                                st.write(generate_context(client, meta))
                            with st.spinner("Generating iconography..."):
                                st.markdown("**Iconography & Myth Interpretation:**")
                                st.write(generate_iconography(client, meta))
                        if meta.get("objectURL"):
                            st.markdown(f"[View on MET website]({meta.get('objectURL')})")

# ---------------- INTERACTIVE ART ZONE ----------------
st.header("Interactive Art Zone")
st.subheader("Myth Identifier")
desc = st.text_input("Describe a scene or motif:", key="myth_desc")
if st.button("Identify myth", key="identify_myth_btn"):
    if client:
        with st.spinner("Identifying..."):
            st.write(ai_myth_identifier(client, desc))
    else:
        st.error("OpenAI client not configured.")

st.subheader("Personality Archetype Matcher")
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
        st.error("OpenAI client not configured.")

# ---------------- BIG DATA ANALYSIS ----------------
st.header("Big Data — Artworks Analysis")
st.markdown("### Time Dimension: Work Distribution by Era")
# Dummy example: you can replace with actual analysis
years = [1600, 1700, 1800, 1900, 2000]
counts = [5, 12, 22, 18, 10]
fig = px.bar(x=years, y=counts, labels={"x":"Year","y":"Number of Works"})
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Medium/Type Distribution")
types = ["Painting","Sculpture","Book","Manuscript","Ceramic"]
counts2 = [15, 10, 8, 6, 12]
fig2 = px.pie(values=counts2, names=types, title="Medium Distribution")
st.plotly_chart(fig2, use_container_width=True)

st.markdown("### Style/Genre Distribution")
styles = ["Classical","Renaissance","Baroque","Modern"]
counts3 = [10, 15, 7, 9]
fig3 = px.bar(x=styles, y=counts3, labels={"x":"Style","y":"Number of Works"})
st.plotly_chart(fig3, use_container_width=True)
