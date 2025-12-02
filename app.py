# app.py — Mythic Art Explorer (Final integrated)
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

# Optional OpenAI (used only if user supplies API key in sidebar)
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

# ---------------- Helpers: MET API ----------------
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

# ---------------- Sidebar ----------------
st.sidebar.title("Mythic Art Explorer")
st.sidebar.markdown("Browse Greek myth figures, view MET artworks, run big-data analysis, and try interactive myth tests.")
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

# ---------------- Home ----------------
if page == "Home":
    st.title("🏛️ Mythic Art Explorer — Greek Myth Edition")
    st.markdown("""
    Welcome — this app lets you explore Greek mythological figures and real artworks from The Metropolitan Museum of Art.
    - **Gallery**: image-first browsing (thumbnail waterfall + modal detail)
    - **Art Data**: dataset-level visualizations
    - **Interactive Tests**: a 16-question personality-style test + quick quizzes
    - **Mythic Lineages**: network genealogy visualization
    """)

# ---------------- Gallery (merged Greek Figures & Works & Analysis) ----------------
elif page == "Gallery (Mythic Art Explorer)":
    st.header("Gallery — Mythic Art Explorer")
    selected = st.selectbox("Choose a mythic figure:", MYTH_LIST, key="gallery_select")
    st.write(FIXED_BIOS.get(selected, f"{selected} is a canonical figure in Greek myth."))

    st.markdown("**Search aliases:**")
    st.write(generate_aliases(selected))

    # fetch control
    max_results = st.slider("Max MET records to try (per alias)", 50, 800, 300, 50, key="gallery_max")
    if st.button("Fetch artworks (images)", key="gallery_fetch"):
        aliases = generate_aliases(selected)
        all_ids = []
        prog = st.progress(0)
        for i,a in enumerate(aliases):
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
        # waterfall-like layout: 3 columns with variable image heights (approximate)
        per_page = st.number_input("Thumbnails per page", min_value=6, max_value=48, value=12, step=6, key="gallery_pp")
        pages = math.ceil(len(thumbs)/per_page)
        page_idx = st.number_input("Page", min_value=1, max_value=max(1,pages), value=1, key="gallery_page")
        start = (page_idx-1)*per_page
        page_items = thumbs[start:start+per_page]

        cols = st.columns(3)
        # randomize heights slightly to emulate masonry
        for i, item in enumerate(page_items):
            col = cols[i % 3]
            with col:
                try:
                    # resize to variable height while maintaining width
                    w_target = 300
                    img = item["img"]
                    w,h = img.size
                    ratio = w_target / w
                    new_h = int(h * ratio)
                    # small random jitter to emulate masonry feel
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
                    # open modal with absolute index
                    # store the full list in session for modal navigation
                    st.session_state["modal_thumbs"] = thumbs
                    st.session_state["modal_index"] = start + i
                    st.session_state["modal_open"] = True

        # Modal (use st.modal) - placed after grid to avoid widget id duplication
        if st.session_state.get("modal_open", False):
            idx = st.session_state.get("modal_index", 0)
            modal_thumbs = st.session_state.get("modal_thumbs", thumbs)
            idx = max(0, min(idx, len(modal_thumbs)-1))
            st.session_state["modal_index"] = idx

            with st.modal("Artwork Details", key="gallery_modal"):
                record = modal_thumbs[idx]
                oid = record["objectID"]
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
                    # curator AI analysis
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
                    # navigation buttons
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

# ---------------- Art Data (Big Data) ----------------
elif page == "Art Data":
    st.header("Art Data — Dataset Analysis")
    st.markdown("Build and visualize a dataset for a chosen mythic figure (MET metadata).")
    figure_for_analysis = st.selectbox("Figure to analyze:", MYTH_LIST, key="ad_figure")
    aliases = generate_aliases(figure_for_analysis)
    max_results = st.slider("Max MET records per alias", 50, 800, 300, 50, key="ad_max")

    if st.button("Fetch dataset & analyze", key="ad_fetch"):
        all_ids = []
        p = st.progress(0)
        for i,a in enumerate(aliases):
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
            time.sleep(0.003)
        prog.empty()
        st.session_state["analysis_dataset"] = metas
        st.success(f"Built dataset: {len(metas)} records.")

    dataset = st.session_state.get("analysis_dataset", None)
    if not dataset:
        st.info("No dataset. Click 'Fetch dataset & analyze'.")
    else:
        st.success(f"Analyzing {len(dataset)} records.")
        # extract stats (robust)
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

        # Visualizations
        st.subheader("Timeline (objectBeginDate / heuristic)")
        if stats["years"]:
            fig = px.histogram(x=stats["years"], nbins=40, labels={'x':'Year','y':'Count'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No reliable year data.")

        st.subheader("Medium / Material (top 20)")
        if stats["mediums"]:
            topm = stats["mediums"].most_common(20)
            fig2 = px.bar(x=[v for _,v in topm], y=[k.title() for k,_ in topm], orientation='h', labels={'x':'Count','y':'Medium'})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No medium data.")

        st.subheader("Geography / Culture (top 20)")
        if stats["cultures"]:
            topc = stats["cultures"].most_common(20)
            fig3 = px.bar(x=[v for _,v in topc], y=[k for k,_ in topc], orientation='h', labels={'x':'Count','y':'Culture'})
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No culture data.")

        st.subheader("Tags / Themes (top 20)")
        if stats["tags"]:
            toptags = stats["tags"].most_common(20)
            fig4 = px.bar(x=[v for _,v in toptags], y=[k.title() for k,_ in toptags], orientation='h', labels={'x':'Count','y':'Tag'})
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No tags available.")

        st.subheader("Greek vs Roman (heuristic)")
        gv = stats["gvr"]
        fig5 = px.pie(values=[gv["greek"],gv["roman"],gv["other"]], names=["Greek","Roman","Other"])
        st.plotly_chart(fig5, use_container_width=True)

        st.subheader("Vase / Vessel examples (sample)")
        if stats["vases"]:
            for i, v in enumerate(stats["vases"][:30]): st.write(f"{i+1}. {v}")
        else:
            st.info("No vase items detected.")

        st.subheader("Acquisition years (accessionYear)")
        if stats["acqs"]:
            fig6 = px.histogram(x=stats["acqs"], nbins=30, labels={'x':'Year','y':'Count'})
            st.plotly_chart(fig6, use_container_width=True)
        else:
            st.info("No accessionYear data.")

        # CSV Export
        if st.button("Export cleaned dataset (CSV)", key="export_csv"):
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

# ---------------- Interactive Tests (advanced 16-question) ----------------
elif page == "Interactive Tests":
    st.header("Interactive Tests — 16-question Personality (Mythic)")

    st.markdown("""
    This is a 16-question myth-inspired personality measure. It maps answers to four dimensions:
    - Authority / Leadership (Zeus-like)
    - Wisdom / Strategy (Athena-like)
    - Sensuality / Relationship (Aphrodite-like)
    - Creativity / Transcendence (Apollo/Dionysus-like)

    Answer honestly — results include profile, strengths, shadow, and suggested artwork themes.
    """)

    # define questions (16) and mapping to dimensions
    QUESTIONS = [
        ("In a group task you usually:", ["Take charge","Design the plan","Create the mood","Support others"]),
        ("When solving problems you:", ["Decide quickly","Weigh options logically","Follow intuition","Experiment with creativity"]),
        ("Your ideal weekend:", ["Host a gathering","Study/learn","Make art/romance","Go to a performance/party"]),
        ("You value most:", ["Order","Insight","Connection","Expression"]),
        ("Under stress you tend to:", ["Assert control","Withdraw to think","Seek comfort","Act impulsively for release"]),
        ("Favorite symbol:", ["Thunderbolt","Owl","Dove","Lyre"]),
        ("Which role appeals most:", ["Judge/Leader","Strategist/Advisor","Lover/Mediator","Artist/Prophet"]),
        ("You admire people who:", ["Hold responsibility","Think deeply","Love openly","Create boldly"]),
        ("Your decision style:", ["Command","Analyze","Relate","Innovate"]),
        ("You prefer art that is:", ["Monumental","Intellectual","Sensual","Expressive"]),
        ("Moral code you respect:", ["Duty","Truth","Compassion","Freedom"]),
        ("You respond to conflict by:", ["Imposing order","Negotiating logically","Appealing to feelings","Transforming the scene"]),
        ("Which environment soothes you:", ["Structured hall","Library","Salon","Theatre"]),
        ("What do you fear most:", ["Chaos beneath order","Ignorance","Loneliness","Sterility/banality"]),
        ("What energizes you:", ["Recognition of duty","Discovery of patterns","Warm relationships","Aesthetic breakthrough"]),
        ("If a crisis happens you:", ["Take command","Plan a solution","Comfort others","Change the mood"])
    ]

    # build dynamic form
    answers = []
    if "test_answers" not in st.session_state:
        st.session_state["test_answers"] = [None]*len(QUESTIONS)
    for i, (q, opts) in enumerate(QUESTIONS):
        st.session_state["test_answers"][i] = st.radio(f"{i+1}. {q}", opts, key=f"q_{i}")

    if st.button("Submit 16-question test", key="submit_16"):
        # scoring rules: map each option index to one of 4 archetype scores
        # mapping order: [Zeus, Athena, Aphrodite, Apollo/Dionysus]
        scores = {"Zeus":0, "Athena":0, "Aphrodite":0, "Apollo":0}
        mapping = {
            0: "Zeus", 1: "Athena", 2: "Aphrodite", 3: "Apollo"
        }
        for i, ans in enumerate(st.session_state["test_answers"]):
            if ans is None:
                st.warning(f"Please answer question {i+1}.")
                st.stop()
            # find index of selected option in QUESTIONS[i][1]
            opts = QUESTIONS[i][1]
            idx = opts.index(ans)
            arche = mapping[idx]
            scores[arche] += 1

        # normalize & interpret
        total = sum(scores.values())
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary, primary_score = sorted_scores[0]
        second, second_score = sorted_scores[1]

        st.markdown(f"## Your primary mythic alignment: **{primary}**")
        st.write(f"Scores: {scores}")

        # richer analysis text
        def archetype_text(name):
            if name=="Zeus":
                return ("**Zeus — The Guardian/Ruler.** Leadership, responsibility, system-building. "
                        "Strengths: decisiveness, protective authority. Shadow: authoritarian rigidity.")
            if name=="Athena":
                return ("**Athena — The Strategist/Sage.** Clarity, craft, strategy. "
                        "Strengths: insight, problem-solving. Shadow: over-intellectualizing, emotional distance.")
            if name=="Aphrodite":
                return ("**Aphrodite — The Lover/Connector.** Sensuality, relational intelligence. "
                        "Strengths: empathy, aesthetic sensibility. Shadow: loss of boundaries.")
            return ("**Apollo/Dionysus (Apollo here)** — The Creative/Harmonizer.** Beauty, prophecy, artistic drive. "
                    "Strengths: synthesis of art and thought. Shadow: perfectionism or excess.")

        st.markdown("### Profile")
        st.write(archetype_text(primary))
        st.markdown("### Secondary tendency")
        st.write(archetype_text(second))

        st.markdown("### Practical suggestions for art exploration")
        if primary == "Zeus":
            st.write("- Look for throne/chair imagery, oath scenes, statuary of rulers, large-scale public monuments.")
        elif primary == "Athena":
            st.write("- Look for votive offerings, armor, owl motifs, vase scenes of strategy.")
        elif primary == "Aphrodite":
            st.write("- Look for intimate portraits, love scenes, ritual objects associated with beauty.")
        else:
            st.write("- Look for lyres, theater-related objects, ecstatic scenes, and richly colored works.")

        # optional OpenAI deeper narrative
        client = get_openai_client()
        if client:
            if st.button("Ask AI to write a 3-paragraph mythic narrative of your profile"):
                with st.spinner("AI writing..."):
                    prompt = f"Write a 3-paragraph mythicized character sketch for someone with profile {primary} (scores {scores}). Make it poetic and museum-friendly."
                    out = chat_complete_simple(client, prompt, max_tokens=500)
                    st.markdown("### AI narrative")
                    st.write(out)

# ---------------- Mythic Lineages (network graph) ----------------
elif page == "Mythic Lineages":
    st.header("Mythic Lineages — Network Graph")

    # build nodes and edges (simplified but extensible)
    nodes = [
        ("Chaos","Primordial"),("Gaia","Primordial"),("Uranus","Primordial"),
        ("Cronus","Titan"),("Rhea","Titan"),("Oceanus","Titan"),("Hyperion","Titan"),
        ("Zeus","Olympian"),("Hera","Olympian"),("Poseidon","Olympian"),("Hades","Olympian"),
        ("Athena","Olympian"),("Apollo","Olympian"),("Artemis","Olympian"),
        ("Heracles","Hero"),("Perseus","Hero"),("Theseus","Hero")
    ]
    edges = [
        ("Chaos","Gaia"),("Gaia","Uranus"),
        ("Gaia","Cronus"),("Uranus","Cronus"),
        ("Cronus","Zeus"),("Rhea","Zeus"),
        ("Zeus","Athena"),("Zeus","Apollo"),("Zeus","Artemis"),
        ("Zeus","Heracles"),("Perseus","Heracles"),("Zeus","Heracles")
    ]

    G = nx.DiGraph()
    for n,cat in nodes:
        G.add_node(n, category=cat)
    for a,b in edges:
        G.add_edge(a,b)

    # layout
    pos = nx.spring_layout(G, seed=42, k=0.8)

    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0,y0 = pos[edge[0]]
        x1,y1 = pos[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    node_x = []
    node_y = []
    texts = []
    colors = []
    cat_color = {"Primordial":"#8E44AD","Titan":"#E67E22","Olympian":"#3498DB","Hero":"#E74C3C"}
    for n in G.nodes():
        x,y = pos[n]
        node_x.append(x)
        node_y.append(y)
        texts.append(f"{n} ({G.nodes[n]['category']})")
        colors.append(cat_color.get(G.nodes[n]['category'], "#7F8C8D"))

    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(width=1, color='#888'), hoverinfo='none')
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode='markers+text',
        hoverinfo='text',
        marker=dict(size=28, color=colors, line=dict(width=1, color='#222')),
        text=[n for n in G.nodes()],
        textposition="bottom center"
    )

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title='Mythic Network (simplified)',
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                    ))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- End ----------------
