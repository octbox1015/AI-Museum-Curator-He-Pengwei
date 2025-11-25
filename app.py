import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import time
import pandas as pd
import altair as alt
import re

# ---------------- Constants ----------------
MYTH_LIST = [
    "Zeus","Hera","Athena","Apollo","Artemis","Aphrodite","Hermes","Dionysus","Ares","Hephaestus",
    "Poseidon","Hades","Demeter","Persephone","Hestia","Heracles","Perseus","Achilles","Odysseus",
    "Theseus","Jason","Medusa","Minotaur","Sirens","Cyclops","Centaur","Prometheus","Orpheus",
    "Eros","Nike","The Muses","The Fates","The Graces","Hecate","Atlas","Pandora"
]

MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# ---------------- Helpers ----------------
@st.cache_data
def met_search_ids(query: str, max_results=100):
    params = {"q": query, "hasImages": True}
    r = requests.get(MET_SEARCH, params=params, timeout=10)
    r.raise_for_status()
    ids = r.json().get("objectIDs") or []
    return ids[:max_results]

@st.cache_data
def met_get_object(object_id: int):
    r = requests.get(MET_OBJECT.format(object_id), timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_image(meta):
    urls = [meta.get("primaryImageSmall"), meta.get("primaryImage")]
    for u in urls:
        if u:
            try:
                r = requests.get(u, timeout=10)
                r.raise_for_status()
                return Image.open(BytesIO(r.content))
            except:
                continue
    return None

# ---------------- UI ----------------
st.set_page_config(page_title="AI Museum Curator", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------------- Tabs ----------------
tabs = st.tabs(["Home","Greek Deities & Works","Interactive Art Zone"])

# ---------------- HOME ----------------
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
Explore Greek gods, heroes, and mythic creatures via MET collections.  

**Quick guide:**  
- Go to **Greek Deities & Works**, select a figure or view popular works.  
- Click a card to view artwork details (with curator notes).  
- Use **Interactive Art Zone** to identify myths or explore archetypes.  

**Big Data Analysis:**  
- Time period trends of artworks  
- Media and material distribution  
- Most depicted mythological figures  
- Geographic and cultural spread  
- Art style trends
    """)

# ---------------- GREEK DEITIES & WORKS ----------------
with tabs[1]:
    st.header("Greek Deities & Popular Works")
    selected = st.selectbox("Choose a figure (optional):", [""] + MYTH_LIST)
    st.markdown("**Note:** Leaving blank shows most famous works across Greek Mythology.")

    # ---------------- Fetch artworks ----------------
    if selected:
        ids = met_search_ids(selected, max_results=50)
    else:
        ids = met_search_ids("Greek Myth", max_results=50)

    artworks = []
    for oid in ids:
        meta = met_get_object(oid)
        img = fetch_image(meta)
        if img:
            artworks.append({"id": oid, "meta": meta, "img": img})

    # ---------------- Display works as grid ----------------
    st.subheader("Artworks / Items Grid")
    per_row = 4
    rows = math.ceil(len(artworks)/per_row)
    for r in range(rows):
        cols = st.columns(per_row)
        for c in range(per_row):
            idx = r*per_row + c
            if idx < len(artworks):
                art = artworks[idx]
                with cols[c]:
                    st.image(art["img"].resize((200,200)))
                    st.markdown(f"**{art['meta'].get('title') or 'Untitled'}**")
                    with st.expander("View Details"):
                        st.markdown(f"**Artist:** {art['meta'].get('artistDisplayName') or 'Unknown'}")
                        st.markdown(f"**Medium:** {art['meta'].get('medium')}")
                        st.markdown(f"**Date:** {art['meta'].get('objectDate')}")
                        st.markdown(f"**Department:** {art['meta'].get('department')}")
                        if art['meta'].get("objectURL"):
                            st.markdown(f"[View on MET Website]({art['meta'].get('objectURL')})")

    # ---------------- Big Data Visualizations ----------------
    st.subheader("📊 Big Data Analysis")
    left, right = st.columns(2)

    # Prepare data
    dates = []
    mediums, titles, cultures, departments = [], [], [], []
    for art in artworks:
        # 时间维度
        date_str = art["meta"].get("objectDate")
        try:
            year = int(re.findall(r"\d{3,4}", date_str or "")[0])
            dates.append(year)
        except:
            continue
        # 其他
        mediums.append(art["meta"].get("medium") or "Unknown")
        titles.append(art["meta"].get("title") or "")
        cultures.append(art["meta"].get("culture") or "Unknown")
        departments.append(art["meta"].get("department") or "Unknown")

    # Time analysis
    with left.expander("📅 Time Period Analysis"):
        if dates:
            df_time = pd.DataFrame({"year": dates})
            chart = alt.Chart(df_time).mark_bar().encode(
                x=alt.X('year:O', title="Year"),
                y=alt.Y('count()', title="Number of Artworks")
            ).properties(width=350, height=300)
            st.altair_chart(chart)

    # Medium / Type
    with left.expander("🎨 Medium & Type Analysis"):
        df_medium = pd.DataFrame({"medium": mediums})
        chart2 = alt.Chart(df_medium).mark_bar().encode(
            x=alt.X('medium:N', sort='-y', title="Medium"),
            y=alt.Y('count()', title="Count")
        ).properties(width=350, height=300)
        st.altair_chart(chart2)

    # Character / Theme
    with right.expander("🧙 Mythological Characters Analysis"):
        characters = []
        for t in titles:
            for m in MYTH_LIST:
                if m.lower() in t.lower():
                    characters.append(m)
        if characters:
            df_chars = pd.DataFrame({"character": characters})
            chart3 = alt.Chart(df_chars).mark_bar().encode(
                x=alt.X('character:N', sort='-y'),
                y=alt.Y('count():Q', title="Number of Appearances")
            ).properties(width=350, height=300)
            st.altair_chart(chart3)

    # Culture / Geography
    with right.expander("🌍 Culture / Geographic Distribution"):
        df_culture = pd.DataFrame({"culture": cultures})
        chart4 = alt.Chart(df_culture).mark_bar().encode(
            x=alt.X('culture:N', sort='-y'),
            y=alt.Y('count()', title="Number of Artworks")
        ).properties(width=350, height=300)
        st.altair_chart(chart4)

    # Style / Department
    with right.expander("🏛️ Style & Department Analysis"):
        df_dept = pd.DataFrame({"department": departments})
        chart5 = alt.Chart(df_dept).mark_bar().encode(
            x=alt.X('department:N', sort='-y'),
            y=alt.Y('count()', title="Number of Artworks")
        ).properties(width=350, height=300)
        st.altair_chart(chart5)

# ---------------- INTERACTIVE ART ZONE ----------------
with tabs[2]:
    st.header("Interactive Art Zone")
    st.markdown("Myth Identifier & Archetype Mapping (Art-based / Myth-based)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎨 Art-based", key="tab_art"):
            st.session_state['tab_mode'] = "Art-based"
    with col2:
        if st.button("📜 Myth-based", key="tab_myth"):
            st.session_state['tab_mode'] = "Myth-based"
