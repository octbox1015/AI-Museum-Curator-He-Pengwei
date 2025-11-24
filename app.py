# app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import openai
import base64
from typing import List, Dict

# Load environment
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Page config
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------- Constants ----------
MYTH_LIST = [
    "Zeus", "Hera", "Athena", "Apollo", "Artemis", "Aphrodite",
    "Hermes", "Dionysus", "Ares", "Hephaestus", "Poseidon", "Hades",
    "Demeter", "Persephone", "Hestia",
    "Heracles", "Perseus", "Achilles", "Odysseus", "Theseus", "Jason",
    "Medusa", "Minotaur", "Sirens", "Cyclops", "Centaur"
]

FIXED_BIOS = {
    "Athena": "Athena (Pallas Athena) is the goddess of wisdom, craft, and strategic warfare. She is often depicted armored with a helmet, spear, and the aegis; her symbol is the owl.",
    "Zeus": "Zeus is the king of the Olympian gods, ruler of the sky and thunder. Often shown with a thunderbolt and eagle.",
    "Medusa": "Medusa is one of the Gorgons—monstrous female figures whose gaze turns viewers to stone. Her image functions as protection and warning.",
    "Perseus": "Perseus is the hero who beheaded Medusa and rescued Andromeda, often shown with winged sandals and a reflective shield.",
    "Aphrodite": "Aphrodite is the goddess of love and beauty, frequently represented in nudity or semi-nudity and associated with the sea and doves."
}

MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# ---------- Helpers ----------
def met_search_ids(query: str, max_results: int = 20) -> List[int]:
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=10)
        r.raise_for_status()
        ids = r.json().get("objectIDs") or []
        return ids[:max_results]
    except Exception as e:
        st.error(f"MET search failed: {e}")
        return []

def met_get_object(object_id: int) -> Dict:
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to fetch object {object_id}: {e}")
        return {}

def fetch_image_from_url(url: str):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

def generate_aliases(name: str) -> List[str]:
    aliases = [name]
    if name == "Athena":
        aliases += ["Pallas Athena", "Minerva"]
    if name == "Zeus":
        aliases += ["Jupiter"]
    if name == "Aphrodite":
        aliases += ["Venus"]
    if name == "Hermes":
        aliases += ["Mercury"]
    if name == "Medusa":
        aliases += ["Gorgon"]
    aliases += [f"{name} Greek", f"{name} myth"]
    return list(dict.fromkeys(aliases))

# ---------- OpenAI wrappers ----------
def chat_completion(prompt: str, system: str = None, max_tokens: int = 600):
    messages = []
    if system:
        messages.append({"role":"system","content":system})
    messages.append({"role":"user","content":prompt})
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"OpenAI request failed: {e}")
        return "OpenAI error."

def expand_bio_with_ai(fixed_bio: str, name: str):
    system = "You are an expert in Greek myth and museum interpretation. Expand concisely into three museum-friendly paragraphs."
    prompt = f"""Expand this concise bio about "{name}" into a three-paragraph museum-friendly introduction including: who they are, key myths, common artistic depictions, and suggestions for exhibition context.\n\nBio:\n{fixed_bio}"""
    return chat_completion(prompt, system=system, max_tokens=500)

def ai_analyze_artwork(metadata: Dict):
    title = metadata.get("title","Untitled")
    artist = metadata.get("artistDisplayName","Unknown")
    date = metadata.get("objectDate","?")
    medium = metadata.get("medium","?")
    url = metadata.get("objectURL","")
    prompt = f"""You are a museum curator. Analyze the artwork:
Title: {title}
Artist: {artist}
Date: {date}
Medium: {medium}
URL: {url}

Provide labeled sections: Overview; Historical & Artistic Context; Iconography & Symbols; Mythological Reading; Exhibition Recommendation."""
    return chat_completion(prompt, max_tokens=700)

def ai_detail_symbolism(question: str, metadata: Dict):
    prompt = f"""A visitor asked: "{question}" about this artwork. Metadata: Title: {metadata.get('title')}; Artist: {metadata.get('artistDisplayName')}; Date: {metadata.get('objectDate')}. Provide a short curator response explaining the visual detail's possible symbolic meanings, and note if the interpretation is speculative."""
    return chat_completion(prompt, max_tokens=350)

def ai_style_match_from_image(user_text: str, img_bytes_b64: str):
    # We will use textual description + optional user sketch text to produce a style-match reply.
    prompt = f"""Given this user text describing an uploaded image/sketch: "{user_text}". The app also has the uploaded image (base64 provided). Without seeing the image here, provide guidance on which period or style of ancient Greek art the sketch most resembles (e.g., Archaic black-figure vase painting, Classical marble sculpture, Hellenistic dynamic composition). Explain key visual clues to look for and give a probable classification and short suggestion for attribution practice."""
    return chat_completion(prompt, max_tokens=500)

def ai_myth_identifier(description: str):
    prompt = f"""A user describes a scene in one sentence: "{description}". Identify which Greek deity/hero/creature is most likely referenced, explain why (visual cues or motifs), and suggest 2 related MET artworks to search for with short justification."""
    return chat_completion(prompt, max_tokens=400)

def ai_personality_quiz_responses(answers: Dict):
    # build narrative
    prompt = f"""Based on these short answers, determine which Greek god/hero the user most resembles. Answers: {answers}\nProvide: 1) a best-fit deity, 2) a short psychological explanation, 3) 3 recommended artworks (by theme) and why."""
    return chat_completion(prompt, max_tokens=500)

def generate_image_from_prompt(prompt_text: str, size: str = "1024x1024"):
    try:
        resp = openai.Image.create(
            prompt=prompt_text,
            n=1,
            size=size
        )
        img_b64 = resp['data'][0]['b64_json']
        img_bytes = base64.b64decode(img_b64)
        return Image.open(BytesIO(img_bytes))
    except Exception as e:
        st.error(f"Image generation failed: {e}")
        return None

# ---------- Layout: tabs ----------
tabs = st.tabs(["Home", "Greek Deities", "Works & Analysis", "Compare", "Interactive Art Zone", "Course Materials"])

# HOME
with tabs[0]:
    st.header("Welcome")
    st.markdown("""
Explore Greek gods, heroes, and mythic creatures via real museum artworks and AI-powered curatorial interpretation.
**Interactive Art Zone** contains hands-on tools: detail analysis, style-matching (user uploads), myth ID, personality quiz, and image generation.
    """)

# GREEK DEITIES
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    col1, col2 = st.columns([2,1])
    with col1:
        selected = st.selectbox("Choose a figure:", MYTH_LIST)
        fixed = FIXED_BIOS.get(selected, f"{selected} is a well-known figure in Greek mythology. Typical myths and artistic depictions vary.")
        st.subheader(f"Short description — {selected}")
        st.write(fixed)
        if st.button("Expand description with AI"):
            with st.spinner("Expanding..."):
                expanded = expand_bio_with_ai(fixed, selected)
                st.markdown("### AI Expanded Introduction")
                st.write(expanded)
                st.session_state["expanded_bio"] = expanded
                st.session_state["last_bio_for"] = selected
        else:
            if st.session_state.get("expanded_bio") and st.session_state.get("last_bio_for") == selected:
                st.markdown("### AI Expanded Introduction (cached)")
                st.write(st.session_state["expanded_bio"])
    with col2:
        st.subheader("Related search aliases")
        st.write(generate_aliases(selected))
        if st.button("Fetch related works from MET"):
            all_ids = []
            for alias in generate_aliases(selected):
                ids = met_search_ids(alias, max_results=12)
                for i in ids:
                    if i not in all_ids:
                        all_ids.append(i)
            if not all_ids:
                st.info("No works found.")
            else:
                st.success(f"Found {len(all_ids)} candidate works.")
                st.session_state["related_ids"] = all_ids

# WORKS & ANALYSIS
with tabs[2]:
    st.header("Works & Analysis")
    if "related_ids" not in st.session_state:
        st.info("Fetch related works from the Greek Deities tab first.")
    else:
        ids = st.session_state["related_ids"]
        st.subheader("Gallery (click to select)")
        cols = st.columns(4)
        for idx, oid in enumerate(ids):
            meta = met_get_object(oid)
            img_url = meta.get("primaryImageSmall") or meta.get("primaryImage")
            if img_url:
                img = fetch_image_from_url(img_url)
                if img:
                    with cols[idx % 4]:
                        st.image(img.resize((220,220)), caption=f"{meta.get('title')} ({oid})")
                        if st.button(f"Select {oid}", key=f"sel_{oid}"):
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
                image = fetch_image_from_url(meta.get("primaryImage"))
                if image:
                    st.image(image, use_column_width=True)
            if st.button("Generate AI Curatorial Analysis"):
                with st.spinner("Generating analysis..."):
                    analysis = ai_analyze_artwork(meta)
                    st.markdown("### AI Curatorial Analysis")
                    st.write(analysis)

# COMPARE
with tabs[3]:
    st.header("Compare Two Artworks")
    id_a = st.text_input("Artwork A Object ID", value=st.session_state.get("selected_artwork",""))
    id_b = st.text_input("Artwork B Object ID", value="")
    if st.button("Compare"):
        if not id_a or not id_b:
            st.error("Provide both IDs.")
        else:
            meta_a = met_get_object(id_a)
            meta_b = met_get_object(id_b)
            if meta_a and meta_b:
                with st.spinner("Comparing..."):
                    comp = ai_compare_artworks(meta_a, meta_b)
                    st.markdown("### Comparative Analysis")
                    st.write(comp)

# INTERACTIVE ART ZONE (C: two categories: Art-based / Myth-based)
with tabs[4]:
    st.header("Interactive Art Zone")
    st.markdown("Two sections: **Art-based Interactions** and **Myth-based Interactions**")
    sub = st.radio("Choose interaction category:", ["Art-based", "Myth-based"])

    if sub == "Art-based":
        st.subheader("Art-based Interactions")
        # ④ Detail Symbolism
        st.markdown("#### Detail & Symbolism (Ask about a visual detail)")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork in Works & Analysis first to ask about its details.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            question = st.text_input("Type a question about a detail in this artwork (e.g., 'What does the owl mean?'):")
            if st.button("Ask about detail"):
                with st.spinner("Analyzing detail..."):
                    answer = ai_detail_symbolism(question, meta)
                    st.write(answer)

        st.markdown("---")
        # ⑤ Style Analyzer (upload sketch)
        st.markdown("#### Style Analyzer — Upload a sketch/photo")
        st.write("Upload a simple sketch or photo. The AI will suggest which Greek art style/period it resembles and explain visual clues.")
        uploaded = st.file_uploader("Upload an image (jpg/png)", type=["png","jpg","jpeg"])
        user_sketch_note = st.text_input("Optional: Describe your sketch in a few words")
        if uploaded and st.button("Analyze uploaded sketch"):
            img = Image.open(uploaded).convert("RGB")
            st.image(img, caption="Uploaded sketch", use_column_width=False)
            # convert to base64 to provide context to prompt (not sending binary to model)
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            b64 = base64.b64encode(buffered.getvalue()).decode()
            with st.spinner("Analyzing style..."):
                style_resp = ai_style_match_from_image(user_sketch_note or "User sketch", b64)
                st.write(style_resp)

    else:
        st.subheader("Myth-based Interactions")
        # ⑨ Myth Identifier
        st.markdown("#### Myth Identifier — Describe a scene in one sentence")
        desc = st.text_input("Describe a scene or motif (e.g., 'A winged man holding a head and a shield that reflects faces')")
        if st.button("Identify myth"):
            with st.spinner("Identifying..."):
                res = ai_myth_identifier(desc)
                st.write(res)

        st.markdown("---")
        # ⑩ Which God Are You? quiz
        st.markdown("#### Which Greek Deity Are You? — Short quiz")
        q1 = st.selectbox("In a group project you are:", ["Leader", "Supporter", "Analyst", "Visionary"])
        q2 = st.selectbox("You value most:", ["Wisdom", "Glory", "Pleasure", "Order"])
        q3 = st.selectbox("In conflict you tend to:", ["Strategize", "Confront", "Avoid", "Negotiate"])
        if st.button("Find my deity"):
            answers = {"q1": q1, "q2": q2, "q3": q3}
            with st.spinner("Determining..."):
                profile = ai_personality_quiz_responses(answers)
                st.write(profile)

        st.markdown("---")
        # ⑪ Myth Image Generator (DALL·E)
        st.markdown("#### Myth Image Generator — Describe a scene for AI to illustrate")
        scene = st.text_area("Describe the mythological scene (style, mood, color, e.g., 'Perseus beheading Medusa, dramatic chiaroscuro, Baroque style')", height=120)
        size = st.selectbox("Image size", ["512x512","1024x1024"])
        if st.button("Generate image"):
            if not scene:
                st.error("Please describe a scene.")
            else:
                with st.spinner("Generating image (this may take a while)..."):
                    img = generate_image_from_prompt(scene, size=size)
                    if img:
                        st.image(img, caption="AI-generated myth scene", use_column_width=True)
                        # optionally provide download
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        st.download_button("Download image", data=buf.getvalue(), file_name="myth_scene.png", mime="image/png")

# COURSE MATERIALS
with tabs[5]:
    st.header("Course Materials & Slides")
    st.markdown("Course slides (uploaded):")
    # Use developer-provided local path; deployment will handle static serving or you can add pdf to repo.
    st.markdown("[Download / View slides](/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf)")
    st.markdown("""
**Notes**
- The app integrates MET Museum API, OpenAI for text generation and DALL·E for image generation.
- Be mindful of token usage when generating many AI responses.
""")
