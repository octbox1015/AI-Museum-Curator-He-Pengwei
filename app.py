from graphviz import Digraph
import streamlit as st

import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import base64
import os
from typing import List, Dict
import plotly.express as px
from pyvis.network import Network
import tempfile

# ----------------- Config -----------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ----------------- Constants -----------------
MYTH_LIST = [
    "Zeus","Hera","Athena","Apollo","Artemis","Aphrodite","Hermes","Dionysus","Ares","Hephaestus",
    "Poseidon","Hades","Demeter","Persephone","Hestia","Heracles","Perseus","Achilles","Odysseus",
    "Theseus","Jason","Medusa","Minotaur","Sirens","Cyclops","Centaur","Prometheus","Orpheus",
    "Eros","Nike","The Muses","The Fates","The Graces","Hecate","Atlas","Pandora"
]

FIXED_BIOS = {
    "Zeus": "Zeus is the king of the Olympian gods, ruler of the sky and thunder. Often shown with a thunderbolt and eagle.",
    "Athena": "Athena is goddess of wisdom, strategy, and craft. Often accompanied by an owl.",
    "Medusa": "Medusa, one of the Gorgons, is a powerful figure whose gaze turns viewers into stone.",
    "Perseus": "Perseus is the hero who slew Medusa and rescued Andromeda."
}

MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# ----------------- OpenAI Client -----------------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        return OpenAI(api_key=key)
    except:
        return None

def chat(client, system, user, max_tokens=500):
    if client is None:
        return "⚠️ OpenAI API Key not set."
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            max_tokens=max_tokens
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"⚠️ OpenAI Error: {e}"

# ----------------- MET Helpers -----------------
def met_search_ids(query: str, max_results: int = 100) -> List[int]:
    try:
        r = requests.get(MET_SEARCH, params={"q": query, "hasImages": True}, timeout=10)
        r.raise_for_status()
        ids = r.json().get("objectIDs", [])
        if ids is None:
            return []
        return ids[:max_results]
    except:
        return []

def met_get_object(oid: int) -> Dict:
    try:
        r = requests.get(MET_OBJECT.format(oid), timeout=10)
        r.raise_for_status()
        return r.json()
    except:
        return {}

def load_image(meta: Dict):
    urls = []
    if meta.get("primaryImageSmall"):
        urls.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"):
        urls.append(meta["primaryImage"])
    if meta.get("additionalImages"):
        urls.extend(meta["additionalImages"])

    for u in urls:
        try:
            img = Image.open(BytesIO(requests.get(u).content)).convert("RGB")
            return img
        except:
            continue
    return None

def generate_aliases(name: str):
    mapping = {
        "Athena": ["Minerva","Pallas Athena"],
        "Zeus": ["Jupiter"],
        "Aphrodite": ["Venus"],
        "Dionysus": ["Bacchus"],
        "Heracles": ["Hercules"]
    }
    base = [name]
    if name in mapping:
        base.extend(mapping[name])
    base += [f"{name} myth", f"{name} Greek"]
    return list(dict.fromkeys(base))

# ----------------- UI Tabs -----------------
tabs = st.tabs(["Home","Greek Deities","Works & Analysis","Interactive Art Zone","Mythology Network","Artwork Timeline"])

# ----------------- HOME -----------------
with tabs[0]:
    st.header("Welcome — AI Museum Curator (Greek Myth Edition)")
    st.markdown("""
**About:**  
This app fetches real artwork data from *The Metropolitan Museum of Art* and (optionally) uses OpenAI to generate curator-style explanations.

**Quick steps**
1. Go to **Greek Deities**, select a figure, then **Fetch related works**.  
2. Click a thumbnail → it will be selected and you can view full analysis in **Works & Analysis**.  
3. Use **Interactive Art Zone** for detail questions, sketch analysis, myth ID, archetype quiz, or image generation (requires OpenAI key).  
4. Explore **Mythology Network** and **Artwork Timeline** for visualizations.
    """)
    st.markdown("---")
    st.subheader("OpenAI API Key (session only)")
    api_in = st.text_input("Paste your OpenAI API Key (sk-...)", type="password", key="home_api_input_v2")
    if st.button("Save API Key", key="home_save_key"):
        if api_in:
            st.session_state["OPENAI_API_KEY"] = api_in
            st.success("API Key saved to session.")
        else:
            st.warning("Please enter a valid API key.")
    if OpenAI is None:
        st.info("OpenAI SDK not installed or unavailable. AI features will be disabled until you install 'openai'.")

    st.markdown("---")
    st.markdown("Course slides (reference):")
    # Use developer-provided local path (will be transformed by your deployment)
    st.markdown(f"[Open course PDF](/mnt/data/LN_-_Art_and_Advanced_Big_Data_-_W12_-_Designing_%26_Implementing_with_AI (1).pdf)")

# ----------------- GREEK DEITIES -----------------
with tabs[1]:
    st.header("Greek Deities / Heroes / Creatures")
    deity = st.selectbox("Choose a figure:", MYTH_LIST, key="deity_select_v2")
    st.subheader(f"Short description — {deity}")
    st.write(FIXED_BIOS.get(deity, f"{deity} is an important figure in Greek myth."))

    client = get_openai_client()
    if st.button("Expand description with AI", key="deity_expand_btn"):
        if client:
            with st.spinner("Expanding description..."):
                bio = expand_bio_ai(client, deity, FIXED_BIOS.get(deity, f"{deity} is a canonical figure in Greek myth."))
                st.session_state["expanded_bio"] = bio
                st.session_state["expanded_bio_for"] = deity
                st.markdown("### AI Expanded Introduction")
                st.write(bio)
        else:
            st.error("OpenAI client not configured. Enter API key on Home.")

    if st.session_state.get("expanded_bio") and st.session_state.get("expanded_bio_for")==deity:
        st.markdown("### AI Expanded Introduction (cached)")
        st.write(st.session_state["expanded_bio"])

    st.markdown("#### Related search aliases")
    st.write(generate_aliases(deity))

    st.markdown("---")
    st.write("Fetch artworks related to this figure (only those with downloadable images will be shown).")
    max_try = st.slider("Max MET records to try", 40, 400, 120, step=20, key="deity_max_try_v2")
    if st.button("Fetch related works from MET", key="fetch_deity_v2"):
        aliases = generate_aliases(deity)
        all_ids = []
        for a in aliases:
            ids = met_search_ids(a, max_results=max_try)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
        if not all_ids:
            st.info("No candidate works found.")
            st.session_state.pop("related_ids", None)
            st.session_state.pop("thumbs_data", None)
        else:
            st.success(f"Found {len(all_ids)} candidate works. Loading images (this may take some time)...")
            thumbs = []
            prog = st.progress(0)
            for i, oid in enumerate(all_ids):
                meta = met_get_object(oid)
                if meta:
                    img = load_image(meta)
                    if img:
                        thumbs.append((oid, meta, img))
                prog.progress(min(100, int((i+1)/len(all_ids)*100)))
                time.sleep(0.01)
            prog.empty()
            if not thumbs:
                st.info("No downloadable images among candidates.")
                st.session_state["related_ids"] = []
                st.session_state.pop("thumbs_data", None)
            else:
                st.session_state["related_ids"] = [t[0] for t in thumbs]
                st.session_state["thumbs_data"] = thumbs
                st.success(f"Loaded {len(thumbs)} artworks with images.")
                per_page = st.number_input("Thumbnails per page (deity gallery)", min_value=8, max_value=48, value=24, step=4, key="deity_pp_v2")
                pages = max(1, math.ceil(len(thumbs)/per_page))
                page = st.number_input("Gallery page (Deity)", min_value=1, max_value=pages, value=1, key="deity_page_v2")
                start = (page-1)*per_page
                page_items = thumbs[start:start+per_page]
                # grid display
                rows = math.ceil(len(page_items)/4)
                for r in range(rows):
                    cols = st.columns(4)
                    for c in range(4):
                        idx = r*4 + c
                        if idx < len(page_items):
                            oid, meta, img = page_items[idx]
                            with cols[c]:
                                st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                                if st.button("Select", key=f"deity_select_{oid}"):
                                    st.session_state["selected_artwork"] = oid
                                    st.success(f"Selected {oid}. Switch to 'Works & Analysis' tab to view details.")

# ----------------- WORKS & ANALYSIS -----------------
with tabs[2]:
    st.header("Works & Analysis — Selected Artwork View")
    if "selected_artwork" in st.session_state:
        art_id = st.session_state["selected_artwork"]
        meta = met_get_object(art_id)
        left, right = st.columns([0.5, 0.5])
        with left:
            img = load_image(meta)
            if img:
                max_w = 650
                w, h = img.size
                if w > max_w:
                    img = img.resize((max_w, int(h*(max_w/w))))
                st.image(img, use_column_width=False)
            else:
                st.info("Image not available for this object.")
            if st.button("Back to Gallery", key="back_gallery_btn"):
                st.session_state.pop("selected_artwork", None)
                st.rerun()

        # --- RIGHT: Object Info + About + AI sections ---
        with right:
            st.subheader("Artwork Information")
            st.markdown(f"### **{meta.get('title') or meta.get('objectName') or 'Untitled'}**")
            st.write(f"**Object ID:** {art_id}")
            st.write(f"**Artist:** {meta.get('artistDisplayName') or 'Unknown'}")
            st.write(f"**Culture:** {meta.get('culture') or '—'}")
            st.write(f"**Department:** {meta.get('department') or '—'}")
            st.write(f"**Date:** {meta.get('objectDate') or '—'}")
            st.write(f"**Medium:** {meta.get('medium') or '—'}")
            st.write(f"**Dimensions:** {meta.get('dimensions') or '—'}")
            st.write(f"**Classification:** {meta.get('classification') or '—'}")
            st.write(f"**Accession Number:** {meta.get('accessionNumber') or '—'}")
            if meta.get("objectURL"):
                st.markdown(f"🔗 [View on The MET Website]({meta.get('objectURL')})")

            st.markdown("---")
            st.markdown("### About This Artwork Page")
            st.markdown("""
This page displays real artwork metadata retrieved directly from **The Metropolitan Museum of Art**.

The AI-generated curator texts (Overview, Context, Iconography) rely on this metadata to ensure accuracy and consistency.

**Data Source:** MET Museum Open API
            """)

            st.markdown("---")
            # AI-assisted sections
            client = get_openai_client()
            st.markdown("#### Overview")
            if client:
                with st.spinner("Generating overview..."):
                    st.write(generate_overview(client, meta))
            else:
                st.write("(Enable OpenAI API Key on Home to auto-generate overview)")

            st.markdown("#### Historical & Artistic Context")
            if client:
                with st.spinner("Generating context..."):
                    st.write(generate_context(client, meta))
            else:
                st.write("(Enable OpenAI API Key on Home to auto-generate context)")

            st.markdown("#### Artistic Features")
            st.write("Materials, technique, composition — AI will expand when API enabled.")

            st.markdown("#### Iconography & Myth Interpretation")
            if client:
                with st.spinner("Analyzing iconography..."):
                    st.write(generate_iconography(client, meta))
            else:
                st.write("(Enable OpenAI API Key)")

            st.markdown("#### Exhibition Notes")
            st.write("Placement suggestions and related objects will appear here when AI is enabled.")

    else:
        st.info("No artwork selected. Please go to 'Greek Deities' and fetch/select works.")
        thumbs = st.session_state.get("thumbs_data", [])
        if thumbs:
            per_page = st.number_input("Thumbnails per page (works gallery)", min_value=8, max_value=48, value=24, step=4, key="wa_pp_v2")
            pages = max(1, math.ceil(len(thumbs)/per_page))
            page = st.number_input("Gallery page (Works)", min_value=1, max_value=pages, value=1, key="wa_page_v2")
            start = (page-1)*per_page
            items = thumbs[start:start+per_page]
            rows = math.ceil(len(items)/4)
            for r in range(rows):
                cols = st.columns(4)
                for c in range(4):
                    idx = r*4 + c
                    if idx < len(items):
                        oid, meta, img = items[idx]
                        with cols[c]:
                            st.image(img.resize((220,220)), caption=f"{meta.get('title') or meta.get('objectName')} ({oid})")
                            if st.button("Select", key=f"wa_sel_{oid}"):
                                st.session_state["selected_artwork"] = oid
                                st.rerun()

# ----------------- INTERACTIVE ART ZONE -----------------
with tabs[3]:
    st.header("Interactive Art Zone")
    mode = st.radio("Mode:", ["Art-based","Myth-based"], key="interactive_mode_v2")
    client = get_openai_client()

    if mode=="Art-based":
        st.subheader("Ask about a visual detail")
        if "selected_artwork" not in st.session_state:
            st.info("Select an artwork in Works & Analysis first.")
        else:
            meta = met_get_object(st.session_state["selected_artwork"])
            q = st.text_input("Ask a question (e.g., 'What does the owl mean?')", key="detail_q_v2")
            if st.button("Ask", key="ask_btn_v2"):
                if client:
                    with st.spinner("Answering..."):
                        st.write(ai_answer_detail(client, q, meta))
                else:
                    st.error("Enable OpenAI API Key on Home.")

        st.markdown("---")
        st.subheader("Style Analyzer — upload a sketch")
        uploaded = st.file_uploader("Upload sketch/photo", type=["png","jpg","jpeg"], key="style_upload_v2")
        note = st.text_input("Describe sketch...", key="style_note_v2")
        if uploaded and st.button("Analyze", key="analyze_btn_v2"):
            if client:
                img = Image.open(BytesIO(uploaded.getvalue())).convert("RGB")
                st.image(img, caption="Uploaded")
                with st.spinner("Analyzing..."):
                    st.write(ai_style_match(client, note or "User sketch"))
            else:
                st.error("Enable OpenAI API Key on Home.")

    else:
        st.subheader("Myth Identifier")
        desc = st.text_input("Describe a scene or motif", key="myth_desc_v2")
        if st.button("Identify", key="identify_btn_v2"):
            if client:
                with st.spinner("Identifying..."):
                    st.write(ai_myth_identifier(client, desc))
            else:
                st.error("Enable OpenAI API Key on Home.")

        st.markdown("---")
        st.subheader("Myth Archetype Matcher")
        a1 = st.selectbox("Preferred role:", ["Leader","Supporter","Strategist","Creator"], key="arch_a1")
        a2 = st.selectbox("Which drives you:", ["Duty","Fame","Pleasure","Wisdom"], key="arch_a2")
        a3 = st.selectbox("You respond to crisis by:", ["Plan","Fight","Flee","Negotiate"], key="arch_a3")
        a4 = st.selectbox("Which image appeals most:", ["Eagle","Owl","Serpent","Laurel"], key="arch_a4")
        if st.button("Get archetype", key="arch_btn_v2"):
            if client:
                answers = {"role":a1,"drive":a2,"crisis":a3,"image":a4}
                with st.spinner("Mapping archetype..."):
                    st.write(ai_personality_archetype(client, answers))
            else:
                st.error("Enable OpenAI API Key on Home.")

# ----------------- MYTHOLOGY NETWORK -----------------
with tabs[4]:
    st.header("Mythology Relationship Graph")
    st.markdown("Interactive network of mythological relationships. Drag nodes to explore.")

    relations = [
        ("Zeus","Hera","married"),
        ("Zeus","Athena","father"),
        ("Zeus","Apollo","father"),
        ("Zeus","Artemis","father"),
        ("Zeus","Ares","father"),
        ("Hades","Persephone","husband"),
        ("Perseus","Medusa","slays"),
        ("Apollo","Artemis","twin"),
        ("Poseidon","Theseus","father"),
        ("Zeus","Heracles","father"),
        ("Demeter","Persephone","mother"),
        ("Odysseus","Athena","favored_by"),
        ("Aphrodite","Eros","mother"),
    ]

    G = nx.DiGraph()
    for a,b,rel in relations:
        G.add_node(a)
        G.add_node(b)
        G.add_edge(a,b,label=rel)

    net = Network(height="600px", width="100%", directed=True, notebook=False)
    net.from_nx(G)
    net.repulsion(node_distance=180, spring_length=120)

    # Generate HTML safely and embed
    try:
        html_str = net.generate_html(notebook=False)
        from streamlit.components.v1 import html
        html(html_str, height=640, scrolling=True)
    except Exception as e:
        st.error(f"Network graph rendering failed: {e}")

# ----------------- ARTWORK TIMELINE -----------------
with tabs[5]:
    st.header("Artwork Timeline & Distribution")
    st.markdown("Timeline and histogram of object begin dates from current gallery (if available).")

    thumbs = st.session_state.get("thumbs_data", [])
    years = []
    titles = []
    for oid, meta, img in thumbs:
        y = meta.get("objectBeginDate")
        if isinstance(y, int):
            years.append(y)
            titles.append(meta.get("title") or meta.get("objectName") or str(oid))
        else:
            od = meta.get("objectDate") or ""
            m = re.search(r"-?\d{1,4}", od)
            if m:
                try:
                    years.append(int(m.group(0)))
                    titles.append(meta.get("title") or meta.get("objectName") or str(oid))
                except:
                    pass

    if not years:
        st.info("No date info available. Fetch a deity's works first.")
    else:
        df = {"year": years, "title": titles}
        fig = px.scatter(df, x="year", y=[1]*len(years), hover_data=["title"], labels={"x":"Year"})
        fig.update_yaxes(visible=False)
        st.plotly_chart(fig, use_container_width=True)
        hist = px.histogram(df, x="year", nbins=20, title="Distribution of object dates")
        st.plotly_chart(hist, use_container_width=True)

# ---- MYTHIC LINEAGES (Graphviz Tree) ----
with tab_lineages:
    st.header("🌳 Mythic Lineages — Greek Myth Family Tree")

    st.markdown("""
This genealogical tree shows the major divine and heroic lineages in Greek mythology —  
from the **Primordial Gods**, to the **Titans**, the **Olympian Gods**, and the **Heroic Age**.

Each level uses different colors for readability:
- 🟠 Primordial Gods  
- 🔵 Titans  
- 🟢 Olympians  
- 🟡 Heroes  
    """)

    # Create Graphviz diagram
    dot = Digraph("GreekMythTree", format="svg")
    dot.attr(rankdir="TB", size="8,8", nodesep="0.4", ranksep="0.6")  # Top → Bottom tree

    # ---------- LAYERS & COLORS ----------
    primordial = ["Chaos", "Gaia", "Tartarus", "Eros"]
    for p in primordial:
        dot.node(p, shape="oval", style="filled", fillcolor="#fdebd0")  # light orange

    titans = [
        "Uranus", "Cronus", "Rhea",
        "Oceanus", "Tethys", "Hyperion", "Theia", "Iapetus"
    ]
    for t in titans:
        dot.node(t, shape="oval", style="filled", fillcolor="#d6eaf8")  # light blue

    olympians = [
        "Zeus", "Hera", "Poseidon", "Hades", "Demeter", "Hestia",
        "Apollo", "Artemis", "Athena", "Ares",
        "Hermes", "Dionysus", "Aphrodite", "Hephaestus"
    ]
    for o in olympians:
        dot.node(o, shape="oval", style="filled", fillcolor="#d5f5e3")  # light green

    heroes = ["Heracles", "Perseus", "Theseus", "Odysseus", "Achilles", "Jason", "Orpheus"]
    for h in heroes:
        dot.node(h, shape="oval", style="filled", fillcolor="#f9e79f")  # light yellow

    # ---------- RELATIONSHIPS ----------
    relations = [
        ("Chaos", "Gaia"),
        ("Chaos", "Tartarus"),
        ("Gaia", "Uranus"),

        ("Gaia", "Cronus"),
        ("Gaia", "Rhea"),
        ("Uranus", "Cronus"),
        ("Uranus", "Rhea"),

        # Olympian generation
        ("Cronus", "Zeus"),
        ("Cronus", "Hera"),
        ("Cronus", "Poseidon"),
        ("Cronus", "Hades"),
        ("Cronus", "Demeter"),
        ("Cronus", "Hestia"),

        # Zeus children
        ("Zeus", "Ares"),
        ("Zeus", "Apollo"),
        ("Zeus", "Artemis"),
        ("Zeus", "Athena"),
        ("Zeus", "Hermes"),
        ("Zeus", "Dionysus"),
        ("Zeus", "Aphrodite"),
        ("Hera", "Hephaestus"),

        # Heroes
        ("Zeus", "Heracles"),
        ("Zeus", "Perseus"),
        ("Poseidon", "Theseus"),
        ("Hermes", "Odysseus"),
        ("Peleus", "Achilles"),
        ("Aeson", "Jason"),
        ("Apollo", "Orpheus"),
    ]

    for parent, child in relations:
        dot.edge(parent, child)

    # Display SVG
    svg = dot.pipe().decode("utf-8")
    st.write(svg, unsafe_allow_html=True)


# End of app
