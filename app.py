# app.py
import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import time
import collections
import plotly.express as px
from typing import List, Dict

# Optional OpenAI (only used if user provides API key on Home)
try:
    import openai
except Exception:
    openai = None

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
# small header area (title shown on Home page too)
st.sidebar.image("https://raw.githubusercontent.com/your-repo-placeholder/placeholder/main/icon.png" if False else "", width=1)  # placeholder to keep sidebar height consistent if desired

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

def fetch_image_from_meta(meta: Dict):
    candidates = []
    if meta.get("primaryImageSmall"):
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

# ---------------- OpenAI wrappers (optional) ----------------
def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or openai is None:
        return None
    openai.api_key = key
    return openai

def chat_complete_simple(client, prompt: str, max_tokens: int = 350):
    if client is None:
        return "OpenAI not configured. Paste API key on Home to enable."
    try:
        resp = client.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a museum curator."},{"role":"user","content":prompt}],
            max_tokens=max_tokens,
            temperature=0.2
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"

def ai_expand_bio(client, name, base):
    prompt = f"Expand this short bio about {name} into a concise museum-friendly 3-paragraph introduction:\n\n{base}"
    return chat_complete_simple(client, prompt, max_tokens=450)

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

# ---------------- Big Data extraction ----------------
@st.cache_data(show_spinner=False)
def build_dataset_from_ids(object_ids: List[int]) -> List[Dict]:
    dataset = []
    for oid in object_ids:
        meta = met_get_object_cached(oid)
        if meta:
            dataset.append(meta)
    return dataset

def extract_bigdata_stats(dataset: List[Dict]):
    years = []
    mediums = []
    cultures = []
    classifications = []
    tags_flat = []
    vase_examples = []
    acquisitions = []
    greek_vs_roman = {"greek":0, "roman":0, "other":0}

    import re
    for meta in dataset:
        # year
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
        # medium
        medium = (meta.get("medium") or "").strip()
        if medium:
            mediums.append(medium.lower())
        # culture
        culture = (meta.get("culture") or "").strip()
        if culture:
            cultures.append(culture)
        # classification
        cl = (meta.get("classification") or "").strip()
        if cl:
            classifications.append(cl)
        # tags
        t = meta.get("tags") or []
        if isinstance(t, list):
            for item in t:
                if isinstance(item, dict):
                    term = item.get("term")
                else:
                    term = str(item)
                if term:
                    tags_flat.append(term.lower())
        # vase examples heuristics
        title = (meta.get("title") or meta.get("objectName") or "")
        if any(k in (cl or "").lower() for k in ["vase","vessel","amphora","pottery","ceramic","terracott"]) or any(k in (medium or "").lower() for k in ["vase","ceramic","terracotta","earthenware"]):
            vase_examples.append(title or cl or medium)
        # acquisition (accessionYear)
        acc = meta.get("accessionYear")
        if isinstance(acc, int):
            acquisitions.append(acc)
        else:
            try:
                if isinstance(acc, str) and acc.isdigit():
                    acquisitions.append(int(acc))
            except:
                pass
        # greek vs roman heuristic
        period = (meta.get("period") or "").lower()
        title_low = title.lower()
        if "roman" in period or "roman" in title_low:
            greek_vs_roman["roman"] += 1
        elif "greek" in period or "classical" in period or "hellenistic" in period or "greek" in title_low:
            greek_vs_roman["greek"] += 1
        else:
            greek_vs_roman["other"] += 1

    stats = {
        "years": years,
        "mediums": collections.Counter(mediums),
        "cultures": collections.Counter(cultures),
        "classifications": collections.Counter(classifications),
        "tags": collections.Counter(tags_flat),
        "vase_examples": vase_examples,
        "acquisitions": acquisitions,
        "greek_vs_roman": greek_vs_roman
    }
    return stats

# ---------------- Sidebar navigation ----------------
st.sidebar.title("AI Museum Curator")
page = st.sidebar.radio("Navigate to", ["Home","Greek Figures","Works & Analysis","Art Data","Interactive Tests","Mythic Lineages"], index=0)

# ---------------- HOME ----------------
if page == "Home":
    st.title("🏛️ AI Museum Curator — Greek Mythology Edition")
    st.markdown("""
Explore Greek gods, heroes, and mythic creatures through real artworks from The Metropolitan Museum of Art.  
This app supports **image-first browsing**, curator-style AI analysis (optional), and **big data** visualizations.
    """)
    st.markdown("### Quick start")
    st.markdown("""
1. Go to **Greek Figures** → choose a figure → fetch related artworks (images will be displayed).  
2. Click **Analyze** on a thumbnail to open **Works & Analysis** (large image + metadata + optional AI analysis).  
3. Use **Art Data** to run big-data analyses (time, medium, geography, tags, Greek vs Roman, vessel examples, acquisition years).  
4. Try **Interactive Tests** for personality / myth archetype results.  
5. See **Mythic Lineages** for a color-coded genealogy visualization.
    """)
    st.markdown("---")
    st.subheader("OpenAI API Key (optional)")
    api_key = st.text_input("Paste OpenAI API Key (session only)", type="password", key="home_openai")
    if st.button("Save API Key", key="home_save_key"):
        if api_key:
            st.session_state["OPENAI_API_KEY"] = api_key
            st.success("API key saved to the session.")
        else:
            st.warning("Please paste a valid OpenAI API key.")
    st.markdown("---")
    st.markdown("**Data source:** The Metropolitan Museum of Art Open Access API (MET).")
    st.markdown("If you want the course slides reference included on Home, place the PDF under `/mnt/data/` and I can link it.")

# ---------------- GREEK FIGURES ----------------
elif page == "Greek Figures":
    st.header("Greek Figures — Explorer (image-first)")
    selected = st.selectbox("Choose a figure:", MYTH_LIST, key="gf_select")
    st.subheader(f"Short description — {selected}")
    st.write(FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth."))

    st.markdown("#### Search aliases (used for MET queries)")
    st.write(generate_aliases(selected))

    max_results = st.slider("Max MET records to try (per alias)", 50, 800, 300, 50, key="gf_max_results")
    if st.button("Fetch related works (images)", key="gf_fetch"):
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
            time.sleep(0.005)
        prog.empty()
        st.session_state["thumbs"] = thumbs
        st.success(f"Loaded {len(thumbs)} artworks with images.")

    thumbs = st.session_state.get("thumbs", [])
    if not thumbs:
        st.info("No artworks loaded yet. Use 'Fetch related works (images)'.")
    else:
        per_page = st.number_input("Thumbnails per page", min_value=6, max_value=48, value=12, step=6, key="gf_pp")
        pages = math.ceil(len(thumbs)/per_page)
        page_idx = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="gf_page")
        start = (page_idx-1)*per_page
        page_items = thumbs[start:start+per_page]

        cols = st.columns(3)
        for i, (oid, meta, img) in enumerate(page_items):
            col = cols[i % 3]
            with col:
                st.image(img.resize((300,300)), use_column_width=False)
                st.markdown(f"**{meta.get('title') or meta.get('objectName') or 'Untitled'}**")
                st.write(meta.get("artistDisplayName") or "Unknown")
                st.write(meta.get("objectDate") or "—")
                st.write(meta.get("medium") or "—")
                if st.button("Analyze", key=f"analyze_{oid}"):
                    st.session_state["selected_artwork"] = oid
                    # navigate to Works & Analysis
                    st.experimental_set_query_params(_page="works")
                    st.experimental_rerun()

# ---------------- WORKS & ANALYSIS ----------------
elif page == "Works & Analysis":
    st.header("Works & Analysis — Detailed Artwork View")
    if "selected_artwork" not in st.session_state:
        st.info("No artwork selected. In 'Greek Figures' click Analyze on a thumbnail.")
    else:
        art_id = st.session_state["selected_artwork"]
        meta = met_get_object_cached(art_id)
        if not meta:
            st.error("Failed to load metadata for the selected artwork.")
        else:
            # Back button
            if st.button("← Back to gallery", key="back_gallery"):
                # clear selection and go back
                st.session_state.pop("selected_artwork", None)
                st.experimental_set_query_params()
                st.experimental_rerun()

            left, right = st.columns([0.62, 0.38])
            with left:
                img = fetch_image_from_meta(meta)
                if img:
                    max_w = 850
                    w,h = img.size
                    if w > max_w:
                        img = img.resize((max_w, int(h*(max_w/w))))
                    st.image(img, use_column_width=False)
                else:
                    st.info("Image not available.")
            with right:
                st.subheader(meta.get("title") or meta.get("objectName") or "Untitled")
                st.write(f"**Object ID:** {art_id}")
                st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
                st.write(f"**Date:** {meta.get('objectDate') or '—'}")
                st.write(f"**Medium:** {meta.get('medium') or '—'}")
                st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
                st.write(f"**Classification:** {meta.get('classification') or '—'}")
                if meta.get("objectURL"):
                    st.markdown(f"[View on The MET Website]({meta.get('objectURL')})")
                st.markdown("---")
                client = get_openai_client()
                st.markdown("### Curator AI (optional)")
                if client and st.button("Generate AI analysis", key=f"gen_ai_{art_id}"):
                    with st.spinner("Generating overview..."):
                        st.write(ai_artwork_overview(client, meta))
                    with st.spinner("Generating historical context..."):
                        st.write(ai_artwork_context(client, meta))
                    with st.spinner("Analyzing iconography..."):
                        st.write(ai_artwork_iconography(client, meta))
                else:
                    st.write("(Enable OpenAI API key on Home and click 'Generate AI analysis')")

# ---------------- ART DATA (Big Data Analysis) ----------------
elif page == "Art Data":
    st.header("Art Data — Big Data Analysis")
    st.markdown("""
This page computes data-driven visualizations for artworks related to a selected mythic figure.
It covers 8 dimensions: timeline, medium, geography/culture, classification, tags, Greek vs Roman heuristic, vase examples, and acquisition years.
    """)

    figure_for_analysis = st.selectbox("Choose a figure to analyze:", MYTH_LIST, key="ad_figure")
    aliases = generate_aliases(figure_for_analysis)
    max_results = st.slider("Max MET search results per alias", 50, 800, 300, 50, key="ad_max")

    if st.button("Fetch dataset & analyze", key="ad_fetch"):
        # 1) gather IDs across aliases
        all_ids = []
        prog = st.progress(0)
        for i, a in enumerate(aliases):
            ids = met_search_ids(a, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            prog.progress(int((i+1)/len(aliases)*100))
        prog.empty()
        st.success(f"Found {len(all_ids)} candidate works. Fetching metadata...")

        # 2) fetch metadata
        metas = []
        prog = st.progress(0)
        total = max(1, len(all_ids))
        for i, oid in enumerate(all_ids):
            m = met_get_object_cached(oid)
            if m:
                metas.append(m)
            if i % 10 == 0:
                prog.progress(min(100, int((i+1)/total*100)))
            time.sleep(0.003)
        prog.empty()
        st.session_state["analysis_dataset"] = metas
        st.success(f"Built dataset with {len(metas)} metadata records (may include items lacking some fields).")

    dataset = st.session_state.get("analysis_dataset", None)
    if not dataset:
        st.info("No dataset present yet. Click 'Fetch dataset & analyze' to build one.")
    else:
        st.success(f"Analyzing {len(dataset)} records.")
        stats = extract_bigdata_stats(dataset)

        # 1. Timeline
        st.markdown("### 1. Timeline — Artwork Dates (objectBeginDate / heuristics)")
        years = stats['years']
        if years:
            fig = px.histogram(x=years, nbins=40, labels={'x':'Year','y':'Count'}, title="Artwork Time Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No reliable year data available for this dataset.")

        # 2. Medium
        st.markdown("### 2. Medium / Material Distribution")
        mcounts = stats['mediums']
        if mcounts:
            top_mediums = mcounts.most_common(20)
            fig2 = px.bar(x=[v for _,v in top_mediums], y=[k.title() for k,_ in top_mediums], orientation='h', labels={'x':'Count','y':'Medium'}, title="Top Media (top 20)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No medium data available.")

        # 3. Geography / Culture
        st.markdown("### 3. Geography / Culture")
        cultures = stats['cultures']
        if cultures:
            topc = cultures.most_common(20)
            fig3 = px.bar(x=[v for _,v in topc], y=[k for k,_ in topc], orientation='h', labels={'x':'Count','y':'Culture'}, title="Top Cultures / Provenances")
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No culture/geography data available.")

        # 4. Classification
        st.markdown("### 4. Classification (object types)")
        cl = stats['classifications']
        if cl:
            topcl = cl.most_common(20)
            fig4 = px.bar(x=[v for _,v in topcl], y=[k for k,_ in topcl], orientation='h', labels={'x':'Count','y':'Classification'}, title="Top Classifications")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No classification data available.")

        # 5. Tags / Themes
        st.markdown("### 5. Tags / Themes (top 20)")
        tags = stats['tags']
        if tags:
            toptags = tags.most_common(20)
            fig5 = px.bar(x=[v for _,v in toptags], y=[k.title() for k,_ in toptags], orientation='h', labels={'x':'Count','y':'Tag'}, title="Top Tags / Themes")
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("No useful tags found (MET tagging is inconsistent).")

        # 6. Greek vs Roman
        st.markdown("### 6. Greek vs Roman vs Other (heuristic detection)")
        gvr = stats['greek_vs_roman']
        fig6 = px.pie(values=[gvr['greek'], gvr['roman'], gvr['other']], names=['Greek','Roman','Other'], title="Greek vs Roman vs Other (heuristic)")
        st.plotly_chart(fig6, use_container_width=True)

        # 7. Vase examples
        st.markdown("### 7. Vase / Vessel examples (raw titles / classifications)")
        if stats['vase_examples']:
            for i, ex in enumerate(stats['vase_examples'][:30]):
                st.write(f"{i+1}. {ex}")
        else:
            st.info("No obvious vase/vessel items detected in this dataset.")

        # 8. Acquisition timeline
        st.markdown("### 8. Acquisition years (accessionYear)")
        acq = stats['acquisitions']
        if acq:
            fig7 = px.histogram(x=acq, nbins=30, labels={'x':'Accession Year','y':'Count'}, title="Museum Accession Years")
            st.plotly_chart(fig7, use_container_width=True)
        else:
            st.info("No accessionYear data available.")

        # Export cleaned CSV
        if st.button("Export cleaned dataset (CSV)", key="export_csv_ad"):
            import pandas as pd
            rows = []
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

# ---------------- INTERACTIVE TESTS ----------------
elif page == "Interactive Tests":
    st.header("Interactive Tests — Personality & Myth Archetypes")
    st.markdown("""
These quizzes map your choices to mythic roles and provide interpretive readings and recommended artwork themes.
They are meant for reflection and classroom/demo use (not a clinical assessment).
    """)

    # Test 1
    st.subheader("Which Greek Deity Are You? (short)")
    q1 = st.radio("In a group you:", ["Lead","Support","Create","Plan"], key="iq1")
    q2 = st.radio("You value most:", ["Power","Wisdom","Love","Joy"], key="iq2")
    q3 = st.radio("Pick a symbol:", ["Thunderbolt","Owl","Dove","Lyre"], key="iq3")
    if st.button("Reveal My Deity", key="iq_btn"):
        if q2 == "Wisdom" or q3 == "Owl":
            deity = "Athena"
            explanation = ("Athena represents strategic intelligence and disciplined creativity. "
                           "You value reflective thinking and solve problems methodically; people rely on your counsel.")
            themes = "council scenes, weaving imagery, protective iconography, owl motifs"
        elif q2 == "Love" or q3 == "Dove":
            deity = "Aphrodite"
            explanation = ("Aphrodite symbolizes beauty, desire, and emotional connection. "
                           "You are drawn to aesthetics and interpersonal harmony; you value relational meaning.")
            themes = "love scenes, marriage iconography, beauty rituals"
        elif q2 == "Power" or q3 == "Thunderbolt":
            deity = "Zeus"
            explanation = ("Zeus embodies authority, leadership, and protective power. "
                           "You take responsibility and command presence; you shape structures and decisions.")
            themes = "thrones, lightning symbols, oath-taking scenes"
        else:
            deity = "Apollo"
            explanation = ("Apollo blends logic and artistry: prophecy, music, and measured excellence. "
                           "You value harmony between intellect and creative expression.")
            themes = "lyres, oracles, solar imagery"
        st.markdown(f"### You resemble **{deity}**")
        st.write(explanation)
        st.markdown("**Recommended art themes:**")
        st.write(f"- {themes}")

    st.markdown("---")

    # Test 2
    st.subheader("Personality Archetype — Jungian-inspired")
    s1 = st.selectbox("Preferred role:", ["Leader","Supporter","Strategist","Creator"], key="pt1")
    s2 = st.selectbox("Main motivation:", ["Duty","Glory","Pleasure","Wisdom"], key="pt2")
    s3 = st.selectbox("Crisis reaction:", ["Plan","Fight","Flee","Negotiate"], key="pt3")
    if st.button("Reveal Archetype", key="pt_btn"):
        if s2 == "Wisdom":
            arche = "The Sage — Athena / Prometheus"
            desc = ("You seek knowledge and structure. You are reflective and value the dissemination of insight. "
                    "Artistic suggestions: iconography emphasizing wisdom—owl, scrolls, teaching scenes.")
        elif s2 == "Glory":
            arche = "The Warrior — Ares / Achilles"
            desc = ("You are energized by challenge and honor; your art interests include battle scenes, heroic moments, and trophies.")
        elif s2 == "Pleasure":
            arche = "The Seeker — Dionysus / Pan"
            desc = ("You prioritize experience and emotional richness; visual themes include feasting, music, and ecstatic gatherings.")
        else:
            arche = "The Guardian — Zeus / Hera"
            desc = ("You prioritize order, duty, and social cohesion; relevant art includes ritual objects, thrones, and communal ceremonies.")
        st.markdown(f"### Archetype: **{arche}**")
        st.write(desc)
        st.markdown("**Suggested artwork themes:**")
        st.write("- heroic narratives\n- ritual/ceremonial objects\n- deity portraits\n- symbolic animals and sacred emblems")

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
    fig = px.treemap(names=labels, parents=parents, color=labels, color_discrete_map=color_map, title="Genealogy of Greek Mythology (Simplified)")
    fig.update_layout(margin=dict(t=40, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- End of app ----------------

