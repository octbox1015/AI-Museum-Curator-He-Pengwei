# app.py (final) — Part 1/2
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import time
import collections
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import random
import pandas as pd
from typing import List, Dict, Optional

# Optional OpenAI — only used if user pastes API key in sidebar
try:
    import openai
except Exception:
    openai = None

# ---------------- Page config ----------------
st.set_page_config(page_title="Mythic Art Explorer", layout="wide", initial_sidebar_state="expanded")

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

# ---------------- MET helpers ----------------
@st.cache_data(show_spinner=False)
def met_search_ids(query: str, max_results: int = 300) -> List[int]:
    """Search MET and return object IDs (may be many)"""
    try:
        r = requests.get(MET_SEARCH, params={"q": query, "hasImages": True}, timeout=12)
        r.raise_for_status()
        ids = r.json().get("objectIDs") or []
        return ids[:max_results]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def met_get_object_cached(object_id: int) -> Dict:
    """Fetch MET object metadata (cached)"""
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def fetch_image_from_meta(meta: Dict, prefer_small: bool = True) -> Optional[Image.Image]:
    """Try primaryImageSmall, primaryImage, additionalImages (return PIL.Image or None)"""
    candidates = []
    if prefer_small and meta.get("primaryImageSmall"):
        candidates.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"):
        candidates.append(meta["primaryImage"])
    if meta.get("additionalImages"):
        candidates += meta.get("additionalImages", [])
    for url in candidates:
        try:
            r = requests.get(url, timeout=12)
            r.raise_for_status()
            return Image.open(BytesIO(r.content)).convert("RGB")
        except Exception:
            continue
    return None

def generate_aliases(name: str) -> List[str]:
    mapping = {
        "Athena": ["Pallas Athena", "Minerva"],
        "Zeus": ["Jupiter"],
        "Aphrodite": ["Venus"],
        "Hermes": ["Mercury"],
        "Heracles": ["Hercules"],
        "Persephone": ["Proserpina"],
        "Medusa": ["Gorgon"]
    }
    aliases = [name] + mapping.get(name, [])
    aliases += [f"{name} myth", f"{name} greek"]
    return list(dict.fromkeys(aliases))

# ---------------- OpenAI helpers (optional) ----------------
def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or openai is None:
        return None
    openai.api_key = key
    return openai

def chat_complete_simple(client, prompt: str, max_tokens: int = 350):
    if client is None:
        return "OpenAI not configured. Paste API key in Sidebar to enable AI features."
    try:
        resp = client.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a museum curator."},{"role":"user","content":prompt}],
            max_tokens=max_tokens,
            temperature=0.2
        )
        return getattr(resp.choices[0].message, "content", str(resp))
    except Exception as e:
        return f"OpenAI error: {e}"

def ai_enhanced_interpretation(client, heading: str, meta: Dict):
    prompt = f"{heading}\n\nUse this metadata to produce a concise museum-style paragraph:\n{meta}"
    return chat_complete_simple(client, prompt, max_tokens=300)

# ---------------- Sidebar / Navigation ----------------
st.sidebar.title("Mythic Art Explorer")
st.sidebar.markdown("Browse Greek myth figures, view MET artworks, run dataset analyses, and try interactive tests.")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate to", ["Home","Gallery (Mythic Art Explorer)","Art Data","Interactive Tests","Mythic Lineages"], index=1)
st.sidebar.markdown("---")
st.sidebar.subheader("OpenAI (optional)")
api_key_input = st.sidebar.text_input("OpenAI API Key (session only)", type="password", key="openai_key_input")
if st.sidebar.button("Save API Key", key="save_openai_key"):
    if api_key_input:
        st.session_state["OPENAI_API_KEY"] = api_key_input
        st.sidebar.success("API key saved to session.")
    else:
        st.sidebar.warning("Please paste a valid API key to enable AI features.")
st.sidebar.markdown("---")
st.sidebar.markdown("Data source: The MET Museum Open Access API")
st.sidebar.markdown("Tip: use a small 'Max MET records' while testing (50–150)")

# ---------------- Home ----------------
if page == "Home":
    st.title("🏛️ Mythic Art Explorer — Greek Myth Edition")
    st.markdown("""
Explore Greek mythological figures and real artworks from The Metropolitan Museum of Art.
**Main features**
- Image-first gallery with modal (prev/next)
- Optional AI curator (requires OpenAI API key)
- Dataset-level analytics (timeline, mediums, geography, tags)
- 16-question mythic personality test
- Mythic Lineages network visualization
""")

# ---------------- Gallery (image-first) ----------------
elif page == "Gallery (Mythic Art Explorer)":
    st.header("Gallery — Mythic Art Explorer")
    selected = st.selectbox("Choose a mythic figure:", MYTH_LIST, key="gallery_select")
    st.subheader(selected)
    st.write(FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth."))

    st.markdown("**Search aliases (used for MET queries):**")
    st.write(generate_aliases(selected))

    max_results = st.slider("Max MET records to try (per alias)", 50, 800, 300, 50, key="gallery_max")
    if st.button("Fetch artworks (images)", key="gallery_fetch"):
        aliases = generate_aliases(selected)
        all_ids = []
        prog = st.progress(0)
        for i, a in enumerate(aliases):
            ids = met_search_ids(a, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            prog.progress(int((i+1)/len(aliases)*100))
        prog.empty()
        st.success(f"Found {len(all_ids)} candidate works. Loading images...")

        thumbs = []
        prog2 = st.progress(0)
        total = max(1, len(all_ids))
        for i, oid in enumerate(all_ids):
            meta = met_get_object_cached(oid)
            if meta and (meta.get("primaryImageSmall") or meta.get("primaryImage")):
                img = fetch_image_from_meta(meta)
                if img:
                    thumbs.append({"objectID": oid, "meta": meta, "img": img})
            if i % 10 == 0:
                prog2.progress(min(100, int((i+1)/total*100)))
            time.sleep(0.003)
        prog2.empty()
        st.session_state["gallery_thumbs"] = thumbs
        st.success(f"Loaded {len(thumbs)} artworks with images.")

    thumbs = st.session_state.get("gallery_thumbs", [])
    if not thumbs:
        st.info("No artworks loaded yet. Click 'Fetch artworks (images)'.")
    else:
        per_page = st.number_input("Thumbnails per page", min_value=6, max_value=48, value=12, step=6, key="gallery_pp")
        pages = math.ceil(len(thumbs)/per_page)
        page_idx = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="gallery_page")
        start = (page_idx-1)*per_page
        page_items = thumbs[start:start+per_page]

        # waterfall-like layout: 3 columns with jittered heights
        cols = st.columns(3)
        for i, item in enumerate(page_items):
            col = cols[i % 3]
            with col:
                try:
                    w_target = 300
                    img = item["img"]
                    w,h = img.size
                    ratio = w_target / w
                    new_h = int(h * ratio)
                    jitter = random.randint(-40,40)
                    display_h = max(140, new_h + jitter)
                    thumb = img.resize((w_target, display_h))
                    st.image(thumb, use_column_width=False)
                except Exception:
                    st.write("Image unavailable")
                meta = item["meta"]
                st.markdown(f"**{meta.get('title') or meta.get('objectName') or 'Untitled'}**")
                st.write(meta.get("artistDisplayName") or "Unknown")
                st.write(meta.get("objectDate") or "—")
                if st.button("View Details", key=f"view_{item['objectID']}"):
                    st.session_state["modal_thumbs"] = thumbs
                    st.session_state["modal_index"] = start + i
                    st.session_state["modal_open"] = True

        # Modal block placed after grid (controlled by session_state)
        if st.session_state.get("modal_open", False):
            idx = st.session_state.get("modal_index", 0)
            modal_thumbs = st.session_state.get("modal_thumbs", thumbs)
            idx = max(0, min(idx, len(modal_thumbs)-1))
            st.session_state["modal_index"] = idx

            with st.modal("Artwork Details", key="gallery_modal"):
                record = modal_thumbs[idx]
                oid = record["objectID"]
                # Try to get freshest metadata
                meta = met_get_object_cached(oid) or record["meta"]
                img_full = fetch_image_from_meta(meta, prefer_small=False) or record["img"]

                left, right = st.columns([0.63, 0.37])
                with left:
                    if img_full:
                        w,h = img_full.size
                        max_w = 900
                        if w > max_w:
                            img_full = img_full.resize((max_w, int(h*(max_w/w))))
                        st.image(img_full, use_column_width=False)
                    else:
                        st.info("Image unavailable.")
                with right:
                    st.subheader(meta.get("title") or meta.get("objectName") or "Untitled")
                    st.write(f"**Object ID:** {oid}")
                    st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
                    st.write(f"**Date:** {meta.get('objectDate') or '—'}")
                    st.write(f"**Medium:** {meta.get('medium') or '—'}")
                    st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
                    st.write(f"**Classification:** {meta.get('classification') or '—'}")
                    if meta.get("objectURL"):
                        st.markdown(f"[View on The MET Website]({meta.get('objectURL')})")
                    st.markdown("---")
                    client = get_openai_client()
                    if client:
                        if st.button("Generate AI curator analysis", key=f"ai_{oid}"):
                            with st.spinner("Generating overview..."):
                                st.write(ai_enhanced_interpretation(client, "Overview", meta))
                            with st.spinner("Iconography..."):
                                st.write(ai_enhanced_interpretation(client, "Iconography & meaning", meta))
                    else:
                        st.write("(Enable OpenAI API key in Sidebar to use AI features)")
                    st.markdown("---")
                    nav_prev, nav_close, nav_next = st.columns([1,1,1])
                    with nav_prev:
                        if st.button("← Previous", key=f"prev_{oid}"):
                            st.session_state["modal_index"] = max(0, idx-1)
                            st.experimental_rerun()
                    with nav_close:
                        if st.button("Close", key=f"close_{oid}"):
                            st.session_state["modal_open"] = False
                    with nav_next:
                        if st.button("Next →", key=f"next_{oid}"):
                            st.session_state["modal_index"] = min(len(modal_thumbs)-1, idx+1)
                            st.experimental_rerun()

# ---------------- ART DATA (big-data visualization) ----------------
elif page == "Art Data":
    st.header("Art Data — Big Data Analysis (MET Statistics)")
    figure_sel = st.selectbox("Choose a figure to analyze:", MYTH_LIST, key="ad_select2")
    aliases = generate_aliases(figure_sel)
    max_results = st.slider("Max MET records per alias", 50, 800, 300, 50, key="ad_max2")

    if st.button("Fetch dataset & analyze", key="ad_fetch2"):
        all_ids = []
        prog = st.progress(0)
        for i, a in enumerate(aliases):
            ids = met_search_ids(a, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            prog.progress(int((i+1)/len(aliases)*100))
        prog.empty()

        metas = []
        prog2 = st.progress(0)
        total = max(1, len(all_ids))
        for i, oid in enumerate(all_ids):
            m = met_get_object_cached(oid)
            if m:
                metas.append(m)
            if i % 10 == 0:
                prog2.progress(min(100, int((i+1)/total*100)))
        prog2.empty()
        st.session_state["analysis_dataset2"] = metas
        st.success(f"Dataset built: {len(metas)} artworks")

    dataset = st.session_state.get("analysis_dataset2")
    if not dataset:
        st.info("No dataset. Click 'Fetch dataset & analyze'.")
    else:
        # extract stats --------------------------
        def extract_stats(ds):
            years=[]; mediums=[]; cultures=[]; classes=[]; tags=[]; vases=[]; acqs=[]; gvr={"greek":0,"roman":0,"other":0}
            import re
            for m in ds:
                y = m.get("objectBeginDate")
                if isinstance(y,int): years.append(y)
                else:
                    s = m.get("objectDate","")
                    mo = re.search(r"-?\d{1,4}", s)
                    if mo:
                        try: years.append(int(mo.group(0)))
                        except: pass
                med = (m.get("medium") or "").lower().strip()
                if med: mediums.append(med)
                cult = m.get("culture")
                if cult: cultures.append(cult)
                cl = m.get("classification")
                if cl: classes.append(cl)
                tg = m.get("tags") or []
                if isinstance(tg,list):
                    for t in tg:
                        term = t.get("term") if isinstance(t,dict) else str(t)
                        if term: tags.append(term.lower())
                title = (m.get("title") or "").lower()
                if "vase" in med or "ceramic" in med or "terracotta" in med:
                    vases.append(m.get("title") or "")
                acc = m.get("accessionYear")
                if isinstance(acc,int): acqs.append(acc)
                elif isinstance(acc,str) and acc.isdigit():
                    acqs.append(int(acc))

                # Greek vs Roman heuristic
                tl = title.lower()
                period = (m.get("period") or "").lower()
                if "roman" in period or "roman" in tl: gvr["roman"]+=1
                elif "greek" in period or "hellenistic" in period or "classical" in period: gvr["greek"]+=1
                else: gvr["other"]+=1

            return {
                "years":years,
                "mediums": collections.Counter(mediums),
                "cultures": collections.Counter(cultures),
                "classes": collections.Counter(classes),
                "tags": collections.Counter(tags),
                "vases": vases,
                "acqs": acqs,
                "gvr": gvr,
            }

        stats = extract_stats(dataset)

        # --- Timeline ---
        st.subheader("1. Timeline")
        if stats["years"]:
            fig = px.histogram(x=stats["years"], nbins=40, title="Artwork years")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No year data.")

        # --- Medium ---
        st.subheader("2. Medium / Material")
        if stats["mediums"]:
            top = stats["mediums"].most_common(20)
            fig2 = px.bar(
                x=[v for k,v in top],
                y=[k for k,v in top],
                orientation="h",
                title="Top 20 mediums"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No medium data.")

        # --- Cultures ---
        st.subheader("3. Geography / Culture")
        if stats["cultures"]:
            topc = stats["cultures"].most_common(20)
            fig3 = px.bar(
                x=[v for k,v in topc],
                y=[k for k,v in topc],
                title="Top cultural origins",
                orientation="h"
            )
            st.plotly_chart(fig3, use_container_width=True)

        # --- Tags ---
        st.subheader("4. Tags / Themes")
        if stats["tags"]:
            ttop = stats["tags"].most_common(20)
            fig4 = px.bar(
                x=[v for k,v in ttop],
                y=[k for k,v in ttop],
                title="Top 20 tags",
                orientation="h"
            )
            st.plotly_chart(fig4, use_container_width=True)

        # --- Greek vs Roman ---
        st.subheader("5. Greek vs Roman vs Other")
        g = stats["gvr"]
        fig5 = px.pie(
            values=[g["greek"],g["roman"],g["other"]],
            names=["Greek","Roman","Other"],
            title="Greek vs Roman"
        )
        st.plotly_chart(fig5, use_container_width=True)

        # --- Vase items ---
        st.subheader("6. Vase / Pottery items")
        if stats["vases"]:
            for i, name in enumerate(stats["vases"][:30]):
                st.write(f"{i+1}. {name}")
        else:
            st.info("No vases found.")

        # --- Acquisition ---
        st.subheader("7. Acquisition years")
        if stats["acqs"]:
            fig6 = px.histogram(x=stats["acqs"], nbins=30, title="Acquisition distribution")
            st.plotly_chart(fig6, use_container_width=True)

        # --- Export dataset ---
        if st.button("Export dataset (CSV)", key="export_csv"):
            df = pd.DataFrame(dataset)
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, f"{figure_sel}_dataset.csv")

# ---------------- INTERACTIVE TESTS (16-question edition) ----------------
elif page == "Interactive Tests":
    st.header("Interactive Tests — Myth Personality System (16 items)")
    st.write("A more complete personality model inspired by Greek myth archetypes + Jungian systems.")

    QUESTIONS = [
        "You feel energized by being around people.",
        "You trust logic over emotion in decision-making.",
        "You take initiative when a situation lacks leadership.",
        "You prefer harmony over conflict resolution.",
        "You enjoy abstract thinking more than practical tasks.",
        "You rely on intuition to understand others.",
        "You like planning in advance rather than improvising.",
        "You value tradition more than personal freedom.",
        "You handle crises with calm analysis.",
        "You express emotions openly.",
        "You prefer competition over collaboration.",
        "You often help mediate disputes.",
        "You enjoy artistic creativity.",
        "You feel responsible for others’ well-being.",
        "You follow curiosity, even if risky.",
        "You like being in control of situations."
    ]

    # answer store
    answers = []
    for i, q in enumerate(QUESTIONS):
        ans = st.slider(f"{i+1}. {q}", 1, 5, 3)
        answers.append(ans)

    if st.button("Reveal My Archetype", key="test16_btn"):
        score_extro = answers[0] + answers[10]
        score_logic = answers[1] + answers[8]
        score_empathy = answers[3] + answers[11] + answers[14]
        score_control = answers[2] + answers[6] + answers[15]

        # classification
        if score_control > 10 and score_logic > 8:
            arche = "⚡ Zeus / Hera — The Guardian"
            desc = "You value structure, responsibility, and protecting your world."
        elif score_logic > score_empathy:
            arche = "🦉 Athena / Prometheus — The Sage"
            desc = "You think in structures, concepts, and long-term clarity."
        elif score_empathy > score_logic:
            arche = "🌿 Dionysus / Pan — The Seeker"
            desc = "You value emotion, authenticity, and transformative experience."
        else:
            arche = "🔥 Ares / Achilles — The Warrior"
            desc = "You seek challenge, movement, and overcoming limits."

        st.markdown(f"## Your Archetype: **{arche}**")
        st.write(desc)

# ---------------- MYTHIC LINEAGES (network graph) ----------------
elif page == "Mythic Lineages":
    st.header("Mythic Lineages — Network Visualization")
    st.write("A directed mythological genealogy network (Primordials → Titans → Olympians → Heroes → Creatures).")

    # graph
    G = nx.DiGraph()

    edges = [
        ("Chaos","Gaia"),
        ("Gaia","Uranus"),
        ("Uranus","Cronus"),
        ("Cronus","Zeus"),
        ("Cronus","Hera"),
        ("Cronus","Poseidon"),
        ("Cronus","Hades"),
        ("Zeus","Athena"),
        ("Zeus","Apollo"),
        ("Zeus","Artemis"),
        ("Zeus","Ares"),
        ("Zeus","Hermes"),
        ("Zeus","Dionysus"),
        ("Zeus","Perseus"),
        ("Zeus","Heracles"),
        ("Perseus","Theseus"),
        ("Theseus","Achilles"),
        ("Achilles","Odysseus"),
        ("Medusa","Perseus"),
        ("Minotaur","Theseus"),
        ("Cyclops","Poseidon"),
    ]

    for a,b in edges:
        G.add_edge(a,b)

    pos = nx.spring_layout(G, seed=42)

    edge_x=[]; edge_y=[]
    for src, dst in G.edges():
        x0,y0 = pos[src]
        x1,y1 = pos[dst]
        edge_x.extend([x0,x1,None])
        edge_y.extend([y0,y1,None])

    node_x=[]; node_y=[]; labels=[]
    for node in G.nodes():
        x,y = pos[node]
        node_x.append(x)
        node_y.append(y)
        labels.append(node)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=1,color="#888"),
        hoverinfo="none"
    ))

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=labels,
        textposition="top center",
        marker=dict(size=14, color="#4A90E2"),
    ))

    fig.update_layout(
        title="Mythic Genealogy Network",
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=700
    )

    st.plotly_chart(fig, use_container_width=True)
