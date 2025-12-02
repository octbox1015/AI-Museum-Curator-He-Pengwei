# app.py — Modal details + improved sidebar + merged Greek Figures page
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

# ---------------- Page setup ----------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")

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

# ---------------- Helpers: MET ----------------
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

# ---------------- OpenAI (optional) ----------------
def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or openai is None:
        return None
    openai.api_key = key
    return openai

def chat_complete_simple(client, prompt: str, max_tokens: int = 350):
    if client is None:
        return "OpenAI not configured. Paste API key on Home to enable AI features."
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
    prompt = f"Write a 2-3 sentence public-facing overview for the artwork titled '{title}', grounding in this metadata: {meta}"
    return chat_complete_simple(client, prompt, max_tokens=220)

def ai_artwork_context(client, meta):
    prompt = f"Using this metadata: {meta}, write 4-6 sentences about the artwork's historical and artistic context."
    return chat_complete_simple(client, prompt, max_tokens=350)

def ai_artwork_iconography(client, meta):
    prompt = f"Analyze the iconography and mythological symbols in this artwork using metadata: {meta}"
    return chat_complete_simple(client, prompt, max_tokens=350)

# ---------------- UI: Sidebar (beautified) ----------------
st.sidebar.markdown("## 🏛️ AI Museum Curator")
st.sidebar.markdown("---")
st.sidebar.markdown("**Explore**")
nav = st.sidebar.radio(
    "",
    options=["Home", "Greek Figures", "Art Data", "Interactive Tests", "Mythic Lineages"],
    index=1,
    key="sidebar_nav"
)
st.sidebar.markdown("---")
st.sidebar.markdown("**Settings**")
api_key = st.sidebar.text_input("OpenAI API Key (optional)", type="password", key="sidebar_api")
if st.sidebar.button("Save API Key", key="sidebar_save"):
    if api_key:
        st.session_state["OPENAI_API_KEY"] = api_key
        st.sidebar.success("API key saved for this session.")
    else:
        st.sidebar.warning("Paste a valid OpenAI API key to enable AI features.")
st.sidebar.markdown(" ")
st.sidebar.markdown("Data source: The MET Museum Open Access API")
st.sidebar.markdown("---")
st.sidebar.markdown("Tip: thumbnails show images first; click **View Details** to open modal with full info.")

# Make 'page' variable consistent with earlier code expectations
page = nav

# ---------------- HOME ----------------
if page == "Home":
    st.title("🏛️ AI Museum Curator — Greek Mythology Edition")
    st.markdown("""
Welcome — explore Greek gods, heroes, and mythic creatures through real MET artworks.  
**Image-first browsing** with modal detail view; optional AI curator analysis if you paste an OpenAI key.
""")
    st.markdown("### Quick Start")
    st.markdown("""
- Go to **Greek Figures** to browse artworks by mythological figure (images first).  
- Click **View Details** on any thumbnail to open a modal with full image and curator info.  
- Use **Art Data** for big-data visualizations (timeline, mediums, geography, tags, &c.).  
- Try **Interactive Tests** for short mythic personality quizzes.
""")

# ---------------- GREEK FIGURES (merged with Works & Analysis via modal) ----------------
elif page == "Greek Figures":
    st.header("Greek Figures — Image-first Explorer (modal details)")
    selected = st.selectbox("Choose a figure:", MYTH_LIST, key="gf_select_modal")
    st.subheader(selected)
    st.write(FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth."))

    st.markdown("**Search aliases (used for MET queries):**")
    st.write(generate_aliases(selected))

    # Fetch artworks
    max_results = st.slider("Max MET records per alias", 50, 600, 200, 50, key="gf_max_modal")
    if st.button("Fetch related works (images)", key="gf_fetch_modal"):
        aliases = generate_aliases(selected)
        all_ids = []
        p = st.progress(0)
        for i, a in enumerate(aliases):
            ids = met_search_ids(a, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            p.progress(int((i+1)/len(aliases)*100))
        p.empty()
        st.success(f"Found {len(all_ids)} candidate works. Loading images...")

        thumbs = []
        prog = st.progress(0)
        total = max(1, len(all_ids))
        for i, oid in enumerate(all_ids):
            meta = met_get_object_cached(oid)
            if meta and (meta.get("primaryImageSmall") or meta.get("primaryImage")):
                img = fetch_image_from_meta(meta)
                if img:
                    thumbs.append((oid, meta, img))
            if i % 10 == 0:
                prog.progress(min(100, int((i+1)/total*100)))
            time.sleep(0.002)
        prog.empty()
        st.session_state["thumbs_modal"] = thumbs
        st.success(f"Loaded {len(thumbs)} artworks with images.")

    thumbs = st.session_state.get("thumbs_modal", [])
    if not thumbs:
        st.info("No artworks loaded yet. Click 'Fetch related works (images)'.")
    else:
        per_row = 3
        per_page = st.number_input("Thumbnails per page", min_value=6, max_value=48, value=12, step=6, key="gf_pp_modal")
        pages = math.ceil(len(thumbs)/per_page)
        page_idx = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="gf_page_modal")
        start = (page_idx-1)*per_page
        page_items = thumbs[start:start+per_page]

        # grid layout: 3 columns
        cols = st.columns(per_row)
        for i, (oid, meta, img) in enumerate(page_items):
            col = cols[i % per_row]
            with col:
                # thumbnail
                try:
                    thumb = img.resize((300,300))
                    st.image(thumb, use_column_width=False)
                except Exception:
                    st.write("Image preview unavailable")
                st.markdown(f"**{meta.get('title') or meta.get('objectName') or 'Untitled'}**")
                st.write(meta.get("artistDisplayName") or "Unknown")
                st.write(meta.get("objectDate") or "—")
                st.write(meta.get("medium") or "—")
                # Modal: View Details
                if st.button("View Details", key=f"view_modal_{oid}"):
                    # Open modal with detailed view and AI button
                    with st.modal(f"Artwork {oid} — Details", key=f"modal_{oid}"):
                        left, right = st.columns([0.62, 0.38])
                        with left:
                            # show larger image if available (try prefer full)
                            meta_local = met_get_object_cached(oid)
                            img_full = fetch_image_from_meta(meta_local, prefer_small=False)
                            if img_full:
                                max_w = 900
                                w,h = img_full.size
                                if w > max_w:
                                    img_full = img_full.resize((max_w, int(h*(max_w/w))))
                                st.image(img_full, use_column_width=False)
                            else:
                                st.info("Large image not available.")
                        with right:
                            st.subheader(meta_local.get("title") or meta_local.get("objectName") or "Untitled")
                            st.write(f"**Object ID:** {oid}")
                            st.write(f"**Artist:** {meta_local.get('artistDisplayName') or 'Unknown'}")
                            st.write(f"**Date:** {meta_local.get('objectDate') or '—'}")
                            st.write(f"**Medium:** {meta_local.get('medium') or '—'}")
                            st.write(f"**Dimensions:** {meta_local.get('dimensions') or '—'}")
                            st.write(f"**Classification:** {meta_local.get('classification') or '—'}")
                            if meta_local.get("objectURL"):
                                st.markdown(f"[View on The MET Website]({meta_local.get('objectURL')})")
                            st.markdown("---")
                            client = get_openai_client()
                            st.markdown("### Curator AI (optional)")
                            if client:
                                if st.button("Generate AI analysis", key=f"ai_modal_{oid}"):
                                    with st.spinner("Generating overview..."):
                                        st.write(ai_artwork_overview(client, meta_local))
                                    with st.spinner("Generating context..."):
                                        st.write(ai_artwork_context(client, meta_local))
                                    with st.spinner("Analyzing iconography..."):
                                        st.write(ai_artwork_iconography(client, meta_local))
                            else:
                                st.write("(Enable OpenAI API key in Sidebar to use AI analysis)")

# ---------------- ART DATA ----------------
elif page == "Art Data":
    st.header("Art Data — Big Data Analysis")
    st.markdown("Compute data-driven visualizations for artworks related to a selected mythic figure.")
    figure_for_analysis = st.selectbox("Choose a figure to analyze:", MYTH_LIST, key="ad_figure_modal")
    aliases = generate_aliases(figure_for_analysis)
    max_results = st.slider("Max MET search results per alias", 50, 800, 300, 50, key="ad_max_modal")

    if st.button("Fetch dataset & analyze", key="ad_fetch_modal"):
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
        st.session_state["analysis_dataset_modal"] = metas
        st.success(f"Built dataset with {len(metas)} records.")

    dataset = st.session_state.get("analysis_dataset_modal", None)
    if not dataset:
        st.info("No dataset present yet. Click 'Fetch dataset & analyze' to build one.")
    else:
        st.success(f"Analyzing {len(dataset)} records.")
        # reuse previously defined extract function if present; otherwise re-implement basic stats here
        def extract_basic_stats(dataset):
            import re
            years = []
            mediums = []
            cultures = []
            classifications = []
            tags_flat = []
            acquisitions = []
            greek_vs_roman = {"greek":0,"roman":0,"other":0}
            vase_examples = []
            for meta in dataset:
                y = meta.get("objectBeginDate")
                if isinstance(y, int):
                    years.append(y)
                else:
                    od = meta.get("objectDate") or ""
                    m = re.search(r"-?\d{1,4}", od)
                    if m:
                        try:
                            years.append(int(m.group(0)))
                        except:
                            pass
                medium = (meta.get("medium") or "").strip()
                if medium:
                    mediums.append(medium.lower())
                culture = (meta.get("culture") or "").strip()
                if culture:
                    cultures.append(culture)
                cl = (meta.get("classification") or "").strip()
                if cl:
                    classifications.append(cl)
                t = meta.get("tags") or []
                if isinstance(t, list):
                    for item in t:
                        if isinstance(item, dict):
                            term = item.get("term")
                        else:
                            term = str(item)
                        if term:
                            tags_flat.append(term.lower())
                title = (meta.get("title") or meta.get("objectName") or "")
                if any(k in (cl or "").lower() for k in ["vase","vessel","amphora","pottery","ceramic","terracott"]) or any(k in (medium or "").lower() for k in ["vase","ceramic","terracotta","earthenware"]):
                    vase_examples.append(title or cl or medium)
                acc = meta.get("accessionYear")
                if isinstance(acc, int):
                    acquisitions.append(acc)
                else:
                    try:
                        if isinstance(acc, str) and acc.isdigit():
                            acquisitions.append(int(acc))
                    except:
                        pass
                period = (meta.get("period") or "").lower()
                title_low = title.lower()
                if "roman" in period or "roman" in title_low:
                    greek_vs_roman["roman"] += 1
                elif "greek" in period or "classical" in period or "hellenistic" in period or "greek" in title_low:
                    greek_vs_roman["greek"] += 1
                else:
                    greek_vs_roman["other"] += 1
            return {
                "years": years,
                "mediums": collections.Counter(mediums),
                "cultures": collections.Counter(cultures),
                "classifications": collections.Counter(classifications),
                "tags": collections.Counter(tags_flat),
                "vase_examples": vase_examples,
                "acquisitions": acquisitions,
                "greek_vs_roman": greek_vs_roman
            }
        stats = extract_basic_stats(dataset)

        # Timeline
        st.markdown("### Timeline")
        years = stats["years"]
        if years:
            fig = px.histogram(x=years, nbins=40, labels={'x':'Year','y':'Count'}, title="Artwork Time Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No reliable year data.")

        # Mediums
        st.markdown("### Medium / Material")
        mcounts = stats["mediums"]
        if mcounts:
            top = mcounts.most_common(20)
            fig2 = px.bar(x=[v for _,v in top], y=[k.title() for k,_ in top], orientation='h', labels={'x':'Count','y':'Medium'}, title="Top Media")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No medium data.")

        # Geography
        st.markdown("### Geography / Culture")
        cultures = stats["cultures"]
        if cultures:
            topc = cultures.most_common(20)
            fig3 = px.bar(x=[v for _,v in topc], y=[k for k,_ in topc], orientation='h', labels={'x':'Count','y':'Culture'}, title="Top Cultures")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No culture data.")

        # Tags
        st.markdown("### Tags / Themes")
        tags = stats["tags"]
        if tags:
            topt = tags.most_common(20)
            fig4 = px.bar(x=[v for _,v in topt], y=[k.title() for k,_ in topt], orientation='h', labels={'x':'Count','y':'Tag'}, title="Top Tags")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No useful tags.")

        # Greek vs Roman
        st.markdown("### Greek vs Roman (heuristic)")
        gvr = stats["greek_vs_roman"]
        fig5 = px.pie(values=[gvr['greek'], gvr['roman'], gvr['other']], names=['Greek','Roman','Other'], title="Greek vs Roman vs Other")
        st.plotly_chart(fig5, use_container_width=True)

        # Vase examples
        st.markdown("### Vase / Vessel examples")
        if stats["vase_examples"]:
            for i, ex in enumerate(stats["vase_examples"][:30]):
                st.write(f"{i+1}. {ex}")
        else:
            st.info("No vase-related items detected.")

        # Acquisition years
        st.markdown("### Acquisition years")
        acq = stats["acquisitions"]
        if acq:
            fig6 = px.histogram(x=acq, nbins=30, labels={'x':'Accession Year','y':'Count'}, title="Accession Years")
            st.plotly_chart(fig6, use_container_width=True)
        else:
            st.info("No accessionYear data.")

# ---------------- INTERACTIVE TESTS ----------------
elif page == "Interactive Tests":
    st.header("Interactive Tests — Personality & Myth Archetypes")
    st.markdown("Two short quizzes mapping responses to mythic archetypes with suggested artwork themes.")

    # Test 1 (short)
    st.subheader("Which Greek Deity Are You? (short)")
    q1 = st.radio("In a group you:", ["Lead","Support","Create","Plan"], key="it_q1")
    q2 = st.radio("You value most:", ["Power","Wisdom","Love","Joy"], key="it_q2")
    q3 = st.radio("Pick a symbol:", ["Thunderbolt","Owl","Dove","Lyre"], key="it_q3")
    if st.button("Reveal My Deity", key="it_btn1"):
        if q2 == "Wisdom" or q3 == "Owl":
            deity = "Athena"
            explanation = "Athena: strategic intelligence, disciplined creativity."
            themes = "council scenes, owls, weaving"
        elif q2 == "Love" or q3 == "Dove":
            deity = "Aphrodite"
            explanation = "Aphrodite: beauty, desire, interpersonal harmony."
            themes = "love scenes, ritual gestures"
        elif q2 == "Power" or q3 == "Thunderbolt":
            deity = "Zeus"
            explanation = "Zeus: authority, leadership, protective power."
            themes = "thrones, lightning symbols"
        else:
            deity = "Apollo"
            explanation = "Apollo: logic & artistry, prophecy & music."
            themes = "lyres, oracles"
        st.markdown(f"### You resemble **{deity}**")
        st.write(explanation)
        st.markdown("**Recommended art themes:**")
        st.write(f"- {themes}")

    st.markdown("---")
    # Test 2 (archetype)
    st.subheader("Personality Archetype — Jungian-inspired")
    s1 = st.selectbox("Preferred role:", ["Leader","Supporter","Strategist","Creator"], key="it_s1")
    s2 = st.selectbox("Main motivation:", ["Duty","Glory","Pleasure","Wisdom"], key="it_s2")
    s3 = st.selectbox("Crisis reaction:", ["Plan","Fight","Flee","Negotiate"], key="it_s3")
    if st.button("Reveal Archetype", key="it_btn2"):
        if s2 == "Wisdom":
            arche = "The Sage — Athena / Prometheus"
            desc = "Knowledge-seeker, values insight and structure."
        elif s2 == "Glory":
            arche = "The Warrior — Ares / Achilles"
            desc = "Driven by honor and challenge."
        elif s2 == "Pleasure":
            arche = "The Seeker — Dionysus / Pan"
            desc = "Values emotional richness and experience."
        else:
            arche = "The Guardian — Zeus / Hera"
            desc = "Values duty, order, and social cohesion."
        st.markdown(f"### Archetype: **{arche}**")
        st.write(desc)
        st.markdown("**Suggested artwork themes:**")
        st.write("- heroic narratives\n- ritual objects\n- deity portraits")

# ---------------- MYTHIC LINEAGES ----------------
elif page == "Mythic Lineages":
    st.header("Mythic Lineages — Genealogy Visualization")
    st.markdown("A simplified genealogy grouped into Primordials / Titans / Olympians / Heroes / Creatures.")
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
        if label in ["Primordials","Chaos","Gaia","Uranus"]:
            return "Primordials"
        if label in ["Titans","Cronus","Rhea","Oceanus","Hyperion"]:
            return "Titans"
        if label in ["Olympians","Zeus","Hera","Poseidon","Hades","Demeter","Hestia","Athena","Apollo","Artemis","Ares","Hermes","Dionysus","Aphrodite","Hephaestus"]:
            return "Olympians"
        if label in ["Heroes","Heracles","Perseus","Theseus","Odysseus","Achilles","Jason"]:
            return "Heroes"
        if label in ["Creatures","Medusa","Cyclops","Minotaur","Sirens"]:
            return "Creatures"
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
