import streamlit as st
import requests
from io import BytesIO
from PIL import Image
import os
import math
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------
#  PAGE CONFIG
# ------------------------------------
st.set_page_config(page_title="AI Museum Curator — Greek Myth", layout="wide")
st.title("🏛️ AI Museum Curator — Greek Mythology Edition")

# ------------------------------------
#  CONSTANTS
# ------------------------------------
MET_SEARCH = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"

# Full Greek Mythology List (Olympians + Titans + Primordials + Heroes + Creatures)
MYTH_LIST = [
    # Olympians
    "Zeus","Hera","Athena","Apollo","Artemis","Aphrodite","Hermes","Dionysus",
    "Ares","Hephaestus","Poseidon","Hades","Demeter","Persephone","Hestia",

    # Titans
    "Cronus","Rhea","Oceanus","Tethys","Hyperion","Theia","Coeus","Phoebe",
    "Iapetus","Themis","Mnemosyne","Atlas","Prometheus",

    # Primordials
    "Chaos","Gaia","Uranus","Nyx","Erebus","Tartarus","Eros (Primordial)",

    # Heroes
    "Heracles","Perseus","Achilles","Odysseus","Theseus","Jason","Atalanta",

    # Creatures / Others
    "Medusa","Minotaur","Cyclops","Sirens","Centaur","Cerberus","Hydra"
]

# Short fixed bios (extendable)
FIXED_BIOS = {
    "Zeus":"Zeus is the king of the Olympian gods and ruler of the sky and thunder.",
    "Athena":"Athena is the goddess of wisdom, craft, and strategic warfare.",
    "Medusa":"Medusa is a Gorgon whose gaze turns viewers to stone.",
    "Heracles":"Heracles is the hero known for completing the Twelve Labors.",
    "Chaos":"Chaos is the primordial void from which the universe was born.",
    "Gaia":"Gaia is the personification of Earth and the mother of many gods.",
    "Uranus":"Uranus is the primordial sky, father of the Titans."
}

# ------------------------------------
#  OPENAI CLIENT WRAPPER
# ------------------------------------
try:
    import openai
except:
    openai = None

def get_openai_client():
    key = st.session_state.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if openai and key:
        openai.api_key = key
        return openai
    return None

def ai_answer(client, prompt):
    if not client:
        return "OpenAI key missing."
    try:
        resp = client.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a museum curator."},
                      {"role":"user","content":prompt}],
            max_tokens=350,
            temperature=0.2
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"OpenAI error: {e}"

# ------------------------------------
#  MET API HELPERS
# ------------------------------------
@st.cache_data
def met_search_ids(query):
    try:
        r = requests.get(MET_SEARCH, params={"q":query, "hasImages":True})
        data = r.json()
        return data.get("objectIDs") or []
    except:
        return []

@st.cache_data
def met_get_object(object_id):
    try:
        data = requests.get(MET_OBJECT.format(object_id)).json()
        return data
    except:
        return {}

def fetch_image(meta):
    img_urls = []
    if meta.get("primaryImageSmall"): img_urls.append(meta["primaryImageSmall"])
    if meta.get("primaryImage"): img_urls.append(meta["primaryImage"])
    if meta.get("additionalImages"): img_urls += meta["additionalImages"]

    for url in img_urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return Image.open(BytesIO(r.content)).convert("RGB")
        except:
            continue
    return None

def generate_aliases(name):
    base = [name, f"{name} myth", f"{name} greek"]
    mapping = {
        "Zeus":["Jupiter"], "Athena":["Minerva"], "Aphrodite":["Venus"],
        "Dionysus":["Bacchus"], "Hermes":["Mercury"],
        "Heracles":["Hercules"], "Persephone":["Proserpina"],
        "Medusa":["Gorgon"]
    }
    if name in mapping:
        base += mapping[name]
    return list(dict.fromkeys(base))

# ------------------------------------
#  HOME PAGE
# ------------------------------------
st.header("Welcome")
st.markdown("""
Explore Greek mythology through real artworks from The Metropolitan Museum of Art.  

### 🔧 How to Use
1. Enter your **OpenAI API Key** below.  
2. Go to **Greek Figures** → choose a god, titan, hero, or creature.  
3. Explore **real artworks**, each with AI-generated:
   - Overview  
   - Historical Context  
   - Iconography Analysis  
4. Visit **Works & Analysis** for a structured deep dive.  
5. Explore **Mythic Lineages** (tree diagram of Greek genealogy).  
6. Try interactive tools in **Interactive Art Zone**.
""")

api_key_input = st.text_input("Enter OpenAI API Key:", type="password")
if st.button("Save Key"):
    st.session_state["OPENAI_API_KEY"] = api_key_input
    st.success("API key saved.")

client = get_openai_client()

# ------------------------------------
#  SELECT GREEK FIGURE
# ------------------------------------
st.header("Greek Figures")
selected = st.selectbox("Choose a figure:", MYTH_LIST)

bio = FIXED_BIOS.get(selected, f"{selected} is a major figure in Greek myth.")
st.subheader(f"Short Description — {selected}")
st.write(bio)

if st.button("Expand with AI"):
    st.session_state["expanded_bio"] = ai_answer(client, f"Expand this biography of {selected}: {bio}")

if st.session_state.get("expanded_bio"):
    st.markdown("### AI Expanded Description")
    st.write(st.session_state["expanded_bio"])

# ------------------------------------
#  FETCH REAL ARTWORKS
# ------------------------------------
st.subheader("Related Artworks (Real MET Data)")

aliases = generate_aliases(selected)
object_ids = []
for a in aliases:
    object_ids += met_search_ids(a)
object_ids = list(dict.fromkeys(object_ids))[:200]

artworks = []
for oid in object_ids:
    meta = met_get_object(oid)
    img = fetch_image(meta)
    if img:
        artworks.append((oid, meta, img))

if not artworks:
    st.info("No artworks found.")
else:
    for oid, meta, img in artworks:
        with st.expander(f"{meta.get('title','Untitled')}"):
            st.image(img, use_column_width=True)
            st.write(f"**Artist:** {meta.get('artistDisplayName','Unknown')}")
            st.write(f"**Date:** {meta.get('objectDate','—')}")
            st.write(f"**Medium:** {meta.get('medium','—')}")
            st.write(f"**Dimensions:** {meta.get('dimensions','—')}")
            st.write(f"[View on MET Website]({meta.get('objectURL')})")

            st.markdown("#### AI Overview")
            st.write(ai_answer(client, f"Give an overview of this artwork: {meta}"))

            st.markdown("#### Historical & Artistic Context")
            st.write(ai_answer(client, f"Explain the historical context using metadata: {meta}"))

            st.markdown("#### Iconography / Myth Analysis")
            st.write(ai_answer(client, f"Analyze the mythological meaning: {meta}"))

# ------------------------------------
#  WORKS & ANALYSIS — STRUCTURED VIEW
# ------------------------------------
st.header("Works & Analysis — Structured View")
st.markdown("### Paintings / Sculpture / Books / Manuscripts / Objects")

def filter_by_type(items, keyword):
    return [i for i in items if keyword.lower() in (i[1].get("objectName","").lower()
                + " " + i[1].get("classification","").lower())]

categories = {
    "Paintings": filter_by_type(artworks, "painting"),
    "Sculpture": filter_by_type(artworks, "sculpture"),
    "Manuscripts / Books": filter_by_type(artworks, "book"),
    "Objects / Ceramics / Misc": filter_by_type(artworks, "object"),
}

for cat, items in categories.items():
    st.subheader(cat)
    if not items:
        st.write("No items.")
    else:
        for oid, meta, img in items:
            with st.expander(f"{meta.get('title','Untitled')}"):
                st.image(img, use_column_width=False, width=300)
                st.write(f"**Artist:** {meta.get('artistDisplayName','Unknown')}")
                st.write(f"**Date:** {meta.get('objectDate','—')}")

# ------------------------------------
#  MYTHIC LINEAGES (TREE DIAGRAM)
# ------------------------------------
st.header("Mythic Lineages — Genealogy Tree")

tree_labels = [
    "Chaos","Gaia","Uranus",
    "Titans","Olympians","Heroes"
]
tree_parents = [
    "", "Chaos", "Chaos",
    "Gaia","Titans","Olympians"
]

fig = go.Figure(go.Treemap(
    labels=tree_labels,
    parents=tree_parents,
    branchvalues="total"
))
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------
# INTERACTIVE ART ZONE
# ------------------------------------
st.header("Interactive Art Zone")

prompt = st.text_input("Describe a scene or symbol:")
if st.button("Identify Myth"):
    st.write(ai_answer(client, f"Identify myth: {prompt}"))

archetype_q = st.text_area("Write freely about yourself:")
if st.button("Find my Archetype"):
    st.write(ai_answer(client, f"Which Greek myth archetype fits this personality: {archetype_q}"))
