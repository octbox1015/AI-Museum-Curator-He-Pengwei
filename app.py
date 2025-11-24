# app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
from typing import List, Dict, Optional

# Use modern OpenAI client
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # will check later

load_dotenv()

# ---------- Config ----------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# Comprehensive myth list (Option A)
MYTH_LIST = [
    "Zeus", "Hera", "Athena", "Apollo", "Artemis", "Aphrodite",
    "Hermes", "Dionysus", "Ares", "Hephaestus", "Poseidon", "Hades",
    "Demeter", "Persephone", "Hestia",
    "Heracles", "Perseus", "Achilles", "Odysseus", "Theseus", "Jason",
    "Medusa", "Minotaur", "Sirens", "Cyclops", "Centaur"
]

# Small set of short fixed bios (stable offline)
FIXED_BIOS = {
    "Zeus": "Zeus is the king of the Olympian gods, ruler of the sky and thunder. Often shown with a thunderbolt and eagle.",
    "Athena": "Athena (Pallas Athena) is the goddess of wisdom, craft, and strategic warfare; often depicted armed with helmet, spear, and aegis; symbol: owl.",
    "Medusa": "Medusa is one of the Gorgons—monstrous female figures whose gaze turns viewers to stone. Her image is used as protective apotropaic symbol.",
    "Perseus": "Perseus is the hero who beheaded Medusa and rescued Andromeda; often shown with winged sandals and a reflective shield.",
    "Aphrodite": "Aphrodite is the goddess of love and beauty, frequently represented with seashells or in semi-nude figure; associated with desire."
}

# ---------- Utilities ----------
def get_openai_client() -> Optional[OpenAI]:
    """Return an OpenAI client using session key or environment key; None if not available."""
    key = st.session_state.get("USER_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    if OpenAI is None:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        # fallback: try without explicit api_key if environment variable present
        try:
            return OpenAI()
        except Exception:
            return None

def met_search_ids(query: str, max_results: int = 15) -> List[int]:
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        ids = data.get("objectIDs") or []
        return ids[:max_results]
    except Exception:
        return []

def met_get_object(object_id: int) -> Dict:
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def fetch_image(url: str):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

def generate_aliases(name: str) -> List[str]:
    aliases = [name]
    mapping = {
        "Athena": ["Pallas Athena","Minerva"],
        "Zeus": ["Jupiter"],
        "Aphrodite": ["Venus"],
        "Hermes": ["Mercury"],
        "Medusa": ["Gorgon"],
        "Perseus": ["Perseus (hero)"]
    }
    if name in mapping:
        aliases = mapping[name] + aliases
    aliases += [f"{name} Greek", f"{name} myth"]
    return list(dict.fromkeys(aliases))

# ---------- OpenAI-based helpers (modern client) ----------
def ai_expand_bio(client: OpenAI, name: str, fixed_bio: str) -> str:
    system = "You are an expert in Greek myth and museum interpretation. Produce a museum-friendly expansion of a short bio."
    user = f"""Expand this concise bio about "{name}" into a three-paragraph museum-friendly introduction including: who they are, key myths, common artistic depictions, and suggested exhibition context.\n\nBio:\n{fixed_bio}"""
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0.2, max_tokens=600)
    return resp.choices[0].message.content

def ai_identify_deity(client: OpenAI, description: str) -> str:
    system = "You are an expert in Greek mythology and visual iconography."
    user = f"""Identify which Greek deity, hero, or creature is most likely referenced by this single-sentence description: "{description}".
Return a short answer with:
1) The best-fit name (one line).
2) A 2-3 sentence explanation linking visual cues to the deity/hero.
3) Two brief keywords the app can use to search museum collections for artworks (comma-separated)."""
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0.0, max_tokens=250)
    return resp.choices[0].message.content

def ai_personality_quiz(client: OpenAI, answers: Dict) -> str:
    system = "You are an interpretive museum educator who maps personality to mythic figures."
    user = f"""Given these short answers, determine the best-fit Greek deity/hero and provide: 1) the deity name, 2) a short psychological explanation (3-4 sentences), 3) three suggested keywords for searching related artworks. Answers: {answers}"""
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0.2, max_tokens=400)
    return resp.choices[0].message.content

def ai_art_analysis(client: OpenAI, metadata: Dict) -> str:
    system = "You are an art historian and museum curator."
    title = metadata.get("title","Untitled")
    artist = metadata.get("artistDisplayName","Unknown")
    date = metadata.get("objectDate","?")
    prompt = f"""Provide a short curator-style analysis of this artwork. Title: {title}; Artist: {artist}; Date: {date}; URL: {metadata.get('objectURL','')}. Sections: Overview; Iconography; Historical context; Mythological reading; Exhibition note."""
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":system},{"role":"user","content":prompt}], temperature=0.2, max_tokens=500)
    return resp.choices[0].message.content

# ---------- UI: Home (with API key input, tutorial, sources) ----------
def render_home():
    st.header("Home — How to use this site")
    st.markdown("""
**This site lets you explore Greek gods, heroes, and mythic creatures through museum artworks and AI-curated interpretation.**

**Important:** To use AI features (expanded bios, deity identification, personality quiz, curator analysis), enter your OpenAI API key below or set environment variable `OPENAI_API_KEY`.  
(Your key is stored only in this session and not sent anywhere else.)
    """)
    # API key input
    col_api, col_blank = st.columns([2,5])
    with col_api:
        key_input = st.text_input("Enter your OpenAI API Key (sk-...)", type="password", key="api_input")
        if st.button("Save API Key"):
            if key_input.strip():
                st.session_state["USER_OPENAI_KEY"] = key_input.strip()
                st.success("OpenAI API Key saved for this session.")
            else:
                st.error("Please enter a valid key.")
        if st.session_state.get("USER_OPENAI_KEY"):
            st.info("AI is enabled for this session.")
    # Step-by-step quick guide
    st.markdown("## Quick start")
    st.markdown("""
1. Go to **Greek Deities** tab → choose a figure → click **Expand description with AI** (optional).  
2. Click **Fetch related works** to gather MET artworks.  
3. Go to **Works & Analysis** → select a thumbnail → click **Generate AI Curatorial Analysis**.  
4. Try **Interactive Art Zone**: (a) describe a scene to identify the deity; (b) take the personality quiz; (c) ask about visual details.  
    """)
    # Sources
    st.markdown("## Sources & Acknowledgments")
    st.markdown("""
- Metropolitan Museum of Art — Open Access API (collectionapi.metmuseum.org)  
- OpenAI (GPT models) for text generation  
- Project: AI Museum Curator — Greek Mythology Edition  
    """)
    st.markdown("---")

# ---------- UI Layout (Tabs) ----------
render_home()

tabs = st.tabs(["Greek Deities", "Works & Analysis", "Interactive Art Zone"])

# ---------- Greek Deities tab ----------
with tabs[0]:
    st.header("Greek Deities / Heroes / Creatures")
    colL, colR = st.columns([2,1])
    with colL:
        selected = st.selectbox("Choose a figure:", MYTH_LIST, index=MYTH_LIST.index("Zeus"))
        fixed = FIXED_BIOS.get(selected, f"{selected} is a well-known figure in Greek mythology.")
        st.subheader(f"Short description — {selected}")
        st.write(fixed)
        st.markdown("**Expand description with AI** (recommended for exhibition-style text)")
        if st.button("Expand description with AI", key="expand_"+selected):
            client = get_openai_client()
            if not client:
                st.error("No OpenAI API key found. Enter it on Home to enable AI features.")
            else:
                with st.spinner("Generating expanded introduction..."):
                    expanded = ai_expand_bio(client, selected, fixed)
                    st.markdown("### AI Expanded Introduction")
                    st.write(expanded)
                    st.session_state["expanded_bio"] = expanded
                    st.session_state["last_bio_for"] = selected
        else:
            if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for") == selected:
                st.markdown("### AI Expanded Introduction (cached)")
                st.write(st.session_state["expanded_bio"])
    with colR:
        st.subheader("Related search aliases")
        st.write(generate_aliases(selected))
        if st.button("Fetch related works from MET", key="fetch_"+selected):
            all_ids = []
            for alias in generate_aliases(selected):
                ids = met_search_ids(alias, max_results=12)
                for i in ids:
                    if i not in all_ids:
                        all_ids.append(i)
            if not all_ids:
                st.info("No works found for this figure.")
            else:
                st.success(f"Found {len(all_ids)} candidate works.")
                st.session_state["related_ids"] = all_ids
                st.session_state["last_bio_for"] = selected

# ---------- Works & Analysis tab ----------
with tabs[1]:
    st.header("Works & Analysis")
    if "related_ids" not in st.session_state:
        st.info("No related works fetched. Go to Greek Deities and click 'Fetch related works from MET'.")
    else:
        ids = st.session_state["related_ids"]
        st.subheader("Gallery")
        cols = st.columns(4)
        for idx, oid in enumerate(ids):
            meta = met_get_object(oid)
            title = meta.get("title","Untitled")
            img_url = meta.get("primaryImageSmall") or meta.get("primaryImage")
            if img_url:
                img = fetch_image(img_url)
                if img:
                    with cols[idx % 4]:
                        st.image(img.resize((220,220)), caption=f"{title} ({oid})")
                        if st.button(f"Select {oid}", key=f"select_{oid}"):
                            st.session_state["selected_artwork"] = oid
        if "selected_artwork" in st.session_state:
            art_id = st.session_state["selected_artwork"]
            meta = met_get_object(art_id)
            st.markdown("---")
            st.subheader(f"{meta.get('title')}  —  Object ID: {art_id}")
            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
            st.write(f"**Date:** {meta.get('objectDate') or 'Unknown'}")
            st.write(f"**Medium:** {meta.get('medium') or 'Unknown'}")
            if meta.get("primaryImage"):
                image = fetch_image(meta.get("primaryImage"))
                if image:
                    st.image(image, use_column_width=True)
            st.markdown("**Source / Object URL:**")
            st.write(meta.get("objectURL") or "N/A")
            # AI analysis button
            client = get_openai_client()
            if st.button("Generate AI Curatorial Analysis"):
                if not client:
                    st.error("OpenAI API key required. Add it on Home.")
                else:
                    with st.spinner("Generating analysis..."):
                        analysis = ai_art_analysis(client, meta)
                        st.markdown("### AI Curatorial Analysis")
                        st.write(analysis)

# ---------- Interactive Art Zone ----------
with tabs[2]:
    st.header("Interactive Art Zone")
    st.markdown("Two sections: Art-based interactions (left) and Myth-based interactions (right).")
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Art-based Interactions")
        st.markdown("**Detail & Symbolism** — Ask about a visual detail of the selected artwork.")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork in Works & Analysis to use this feature.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            question = st.text_input("Ask about a detail (e.g., 'What does the owl symbolize?')", key="detail_q")
            if st.button("Ask curator about detail"):
                client = get_openai_client()
                if not client:
                    st.error("OpenAI API key required. Add it on Home.")
                else:
                    with st.spinner("Analyzing detail..."):
                        ans = ai_identify_deity(client, question) if False else None
                        # actually use ai to explain detail
                        prompt = f"A visitor asked: '{question}' about this artwork. Metadata: Title: {meta.get('title')}; Artist: {meta.get('artistDisplayName')}. Provide a short curator response explaining the visual detail and its possible symbolic meanings."
                        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=350)
                        st.write(resp.choices[0].message.content)

        st.markdown("---")
        st.subheader("Style Analyzer — Upload a sketch/photo")
        st.write("Upload a sketch or photo and optionally describe it. The AI will suggest which Greek art style/period it resembles.")
        uploaded = st.file_uploader("Upload sketch (jpg/png)", type=["jpg","jpeg","png"], key="upload_sketch")
        sketch_desc = st.text_input("Describe your sketch (optional)", key="sketch_desc")
        if uploaded and st.button("Analyze sketch"):
            client = get_openai_client()
            if not client:
                st.error("OpenAI API key required.")
            else:
                img = Image.open(uploaded).convert("RGB")
                st.image(img, caption="Uploaded sketch", use_column_width=False)
                # We won't send binary to model; we provide user description and offer visual clues in prompt
                prompt = f"User uploaded a sketch and described it as: '{sketch_desc}'. Suggest which ancient Greek art style/period it most resembles (Archaic black-figure vase, Classical sculpture, Hellenistic, etc.), explain visual clues to look for, and provide an informal classification."
                with st.spinner("Analyzing style..."):
                    resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.2, max_tokens=400)
                    st.write(resp.choices[0].message.content)

    with colB:
        st.subheader("Myth-based Interactions")
        st.markdown("**Describe a scene (one sentence)** → AI identifies the likely deity/hero and explains why, then fetches related artworks.")
        desc = st.text_input("Describe a scene or motif (e.g., 'A winged man holding a reflective shield')", key="myth_desc")
        if st.button("Identify deity from description"):
            client = get_openai_client()
            if not client:
                st.error("OpenAI API key required.")
            else:
                with st.spinner("Identifying..."):
                    ident = ai_identify_deity(client, desc)
                    st.markdown("### AI Identification Result")
                    st.write(ident)
                    # Try to extract keywords from AI reply by taking the last line or suggested keywords
                    # Simple heuristic: search MET using the selected deity or suggested keywords if present
                    # For robustness, use first token before newline as name candidate
                    # We'll also set selected figure (best effort)
                    # Quick attempt: find a name from known MYTH_LIST in the AI reply
                    chosen_name = None
                    for name in MYTH_LIST:
                        if name.lower() in ident.lower():
                            chosen_name = name
                            break
                    if chosen_name:
                        st.info(f"Selecting {chosen_name} and fetching related works.")
                        st.session_state["last_bio_for"] = chosen_name
                        all_ids = []
                        for alias in generate_aliases(chosen_name):
                            ids = met_search_ids(alias, max_results=10)
                            for i in ids:
                                if i not in all_ids:
                                    all_ids.append(i)
                        if all_ids:
                            st.session_state["related_ids"] = all_ids
                            st.success(f"Found {len(all_ids)} works for {chosen_name}. Go to Works & Analysis to browse.")
                        else:
                            st.info("No related works found automatically.")
                    else:
                        st.info("Could not confidently map to a single known figure. Please try a different description.")

        st.markdown("---")
        st.subheader("Which Greek Deity Are You? — Personality Quiz")
        st.write("Answer three short questions and let the AI map your personality to a Greek deity or hero.")
        q1 = st.selectbox("In a group project you are:", ["Leader", "Supporter", "Analyst", "Visionary"], key="quiz_q1")
        q2 = st.selectbox("You value most:", ["Wisdom", "Glory", "Pleasure", "Order"], key="quiz_q2")
        q3 = st.selectbox("In conflict you tend to:", ["Strategize", "Confront", "Avoid", "Negotiate"], key="quiz_q3")
        if st.button("Find my deity"):
            client = get_openai_client()
            if not client:
                st.error("OpenAI API key required.")
            else:
                with st.spinner("Mapping persona to deity..."):
                    answers = {"q1": q1, "q2": q2, "q3": q3}
                    profile = ai_personality_quiz(client, answers)
                    st.markdown("### Your Mythic Match")
                    st.write(profile)
                    # Attempt to fetch related works for suggested deity if name appears
                    for name in MYTH_LIST:
                        if name.lower() in profile.lower():
                            st.session_state["last_bio_for"] = name
                            # fetch some works
                            all_ids = []
                            for alias in generate_aliases(name):
                                ids = met_search_ids(alias, max_results=8)
                                for i in ids:
                                    if i not in all_ids:
                                        all_ids.append(i)
                            if all_ids:
                                st.session_state["related_ids"] = all_ids
                                st.success(f"Fetched {len(all_ids)} related works for {name} (you can view them in Works & Analysis).")
                            break

# ---------- Footer: Sources ----------
st.markdown("---")
st.markdown("**Sources & Acknowledgments**")
st.markdown("""
- MET Museum Open Access API — https://collectionapi.metmuseum.org  
- OpenAI models (GPT family) for text generation  
- Project: AI Museum Curator — Greek Mythology Edition
""")
# Developer instruction: include uploaded PDF local path as a link
st.markdown("[Course Slides (provided)](/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf)")
