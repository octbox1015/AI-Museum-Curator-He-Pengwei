# app.py — Final integrated version
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import time
import collections
import plotly.express as px
from typing import List, Dict, Optional

# Optional OpenAI
try:
    import openai
except Exception:
    openai = None

# ---------- Page config ----------
st.set_page_config(page_title="Mythic Art Explorer — Greek Figures & Artworks", layout="wide")

# ---------- Constants ----------
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

# ---------- Helpers (MET) ----------
@st.cache_data(show_spinner=False)
def met_search_ids(query: str, max_results: int = 300) -> List[int]:
    try:
        r = requests.get(MET_SEARCH, params={"q": query, "hasImages": True}, timeout=12)
        r.raise_for_status()
        ids = r.json().get("objectIDs") or []
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

def fetch_image_from_meta(meta: Dict, prefer_small: bool = True) -> Optional[Image.Image]:
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

# ---------- OpenAI helpers (optional) ----------
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

def ai_artwork_overview(client, meta): 
    title = meta.get("title") or meta.get("objectName") or "Untitled"
    prompt = f"Write a 2-3 sentence public-facing overview for the artwork titled '{title}', using metadata: {meta}"
    return chat_complete_simple(client, prompt, max_tokens=220)
def ai_artwork_context(client, meta):
    prompt = f"Using metadata: {meta}, write 4-6 sentences about the artwork's historical and artistic context."
    return chat_complete_simple(client, prompt, max_tokens=350)
def ai_artwork_iconography(client, meta):
    prompt = f"Analyze the iconography and mythological symbols in this artwork using metadata: {meta}"
    return chat_complete_simple(client, prompt, max_tokens=350)

# ---------- Sidebar (beautified) ----------
st.sidebar.markdown("## 🏺 Mythic Art Explorer")
st.sidebar.markdown("### Greek Figures & Artworks")
st.sidebar.markdown("---")
nav = st.sidebar.radio(
    "Navigate",
    options=["Home","Mythic Art Explorer","Art Data","Interactive Tests","Mythic Lineages"],
    index=1,
    key="nav_final"
)
st.sidebar.markdown("---")
st.sidebar.markdown("**Settings**")
api_key_input = st.sidebar.text_input("OpenAI API Key (optional)", type="password", key="sidebar_api_final")
if st.sidebar.button("Save API key", key="sidebar_save_final"):
    if api_key_input:
        st.session_state["OPENAI_API_KEY"] = api_key_input
        st.sidebar.success("API key saved to session.")
    else:
        st.sidebar.warning("Provide a valid API key to enable AI.")
st.sidebar.markdown("Data: MET Museum Open Access API")
st.sidebar.markdown("---")
st.sidebar.markdown("Tip: click *View Details* to open modal with full artwork information.")

page = nav  # main page variable

# ---------- HOME ----------
if page == "Home":
    st.title("🏛️ Mythic Art Explorer — Greek Figures & Artworks")
    st.markdown("Explore Greek myth through real artworks (MET) — image-first browsing with modal details and optional AI curator analysis.")
    st.markdown("Quick start:\n\n1. Mythic Art Explorer → choose a figure → Fetch related works → Click *View Details*.\n2. Art Data → run dataset analysis. 3. Interactive Tests → personality + archetypes.")

# ---------- MYTHIC ART EXPLORER (merged page) ----------
elif page == "Mythic Art Explorer":
    st.header("Mythic Art Explorer — Greek Figures & Artworks")
    selected = st.selectbox("Choose a mythic figure:", MYTH_LIST, key="select_final")
    st.subheader(selected)
    st.write(FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth."))

    st.markdown("**Search aliases (for MET queries):**")
    st.write(generate_aliases(selected))

    # fetch artworks
    max_results = st.slider("Max MET records per alias", 50, 800, 300, 50, key="fetch_max_final")
    if st.button("Fetch related works (images)", key="fetch_btn_final"):
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
                    thumbs.append((oid, meta, img))
            if i % 10 == 0:
                prog2.progress(min(100, int((i+1)/total*100)))
            time.sleep(0.002)
        prog2.empty()
        st.session_state["thumbs_final"] = thumbs
        st.success(f"Loaded {len(thumbs)} artworks with images.")

    thumbs = st.session_state.get("thumbs_final", [])
    if not thumbs:
        st.info("No artworks loaded yet. Click 'Fetch related works (images)'.")
    else:
        per_page = st.number_input("Thumbnails per page", min_value=6, max_value=48, value=12, step=6, key="pp_final")
        pages = math.ceil(len(thumbs)/per_page)
        page_idx = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="page_final")
        start = (page_idx-1)*per_page
        page_items = thumbs[start:start+per_page]

        # grid 3 columns
        cols = st.columns(3)
        for i, (oid, meta, img) in enumerate(page_items):
            col = cols[i % 3]
            with col:
                # thumbnail image
                try:
                    thumb = img.resize((300,300))
                    st.image(thumb, use_column_width=False)
                except Exception:
                    st.write("Preview unavailable")
                st.markdown(f"**{meta.get('title') or meta.get('objectName') or 'Untitled'}**")
                st.write(meta.get("artistDisplayName") or "Unknown")
                st.write(meta.get("objectDate") or "—")
                st.write(meta.get("medium") or "—")
                # View Details sets modal state
                if st.button("View Details", key=f"view_btn_{oid}"):
                    st.session_state["modal_art_index"] = start + i  # absolute index in thumbs list
                    st.session_state["modal_open_final"] = True

        # -------- Modal outside loop, controlled by state --------
        if st.session_state.get("modal_open_final", False):
            idx = st.session_state.get("modal_art_index", 0)
            # clamp index
            idx = max(0, min(idx, len(thumbs)-1))
            st.session_state["modal_art_index"] = idx

            # Modal block
            with st.modal("Artwork Details", key=f"modal_final_unique"):
                # load metadata & image for the idx-th item
                try:
                    oid, meta_local, img_local = thumbs[idx]
                except Exception:
                    st.error("Failed to load artwork details.")
                    if st.button("Close", key="close_err_final"):
                        st.session_state["modal_open_final"] = False
                    st.stop()

                left, right = st.columns([0.62, 0.38])
                with left:
                    # try to load full-size image from MET metadata
                    full_meta = met_get_object_cached(oid)
                    img_full = fetch_image_from_meta(full_meta, prefer_small=False) or img_local
                    if img_full:
                        w,h = img_full.size
                        max_w = 900
                        if w > max_w:
                            img_full = img_full.resize((max_w, int(h*(max_w/w))))
                        st.image(img_full, use_column_width=False)
                    else:
                        st.info("Image not available.")

                with right:
                    st.subheader(full_meta.get("title") or full_meta.get("objectName") or "Untitled")
                    st.write(f"**Object ID:** {oid}")
                    st.write(f"**Artist:** {full_meta.get('artistDisplayName') or 'Unknown'}")
                    st.write(f"**Date:** {full_meta.get('objectDate') or '—'}")
                    st.write(f"**Medium:** {full_meta.get('medium') or '—'}")
                    st.write(f"**Dimensions:** {full_meta.get('dimensions') or '—'}")
                    st.write(f"**Classification:** {full_meta.get('classification') or '—'}")
                    if full_meta.get("objectURL"):
                        st.markdown(f"[View on The MET Website]({full_meta.get('objectURL')})")
                    st.markdown("---")
                    # AI analysis (optional)
                    client = get_openai_client()
                    st.markdown("### Curator AI (optional)")
                    if client:
                        if st.button("Generate AI analysis", key=f"ai_btn_{oid}"):
                            with st.spinner("Generating overview..."):
                                st.write(ai_artwork_overview(client, full_meta))
                            with st.spinner("Historical context..."):
                                st.write(ai_artwork_context(client, full_meta))
                            with st.spinner("Iconography..."):
                                st.write(ai_artwork_iconography(client, full_meta))
                    else:
                        st.write("(Enable OpenAI API key in Sidebar to use AI analysis)")
                    st.markdown("---")
                    # navigation inside modal
                    col_prev, col_close, col_next = st.columns([1,1,1])
                    with col_prev:
                        if st.button("← Previous", key=f"prev_{oid}"):
                            new_idx = max(0, idx-1)
                            st.session_state["modal_art_index"] = new_idx
                            st.experimental_rerun()
                    with col_close:
                        if st.button("Close", key=f"close_{oid}"):
                            st.session_state["modal_open_final"] = False
                    with col_next:
                        if st.button("Next →", key=f"next_{oid}"):
                            new_idx = min(len(thumbs)-1, idx+1)
                            st.session_state["modal_art_index"] = new_idx
                            st.experimental_rerun()

# ---------- ART DATA ----------
elif page == "Art Data":
    st.header("Art Data — Big Data Analysis")
    st.markdown("Run dataset-level analyses for artworks related to a selected mythic figure.")
    figure_for_analysis = st.selectbox("Choose a figure:", MYTH_LIST, key="ad_select_final")
    aliases = generate_aliases(figure_for_analysis)
    max_results = st.slider("Max MET search results per alias", 50, 800, 300, 50, key="ad_max_final")

    if st.button("Fetch dataset & analyze", key="ad_fetch_final"):
        all_ids = []
        p = st.progress(0)
        for i, a in enumerate(aliases):
            ids = met_search_ids(a, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            p.progress(int((i+1)/len(aliases)*100))
        p.empty()
        st.success(f"Found {len(all_ids)} candidate works. Fetching metadata...")

        metas = []
        prog = st.progress(0)
        total = max(1, len(all_ids))
        for i, oid in enumerate(all_ids):
            m = met_get_object_cached(oid)
            if m:
                metas.append(m)
            if i % 10 == 0:
                prog.progress(min(100, int((i+1)/total*100)))
            time.sleep(0.002)
        prog.empty()
        st.session_state["analysis_dataset_final"] = metas
        st.success(f"Built dataset with {len(metas)} records.")

    dataset = st.session_state.get("analysis_dataset_final", None)
    if not dataset:
        st.info("No dataset present yet. Click 'Fetch dataset & analyze' to build one.")
    else:
        st.success(f"Analyzing {len(dataset)} records.")
        # basic stats extraction (robust)
        def extract_stats(ds):
            import re
            years=[]; mediums=[]; cultures=[]; classes=[]; tags=[]; vases=[]; acqs=[]; gvr={"greek":0,"roman":0,"other":0}
            for m in ds:
                y = m.get("objectBeginDate")
                if isinstance(y,int): years.append(y)
                else:
                    od = m.get("objectDate") or ""
                    mo = re.search(r"-?\d{1,4}", od)
                    if mo:
                        try: years.append(int(mo.group(0)))
                        except: pass
                med = (m.get("medium") or "").strip()
                if med: mediums.append(med.lower())
                cult = (m.get("culture") or "").strip()
                if cult: cultures.append(cult)
                cl = (m.get("classification") or "").strip()
                if cl: classes.append(cl)
                t = m.get("tags") or []
                if isinstance(t,list):
                    for it in t:
                        term = it.get("term") if isinstance(it,dict) else str(it)
                        if term: tags.append(term.lower())
                title = (m.get("title") or m.get("objectName") or "")
                if any(k in (cl or "").lower() for k in ["vase","amphora","pottery","ceramic","terracott"]) or any(k in (med or "").lower() for k in ["vase","ceramic","terracotta","earthenware"]):
                    vases.append(title or cl or med)
                acc = m.get("accessionYear")
                if isinstance(acc,int): acqs.append(acc)
                else:
                    if isinstance(acc,str) and acc.isdigit(): acqs.append(int(acc))
                period = (m.get("period") or "").lower()
                tl = title.lower()
                if "roman" in period or "roman" in tl: gvr["roman"]+=1
                elif "greek" in period or "classical" in period or "hellenistic" in period or "greek" in tl: gvr["greek"]+=1
                else: gvr["other"]+=1
            return {
                "years":years,"mediums":collections.Counter(mediums),
                "cultures":collections.Counter(cultures),"classes":collections.Counter(classes),
                "tags":collections.Counter(tags),"vases":vases,"acqs":acqs,"gvr":gvr
            }
        stats = extract_stats(dataset)
        # Timeline
        st.markdown("### Timeline")
        if stats["years"]:
            fig = px.histogram(x=stats["years"], nbins=40, labels={'x':'Year','y':'Count'}, title="Artwork Time Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No reliable year data.")
        # Mediums
        st.markdown("### Medium / Material")
        if stats["mediums"]:
            top = stats["mediums"].most_common(20)
            fig2 = px.bar(x=[v for _,v in top], y=[k.title() for k,_ in top], orientation='h', labels={'x':'Count','y':'Medium'})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No medium data.")
        # Geography
        st.markdown("### Geography / Culture")
        if stats["cultures"]:
            topc = stats["cultures"].most_common(20)
            fig3 = px.bar(x=[v for _,v in topc], y=[k for k,_ in topc], orientation='h', labels={'x':'Count','y':'Culture'})
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No culture data.")
        # Tags
        st.markdown("### Tags / Themes")
        if stats["tags"]:
            ttop = stats["tags"].most_common(20)
            fig4 = px.bar(x=[v for _,v in ttop], y=[k.title() for k,_ in ttop], orientation='h', labels={'x':'Count','y':'Tag'})
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No tags found.")
        # Greek vs Roman
        st.markdown("### Greek vs Roman (heuristic)")
        g = stats["gvr"]
        fig5 = px.pie(values=[g["greek"],g["roman"],g["other"]], names=["Greek","Roman","Other"], title="Greek vs Roman")
        st.plotly_chart(fig5, use_container_width=True)
        # Vase examples
        st.markdown("### Vase / Vessel examples")
        if stats["vases"]:
            for i, v in enumerate(stats["vases"][:30]): st.write(f"{i+1}. {v}")
        else:
            st.info("No vase items detected.")
        # Acquisition
        st.markdown("### Acquisition years")
        if stats["acqs"]:
            fig6 = px.histogram(x=stats["acqs"], nbins=30, labels={'x':'Year','y':'Count'}, title="Accession Years")
            st.plotly_chart(fig6, use_container_width=True)
        else:
            st.info("No accessionYear data available.")
        # CSV export
        if st.button("Export cleaned dataset (CSV)", key="export_final"):
            import pandas as pd
            rows=[]
            for m in dataset:
                rows.append({
                    "objectID": m.get("objectID"),
                    "title": m.get("title"),
                    "objectDate": m.get("objectDate"),
                    "objectBeginDate": m.get("objectBeginDate"),
                    "medium": m.get("medium"),
                    "culture": m.get("culture"),
                    "classification": m.get("classification"),
                    "period": m.get("period"),
                    "accessionYear": m.get("accessionYear"),
                    "objectURL": m.get("objectURL")
                })
            df = pd.DataFrame(rows)
            csv = df.to_csv(index=False)
            st.download_button("Download CSV", data=csv, file_name=f"met_{figure_for_analysis}_dataset.csv", mime="text/csv")

# ---------- INTERACTIVE TESTS ----------
elif page == "Interactive Tests":
    st.header("Interactive Tests — Personality & Myth Archetypes")
    st.subheader("1) Which Greek Deity Are You? (short)")
    q1 = st.radio("In a group you:", ["Lead","Support","Create","Plan"], key="iq1_final")
    q2 = st.radio("You value most:", ["Power","Wisdom","Love","Joy"], key="iq2_final")
    q3 = st.radio("Pick a symbol:", ["Thunderbolt","Owl","Dove","Lyre"], key="iq3_final")
    if st.button("Reveal My Deity", key="iq_btn_final"):
        if q2=="Wisdom" or q3=="Owl":
            deity="Athena"; explanation="Athena: strategy, wisdom, protector."; themes="owls, weaving, council scenes"
        elif q2=="Love" or q3=="Dove":
            deity="Aphrodite"; explanation="Aphrodite: beauty and desire."; themes="love scenes, marriage iconography"
        elif q2=="Power" or q3=="Thunderbolt":
            deity="Zeus"; explanation="Zeus: authority and leadership."; themes="thrones, lightning"
        else:
            deity="Apollo"; explanation="Apollo: music, prophecy, balance."; themes="lyres, oracles"
        st.markdown(f"### You resemble **{deity}**"); st.write(explanation); st.markdown("**Themes:**"); st.write(f"- {themes}")

    st.markdown("---")
    st.subheader("2) Mythological Personality Archetype (Jungian-inspired)")
    s1 = st.selectbox("Preferred role:", ["Leader","Supporter","Strategist","Creator"], key="pt1_final")
    s2 = st.selectbox("Main motivation:", ["Duty","Glory","Pleasure","Wisdom"], key="pt2_final")
    s3 = st.selectbox("Crisis reaction:", ["Plan","Fight","Flee","Negotiate"], key="pt3_final")
    if st.button("Reveal Archetype", key="pt_btn_final"):
        if s2=="Wisdom": arche="The Sage — Athena / Prometheus"; desc="Seeks insight and structure."
        elif s2=="Glory": arche="The Warrior — Ares / Achilles"; desc="Seeks honor and challenge."
        elif s2=="Pleasure": arche="The Seeker — Dionysus / Pan"; desc="Seeks experience and feeling."
        else: arche="The Guardian — Zeus / Hera"; desc="Seeks order and duty."
        st.markdown(f"### Archetype: **{arche}**"); st.write(desc)

# ---------- MYTHIC LINEAGES ----------
elif page == "Mythic Lineages":
    st.header("Mythic Lineages — Genealogy Visualization")
    st.markdown("Simplified genealogy grouped into Primordials / Titans / Olympians / Heroes / Creatures.")
    labels = [
        "Greek Mythology",
        "Primordials","Chaos","Gaia","Uranus",
        "Titans","Cronus","Rhea","Oceanus","Hyperion",
        "Olympians","Zeus","Hera","Poseidon","Hades","Demeter","Hestia","Athena","Apollo","Artemis","Ares","Hermes","Dionysus","Aphrodite","Hephaestus",
        "Heroes","Heracles","Perseus","Theseus","Odysseus","Achilles","Jason",
        "Creatures","Medusa","Cyclops","Minotaur","Sirens"
    ]
    parents = [
        "",
        "Greek Mythology","Primordials","Primordials","Primordials",
        "Greek Mythology","Titans","Titans","Titans","Titans",
        "Greek Mythology","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians",
        "Greek Mythology","Heroes","Heroes","Heroes","Heroes","Heroes","Heroes",
        "Greek Mythology","Creatures","Creatures","Creatures","Creatures"
    ]
    category_color = {
        "Greek Mythology":"#7F8C8D",
        "Primordials":"#8E44AD",
        "Titans":"#E67E22",
        "Olympians":"#3498DB",
        "Heroes":"#E74C3C",
        "Creatures":"#27AE60"
    }
    def category_for(label):
        if label in ["Primordials","Chaos","Gaia","Uranus"]: return "Primordials"
        if label in ["Titans","Cronus","Rhea","Oceanus","Hyperion"]: return "Titans"
        if label in ["Olympians","Zeus","Hera","Poseidon","Hades","Demeter","Hestia","Athena","Apollo","Artemis","Ares","Hermes","Dionysus","Aphrodite","Hephaestus"]: return "Olympians"
        if label in ["Heroes","Heracles","Perseus","Theseus","Odysseus","Achilles","Jason"]: return "Heroes"
        if label in ["Creatures","Medusa","Cyclops","Minotaur","Sirens"]: return "Creatures"
        return "Greek Mythology"
    color_map = {label: category_color[category_for(label)] for label in labels}
    try:
        fig = px.treemap(names=labels, parents=parents, color=labels, color_discrete_map=color_map, title="Genealogy of Greek Mythology (Simplified)")
        fig.update_layout(margin=dict(t=40, l=0, r=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.write("Treemap not available; showing simplified lists.")
        st.write("Primordials: Chaos, Gaia, Uranus")
        st.write("Titans: Cronus, Rhea, Oceanus, Hyperion")
        st.write("Olympians: Zeus, Hera, Poseidon, Hades, Demeter, Hestia, Athena, Apollo, Artemis, Ares, Hermes, Dionysus, Aphrodite, Hephaestus")
        st.write("Heroes: Heracles, Perseus, Theseus, Odysseus, Achilles, Jason")
        st.write("Creatures: Medusa, Cyclops, Minotaur, Sirens")

# ---------- End ----------
