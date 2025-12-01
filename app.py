import streamlit as st
import plotly.express as px

# 你的 import ……（略）
# 你的函数 ……（略）

# ---------------- Navigation ----------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to:",
    [
        "Home",
        "Greek Figures",
        "Art Data",
        "Interactive Tests",
        "Mythic Lineages"
    ]
)

# ---------------- HOME ----------------
if page == "Home":
    st.title("🏛️ AI Museum Curator — Greek Mythology Edition")
    st.write("Welcome to the home page.")
    # ……你的 home 内容（略）


# ---------------- GREEK FIGURES ----------------
elif page == "Greek Figures":
    st.title("Greek Figures")
    # ……你的 Greek Figures 内容（略）


# ---------------- ART DATA (你的整段要放这里) ----------------
elif page == "Art Data":
    st.header("Art Data — Big Data Analysis")
    st.markdown("""
This page performs **large-scale statistical analysis** of artworks related to a selected Greek mythological figure.
We fetch real MET museum data → clean → visualize across 8 dimensions.
""")

    # ------------ 你的整段从这里开始（不要改缩进） ------------
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

    # ------------ 你的整段到这里结束 ------------


# ---------------- INTERACTIVE TESTS ----------------
elif page == "Interactive Tests":
    # 你给的内容完整贴这里
    ...
    

# ---------------- MYTHIC LINEAGES ----------------
elif page == "Mythic Lineages":
    # 你给的内容完整贴这里
    ...
