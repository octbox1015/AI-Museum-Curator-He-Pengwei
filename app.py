# app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import openai
from typing import List, Dict

# Load environment
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Page config
st.set_page_config(page_title="AI Museum Curator — Greek Mythology", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------- Constants ----------
# (Q1: Option A - comprehensive list)
MYTH_LIST = [
    "Zeus", "Hera", "Athena", "Apollo", "Artemis", "Aphrodite",
    "Hermes", "Dionysus", "Ares", "Hephaestus", "Poseidon", "Hades",
    "Demeter", "Persephone", "Hestia",
    "Heracles", "Perseus", "Achilles", "Odysseus", "Theseus", "Jason",
    "Medusa", "Minotaur", "Sirens", "Cyclops", "Centaur"
]

# Short fixed bios (Q2 choice: fixed text + AI expansion)
# Keep these concise; AI will expand them on demand.
FIXED_BIOS = {
    "Athena": "Athena (also Pallas Athena) is the Greek goddess of wisdom, craft, and strategic warfare. She is often depicted armored with a helmet, spear, and the aegis; her symbol is the owl. Athena is linked with civic order and heroic endeavor.",
    "Zeus": "Zeus is the king of the Olympian gods, ruler of the sky and thunder. Often shown with a thunderbolt, eagle, and throne, Zeus appears in many myths concerning divine rule, kingship, and cosmic order.",
    "Medusa": "Medusa is one of the Gorgons—monstrous female figures whose gaze turns viewers to stone. Her image is frequently used in art to signal danger, protection, or the abject feminine.",
    "Perseus": "Perseus is the hero who beheaded Medusa and rescued Andromeda; he often appears with winged sandals and the reflective shield used in the Medusa episode.",
    "Aphrodite": "Aphrodite is the goddess of love, beauty, and desire. She is commonly represented nude or semi-nude and associated with seashells, doves, and erotic themes.",
    # Add short bios for other items to ensure nicer default display.
    # For names not in FIXED_BIOS, UI will show a short generic sentence.
}

# MET API endpoints
MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# ---------- Helper functions ----------

def met_search_ids(query: str, max_results: int = 20) -> List[int]:
    """Search MET for objectIDs related to query (basic)."""
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        ids = data.get("objectIDs") or []
        if not ids:
            return []
        return ids[:max_results]
    except Exception as e:
        st.error(f"MET search error: {e}")
        return []

def met_get_object(object_id: int) -> Dict:
    """Fetch MET object metadata JSON."""
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to fetch object {object_id}: {e}")
        return {}

def fetch_image_from_url(url: str) -> Image.Image:
    """Download and return PIL Image from URL."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        st.warning("Could not load image.")
        return None

def ai_expand_bio(fixed_bio: str, myth_name: str) -> str:
    """Use OpenAI to expand a fixed bio into a fuller myth background."""
    system_msg = "You are an expert in Greek myth and art history. Expand concise bios into a 3-paragraph museum-friendly but scholarly introduction."
    user_prompt = f"""Expand the following concise bio about "{myth_name}" into a clear museum-style introduction. Include:
- Who they/it is (1 paragraph)
- Key myths and narrative episodes (1 paragraph)
- Common artistic depictions and symbolic meanings and suggested exhibition context (1 paragraph)

Concise bio:
{fixed_bio}
"""
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":system_msg},
                {"role":"user","content":user_prompt}
            ],
            temperature=0.2,
            max_tokens=600
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI expansion failed: {e}")
        return fixed_bio

def ai_generate_art_analysis(metadata: Dict) -> str:
    """AI: generate curator-level analysis for an artwork (structured)."""
    title = metadata.get("title", "Untitled")
    artist = metadata.get("artistDisplayName", "Unknown")
    date = metadata.get("objectDate", "Unknown date")
    medium = metadata.get("medium", "Unknown medium")
    dept = metadata.get("department", "Unknown department")
    url = metadata.get("objectURL", "")
    prompt = f"""
You are a professional museum curator. Provide a structured analysis for the artwork:
Title: {title}
Artist: {artist}
Date: {date}
Medium: {medium}
Department: {dept}
URL: {url}

Output sections labeled: Overview; Historical & Artistic Context; Iconography & Symbols; Mythological Reading; Exhibition Recommendation.
Write for a general museum audience but include scholarly grounding and note speculative claims.
"""
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=700
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI art analysis failed: {e}")
        return "AI analysis unavailable."

def ai_compare_artworks(meta_a: Dict, meta_b: Dict) -> str:
    """AI: compare two artworks."""
    prompt = f"""
You are an art historian. Compare these two artworks. Provide:
- Quick ID lines
- Visual/compositional comparison
- Differences in style, technique, and period
- Differences in mythic narrative and representation
- A 30-50 word curatorial pairing note

Artwork A: {meta_a.get('title')} — {meta_a.get('artistDisplayName')} — {meta_a.get('objectDate')}
URL: {meta_a.get('objectURL')}

Artwork B: {meta_b.get('title')} — {meta_b.get('artistDisplayName')} — {meta_b.get('objectDate')}
URL: {meta_b.get('objectURL')}
"""
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2,
            max_tokens=800
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"AI comparison failed: {e}")
        return "Comparison unavailable."

def generate_aliases(name: str) -> List[str]:
    """Return a list of synonyms / aliases for searching MET API for better recall."""
    aliases = [name]
    low = name.lower()
    # common variants
    if name == "Athena":
        aliases += ["Pallas Athena", "Minerva"]
    if name == "Zeus":
        aliases += ["Jupiter"]
    if name == "Aphrodite":
        aliases += ["Venus"]
    if name == "Hermes":
        aliases += ["Mercury"]
    if name == "Perseus":
        aliases += ["Perseus (hero)"]
    if name == "Medusa":
        aliases += ["Gorgon", "Medousa"]
    # add general fallback searches
    aliases += [f"{name} Greek", f"{name} myth"]
    return list(dict.fromkeys(aliases))  # unique preserve order

# ---------- UI: Multi-tab layout (Q3: Multi-tab) ----------
tabs = st.tabs(["Home", "Greek Deities", "Works & Analysis", "Compare", "Course Materials"])

# ---- HOME ----
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
This site lets you explore Greek gods, heroes, and mythic creatures through:
- A short fixed introduction for each figure, **plus AI expansion** (museum-friendly).
- Automatically retrieved artworks from the MET Museum.
- Curator-level AI analyses for each artwork.

**Quick start**
1. Go to **Greek Deities** and pick a figure.  
2. Read the fixed bio and click *Expand with AI* to get a full museum-style text.  
3. Scroll to *Related Works* and pick an artwork to view detailed interpretation in **Works & Analysis**.
    """)

# ---- GREEK DEITIES TAB ----
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    st.caption("Select a figure to view a short fixed bio and request an AI expansion.")

    col1, col2 = st.columns([2,1])
    with col1:
        selected = st.selectbox("Choose a figure:", MYTH_LIST)
        fixed = FIXED_BIOS.get(selected, f"{selected} is a well-known figure in Greek mythology. Typical myths and artistic depictions vary.")
        st.subheader(f"Short description — {selected}")
        st.write(fixed)

        if st.button("Expand description with AI"):
            with st.spinner("Expanding with AI..."):
                expanded = ai_expand_bio(fixed, selected)
                st.markdown("### AI Expanded Introduction")
                st.write(expanded)
                # Save to session so other tabs can use the expanded text
                st.session_state["expanded_bio"] = expanded
        else:
            # if previously expanded, show toggle
            if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for") == selected:
                st.markdown("### AI Expanded Introduction (cached)")
                st.write(st.session_state["expanded_bio"])

        # store last selected
        st.session_state["last_bio_for"] = selected

    with col2:
        st.subheader("Related Searches")
        st.write("Aliases used to search MET API for better recall:")
        st.write(generate_aliases(selected))
        if st.button("Fetch related works from MET"):
            # search using aliases and combine results
            all_ids = []
            for alias in generate_aliases(selected):
                ids = met_search_ids(alias, max_results=12)
                for i in ids:
                    if i not in all_ids:
                        all_ids.append(i)
            if not all_ids:
                st.info("No works found for this figure.")
            else:
                st.success(f"Found {len(all_ids)} candidate works. Select one then go to 'Works & Analysis' tab.")
                st.session_state["related_ids"] = all_ids

    st.markdown("---")
    st.write("Tip: after fetching related works, go to the 'Works & Analysis' tab to view and analyze.")

# ---- WORKS & ANALYSIS TAB ----
with tabs[2]:
    st.header("Works & Analysis")
    if "related_ids" not in st.session_state:
        st.info("No related works fetched yet. Go to 'Greek Deities', select a figure, and click 'Fetch related works from MET'.")
    else:
        ids = st.session_state["related_ids"]
        # Show a gallery of thumbnails (first 12)
        st.subheader("Related Artworks (click to select)")
        cols = st.columns(4)
        selected_id = None
        for idx, object_id in enumerate(ids):
            try:
                meta = met_get_object(object_id)
                img_url = meta.get("primaryImageSmall") or meta.get("primaryImage")
                if img_url:
                    img = fetch_image_from_url(img_url)
                    if img:
                        with cols[idx % 4]:
                            st.image(img.resize((250,250)), use_column_width=False, caption=f"{meta.get('title')} ({object_id})")
                            if st.button(f"Select {object_id}", key=f"sel_{object_id}"):
                                st.session_state["selected_artwork"] = object_id
            except Exception:
                continue

        # If an artwork is selected, show details and analysis
        if "selected_artwork" in st.session_state:
            art_id = st.session_state["selected_artwork"]
            meta = met_get_object(art_id)
            st.markdown("---")
            st.subheader(f"{meta.get('title')}  —  Object ID: {art_id}")
            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
            st.write(f"**Date:** {meta.get('objectDate') or 'Unknown'}")
            st.write(f"**Medium:** {meta.get('medium') or 'Unknown'}")
            st.write(f"**Department:** {meta.get('department') or 'Unknown'}")
            if meta.get("primaryImage"):
                image = fetch_image_from_url(meta.get("primaryImage"))
                if image:
                    st.image(image, use_column_width=True)

            # Fixed bio context (if present)
            last_bio_for = st.session_state.get("last_bio_for")
            if last_bio_for:
                st.write(f"Context: selected figure — **{last_bio_for}**")
                fixed = FIXED_BIOS.get(last_bio_for, "")
                if fixed:
                    st.write("Short bio (fixed):")
                    st.write(fixed)
                if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for") == last_bio_for:
                    st.write("AI Expanded Introduction:")
                    st.write(st.session_state["expanded_bio"])

            # Generate analysis
            if st.button("Generate AI Curatorial Analysis"):
                with st.spinner("Generating analysis..."):
                    analysis = ai_generate_art_analysis(meta)
                    st.markdown("### AI Curatorial Analysis")
                    st.write(analysis)

# ---- COMPARE TAB ----
with tabs[3]:
    st.header("Compare Two Artworks")
    st.write("Enter two MET Object IDs (or use previously selected artwork).")
    id_a = st.text_input("Artwork A Object ID", value=st.session_state.get("selected_artwork",""))
    id_b = st.text_input("Artwork B Object ID", value="")
    if st.button("Compare artworks"):
        if not id_a or not id_b:
            st.error("Please provide both object IDs.")
        else:
            meta_a = met_get_object(id_a)
            meta_b = met_get_object(id_b)
            if meta_a and meta_b:
                with st.spinner("Generating comparison..."):
                    comp = ai_compare_artworks(meta_a, meta_b)
                    st.markdown("### Comparative Analysis (AI-generated)")
                    st.write(comp)

# ---- COURSE MATERIALS TAB ----
with tabs[4]:
    st.header("Course Materials & Background")
    st.markdown("""
This project is inspired by the course *Arts & Advanced Big Data*.  
Below are summarized sections from the course that frame this project.
    """)
    st.markdown("**Course slide PDF (uploaded):**")
    # Developer instruction: include the uploaded file path as the URL
    st.markdown(f"[Download / View slides](/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf)")

    st.markdown("---")
    st.subheader("AI Museum Curator — Goal & Workflow")
    st.write("""
- Goal: Build a web application that fetches real artwork data from a museum API and uses an AI model to act as an art curator.
- Workflow: MET API → Curator Prompt → Streamlit Display → User browsing & interpretation.
    """)

    st.subheader("Other project directions (summaries)")
    st.markdown("""
**Generative AI for Art Creation** — Create image/music/text with generative models; curate into a portfolio.  
**Multimodal Prompting** — Combine image + text input for analysis and code generation.  
**Art Data Visualization** — Gather datasets, clean with pandas, visualize with Plotly.  
**Creative Coding: Generative Poster 2.0** — Use Python + AI design suggestions to create poster series.
    """)

    st.caption("End of course materials.")
