import streamlit as st
import requests
import openai
import os
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
from collections import Counter


# -----------------------------
# Load OpenAI Key
# -----------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


# -----------------------------
# Streamlit Page Setup
# -----------------------------
st.set_page_config(
    page_title="AI Museum Curator — Greek Mythology",
    page_icon="🏛️",
    layout="wide"
)


# -----------------------------
# Title + Description
# -----------------------------
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

st.markdown("""
Welcome to **AI Museum Curator — Greek Mythology Edition**, an interactive application that uses:

- **MET Museum Open API**  
- **OpenAI GPT models**  
- **Art-historical curatorial writing**  

to generate intelligent, museum-style interpretations of artworks related to **Ancient Greek mythology**.

Explore artworks, compare styles, and discover mythological symbolism through AI-powered curation.
""")


# -----------------------------
# Usage Guide (expandable)
# -----------------------------
with st.expander("🎮 **How to Use This App**", expanded=True):
    st.markdown("""
### 🔍 1. Enter a Greek Myth Keyword
Examples: *“Medusa”, “Athena”, “Apollo”, “Perseus”, “Heracles”, “Trojan War”, “Greek vase”*.

### 🖼️ 2. Choose a Mode
- **Single Artwork** → explore 1 artwork
- **Comparative Analysis** → compare 2 artworks

### 🎲 3. Select / Randomize
Use random selection or choose object IDs manually.

### 🧠 4. Generate AI Curatorial Text
Click:
- **Generate Curatorial Text**  
- **Fetch & Compare** (for comparative mode)

### 🎨 5. View Details
Includes:
- High-res image  
- Metadata  
- Dominant colors  
- AI analysis  
""")


# -----------------------------
# Course Background (required)
# -----------------------------
st.markdown("""
---

## 📚 Course Background: *Arts & Advanced Big Data*

This project follows one of the five official project directions:

- **AI Museum Curator** *(this project)*
- **Generative AI for Art Creation**
- **Multimodal Prompting**
- **Art Data Visualization**
- **Creative Coding: Generative Poster 2.0***

---
""")


# -----------------------------
# Sidebar Controls
# -----------------------------
st.sidebar.header("🔧 Controls")

mode = st.sidebar.selectbox(
    "Mode",
    ["Single Artwork", "Comparative Analysis"]
)

query = st.sidebar.text_input("Greek Myth Keyword", "Medusa")

randomize = st.sidebar.checkbox("Random Selection", value=True)


# -----------------------------
# MET API functions
# -----------------------------
def search_met(query):
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/search?q={query}"
    data = requests.get(url).json()
    return data.get("objectIDs", [])


def get_artwork(object_id):
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}"
    return requests.get(url).json()


def get_dominant_colors(image, num_colors=5):
    image = image.resize((150, 150))
    pixels = list(image.getdata())
    counter = Counter(pixels)
    return counter.most_common(num_colors)


# -----------------------------
# AI Curator Prompts
# -----------------------------
def ai_curate(artwork):
    prompt = f"""
You are a professional museum curator specializing in Ancient Greek mythology.

Analyze this artwork:

Title: {artwork.get('title')}
Artist: {artwork.get('artistDisplayName')}
Date: {artwork.get('objectDate')}
Medium: {artwork.get('medium')}
Culture: {artwork.get('culture')}
Period: {artwork.get('period')}

Write sections:
1. Overview  
2. Historical & artistic context  
3. Iconography & symbolism  
4. Mythological narrative interpretation  
5. Contemporary relevance  
6. Exhibition recommendation  
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"]


def ai_compare(a, b):
    prompt = f"""
Compare these two artworks from a curatorial perspective.

ARTWORK A:
{a.get('title')} ({a.get('objectDate')}) — {a.get('medium')}

ARTWORK B:
{b.get('title')} ({b.get('objectDate')}) — {b.get('medium')}

Write:
1. Comparative overview  
2. Stylistic differences  
3. Mythological interpretation  
4. Shared themes  
5. Curatorial pairing suggestion  
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"]


# -----------------------------
# MAIN: Single Artwork
# -----------------------------
if mode == "Single Artwork":

    st.header("🎨 Single Artwork Exploration")

    if st.sidebar.button("Search"):
        st.session_state.ids = search_met(query)

    ids = st.session_state.get("ids", [])

    if not ids:
        st.warning("No artworks found.")
    else:
        object_id = st.sidebar.selectbox("Select Object ID", ids)

        artwork = get_artwork(object_id)

        img_url = artwork.get("primaryImage")

        if img_url:
            img = Image.open(BytesIO(requests.get(img_url).content))
            st.image(img, caption=artwork.get("title"), use_column_width=True)

            st.subheader("🎨 Dominant Colors")
            colors = get_dominant_colors(img)
            st.write(colors)

        st.subheader("📘 Metadata")
        st.json(artwork)

        if st.button("Generate Curatorial Text"):
            with st.spinner("Curating..."):
                text = ai_curate(artwork)
            st.subheader("🧠 AI Curatorial Text")
            st.write(text)


# -----------------------------
# MAIN: Comparative Mode
# -----------------------------
else:
    st.header("⚖️ Comparative Artwork Analysis")

    if st.sidebar.button("Search"):
        st.session_state.ids = search_met(query)

    ids = st.session_state.get("ids", [])

    if not ids:
        st.warning("No artworks found.")
    else:
        id_a = st.sidebar.selectbox("Artwork A", ids)
        id_b = st.sidebar.selectbox("Artwork B", ids)

        art_a = get_artwork(id_a)
        art_b = get_artwork(id_b)

        col1, col2 = st.columns(2)
        with col1:
            st.image(art_a.get("primaryImage"), caption=art_a.get("title"), use_column_width=True)
        with col2:
            st.image(art_b.get("primaryImage"), caption=art_b.get("title"), use_column_width=True)

        if st.button("Fetch & Compare"):
            with st.spinner("Analyzing..."):
                result = ai_compare(art_a, art_b)
            st.subheader("🧠 AI Comparative Curatorial Analysis")
            st.write(result)
