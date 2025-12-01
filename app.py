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
import plotly.graph_objects as go
from typing import List, Dict, Tuple

# Optional OpenAI (AI features remain optional)
try:
    import openai
except Exception:
    openai = None

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ---------------- Constants ----------------
MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# legend lists
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

# ---------------- Helpers: MET fetching & images ----------------
@st.cache_data(show_spinner=False)
def met_search_ids(query: str, max_results: int = 300) -> List[int]:
    """Search MET and return up to max_results objectIDs (may be empty)."""
    try:
        r = requests.get(MET_SEARCH, params={"q": query, "hasImages": True}, timeout=10)
        r.raise_for_status()
        ids = r.json().get("objectIDs") or []
        return ids[:max_results]
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def met_get_object_cached(object_id: int) -> Dict:
    try:
        r = requests.get(MET_OBJECT.format(object_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}

def fetch_image_from_meta(meta: Dict):
    """Return PIL Image or None."""
    candidates = []
    if meta.get("primaryImageSmall"):
        candidates.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"):
        candidates.append(meta["primaryImage"])
    if meta.get("additionalImages"):
        candidates += meta.get("additionalImages", [])
    for url in candidates:
        try:
            r = requests.get(url, timeout=10)
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

def chat_complete_simple(client, prompt: str, max_tokens:int=300):
    if client is None:
        return "OpenAI not configured."
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

# ---------------- Data extraction for big data ----------------
@st.cache_data(show_spinner=False)
def build_dataset_from_ids(object_ids: List[int]) -> List[Dict]:
    """Given a list of MET objectIDs, fetch metadata and return list of dicts (only objects with some metadata)."""
    dataset = []
    for oid in object_ids:
        meta = met_get_object_cached(oid)
        if not meta:
            continue
        # minimal filter: require some date or classification or medium
        dataset.append(meta)
    return dataset

def extract_bigdata_stats(dataset: List[Dict]) -> Dict:
    """From dataset compute all statistics for the 8 dimensions. Returns a dict of series."""
    years = []
    mediums = []
    cultures = []
    classifications = []
    tags_flat = []
    period_labels = []
    vase_tag_counts = []
    acquisitions = []
    greek_vs_roman = {"greek":0, "roman":0, "other":0}

    for meta in dataset:
        # YEAR: prefer objectBeginDate
        y = meta.get("objectBeginDate")
        if isinstance(y, int):
            years.append(y)
        else:
            # try objectDate string
            od = meta.get("objectDate") or ""
            # find first 4-digit or 1-4 digit possibly negative
            import re
            m = re.search(r"-?\d{1,4}", od)
            if m:
                try:
                    years.append(int(m.group(0)))
                except:
                    pass

        # MEDIUM
        medium = (meta.get("medium") or "").strip()
        if medium:
            mediums.append(medium.lower())

        # CULTURE / GEOGRAPHY
        culture = (meta.get("culture") or meta.get("region") or meta.get("country") or "").strip()
        if culture:
            cultures.append(culture)

        # CLASSIFICATION
        cl = (meta.get("classification") or "").strip()
        if cl:
            classifications.append(cl)

        # TAGS / SUBJECTS
        t = meta.get("tags") or []
        # tags is list of dicts { 'term': '...' }
        if isinstance(t, list):
            for item in t:
                term = item.get("term") if isinstance(item, dict) else str(item)
                if term:
                    tags_flat.append(term.lower())

        # PERIOD: to detect Roman vs Greek
        period = (meta.get("period") or meta.get("timeline") or "").lower()
        period_labels.append(period)
        # heuristic detection
        title = (meta.get("title") or meta.get("objectName") or "").lower()
        if "roman" in period or "roman" in title:
            greek_vs_roman["roman"] += 1
        elif "greek" in period or "classical" in period or "hellenistic" in period or "greek" in title:
            greek_vs_roman["greek"] += 1
        else:
            greek_vs_roman["other"] += 1

        # VASE related narrative: check classification/medium/title for "vase" "vessel" "amphora"
        if any(k in (cl or "").lower() for k in ["vase","vessel","pottery","amphora","ceramic","terracott"] ) or any(k in (medium or "").lower() for k in ["vase","ceramic","terracotta","earthenware"]):
            # extract tags or title words for vase narratives
            # use tags_flat partial from earlier
            vase_tag_counts.append(title or cl or medium)

        # ACQUISITION YEAR
        acc_year = meta.get("accessionYear")
        if isinstance(acc_year, int):
            acquisitions.append(acc_year)
        else:
            # sometimes accessionYear is string:
            try:
                if isinstance(acc_year, str) and acc_year.isdigit():
                    acquisitions.append(int(acc_year))
            except:
                pass

    # aggregate stats
    stats = {}
    stats['years'] = years
    stats['mediums'] = collections.Counter(mediums)
    stats['cultures'] = collections.Counter(cultures)
    stats['classifications'] = collections.Counter(classifications)
    stats['tags'] = collections.Counter(tags_flat)
    stats['greek_vs_roman'] = greek_vs_roman
    stats['vase_examples'] = vase_tag_counts
    stats['acquisitions'] = acquisitions
    return stats

# ---------------- Sidebar navigation (multipage) ----------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home","Greek Figures","Works & Analysis","Art Data","Interactive Tests","Mythic Lineages"], index=0)

# ---------------- HOME ----------------
if page == "Home":
    st.header("Welcome — AI Museum Curator (Big Data Edition)")
    st.markdown("""
This application connects MET museum open data with curated AI explanations and **big data analyses**.
**Use flow**
1. Go to **Greek Figures** → select a deity/hero → fetch related artworks (images only).  
2. Use **Works & Analysis** to inspect a selected artwork in detail.  
3. Open **Art Data** to run large-scale analyses (timeline, mediums, geography, tags, Greek vs Roman, vase narratives, acquisition years).  
4. Try **Interactive Tests** (two personality quizzes).  
5. See **Mythic Lineages** for genealogy.
    """)
    st.subheader("OpenAI (optional)")
    api_key = st.text_input("Paste your OpenAI API Key (session-only)", type="password", key="home_api")
    if st.button("Save Key", key="home_save"):
        if api_key:
            st.session_state["OPENAI_API_KEY"] = api_key
            st.success("Saved.")
        else:
            st.warning("Please provide a valid key.")

# ---------------- GREEK FIGURES ----------------
elif page == "Greek Figures":
    st.header("Greek Figures — Fetch related artworks")
    st.markdown("Select a figure and fetch related MET artworks. The dataset can then be analyzed on the 'Art Data' page.")
    selected = st.selectbox("Choose a figure:", MYTH_LIST, key="select_fig")
    st.write(FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth."))

    st.markdown("Search aliases (used for MET queries):")
    st.write(generate_aliases(selected))

    max_results = st.slider("Max MET records to try (search breadth)", 50, 800, 300, 50, key="max_results")
    if st.button("Fetch IDs & thumbnails", key="fetch_ids"):
        # gather ids from aliases
        aliases = generate_aliases(selected)
        all_ids = []
        prog = st.progress(0)
        for i, alias in enumerate(aliases):
            ids = met_search_ids(alias, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            prog.progress(int((i+1)/len(aliases)*100))
        prog.empty()
        st.session_state["fetched_ids"] = all_ids
        st.success(f"Found {len(all_ids)} candidate IDs. Now loading images (may take time).")

        # download thumbnails (only keep items with images)
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
        st.success(f"Loaded {len(thumbs)} artworks with images (thumbnails cached).")

    thumbs = st.session_state.get("thumbs", [])
    if thumbs:
        per_page = st.number_input("Thumbnails per page", min_value=6, max_value=48, value=12, step=6, key="thumbs_pp")
        pages = math.ceil(len(thumbs)/per_page)
        page_idx = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="thumb_page")
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
                # analyze button: set selected id, go to Works & Analysis or Art Data
                if st.button("Analyze (open detail)", key=f"analyze_{oid}"):
                    st.session_state["selected_artwork"] = oid
                    st.experimental_set_query_params(_page="works")
                    st.experimental_rerun()
                if st.button("Include in Data Analysis", key=f"include_{oid}"):
                    # include into a session dataset for big data
                    s_ids = st.session_state.get("analysis_ids", [])
                    if oid not in s_ids:
                        s_ids.append(oid)
                    st.session_state["analysis_ids"] = s_ids
                    st.success("Added to analysis set (session).")

# ---------------- WORKS & ANALYSIS ----------------
elif page == "Works & Analysis":
    st.header("Works & Analysis — Detailed Artwork View")
    if "selected_artwork" not in st.session_state:
        st.info("No artwork selected. In 'Greek Figures', click Analyze on a card to open detail.")
    else:
        art_id = st.session_state["selected_artwork"]
        meta = met_get_object_cached(art_id)
        if not meta:
            st.error("Failed to load metadata.")
        else:
            left, right = st.columns([0.6, 0.4])
            with left:
                img = fetch_image_from_meta(meta)
                if img:
                    max_w = 750
                    w,h = img.size
                    if w>max_w:
                        img = img.resize((max_w, int(h*(max_w/w))))
                    st.image(img, use_column_width=False)
                else:
                    st.info("No image available.")
            with right:
                st.subheader(meta.get("title") or meta.get("objectName") or "Untitled")
                st.write(f"**Object ID:** {art_id}")
                st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
                st.write(f"**Date:** {meta.get('objectDate') or '—'}")
                st.write(f"**Medium:** {meta.get('medium') or '—'}")
                st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
                st.write(f"**Classification:** {meta.get('classification') or '—'}")
                if meta.get("objectURL"):
                    st.markdown(f"[View on MET]({meta.get('objectURL')})")
                st.markdown("---")
                client = get_openai_client()
                st.markdown("### Curator AI (optional)")
                if client and st.button("Generate AI analysis", key="gen_ai_detail"):
                    with st.spinner("Generating overview..."):
                        st.write(chat_complete_simple(client, f"Write a 3-sentence overview of the artwork using metadata: {meta}"))
                    with st.spinner("Generating context..."):
                        st.write(chat_complete_simple(client, f"Write 4-6 sentences of historical context for the artwork using metadata: {meta}"))
                    with st.spinner("Analyzing iconography..."):
                        st.write(chat_complete_simple(client, f"Analyze iconography and mythic references for this artwork: {meta}"))
                else:
                    st.write("(Enable OpenAI API key on Home and press 'Generate AI analysis')")

# ---------------- ART DATA (Big Data Analysis) ----------------
elif page == "Art Data":
    st.header("Art Data — Big Data Analysis (selected set or fetch anew)")
    st.markdown("""
This page computes data-driven charts for a set of MET objects.  
You can either:
- Use the **session analysis set** (items you manually added from Greek Figures), or
- Fetch and analyze directly from MET using the same aliases for a selected figure.
""")

    # choose source
    source_option = st.radio("Data source:", ["Session analysis set (manually added)","Fetch new from MET for a figure"], index=1, key="data_source")
    dataset_ids = []
    if source_option.startswith("Session"):
        dataset_ids = st.session_state.get("analysis_ids", [])
        st.write(f"{len(dataset_ids)} objects in the session analysis set.")
    else:
        figure_for_analysis = st.selectbox("Pick figure to fetch for analysis:", MYTH_LIST, key="analysis_figure")
        aliases = generate_aliases(figure_for_analysis)
        max_results = st.slider("Max records to try (fetch breadth)", 50, 800, 300, 50, key="analysis_max_results")
        if st.button("Fetch & build dataset", key="build_dataset"):
            all_ids = []
            prog = st.progress(0)
            for i, a in enumerate(aliases):
                ids = met_search_ids(a, max_results=max_results)
                for oid in ids:
                    if oid not in all_ids:
                        all_ids.append(oid)
                prog.progress(int((i+1)/len(aliases)*100))
            prog.empty()
            st.session_state["analysis_fetch_ids"] = all_ids
            st.success(f"Found {len(all_ids)} candidate ids. Now building dataset (metadata fetch).")

            # fetch metadata
            prog = st.progress(0)
            metas = []
            total = max(1, len(all_ids))
            for i, oid in enumerate(all_ids):
                meta = met_get_object_cached(oid)
                if meta:
                    metas.append(meta)
                if i % 10 == 0:
                    prog.progress(min(100, int((i+1)/total*100)))
                time.sleep(0.005)
            prog.empty()
            st.session_state["analysis_dataset"] = metas
            st.success(f"Built dataset with {len(metas)} metadata records (some may lack images).")
        # try to load fetched dataset if exists
        dataset_ids = st.session_state.get("analysis_fetch_ids", [])

    # If analysis dataset present use it, else check session ids
    dataset = st.session_state.get("analysis_dataset", None)
    if not dataset and dataset_ids:
        # build dataset from IDs
        dataset = []
        prog = st.progress(0)
        total = max(1, len(dataset_ids))
        for i, oid in enumerate(dataset_ids):
            meta = met_get_object_cached(oid)
            if meta:
                dataset.append(meta)
            if i % 10 == 0:
                prog.progress(min(100, int((i+1)/total*100)))
            time.sleep(0.002)
        prog.empty()

    if not dataset:
        st.info("No dataset available. Either add items to the session analysis set from Greek Figures, or fetch a dataset above.")
    else:
        st.success(f"Analyzing {len(dataset)} records.")
        # compute stats
        stats = extract_bigdata_stats(dataset)

        # 1) Timeline: objectBeginDate histogram (years)
        years = stats['years']
        if years:
            df_years = {}
            # create histogram via plotly
            fig = px.histogram(x=years, nbins=40, labels={'x':'Year','y':'Count'}, title="Artwork Time Distribution (objectBeginDate)")
            fig.update_layout(margin=dict(t=40,l=20,r=20,b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No reliable begin-year data available for timeline.")

        # 2) Medium / Material distribution (top 20)
        mcounts = stats['mediums']
        if mcounts:
            top_mediums = mcounts.most_common(20)
            names = [k.title() for k,_ in top_mediums]
            vals = [v for _,v in top_mediums]
            fig2 = px.bar(x=vals, y=names, orientation='h', labels={'x':'Count','y':'Medium'}, title="Medium / Material Distribution (top 20)")
            fig2.update_layout(margin=dict(t=40,l=120))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.write("No medium data available.")

        # 3) Geography / Culture distribution
        cc = stats['cultures']
        if cc:
            topc = cc.most_common(20)
            names = [k for k,_ in topc]
            vals = [v for _,v in topc]
            fig3 = px.bar(x=vals, y=names, orientation='h', labels={'x':'Count','y':'Culture'}, title="Geographic / Culture Distribution (top 20)")
            fig3.update_layout(margin=dict(t=40,l=120))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.write("No culture/geography data available.")

        # 4) Classification distribution
        cl = stats['classifications']
        if cl:
            topcl = cl.most_common(20)
            names = [k for k,_ in topcl]
            vals = [v for _,v in topcl]
            fig4 = px.bar(x=vals, y=names, orientation='h', labels={'x':'Count','y':'Classification'}, title="Classification Distribution (top 20)")
            fig4.update_layout(margin=dict(t=40,l=120))
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.write("No classification data available.")

        # 5) Top tags/themes
        tags = stats['tags']
        if tags:
            top_tags = tags.most_common(20)
            names = [k.title() for k,_ in top_tags]
            vals = [v for _,v in top_tags]
            fig5 = px.bar(x=vals, y=names, orientation='h', labels={'x':'Count','y':'Tag'}, title="Top Tags / Themes")
            fig5.update_layout(margin=dict(t=40,l=120))
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.write("No tag data available (MET records may lack tags).")

        # 6) Greek vs Roman copies
        gvr = stats['greek_vs_roman']
        total = gvr['greek'] + gvr['roman'] + gvr['other']
        fig6 = px.pie(values=[gvr['greek'], gvr['roman'], gvr['other']], names=['Greek','Roman','Other'], title="Greek vs Roman vs Other (heuristic)")
        st.plotly_chart(fig6, use_container_width=True)

        # 7) Vase painting narrative (examples)
        vase_examples = stats['vase_examples']
        if vase_examples:
            st.markdown("### Vase / Vessel examples (titles / classification strings — raw examples)")
            for i, ex in enumerate(vase_examples[:20]):
                st.write(f"{i+1}. {ex}")
        else:
            st.write("No obvious vase objects detected in this dataset.")

        # 8) Acquisition timeline (accessionYear)
        acq = stats['acquisitions']
        if acq:
            fig7 = px.histogram(x=acq, nbins=30, labels={'x':'Accession Year','y':'Count'}, title="Acquisition Years (museum accession)")
            st.plotly_chart(fig7, use_container_width=True)
        else:
            st.write("No accessionYear data available.")

        # Optionally let user download the cleaned CSV (basic)
        if st.button("Export cleaned dataset (CSV)", key="export_csv"):
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
            st.download_button("Download CSV", data=csv, file_name="met_dataset.csv", mime="text/csv")

# ---------------- INTERACTIVE TESTS (two quizzes) ----------------
elif page == "Interactive Tests":
    st.header("Interactive Tests — Two Personality Quizzes")
    client = get_openai_client()
    st.subheader("1) Which Greek Deity Are You? (short)")
    q1 = st.radio("In a group you:", ["Lead","Support","Create","Plan"], key="iq1")
    q2 = st.radio("You value most:", ["Power","Wisdom","Love","Joy"], key="iq2")
    q3 = st.radio("Pick a symbol:", ["Thunderbolt","Owl","Dove","Lyre"], key="iq3")
    if st.button("Get deity result", key="iq_get"):
        if q2 == "Wisdom" or q3 == "Owl":
            deity = "Athena"
        elif q2 == "Love" or q3 == "Dove":
            deity = "Aphrodite"
        elif q2 == "Power" or q3 == "Thunderbolt":
            deity = "Zeus"
        else:
            deity = "Apollo"
        st.markdown(f"### You resemble **{deity}**")
        st.write(FIXED_BIOS.get(deity, ""))

    st.markdown("---")
    st.subheader("2) Personality Archetype (Jungian-style)")
    s1 = st.selectbox("Preferred role:", ["Leader","Supporter","Strategist","Creator"], key="pq1")
    s2 = st.selectbox("Main motivation:", ["Duty","Glory","Pleasure","Wisdom"], key="pq2")
    s3 = st.selectbox("Crisis reaction:", ["Plan","Fight","Flee","Negotiate"], key="pq3")
    if st.button("Map archetype", key="pq_get"):
        if s2 == "Wisdom":
            arch = "Sage (Athena-like)"
        elif s2 == "Glory":
            arch = "Warrior (Ares-like)"
        elif s2 == "Pleasure":
            arch = "Seeker (Dionysus-like)"
        else:
            arch = "Guardian (Zeus-like)"
        st.markdown(f"### Archetype: **{arch}**")
        st.write("Short explanation and recommended artwork themes (leadership portraits, battle scenes, ritual imagery).")

# ---------------- MYTHIC LINEAGES ----------------
elif page == "Mythic Lineages":
    st.header("Mythic Lineages — Genealogy Visualization")
    st.markdown("Color-coded genealogy (Primordials / Titans / Olympians / Heroes / Creatures).")

    labels = [
        "Primordials","Chaos","Gaia","Uranus",
        "Titans","Cronus","Rhea","Oceanus","Hyperion",
        "Olympians","Zeus","Hera","Poseidon","Hades","Demeter","Hestia","Athena","Apollo","Artemis","Ares","Hermes","Dionysus","Aphrodite","Hephaestus",
        "Heroes","Heracles","Perseus","Theseus","Odysseus","Achilles","Jason",
        "Creatures","Medusa","Minotaur","Cyclops","Sirens"
    ]
    parents = [
        "","Primordials","Primordials","Primordials",
        "Primordials","Titans","Titans","Titans","Titans",
        "Primordials","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians","Olympians",
        "Primordials","Heroes","Heroes","Heroes","Heroes","Heroes","Heroes",
        "Primordials","Creatures","Creatures","Creatures","Creatures"
    ]
    category_color = {
        "Primordials":"#8E44AD",
        "Titans":"#E67E22",
        "Olympians":"#3498DB",
        "Heroes":"#E74C3C",
        "Creatures":"#27AE60"
    }
    def label_category(label):
        if label in ["Chaos","Gaia","Uranus","Primordials"]:
            return "Primordials"
        if label in ["Cronus","Rhea","Oceanus","Hyperion","Titans"]:
            return "Titans"
        if label in ["Zeus","Hera","Poseidon","Hades","Demeter","Hestia","Athena","Apollo","Artemis","Ares","Hermes","Dionysus","Aphrodite","Hephaestus","Olympians"]:
            return "Olympians"
        if label in ["Heracles","Perseus","Theseus","Odysseus","Achilles","Jason","Heroes"]:
            return "Heroes"
        if label in ["Medusa","Minotaur","Cyclops","Sirens","Creatures"]:
            return "Creatures"
        return "Primordials"

    color_map = {lbl: category_color[label_category(lbl)] for lbl in labels}
    fig = px.treemap(names=labels, parents=parents, color=labels, color_discrete_map=color_map)
    fig.update_layout(margin=dict(t=30,l=0,r=0,b=0))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- END ----------------
