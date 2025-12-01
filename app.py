elif page == "Art Data":
    st.header("Art Data — Big Data Analysis")
    st.markdown("""
This page performs **large-scale statistical analysis** of artworks related to a selected Greek mythological figure.
We fetch real MET museum data → clean → visualize across 8 dimensions.
""")

    # Pick figure
    figure_for_analysis = st.selectbox("Choose a figure to analyze:", MYTH_LIST, key="analysis_figure")
    aliases = generate_aliases(figure_for_analysis)
    max_results = st.slider("Max MET search results per alias", 50, 800, 300, 50)

    if st.button("Fetch dataset & analyze", key="start_analysis"):
        # 1) gather IDs
        all_ids = []
        prog = st.progress(0)
        for i, a in enumerate(aliases):
            ids = met_search_ids(a, max_results=max_results)
            for oid in ids:
                if oid not in all_ids:
                    all_ids.append(oid)
            prog.progress(int((i + 1) / len(aliases) * 100))
        prog.empty()
        st.success(f"Found {len(all_ids)} candidate works. Fetching metadata...")

        # 2) build dataset
        metas = []
        prog = st.progress(0)
        total = max(1, len(all_ids))
        for i, oid in enumerate(all_ids):
            m = met_get_object_cached(oid)
            if m:
                metas.append(m)
            if i % 10 == 0:
                prog.progress(int((i + 1) / total * 100))
        prog.empty()
        st.success(f"Dataset built: {len(metas)} records.")

        st.session_state["analysis_dataset"] = metas

    dataset = st.session_state.get("analysis_dataset", None)

    if not dataset:
        st.info("Dataset empty. Click 'Fetch dataset & analyze' above.")
    else:
        st.subheader("Statistical Results")
        stats = extract_bigdata_stats(dataset)

        # ---- 1. Timeline ----
        st.markdown("### 1. Timeline — Artwork Dates (objectBeginDate)")
        years = stats['years']
        if years:
            fig = px.histogram(x=years, nbins=40, labels={'x': 'Year', 'y': 'Count'})
            fig.update_layout(title="Artwork Timeline", margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No year data available.")

        # ---- 2. Medium ----
        st.markdown("### 2. Medium / Material Distribution")
        mc = stats['mediums']
        if mc:
            top = mc.most_common(20)
            fig2 = px.bar(
                x=[v for _, v in top],
                y=[k.title() for k, _ in top],
                orientation='h',
                labels={'x': 'Count', 'y': 'Medium'},
                title="Top 20 Media"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No medium data.")

        # ---- 3. Geography ----
        st.markdown("### 3. Geography / Culture")
        cc = stats['cultures']
        if cc:
            top = cc.most_common(20)
            fig3 = px.bar(
                x=[v for _, v in top],
                y=[k for k, _ in top],
                orientation='h',
                labels={'x': 'Count', 'y': 'Culture'},
                title="Top 20 Cultures"
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No culture data.")

        # ---- 4. Classification ----
        st.markdown("### 4. Classification")
        cl = stats['classifications']
        if cl:
            top = cl.most_common(20)
            fig4 = px.bar(
                x=[v for _, v in top],
                y=[k for k, _ in top],
                orientation='h',
                title="Top 20 Classifications"
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No classification data.")

        # ---- 5. Tags ----
        st.markdown("### 5. Tags / Themes")
        tags = stats['tags']
        if tags:
            top = tags.most_common(20)
            fig5 = px.bar(
                x=[v for _, v in top],
                y=[k.title() for k, _ in top],
                orientation='h',
                title="Top 20 Tags"
            )
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.info("MET tags unavailable for most records.")

        # ---- 6. Greek vs Roman ----
        st.markdown("### 6. Greek vs Roman vs Other (heuristic)")
        gv = stats['greek_vs_roman']
        fig6 = px.pie(values=[gv['greek'], gv['roman'], gv['other']],
                      names=['Greek', 'Roman', 'Other'])
        st.plotly_chart(fig6, use_container_width=True)

        # ---- 7. Vase narratives ----
        st.markdown("### 7. Vase-related objects (raw examples)")
        if stats['vase_examples']:
            for i, ex in enumerate(stats['vase_examples'][:20]):
                st.write(f"{i+1}. {ex}")
        else:
            st.info("No vase-related items.")

        # ---- 8. Acquisition ----
        st.markdown("### 8. Acquisition Timeline (accessionYear)")
        acq = stats['acquisitions']
        if acq:
            fig7 = px.histogram(x=acq, nbins=30, title="Museum Acquisition Years")
            st.plotly_chart(fig7, use_container_width=True)
        else:
            st.info("No accessionYear data.")
elif page == "Interactive Tests":
    st.header("Interactive Tests — Personality & Myth Archetypes")
    st.markdown("""
These personality tests are inspired by **ancient Greek character models**,  
blending **myth symbolism**, **Jungian archetypes**, and **modern psychology**.
""")

    # ---------- Test 1 ----------
    st.subheader("1) Which Greek Deity Are You?")
    q1 = st.radio("In a group you:", ["Lead", "Support", "Create", "Plan"])
    q2 = st.radio("You value most:", ["Power", "Wisdom", "Love", "Joy"])
    q3 = st.radio("Pick a symbol:", ["Thunderbolt", "Owl", "Dove", "Lyre"])

    if st.button("Reveal My Deity"):
        if q2 == "Wisdom" or q3 == "Owl":
            deity = "Athena"
            explanation = """
Athena represents **strategic intelligence, rational clarity, and disciplined creativity**.  
Your choices suggest a mind that values **problem-solving**, balanced judgment, and  
the ability to stay calm in difficult situations. You tend to observe deeply,  
prefer thoughtful action over impulsive reaction, and others rely on your clarity.  
"""
            themes = "Recommended artworks: scenes of councils, strategy, weaving, protective guardianship."
        elif q2 == "Love" or q3 == "Dove":
            deity = "Aphrodite"
            explanation = """
Aphrodite symbolizes **emotional intuition, beauty, harmony, and interpersonal sensitivity**.  
You seek meaning through connection and aesthetics, and you bring warmth  
into spaces around you. Your personality blends softness with surprising inner confidence.  
"""
            themes = "Recommended artworks: gestures of affection, beauty rituals, mythic marriages."
        elif q2 == "Power" or q3 == "Thunderbolt":
            deity = "Zeus"
            explanation = """
Zeus reflects **authority, natural leadership, decisiveness, and protective instincts**.  
You value order, responsibility, and have a commanding presence.  
Your inner world is driven by a sense of destiny and the desire to guide others.  
"""
            themes = "Recommended artworks: thrones, lightning scenes, oaths of kingship."
        else:
            deity = "Apollo"
            explanation = """
Apollo merges **logic with artistry**, symbolizing harmony, prophecy, healing,  
and pursuit of excellence. Your answers point to an elegant balance between  
intellect and creativity. You seek truth, beauty, and inner refinement.  
"""
            themes = "Recommended artworks: lyres, oracles, the Muses, solar imagery."

        st.markdown(f"## You resemble **{deity}**")
        st.write(explanation)
        st.markdown(f"**Art Themes:** {themes}")

    st.markdown("---")

    # ---------- Test 2 ----------
    st.subheader("2) Mythological Personality Archetype (Jungian-inspired)")
    s1 = st.selectbox("Preferred role:", ["Leader", "Supporter", "Strategist", "Creator"])
    s2 = st.selectbox("Main motivation:", ["Duty", "Glory", "Pleasure", "Wisdom"])
    s3 = st.selectbox("Crisis reaction:", ["Plan", "Fight", "Flee", "Negotiate"])

    if st.button("Reveal Archetype"):
        if s2 == "Wisdom":
            arche = "The Sage — Athena / Prometheus Type"
            desc = """
You operate through **insight, patterns, and clarity**.  
Your mind searches for structure even in chaos, and you dislike impulsive decisions.  
Your Jungian shadow is *overthinking*, and your mythic energy resembles  
figures who bring knowledge to humanity.  
"""
        elif s2 == "Glory":
            arche = "The Warrior — Ares / Achilles Type"
            desc = """
You are driven by **challenge, mastery, and the desire to transcend limits**.  
Your strength is courage; your risk is impatience.  
Heroes of this archetype face the world head-on, seeking meaning through action.  
"""
        elif s2 == "Pleasure":
            arche = "The Seeker — Dionysus / Pan Type"
            desc = """
You embody **intuition, emotional richness, and the yearning for freedom**.  
Your world is shaped by sensory experience and authenticity.  
Your shadow is losing boundaries, but your gift is inspiring others to feel alive.  
"""
        else:
            arche = "The Guardian — Zeus / Hera Type"
            desc = """
You value **structure, responsibility, loyalty, and ethical duty**.  
People trust you because you bring stability and order.  
Jungian psychology would say you carry the 'Protector' archetype,  
seeking to maintain harmony in your world.  
"""

        st.markdown(f"## Archetype: **{arche}**")
        st.write(desc)
        st.markdown("### Suggested Art Themes:")
        st.write("- hero narratives\n- ceremonial objects\n- deity iconography\n- ritual scenes\n- symbolic animals / sacred objects")
elif page == "Mythic Lineages":
    st.header("Mythic Lineages — Genealogy Visualization")

    st.markdown("""
A simplified **genealogy of Greek mythology**, grouped into  
**Primordials → Titans → Olympians → Heroes → Creatures**.
""")

    labels = [
        "Greek Mythology",
        "Primordials", "Chaos", "Gaia", "Uranus",
        "Titans", "Cronus", "Rhea", "Oceanus", "Hyperion",
        "Olympians", "Zeus", "Hera", "Poseidon", "Hades",
        "Demeter", "Hestia", "Athena", "Apollo", "Artemis",
        "Ares", "Hermes", "Dionysus", "Aphrodite", "Hephaestus",
        "Heroes", "Heracles", "Perseus", "Theseus", "Odysseus",
        "Achilles", "Jason",
        "Creatures", "Medusa", "Cyclops", "Minotaur", "Sirens"
    ]

    parents = [
        "",
        "Greek Mythology", "Primordials", "Primordials", "Primordials",
        "Greek Mythology", "Titans", "Titans", "Titans", "Titans",
        "Greek Mythology",
        "Olympians","Olympians","Olympians","Olympians",
        "Olympians","Olympians","Olympians","Olympians","Olympians",
        "Olympians","Olympians","Olympians","Olympians","Olympians",
        "Greek Mythology","Heroes","Heroes","Heroes","Heroes",
        "Heroes","Heroes",
        "Greek Mythology","Creatures","Creatures","Creatures","Creatures"
    ]

    category_color = {
        "Greek Mythology": "#7F8C8D",
        "Primordials": "#8E44AD",
        "Titans": "#E67E22",
        "Olympians": "#3498DB",
        "Heroes": "#E74C3C",
        "Creatures": "#27AE60"
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

    fig = px.treemap(
        names=labels,
        parents=parents,
        color=labels,
        color_discrete_map=color_map,
        title="Genealogy of Greek Mythology (Simplified)"
    )
    fig.update_layout(margin=dict(t=40, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
if st.button("← Back to gallery"):
    st.experimental_set_query_params(_page="Greek Figures")
    st.experimental_rerun()
