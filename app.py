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
        except:
            resp = client.images.create(prompt=prompt_text, size=size, n=1)
            b64 = resp.data[0].b64_json
        img = Image.open(BytesIO(base64.b64decode(b64)))
        return img, None
    except Exception as e:
        return None, str(e)

# ---------- Prompts ----------
def expand_bio_ai(client, name, base_bio):
    system = "You are an expert in Greek mythology and museum interpretation."
    user = f"Expand the short bio of {name} in 3 museum-style paragraphs.\nShort bio:\n{base_bio}"
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=450)

def generate_overview(client, meta):
    msg = [
        {"role":"system","content":"You are a museum curator."},
        {"role":"user","content":f"Write a 3-sentence public-facing overview for '{meta.get('title')}' using metadata."}
    ]
    return chat_complete(client, msg, max_tokens=220)

def generate_context(client, meta):
    msg = [
        {"role":"system","content":"You are an art historian."},
        {"role":"user","content":f"Using metadata: {meta}. Provide 4–6 sentences on historical & artistic context."}
    ]
    return chat_complete(client, msg, max_tokens=380)

def generate_iconography(client, meta):
    msg = [
        {"role":"system","content":"You are an iconography specialist."},
        {"role":"user","content":f"Analyze the mythic iconography for metadata: {meta}."}
    ]
    return chat_complete(client, msg, max_tokens=400)

def ai_answer_detail(client, q, meta):
    msg = [
        {"role":"system","content":"You are a museum educator."},
        {"role":"user","content":f"Visitor asked '{q}' about artwork '{meta.get('title')}'. Give a concise curator answer."}
    ]
    return chat_complete(client, msg, max_tokens=300)

def ai_style_match(client, note):
    msg = [
        {"role":"system","content":"You are an art historian."},
        {"role":"user","content":f"Explain style cues in sketch described as: {note}."}
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

# ---------- UI ----------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone"])

# =============================
# HOME TAB
# =============================
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
Explore Greek gods & heroes through MET artworks with AI curator analysis.

### Quick guide
1. Go to **Greek Deities**, choose a figure.  
2. Click **Fetch related works**.  
3. Select any artwork → view full analysis in **Works & Analysis** (left–right layout).  
4. Try **Interactive Art Zone** for myth ID, sketch analysis, archetype testing, etc.
""")
    st.markdown("---")

    st.subheader("OpenAI API Key")
    key = st.text_input("Enter your OpenAI API Key (sk-...)", type="password")
    if st.button("Save Key"):
        st.session_state["OPENAI_API_KEY"] = key
        st.success("API Key saved!")

    st.markdown("---")
    st.markdown("Course PDF:")
    st.markdown(f"[View slides]({COURSE_PDF_PATH})")

# (CONTINUE TO PART 2 BELOW)

