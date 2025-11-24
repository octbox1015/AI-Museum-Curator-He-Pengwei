# app.py
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import base64
from dotenv import load_dotenv
import os
from typing import List, Dict

# Use the new OpenAI SDK client style
try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None  # we'll handle missing import in UI

load_dotenv()

# ---------- Config ----------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------- Constants ----------
MYTH_LIST = [
    "Zeus","Hera","Athena","Apollo","Artemis","Aphrodite","Hermes","Dionysus","Ares","Hephaestus",
    "Poseidon","Hades","Demeter","Persephone","Hestia","Heracles","Perseus","Achilles","Odysseus",
    "Theseus","Jason","Medusa","Minotaur","Sirens","Cyclops","Centaur","Prometheus","Orpheus",
    "Eros","Nike","The Muses","The Fates","The Graces","Hecate","Atlas","Pandora"
]

# Short fixed bios (base text) — AI will expand on demand
FIXED_BIOS = {
    "Zeus": "Zeus is the king of the Olympian gods, ruler of the sky and thunder. Often shown with a thunderbolt and eagle.",
    "Athena": "Athena (Pallas Athena) is goddess of wisdom, craft, and strategic warfare. Often shown armored with an owl as symbol.",
    "Medusa": "Medusa is one of the Gorgons whose gaze could turn viewers to stone; a complex symbol in ancient and modern art.",
    # (you can add more short bios as needed)
}

# MET API endpoints
MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# ---------- Helpers: MET ----------
def met_search_ids(query: str, max_results: int = 40) -> List[int]:
    """Search MET for objectIDs (tries to be broad)."""
    try:
        params = {"q": query, "hasImages": True}
        r = requests.get(MET_SEARCH, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        ids = data.get("objectIDs") or []
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
        st.error(f"MET object fetch failed for {object_id}: {e}")
        return {}

def fetch_image(url: str):
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        return None

def generate_aliases(name: str) -> List[str]:
    """Create search aliases to increase recall across MET."""
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

# ---------- Helpers: OpenAI (new client) ----------
def get_openai_client():
    """
    Create and return an OpenAI client using session-stored API key if provided,
    otherwise try environment variable OPENAI_API_KEY.
    """
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    if OpenAI is None:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        # Some environments accept OpenAI(api_key=...) or OpenAI()
        try:
            return OpenAI()
        except Exception:
            return None

def chat_complete(client: OpenAI, messages: List[Dict], model: str = "gpt-4o-mini", max_tokens: int = 700, temperature: float = 0.2):
    """Call OpenAI Chat Completions (new client)."""
    if client is None:
        return "OpenAI client not configured. Enter API key on Home page."
    try:
        resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
        return resp.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"

def image_generate(client: OpenAI, prompt_text: str, size: str = "1024x1024"):
    """Generate image using new images endpoint if available."""
    if client is None:
        return None, "OpenAI client not configured."
    try:
        # Depending on SDK, the method may be images.generate or images.create.
        # We'll try common names and handle exceptions.
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

# ---------- AI Prompting: structured ----------
def expand_bio_ai(client: OpenAI, name: str, base_bio: str):
    system = "You are an expert in Greek mythology and museum interpretation. Produce a concise, museum-friendly 3-paragraph introduction."
    user = f"Expand this short bio about {name} into three paragraphs: who they are; major myths and narrative episodes; common artistic representations and exhibition notes.\n\nShort bio:\n{base_bio}"
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=500)

def generate_curator_analysis(client: OpenAI, metadata: Dict):
    system = "You are a professional museum curator writing accessible but scholarly labels and short essays."
    title = metadata.get("title","Untitled")
    artist = metadata.get("artistDisplayName","Unknown")
    date = metadata.get("objectDate","Unknown")
    medium = metadata.get("medium","Unknown")
    objname = metadata.get("objectName","Object")
    url = metadata.get("objectURL","")
    user = f"""Analyze this artwork for a museum audience. Provide labeled sections:
1) Identification line (Title — Artist — Date — Medium)
2) Short Overview (2-3 sentences)
3) Historical & Artistic Context (3-5 sentences)
4) Iconography & Symbols (3-5 sentences)
5) Mythological Reading / Narrative Connection (2-4 sentences)
6) Exhibition Recommendation (15-40 words)
Metadata:
ObjectName: {objname}
Title: {title}
Artist: {artist}
Date: {date}
Medium: {medium}
URL: {url}
"""
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=800)

def ai_answer_detail(client: OpenAI, question: str, metadata: Dict):
    system = "You are a museum educator answering visitors' questions about visual detail and symbolism."
    user = f"Visitor asked: '{question}' about this artwork titled '{metadata.get('title')}'. Provide a concise curator response explaining possible symbolic meanings. Note if speculative."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=400)

def ai_style_match(client: OpenAI, user_note: str):
    system = "You are an art historian specialized in ancient Mediterranean art."
    user = f"User described/uploaded a sketch: '{user_note}'. Without seeing the image, explain what stylistic features would indicate Archaic black-figure vase painting vs Classical sculpture vs Hellenistic dramatic composition. Provide questions the user should check visually."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=500)

def ai_myth_identifier(client: OpenAI, description: str):
    system = "You are an expert in Greek myth and iconography."
    user = f"Identify which Greek deity/hero/creature best matches this short description: '{description}'. Explain the visual cues and suggest two MET object search terms."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=400)

def ai_personality_quiz(client: OpenAI, answers: Dict):
    system = "You are a playful curator mapping personality answers to Greek deity archetypes."
    user = f"Answers: {answers}. Based on these, suggest the closest Greek deity, a short psychological explanation (3-4 lines), and recommend 3 artwork themes (not specific IDs)."
    return chat_complete(client, [{"role":"system","content":system},{"role":"user","content":user}], max_tokens=400)

# ---------- UI: Tabs ----------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone","Course Materials"])

# ---- HOME ----
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
**What this app does:**  
Explore Greek gods, heroes, and mythic creatures through real museum collections (MET) and AI-generated curator texts.  
- Select a deity → read a short bio (human-written) + expand with AI.  
- Fetch related artworks (sculpture, vase, coins, paintings, textiles, etc.).  
- View each object's metadata and receive a structured, curator-level analysis.
    """)
    st.subheader("What you can do")
    st.markdown("""
- Browse mythological figures and learn their stories.  
- Explore related artworks across object types.  
- Ask about visual details and symbolism.  
- Upload a sketch/photo to get a style-match explanation.  
- Try a short quiz to see which deity you resemble.  
- Generate a new myth image with AI (DALL·E).
    """)
    st.subheader("Step-by-step guide")
    st.markdown("""
1. Open **Greek Deities** and choose a figure.  
2. Click **Expand description with AI** to get a museum-style introduction.  
3. Click **Fetch related works** to find artworks from the MET.  
4. Go to **Works & Analysis** and click a thumbnail to view details and generate curatorial analysis.  
5. Use **Interactive Art Zone** for close-looking, style analysis, myth ID, quiz, and image generation.  
    """)
    st.subheader("FAQ")
    st.markdown("""
**Q: Why do I see 'OpenAI client not configured'?**  
A: Enter your OpenAI API Key below (session-only) and press Save — the app will then use this key for all AI operations.

**Q: Will my API key be stored?**  
A: The key is stored only in your browser session (Streamlit session state). If you want persistent deployment use Streamlit Secrets.

**Q: What object types are supported?**  
A: All MET object types with images (vases, sculptures, coins, textiles, paintings, prints, decorative arts).
    """)

    st.markdown("---")
    st.subheader("Enter your OpenAI API Key (session only)")
    key_input = st.text_input("Paste your OpenAI API Key (sk-...):", type="password")
    if st.button("Save API Key"):
        if not key_input:
            st.warning("Please paste a valid API Key.")
        else:
            st.session_state["OPENAI_API_KEY"] = key_input
            st.success("API Key saved to session. AI features enabled.")
    if st.session_state.get("OPENAI_API_KEY"):
        st.info("OpenAI API Key present in session. You may also set OPENAI_API_KEY in environment or Streamlit Secrets for persistent deployment.")

# ---- GREEK DEITIES ----
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    selected = st.selectbox("Choose a figure:", MYTH_LIST)
    base_bio = FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth, with many visual representations across media.")
    st.subheader(f"Short description — {selected}")
    st.write(base_bio)

    client = get_openai_client()
    if st.button("Expand description with AI"):
        if client is None:
            st.error("OpenAI client not configured. Enter your API key on the Home page.")
        else:
            with st.spinner("Expanding with AI..."):
                expanded = expand_bio_ai(client, selected, base_bio)
                st.markdown("### AI Expanded Introduction")
                st.write(expanded)
                # cache for session
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
            ids = met_search_ids(alias, max_results=24)
            for i in ids:
                if i not in all_ids:
                    all_ids.append(i)
        if not all_ids:
            st.info("No works found for this figure.")
        else:
            st.success(f"Found {len(all_ids)} candidate works.")
            st.session_state["related_ids"] = all_ids

# ---- WORKS & ANALYSIS ----
with tabs[2]:
    st.header("Works & Analysis — View & Analyze Objects")
    if "related_ids" not in st.session_state:
        st.info("No related works yet. Go to 'Greek Deities' and fetch related works for a selected figure.")
    else:
        ids = st.session_state["related_ids"]
        st.subheader("Gallery (click a thumbnail to select)")
        cols = st.columns(4)
        for idx, oid in enumerate(ids):
            meta = met_get_object(oid)
            title = meta.get("title") or meta.get("objectName") or f"Object {oid}"
            img_url = meta.get("primaryImageSmall") or meta.get("primaryImage")
            if img_url:
                img = fetch_image(img_url)
                if img:
                    with cols[idx % 4]:
                        st.image(img.resize((220, 220)), caption=f"{title} ({oid})")
                        if st.button(f"Select {oid}", key=f"select_{oid}"):
                            st.session_state["selected_artwork"] = oid

        if "selected_artwork" in st.session_state:
            art_id = st.session_state["selected_artwork"]
            meta = met_get_object(art_id)
            st.markdown("---")
            st.subheader(f"{meta.get('title') or meta.get('objectName')}  —  Object ID: {art_id}")
            # show key metadata fields
            st.write(f"**Object Name:** {meta.get('objectName')}")
            st.write(f"**Classification:** {meta.get('classification')}")
            st.write(f"**Culture:** {meta.get('culture')}")
            st.write(f"**Department:** {meta.get('department')}")
            st.write(f"**Medium:** {meta.get('medium')}")
            st.write(f"**Accession Number:** {meta.get('accessionNumber')}")
            st.markdown(f"[MET object page]({meta.get('objectURL')})")
            # show image(s)
            if meta.get("primaryImage"):
                img = fetch_image(meta.get("primaryImage"))
                if img:
                    st.image(img, use_column_width=True)
            # AI analysis
            client = get_openai_client()
            if st.button("Generate AI Curatorial Analysis"):
                if client is None:
                    st.error("OpenAI client not configured. Enter API key on Home page.")
                else:
                    with st.spinner("Generating curator analysis..."):
                        analysis = generate_curator_analysis(client, meta)
                        st.markdown("### AI Curatorial Analysis")
                        st.write(analysis)

# ---- INTERACTIVE ART ZONE ----
with tabs[3]:
    st.header("Interactive Art Zone — Art-based / Myth-based")
    section = st.radio("Choose category:", ["Art-based", "Myth-based"])

    client = get_openai_client()

    if section == "Art-based":
        st.subheader("Detail & Symbolism — Ask about an element")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork in Works & Analysis to ask about its details.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            q = st.text_input("Type a question about a visual detail (e.g., 'What does the owl mean?'):")
            if st.button("Ask detail"):
                if client is None:
                    st.error("OpenAI client not configured.")
                else:
                    with st.spinner("Answering..."):
                        ans = ai_answer_detail(client, q, meta)
                        st.write(ans)

        st.markdown("---")
        st.subheader("Style Analyzer — Upload a sketch or photo")
        st.write("Upload a sketch or photo; add a short description; AI will explain which ancient Greek style it most closely resembles and what visual clues to check.")
        uploaded = st.file_uploader("Upload sketch/photo", type=["png","jpg","jpeg"])
        note = st.text_input("Optional: describe your sketch (materials, lines, shapes)")
        if uploaded and st.button("Analyze sketch"):
            buffered = BytesIO(uploaded.getvalue())
            image = Image.open(buffered).convert("RGB")
            st.image(image, caption="Uploaded", use_column_width=False)
            # We do not send image binary to model; we send user's textual description and guidance.
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                with st.spinner("Analyzing style..."):
                    resp = ai_style_match(client, note or "User uploaded sketch")
                    st.write(resp)

    else:
        st.subheader("Myth Identifier — Describe a scene in one sentence")
        desc = st.text_input("Describe a scene or motif (e.g., 'A winged youth holding a severed head reflected in a shield')")
        if st.button("Identify myth"):
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                with st.spinner("Identifying..."):
                    r = ai_myth_identifier(client, desc)
                    st.write(r)

        st.markdown("---")
        st.subheader("Which Greek Deity Are You? — Short quiz")
        q1 = st.selectbox("In a group project you are:", ["Leader","Supporter","Analyst","Visionary"])
        q2 = st.selectbox("You value most:", ["Wisdom","Glory","Pleasure","Order"])
        q3 = st.selectbox("In conflict you tend to:", ["Strategize","Confront","Avoid","Negotiate"])
        if st.button("Find my deity"):
            if client is None:
                st.error("OpenAI client not configured.")
            else:
                answers = {"role":q1,"value":q2,"conflict":q3}
                with st.spinner("Thinking..."):
                    profile = ai_personality_quiz(client, answers)
                    st.markdown("### Your Deity Profile")
                    st.write(profile)

        st.markdown("---")
        st.subheader("Myth Image Generator — Describe a scene")
        scene = st.text_area("Describe a myth scene with style and mood (e.g., 'Perseus beheading Medusa, dramatic chiaroscuro')", height=120)
        size = st.selectbox("Image size", ["512x512","1024x1024"])
        if st.button("Generate image"):
            if client is None:
                st.error("OpenAI client not configured.")
            elif not scene.strip():
                st.error("Please provide a scene description.")
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

# ---- COURSE MATERIALS (optional) ----
with tabs[4]:
    st.header("Course Materials (Reference)")
    st.markdown("You can download or view the course slides (uploaded).")
    st.markdown("[Download / View slides](/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf)")
    st.caption("If deploying publicly, consider moving the PDF into the repository and updating the link.")

# END
