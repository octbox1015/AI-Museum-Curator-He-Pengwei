import streamlit as st
import requests
import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import openai

# Load API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---------- Greek Myth List ----------
GREEK_MYTH_LIST = [
    "Zeus", "Hera", "Athena", "Apollo", "Artemis", "Aphrodite",
    "Hermes", "Dionysus", "Ares", "Poseidon", "Hades",
    "Medusa", "Perseus", "Achilles", "Heracles", "Odysseus"
]

# ---------- Functions ----------

def get_myth_background(myth):
    """Generate myth background using GPT."""
    prompt = f"""
    Provide a clear, engaging overview of the Greek mythological figure: {myth}.
    Include:
    - Who they are
    - Major myths
    - Symbolism
    - Common artistic representations
    Write in 3–5 paragraphs.
    """
    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content


def search_met_api(query):
    """Search MET API for artworks related to the myth."""
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/search?q={query}"
    r = requests.get(url).json()
    return r.get("objectIDs", [])[:20]  # limit for performance


def get_artwork_details(object_id):
    """Fetch MET artwork details."""
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}"
    return requests.get(url).json()


def generate_art_analysis(metadata):
    """Generate AI-based curatorial analysis."""
    prompt = f"""
    You are an expert museum curator. Analyze the following artwork in a structured format:

    Title: {metadata.get('title')}
    Artist: {metadata.get('artistDisplayName')}
    Date: {metadata.get('objectDate')}
    Medium: {metadata.get('medium')}
    Culture: {metadata.get('culture')}
    Period: {metadata.get('period')}
    Department: {metadata.get('department')}

    Provide:
    1) Overview
    2) Historical & Artistic Context
    3) Iconography & Symbolism
    4) Mythological Interpretation
    5) Exhibition Recommendation
    """

    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content


def generate_comparison(meta1, meta2):
    """Compare two artworks using AI."""
    prompt = f"""
    Compare these two artworks like a museum curator.

    Artwork A:
    {meta1.get("title")} — {meta1.get("artistDisplayName")}, {meta1.get("objectDate")}

    Artwork B:
    {meta2.get("title")} — {meta2.get("artistDisplayName")}, {meta2.get("objectDate")}

    Provide:
    - Visual composition comparison
    - Stylistic & material differences
    - Mythological narrative differences
    - Symbolism
    - Curatorial pairing recommendation
    """
    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content


# ---------- Streamlit App Structure ----------

st.set_page_config(page_title="AI Museum Curator: Greek Myth", layout="wide")

st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

tabs = st.tabs(["Home", "Greek Myth Explorer", "Artwork Viewer", 
                "Comparative Analysis", "Course Background"])


# ------------------ HOME TAB ------------------
with tabs[0]:
    st.header("Welcome to AI Museum Curator")
    st.markdown("""
    Explore Ancient Greek mythology through museum artworks and AI-generated curatorial interpretation.

    ## 🔧 How to Use
    1. Go to **Greek Myth Explorer**
    2. Choose a mythological figure
    3. Read AI-generated myth background
    4. View related artworks
    5. Select one → get full curator-style analysis
    6. For comparison → use **Comparative Analysis**
    """)


# ------------------ MYTH EXPLORER TAB ------------------
with tabs[1]:
    st.header("🔱 Greek Myth Explorer")

    myth = st.selectbox("Choose a Greek Myth Figure:", GREEK_MYTH_LIST)

    if myth:
        st.subheader(f"📖 Myth Background: {myth}")
        with st.spinner("Generating myth interpretation..."):
            myth_text = get_myth_background(myth)
        st.write(myth_text)

        st.subheader("🏺 Related Artworks from MET Museum")
        ids = search_met_api(myth)

        if not ids:
            st.write("No artworks found.")
        else:
            chosen = st.radio("Select an Artwork ID:", ids)
            st.session_state["selected_artwork"] = chosen
            st.success("Now go to **Artwork Viewer** to read full analysis.")


# ------------------ ARTWORK VIEWER TAB ------------------
with tabs[2]:
    st.header("🎨 Artwork Viewer & AI Curatorial Analysis")

    if "selected_artwork" not in st.session_state:
        st.info("Please choose an artwork from the **Greek Myth Explorer** tab.")
    else:
        art_id = st.session_state["selected_artwork"]
        metadata = get_artwork_details(art_id)

        st.subheader(metadata.get("title", "Untitled"))
        st.write(f"**Artist:** {metadata.get('artistDisplayName')}")
        st.write(f"**Date:** {metadata.get('objectDate')}")
        st.write(f"**Medium:** {metadata.get('medium')}")
        st.write(f"**Department:** {metadata.get('department')}")

        img_url = metadata.get("primaryImage")
        if img_url:
            img_data = requests.get(img_url).content
            st.image(Image.open(BytesIO(img_data)), use_column_width=True)

        st.subheader("🧠 AI Curatorial Analysis")
        with st.spinner("Generating analysis..."):
            analysis = generate_art_analysis(metadata)
        st.write(analysis)


# ------------------ COMPARATIVE ANALYSIS TAB ------------------
with tabs[3]:
    st.header("⚖️ Comparative Artwork Analysis")

    id1 = st.text_input("Artwork A Object ID")
    id2 = st.text_input("Artwork B Object ID")

    if st.button("Compare"):
        meta1 = get_artwork_details(id1)
        meta2 = get_artwork_details(id2)

        with st.spinner("Generating comparative analysis..."):
            comp = generate_comparison(meta1, meta2)

        st.write(comp)


# ------------------ COURSE BACKGROUND TAB ------------------
with tabs[4]:
    st.header("📚 Course Background")
    st.markdown("""
    ## AI Museum Curator  
    - Goal: Web app that fetches museum artwork data and generates curator-level interpretations  
    - How it works: Metadata → Curator Prompt → Streamlit Display  

    ---

    ## Generative AI for Art Creation  
    - Goal: Create AI-generated artworks (images/music/text)  
    - How it works: Model → Prompt → Portfolio  

    ---

    ## Multimodal Prompting  
    - Combine images + text  
    - AI performs visual analysis and generates code  

    ---

    ## Art Data Visualization  
    - Collect and analyze datasets  
    - Build dashboards using Plotly  

    ---

    ## Creative Coding — Generative Poster 2.0  
    - Use Python to generate posters  
    - AI gives design suggestions  
    """)
