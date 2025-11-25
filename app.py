import streamlit as st
import requests
import os
import openai
from graphviz import Digraph

# -----------------------------
# APP CONFIG
# -----------------------------
st.set_page_config(page_title="AI Museum Curator", layout="wide")

# OpenAI Key Input
st.sidebar.title("🔑 OpenAI API Key")
api_key = st.sidebar.text_input("Enter your API key:", type="password")
if api_key:
    openai.api_key = api_key

st.title("🏛️ AI Museum Curator")
st.write("Explore Greek mythology, artworks, and AI-powered curator insights.")

# ---------------------------------------------
# MET API — Search for artworks
# ---------------------------------------------
def search_met_artworks(query, has_images=True):
    url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    params = {"q": query, "hasImages": has_images}
    r = requests.get(url, params=params)
    data = r.json()
    return data.get("objectIDs", [])[:50]  # top 50 only

def fetch_artwork(object_id):
    url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}"
    r = requests.get(url)
    return r.json()

# ---------------------------------------------
# AI Curator Explanation
# ---------------------------------------------
def ai_explain_artwork(data):
    if not api_key:
        return "⚠️ No API Key."

    prompt = f"""
You are a professional art curator. Explain the following artwork in 2 paragraphs:

Title: {data.get('title')}
Artist: {data.get('artistDisplayName')}
Date: {data.get('objectDate')}
Medium: {data.get('medium')}
Culture: {data.get('culture')}
Period: {data.get('period')}
"""

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message["content"]
    except:
        return "⚠️ AI explanation error."


# ============================================================
# TAB NAVIGATION
# ============================================================
tab_home, tab_greek, tab_gallery, tab_lineages = st.tabs(
    ["Home", "Greek Deities", "Works & Analysis", "Mythic Lineages"]
)

# ============================================================
# 1. HOME
# ============================================================
with tab_home:
    st.subheader("📘 How to Use This App")
    st.markdown("""
1. Enter your **OpenAI API Key** in the left sidebar.
2. Choose a **Greek deity** to explore artworks and mythology.
3. Browse artworks with images, metadata, and AI explanations.
4. Explore the **Mythic Lineages** tree to understand divine genealogy.
    """)


# ============================================================
# 2. GREEK DEITIES → Real artwork from MET
# ============================================================
GODS = {
    "Zeus": ["Zeus", "Jupiter"],
    "Hera": ["Hera", "Juno"],
    "Poseidon": ["Poseidon", "Neptune"],
    "Athena": ["Athena", "Minerva"],
    "Ares": ["Ares", "Mars"],
    "Aphrodite": ["Aphrodite", "Venus"],
    "Apollo": ["Apollo"],
    "Artemis": ["Artemis", "Diana"],
    "Hermes": ["Hermes", "Mercury"],
    "Demeter": ["Demeter", "Ceres"],
    "Dionysus": ["Dionysus", "Bacchus"],
}

with tab_greek:
    st.header("⚡ Greek Myth Explorer")

    selected = st.selectbox("Choose a deity:", list(GODS.keys()))

    aliases = GODS[selected]
    st.markdown(f"**Search terms:** {', '.join(aliases)}")

    # Search MET
    object_ids = None
    for alias in aliases:
        object_ids = search_met_artworks(alias)
        if object_ids:
            break

    if not object_ids:
        st.warning("No artworks found.")
    else:
        st.success(f"Found {len(object_ids)} artworks.")
        for obj in object_ids:
            data = fetch_artwork(obj)
            if not data.get("primaryImageSmall"):
                continue

            st.image(data["primaryImageSmall"], width=350)
            st.write(f"### {data.get('title')}")
            st.write(f"**Artist:** {data.get('artistDisplayName','Unknown')}")
            st.write(f"**Date:** {data.get('objectDate','Unknown')}")
            st.write(f"**Medium:** {data.get('medium','Unknown')}")

            if st.button(f"Explain {obj}", key=f"exp_{obj}"):
                exp = ai_explain_artwork(data)
                st.write(exp)

            st.divider()


# ============================================================
# 3. WORKS & ANALYSIS — gallery view + detail view
# ============================================================
with tab_gallery:
    st.header("🖼️ Works & Analysis — Structured View")

    query = st.text_input("Search artworks from MET:")
    if query:
        ids = search_met_artworks(query)
        st.write(f"Found {len(ids)} results.")

        for obj in ids[:20]:
            a = fetch_artwork(obj)
            if not a.get("primaryImageSmall"):
                continue

            col1, col2 = st.columns([1,2])

            with col1:
                st.image(a["primaryImageSmall"], width=250)

            with col2:
                st.subheader(a.get("title"))
                st.write(f"**Artist:** {a.get('artistDisplayName','Unknown')}")
                st.write(f"**Date:** {a.get('objectDate')}")
                st.write(f"**Medium:** {a.get('medium')}")
                st.write(f"**Dimensions:** {a.get('dimensions')}")
                st.write(f"**Object ID:** {obj}")

                if st.button(f"Explain artwork {obj}", key=f"expgal_{obj}"):
                    st.write(ai_explain_artwork(a))

            st.markdown("---")


# ============================================================
# 4. Mythic Lineages — Full Greek Mythology Family Tree
# ============================================================
with tab_lineages:
    st.header("🌳 Mythic Lineages — Full Greek Mythology Family Tree")
    st.write("A hierarchical genealogy from primordial gods → Titans → Olympians → Heroes.")

    dot = Digraph(comment="Greek Myth Family Tree")
    dot.attr(rankdir="TB", size="8,12")

    # Primordial
    dot.node("Chaos", "Chaos")
    dot.node("Gaia", "Gaia (Earth)")
    dot.node("Uranus", "Uranus (Sky)")

    dot.edge("Chaos", "Gaia")
    dot.edge("Gaia", "Uranus")

    # Titans
    TITANS = ["Cronus", "Rhea", "Oceanus", "Hyperion", "Iapetus"]
    for t in TITANS:
        dot.node(t, t)
        dot.edge("Uranus", t)
        dot.edge("Gaia", t)

    # Olympians
    OLY = {
        "Cronus": ["Zeus", "Hera", "Poseidon", "Hades", "Hestia", "Demeter"]
    }
    for parent, children in OLY.items():
        for c in children:
            dot.node(c, c)
            dot.edge(parent, c)
            dot.edge("Rhea", c)

    # Zeus children
    ZEUS_CHILDREN = ["Apollo", "Artemis", "Ares", "Hephaestus", "Hermes", "Athena", "Dionysus"]
    for child in ZEUS_CHILDREN:
        dot.node(child, child)
        dot.edge("Zeus", child)

    # Heroes
    HEROES = {
        "Zeus": ["Perseus", "Heracles"],
        "Poseidon": ["Theseus"],
        "Hermes": ["Odysseus"]
    }
    for p, heroes in HEROES.items():
        for h in heroes:
            dot.node(h, h)
            dot.edge(p, h)

    st.graphviz_chart(dot)

