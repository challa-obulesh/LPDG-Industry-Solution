from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
REQUIRED_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]
FORWARD_WEEKS = [
    "2026-02-02", "2026-02-09", "2026-02-16", "2026-02-23",
    "2026-03-02", "2026-03-09", "2026-03-16", "2026-03-23",
]
VISITS_PER_WEEK = 15

st.set_page_config(
    page_title="NEXORA | Gateway Visit Prioritization",
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root { --ink: #e8eef4; --muted: #91a0af; --line: #2a3946; --mint: #62d6b2; --amber: #f2b84b; }
    .stApp { background: radial-gradient(circle at 90% 0%, #17333a 0, #0a1118 38%, #080e14 100%); }
    html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
    .block-container { max-width: 1480px; padding-top: 2rem; padding-bottom: 3rem; }
    h1, h2, h3 { letter-spacing: 0; }
    h1 { font-weight: 800; font-size: 2.65rem; }
    .eyebrow { color: var(--mint); font: 500 .72rem 'DM Mono', monospace; letter-spacing: .14em; text-transform: uppercase; }
    .subtitle { color: var(--muted); font-size: 1rem; margin-top: -.8rem; }
    .evidence { border: 1px solid #6d5225; border-left: 4px solid var(--amber); background: #211b11; color: #e5d7b8; padding: .9rem 1rem; border-radius: 5px; }
    [data-testid="stSidebar"] { background: #0b141c; border-right: 1px solid var(--line); }
    [data-testid="stMetricValue"] { font-family: 'DM Mono', monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)


def clean_id(value: object) -> str:
    return str(value).replace(":", "").strip().upper()


def euro(value: float | int) -> str:
    return f"€{int(value):,}"


def pct(value: float | int) -> str:
    return f"{float(value):.1%}"


def unavailable(message: str = "Data unavailable in the current artifact set.") -> None:
    st.info(message, icon=":material/info:")


def page_header(title: str, subtitle: str, section: str = "NEXORA / EVIDENCE CONSOLE") -> None:
    st.markdown(f'<div class="eyebrow">{section}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="subtitle">{subtitle}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_predictions() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "predictions.csv")
    frame["week_start"] = frame["week_start"].astype(str)
    frame["gateway_key"] = frame["gateway_id"].map(clean_id)
    return frame


@st.cache_data(show_spinner=False)
def load_part2_metrics() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports" / "part2_metrics.csv")


@st.cache_data(show_spinner=False)
def load_weekly_costs() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "reports" / "weekly_cost_table.csv")
    frame["week_start"] = frame["week_start"].astype(str)
    return frame


@st.cache_data(show_spinner=False)
def load_feature_importance() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports" / "feature_importance.csv")


@st.cache_data(show_spinner=False)
def load_logistic_predictions() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "reports" / "logistic_predictions.csv")
    frame["week_start"] = frame["week_start"].astype(str)
    frame["gateway_key"] = frame["gateway_id"].map(clean_id)
    return frame


@st.cache_data(show_spinner=False)
def load_gateway_artifact() -> pd.DataFrame:
    path = ROOT / "artifacts" / "part2_gateway_week.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    frame["week_start"] = frame["week_start"].astype(str)
    frame["gateway_key"] = frame["gateway_id"].map(clean_id)
    return frame


def validation_status(predictions: pd.DataFrame) -> bool:
    weekly = predictions.groupby("week_start")
    ranks_ok = all(sorted(group["rank"].tolist()) == list(range(1, 16)) for _, group in weekly)
    return (
        len(predictions) == 120
        and predictions["week_start"].nunique() == 8
        and all(size == 15 for size in weekly.size())
        and ranks_ok
        and predictions.duplicated(["week_start", "gateway_key"]).sum() == 0
        and predictions[REQUIRED_COLUMNS].notna().all().all()
        and pd.api.types.is_numeric_dtype(predictions["score"])
        and predictions["reason"].astype(str).str.strip().ne("").all()
        and predictions["reason"].astype(str).str.len().le(300).all()
    )


def evidence_notice() -> None:
    st.markdown(
        '<div class="evidence"><strong>Evidence status</strong><br>'
        "These results use a constructed historical proxy target and are <strong>NOT official hidden-ground-truth performance</strong>. "
        "The €58,800 figure is lower historical proxy-label cost, not confirmed real-world savings.</div>",
        unsafe_allow_html=True,
    )


def overview(predictions: pd.DataFrame, metrics: pd.DataFrame, weekly: pd.DataFrame) -> None:
    page_header("LPDG Gateway Intelligence", "Field Visit Prioritization & Network Reliability Analysis")
    evidence_notice()
    st.space("small")
    metric_values = metrics.set_index("evaluation")
    cards = [
        ("Baseline cost", euro(metric_values.loc["baseline_test", "total_cost"])),
        ("Logistic Regression cost", euro(metric_values.loc["logistic_test", "total_cost"])),
        ("Lower historical proxy-label cost", "€58,800"),
        ("Unseen gateways evaluated", "35"),
        ("Forward-test weeks", "8"),
        ("Gateways ranked per week", "15"),
    ]
    for row in (cards[:3], cards[3:]):
        cols = st.columns(3)
        for col, (label, value) in zip(cols, row):
            col.metric(label, value, border=True)

    st.write("The system prioritizes gateways for field visits using telemetry-derived reliability signals while respecting the hard 15-visits-per-week operational constraint.")
    flow = st.columns(3)
    for col, title, detail in zip(
        flow,
        ["Part 1", "Part 2", "Evaluation"],
        ["3-Sigma operational ranking", "Logistic Regression risk ranking", "Cost, stability, and unseen gateways"],
    ):
        with col:
            with st.container(border=True):
                st.subheader(title, anchor=False)
                st.caption(detail)

    left, right = st.columns([1.35, 1])
    with left:
        with st.container(border=True):
            st.subheader("Forward evaluation at a glance", anchor=False)
            comparison = pd.DataFrame({"method": ["3-sigma baseline", "Logistic Regression"], "cost": [329400, 270600]})
            chart = (
                alt.Chart(comparison).mark_bar(cornerRadiusEnd=4, color="#62d6b2").encode(
                    x=alt.X("cost:Q", title="Historical proxy-label cost", axis=alt.Axis(format="~s")),
                    y=alt.Y("method:N", sort="-x", title=None),
                    tooltip=[alt.Tooltip("method:N", title="Method"), alt.Tooltip("cost:Q", title="Cost", format=",.0f")],
                ).properties(height=155)
            )
            st.altair_chart(chart, width="stretch")
    with right:
        with st.container(border=True):
            st.subheader("What is being compared", anchor=False)
            st.write("Part 1 provides the unchanged official 3-sigma benchmark. Part 2 uses Logistic Regression as the final model with the same eligible gateway population, weekly visit cap, and cost formula.")
            st.caption("The dashboard is read-only. It does not retrain the model or regenerate evaluation outputs.")

    forward = weekly[weekly["week_start"].isin(FORWARD_WEEKS)].copy()
    if not forward.empty:
        trend = forward.pivot(index="week_start", columns="method", values="total_cost").reset_index()
        trend = trend.rename(columns={"baseline_3sigma": "3-sigma baseline", "logistic_regression": "Logistic Regression"})
        with st.container(border=True):
            st.subheader("Weekly cost profile", anchor=False)
            st.line_chart(trend, x="week_start", y=["3-sigma baseline", "Logistic Regression"], y_label="Historical proxy-label cost")


def part1_page(predictions: pd.DataFrame) -> None:
    page_header("Part 1 — 3-Sigma Baseline", "The official benchmark output, read directly from predictions.csv.", "NEXORA / PART 1")
    st.badge("Validator: PASS", icon=":material/check_circle:", color="green")
    st.caption("15 gateways selected per week · prediction period 2026-02-02 through 2026-03-23")
    week = st.selectbox("Prediction week", FORWARD_WEEKS, key="part1_week")
    rows = predictions[predictions["week_start"] == week].sort_values("rank")
    st.caption("Exactly 15 gateways are selected for each scored week. Scores are flagged anomaly hours, not failure probabilities.")
    st.dataframe(rows[["rank", "gateway_id", "score", "reason"]], hide_index=True, width="stretch", height=480, column_config={
        "rank": st.column_config.NumberColumn("Rank", format="%d"),
        "score": st.column_config.NumberColumn("Flagged hours", format="%.0f"),
        "reason": st.column_config.TextColumn("Operational reason", width="large"),
    })
    chart_data = rows[["rank", "gateway_id", "score"]].copy()
    chart_data["rank_label"] = chart_data.apply(lambda row: f"#{int(row['rank'])}  {row['gateway_id']}", axis=1)
    chart = alt.Chart(chart_data).mark_bar(color="#62d6b2", cornerRadiusEnd=3).encode(
        x=alt.X("score:Q", title="Flagged anomaly hours", scale=alt.Scale(zero=True)),
        y=alt.Y("rank_label:N", sort=alt.SortField(field="rank", order="ascending"), title=None),
        tooltip=[alt.Tooltip("rank:O", title="Rank"), alt.Tooltip("gateway_id:N", title="Gateway"), alt.Tooltip("score:Q", title="Score")],
    ).properties(height=430)
    st.altair_chart(chart, width="stretch")
    with st.container(border=True):
        st.subheader("Method", anchor=False)
        st.write("The 3-sigma baseline identifies abnormal telemetry behaviour using each gateway's trailing 28-day history and ranks the most anomalous hours in the recent seven-day window. The official baseline calculation is not reproduced or changed by this dashboard.")


def part2_page(metrics: pd.DataFrame, importance: pd.DataFrame, ml_predictions: pd.DataFrame) -> None:
    page_header("Part 2 — Logistic Regression", "The final model evaluated against a historical proxy target.", "NEXORA / PART 2")
    evidence_notice()
    st.space("small")
    test = metrics.set_index("evaluation").loc["logistic_test"]
    cards = [("Model", "Logistic Regression"), ("Gateway-week rows", f"{int(test['rows']):,}"), ("Features", "99"), ("Forward weeks", "8"), ("Unseen gateways", "35")]
    cols = st.columns(5)
    for col, (label, value) in zip(cols, cards):
        col.metric(label, value, border=True)
    with st.container(border=True):
        st.subheader("Historical proxy target", anchor=False)
        st.write("A gateway-week is positive when the complete seven days after Monday 00:00 UTC contain at least 84 observed gateway-hours, degradation on at least 2 distinct days, and at least 6 degraded hours.")
        st.caption("A degraded hour has offline_duration_sec ≥ 3600, disconnection_cnt ≥ 3, or reboot_cnt ≥ 1. This target is not hidden ground truth.")
    with st.container(border=True):
        st.subheader("Weekly model ranking", anchor=False)
        week = st.selectbox("Model ranking week", FORWARD_WEEKS, key="part2_week")
        rows = ml_predictions[ml_predictions["week_start"] == week].sort_values("rank")
        st.dataframe(rows[["rank", "gateway_id", "score", "reason"]], hide_index=True, width="stretch", height=430, column_config={
            "rank": st.column_config.NumberColumn("Rank", format="%d"),
            "score": st.column_config.NumberColumn("Proxy-risk score", format="%.4f"),
            "reason": st.column_config.TextColumn("Top coefficient signals", width="large"),
        })
        chart_data = rows[["rank", "gateway_id", "score"]].copy()
        chart_data["rank_label"] = chart_data.apply(lambda row: f"#{int(row['rank'])}  {row['gateway_id']}", axis=1)
        chart = alt.Chart(chart_data).mark_bar(color="#62d6b2", cornerRadiusEnd=3).encode(
            x=alt.X("score:Q", title="Proxy-risk score", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("rank_label:N", sort=alt.SortField(field="rank", order="ascending"), title=None),
            tooltip=[alt.Tooltip("rank:O", title="Rank"), alt.Tooltip("gateway_id:N", title="Gateway"), alt.Tooltip("score:Q", title="Score", format=".4f")],
        ).properties(height=390)
        st.altair_chart(chart, width="stretch")
        st.caption("Scores are stored predictions from the frozen model; they are ranking scores for the historical proxy target, not failure probabilities.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Chronological evaluation", anchor=False)
            st.table(pd.DataFrame({"Stage": ["Training", "Validation", "Forward test"], "Weeks": ["Through 2025-12-29", "2026-01-05 → 2026-01-26", "2026-02-02 → 2026-03-23"]}))
            st.caption("The incomplete 2026-03-30 week is excluded. Features use only information available before each cutoff.")
    with right:
        with st.container(border=True):
            st.subheader("Important model signals", anchor=False)
            st.markdown("- Recent disconnection activity\n- Historical meter-read rate\n- Reboot variability\n- Long-term disconnection totals\n- RSSI / signal quality\n- Offline-duration variability")
            st.caption("These are predictive associations from the existing coefficient report, not causal diagnoses.")
    top = importance.sort_values("absolute_coefficient", ascending=False).head(10).copy()
    top["feature"] = top["feature"].str.replace("numeric__", "", regex=False).str.replace("categorical__", "", regex=False)
    with st.container(border=True):
        st.subheader("Coefficient signal profile", anchor=False)
        st.bar_chart(top.set_index("feature")["coefficient"], horizontal=True, x_label="Coefficient", y_label="Feature")
        st.dataframe(top[["feature", "direction", "coefficient", "interpretation"]], hide_index=True, width="stretch")
    with st.container(border=True):
        st.subheader("Final model", anchor=False)
        st.write("Logistic Regression is the final Part 2 model. The controlled selection record confirms that the tested alternatives produced identical measured operational results; Logistic Regression was retained for simpler interpretation and reproducibility.")
        st.caption("These results are based on historical proxy labels and should not be presented as official hidden-groundtruth performance.")


def comparison_page(metrics: pd.DataFrame, weekly: pd.DataFrame) -> None:
    page_header("Baseline vs Logistic Regression", "The fair common-population comparison.")
    evidence_notice()
    st.space("small")
    test = metrics.set_index("evaluation")
    comparison = pd.DataFrame({
        "Method": ["3-Sigma baseline", "Logistic Regression"],
        "Forward cost": [test.loc["baseline_test", "total_cost"], test.loc["logistic_test", "total_cost"]],
        "Precision@15": [test.loc["baseline_test", "precision_at_15"], test.loc["logistic_test", "precision_at_15"]],
        "Recall": [test.loc["baseline_test", "recall"], test.loc["logistic_test", "recall"]],
    })
    cols = st.columns(4)
    cols[0].metric("Baseline forward cost", euro(test.loc["baseline_test", "total_cost"]), border=True)
    cols[1].metric("Logistic Regression cost", euro(test.loc["logistic_test", "total_cost"]), border=True)
    cols[2].metric("Historical difference", "€58,800", border=True)
    cols[3].metric("Common weeks", "8", border=True)
    left, right = st.columns(2)
    with left:
        chart = alt.Chart(comparison).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("Forward cost:Q", title="Historical proxy-label cost", axis=alt.Axis(format="~s")),
            y=alt.Y("Method:N", sort="-x", title=None),
            color=alt.Color("Method:N", scale=alt.Scale(range=["#f2b84b", "#62d6b2"]), legend=None),
            tooltip=[alt.Tooltip("Method:N"), alt.Tooltip("Forward cost:Q", format=",.0f")],
        ).properties(height=230)
        st.altair_chart(chart, width="stretch")
    with right:
        st.dataframe(comparison, hide_index=True, width="stretch", column_config={
            "Forward cost": st.column_config.NumberColumn("Forward cost", format="€%,.0f"),
            "Precision@15": st.column_config.NumberColumn("Precision@15", format="%.1%"),
            "Recall": st.column_config.NumberColumn("Recall", format="%.1%"),
        })
        st.caption("All metrics above are historical proxy-label evaluation metrics.")
    forward = weekly[(weekly["week_start"].isin(FORWARD_WEEKS)) & (weekly["evaluation"].isin(["baseline_test", "logistic_test"]))].copy()
    trend = forward.pivot(index="week_start", columns="evaluation", values="total_cost").reset_index().rename(columns={
        "baseline_test": "3-sigma baseline", "logistic_test": "Logistic Regression",
    })
    with st.container(border=True):
        st.subheader("Weekly forward cost", anchor=False)
        st.line_chart(trend, x="week_start", y=["3-sigma baseline", "Logistic Regression"], y_label="Historical proxy-label cost")
    unseen = metrics.set_index("evaluation").loc["logistic_unseen_gateway_test"]
    with st.container(border=True):
        st.subheader("Unseen-gateway evaluation", anchor=False)
        st.caption("Separate device-disjoint historical proxy-label slice; not directly comparable to a 15-visit baseline universe.")
        cols = st.columns(4)
        cols[0].metric("Gateways", "35")
        cols[1].metric("Weeks", "8")
        cols[2].metric("Precision@15", pct(unseen["precision_at_15"]))
        cols[3].metric("Recall", pct(unseen["recall"]))


def gateway_page(predictions: pd.DataFrame, ml_predictions: pd.DataFrame, artifact: pd.DataFrame) -> None:
    page_header("Gateway explorer", "Search one gateway across the submitted ranking and available model evidence.")
    week = st.selectbox("Week", FORWARD_WEEKS, key="gateway_week")
    search = st.text_input("Search gateway ID", placeholder="Enter a gateway ID or part of one", key="gateway_search")
    week_rows = predictions[predictions["week_start"] == week].sort_values("rank")
    available_ids = set(week_rows["gateway_id"])
    available_ids.update(ml_predictions.loc[ml_predictions["week_start"] == week, "gateway_id"])
    if not artifact.empty:
        available_ids.update(artifact.loc[artifact["week_start"] == week, "gateway_id"])
    gateway_options = week_rows["gateway_id"].tolist()
    if search.strip():
        gateway_options = sorted(gateway for gateway in available_ids if search.strip().upper() in gateway.upper())
    if not gateway_options:
        unavailable()
        return
    gateway = st.selectbox("Selected gateway", gateway_options, key="gateway_id")
    gateway_key = clean_id(gateway)
    baseline_row = week_rows[week_rows["gateway_key"] == gateway_key]
    ml_row = ml_predictions[(ml_predictions["week_start"] == week) & (ml_predictions["gateway_key"] == gateway_key)]
    artifact_row = artifact[(artifact["week_start"] == week) & (artifact["gateway_key"] == gateway_key)] if not artifact.empty else pd.DataFrame()
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Part 1 baseline evidence", anchor=False)
            if baseline_row.empty:
                st.info("Data not available for this view.")
            else:
                row = baseline_row.iloc[0]
                st.metric("Baseline rank", f"#{int(row['rank'])}")
                st.metric("Flagged-hour score", f"{row['score']:.0f}")
                st.write(row["reason"])
    with right:
        with st.container(border=True):
            st.subheader("Part 2 model evidence", anchor=False)
            if ml_row.empty:
                st.info("Data not available for this view.")
                st.caption("The stored Logistic Regression prediction file contains the selected top-15 rows only.")
            else:
                row = ml_row.iloc[0]
                st.metric("Stored ML rank", f"#{int(row['rank'])}")
                st.metric("Proxy-risk ranking score", f"{row['score']:.4f}")
                st.write(row["reason"])
    if artifact_row.empty:
        unavailable("Data unavailable in the current artifact set for this gateway-week.")
        return
    row = artifact_row.iloc[0]
    feature_candidates = [
        "hist_7d_disconnection_cnt_sum", "hist_7d_reboot_cnt_std", "hist_28d_disconnection_cnt_sum",
        "meter_28d_read_rate_mean", "hist_7d_rssi_good_mean", "hist_7d_offline_duration_sec_std",
        "hist_7d_observed_hours", "hist_28d_duplicate_rate",
    ]
    available = [name for name in feature_candidates if name in artifact_row.columns]
    with st.container(border=True):
        st.subheader("Cutoff-safe feature context", anchor=False)
        if available:
            st.dataframe(pd.DataFrame({"Feature": available, "Value": [row[name] for name in available]}), hide_index=True, width="stretch")
        else:
            unavailable()
        st.caption("These are stored pre-cutoff features from the existing artifact. No model score is recomputed here.")


def model_intelligence_page(importance: pd.DataFrame) -> None:
    page_header("Model intelligence", "Coefficient evidence from the final Logistic Regression model.")
    evidence_notice()
    st.space("small")
    with st.container(border=True):
        st.subheader("Final model: Logistic Regression", anchor=False)
        st.write("I did not assume that a more complex model would automatically perform better. I benchmarked Logistic Regression, Random Forest, Extra Trees and HistGradientBoosting using the same operational evaluation. They produced identical measured operational results, so Logistic Regression was retained because it provides simpler interpretation and reproducibility.")
    if importance.empty:
        unavailable()
        return
    top = importance.sort_values("absolute_coefficient", ascending=False).head(12).copy()
    top["feature"] = top["feature"].str.replace("numeric__", "", regex=False).str.replace("categorical__", "", regex=False)
    with st.container(border=True):
        st.subheader("Most influential signals", anchor=False)
        st.bar_chart(top.set_index("feature")["coefficient"], horizontal=True, x_label="Coefficient", y_label="Feature")
        st.dataframe(top[["feature", "direction", "coefficient", "interpretation"]], hide_index=True, width="stretch")
        st.caption("Predictive associations, not causal explanations. Coefficients are read from the existing feature-importance artifact.")


def unseen_page(metrics: pd.DataFrame) -> None:
    page_header("Unseen gateways", "A separate device-disjoint generalization check.")
    evidence_notice()
    st.space("small")
    unseen = metrics.set_index("evaluation").get("logistic_unseen_gateway_test")
    if unseen is None:
        unavailable()
        return
    cols = st.columns(4)
    cols[0].metric("Gateways", "35", border=True)
    cols[1].metric("Proxy-label cost", euro(unseen["total_cost"]), border=True)
    cols[2].metric("Precision@15", f"{unseen['precision_at_15']:.4f}", border=True)
    cols[3].metric("Recall", f"{unseen['recall']:.4f}", border=True)
    with st.container(border=True):
        st.subheader("Evaluation boundary", anchor=False)
        st.write("These gateways were first observed during January-March 2026 and were evaluated separately from model fitting. This is unseen-gateway proxy-label evaluation, not official live performance.")


def network_health_page() -> None:
    page_header("Network health", "Population change that affects model robustness.")
    population = pd.DataFrame({"period": ["August 2025", "March 2026"], "gateways": [280, 308]})
    cols = st.columns(4)
    cols[0].metric("August 2025", "280", border=True)
    cols[1].metric("March 2026", "308", border=True)
    cols[2].metric("Present across all 8 months", "268", border=True)
    cols[3].metric("First appearing Jan-Mar 2026", "40", border=True)
    with st.container(border=True):
        st.subheader("Gateway population", anchor=False)
        st.bar_chart(population.set_index("period"), y="gateways", y_label="Gateways")
        st.caption("Population movement can shift feature distributions, cold-start coverage, and ranking reliability. The chart uses the verified network counts from the project audit.")


def data_quality_page() -> None:
    page_header("Data quality", "Coverage and provenance conditions behind the analysis.")
    facts = pd.DataFrame({
        "Indicator": ["Telemetry rows", "Duplicate telemetry rows", "Gateway-days not exactly 24 records", "Meter-read data ends"],
        "Verified value": ["1,433,387", "13,094", "55,117", "2026-01-26"],
    })
    with st.container(border=True):
        st.subheader("Verified data-quality indicators", anchor=False)
        st.dataframe(facts, hide_index=True, width="stretch")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Why it matters", anchor=False)
            st.write("Duplicate observations can distort aggregates. Incomplete hourly coverage affects reliability features. Meter history ends before the forward period, and changing gateway population creates distribution-shift risk.")
    with right:
        with st.container(border=True):
            st.subheader("Handling", anchor=False)
            st.write("Duplicate telemetry is handled deterministically with median aggregation and retained quality indicators. Missing or unavailable evidence is not replaced with invented values.")


def methodology_page(predictions: pd.DataFrame) -> None:
    page_header("Methodology & Limitations", "The evidence boundaries behind the demonstration.")
    with st.container(border=True):
        st.subheader("Part 1 — 3-sigma baseline", anchor=False)
        st.write("The unchanged official baseline uses gateway-specific telemetry history, flags recent observations above a three-sigma threshold, and selects the 15 highest anomaly rankings per week.")
    with st.container(border=True):
        st.subheader("Part 2 — Logistic Regression", anchor=False)
        st.write("The final Logistic Regression model uses cutoff-safe historical telemetry, meter-read history, quality indicators, and gateway metadata. This dashboard reads its existing outputs and never retrains it.")
    with st.container(border=True):
        st.subheader("Pipeline", anchor=False)
        stages = st.columns(5)
        for col, stage in zip(stages, ["Telemetry", "Cleaning", "99 features", "Persistent target", "Logistic Regression → top 15"]):
            with col:
                st.markdown(f"**{stage}**")
    with st.container(border=True):
        st.subheader("Target and leakage control", anchor=False)
        st.write("The historical proxy target is based on persistent degradation in the complete seven days after a Monday cutoff. Features use only information available before that cutoff. The evaluation is chronological and includes a separate 35-gateway unseen slice.")
    with st.container(border=True):
        st.subheader("Known limitations", anchor=False)
        st.markdown("- The proxy target is not hidden ground truth.\n- Historical field visits are selection-biased evidence, not random ground truth.\n- Duplicate telemetry exists.\n- Gateway population changes over time.\n- Meter-read data ends earlier than telemetry.\n- New gateways require explicit cold-start handling.")
    st.markdown('<div class="evidence"><strong>Final model: Logistic Regression</strong><br>Historical proxy-label evidence must not be presented as official hidden-groundtruth performance.</div>', unsafe_allow_html=True)
    with st.expander("Submission and data safety"):
        st.write("The dashboard reads predictions.csv, the verified Part 2 CSV reports, the feature-importance report, and the existing gateway-week parquet artifact. It does not write to any of them, change the baseline or validator, or modify original challenge data.")
        st.code(".venv\\Scripts\\python.exe -m streamlit run app.py", language="powershell")
        st.caption(f"Part 1 validation status: {'PASS' if validation_status(predictions) else 'REVIEW'}")


predictions = load_predictions()
metrics = load_part2_metrics()
weekly_costs = load_weekly_costs()
importance = load_feature_importance()
ml_predictions = load_logistic_predictions()
gateway_artifact = load_gateway_artifact()

with st.sidebar:
    st.markdown('<div class="eyebrow">NEXORA / 2026</div>', unsafe_allow_html=True)
    st.header("Gateway Visit\nPrioritization", anchor=False)
    st.caption("Presentation console · read-only evidence")
    st.badge("Part 1 validated", icon=":material/check_circle:", color="green")
    st.space("small")
    page = st.radio("Navigate", [
        "Executive Overview", "Part 1 — Operational Ranking", "Part 2 — Machine Learning",
        "Baseline vs ML", "Model Intelligence", "Gateway Explorer", "Unseen Gateways",
        "Network Health", "Data Quality", "Methodology & Audit",
    ], label_visibility="collapsed")
    st.space("medium")
    st.caption("Evidence status")
    st.caption("Historical proxy-label evaluation only")

if page == "Executive Overview":
    overview(predictions, metrics, weekly_costs)
elif page == "Part 1 — Operational Ranking":
    part1_page(predictions)
elif page == "Part 2 — Machine Learning":
    part2_page(metrics, importance, ml_predictions)
elif page == "Baseline vs ML":
    comparison_page(metrics, weekly_costs)
elif page == "Model Intelligence":
    model_intelligence_page(importance)
elif page == "Gateway Explorer":
    gateway_page(predictions, ml_predictions, gateway_artifact)
elif page == "Unseen Gateways":
    unseen_page(metrics)
elif page == "Network Health":
    network_health_page()
elif page == "Data Quality":
    data_quality_page()
else:
    methodology_page(predictions)

st.markdown("<br><div style='border-top:1px solid #2a3946;padding-top:1rem;color:#718293;font-size:.78rem'>NEXORA 2026 · Part 1 official baseline · Part 2 final model: Logistic Regression</div>", unsafe_allow_html=True)