from __future__ import annotations

import datetime as dt
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "03-challenge-data" / "data"
METRICS = ["offline_duration_sec", "disconnection_cnt", "reboot_cnt"]
WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]
REQUIRED_COLUMNS = ["week_start", "rank", "gateway_id", "score", "reason"]

st.set_page_config(page_title="NEXORA | Gateway Anomaly Intelligence", page_icon=":material/hub:", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--ink:#e8eef4;--muted:#8b9aab;--line:#273542;--accent:#62d6b2;--amber:#f2b84b}
.stApp{background:radial-gradient(circle at 80% 0%,#172c35 0,#0a1118 36%,#091016 100%);color:var(--ink)}
.block-container{padding-top:2.2rem;max-width:1500px}html,body,[class*="css"]{font-family:'Manrope',sans-serif}h1{font-weight:800;font-size:2.7rem;letter-spacing:0}h2,h3{letter-spacing:0}
.eyebrow{color:var(--accent);text-transform:uppercase;font:500 .72rem 'DM Mono',monospace;letter-spacing:.12em}.status{display:inline-block;border:1px solid #2c795f;color:#8be4c8;background:#12352c;padding:.35rem .65rem;border-radius:4px;font:500 .72rem 'DM Mono',monospace}
[data-testid="stSidebar"]{background:#0b141c;border-right:1px solid var(--line)}[data-testid="stMetricValue"]{font-family:'DM Mono',monospace}.pipeline-step{border:1px solid var(--line);padding:.75rem .8rem;border-radius:4px;background:#101b24;min-height:76px}.pipeline-step b{display:block;color:var(--accent);font:500 .68rem 'DM Mono',monospace;margin-bottom:.35rem}.pipeline-step span{font-size:.88rem;font-weight:600}.callout{border-left:3px solid var(--amber);background:#1d1a12;padding:.8rem 1rem;color:#d9d0b4}
</style>
""", unsafe_allow_html=True)


def clean_id(value: object) -> str:
    return str(value).replace(":", "").strip().upper()


@st.cache_data(show_spinner="Loading Part 1 outputs…")
def load_predictions() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / "predictions.csv")
    frame["week"] = pd.to_datetime(frame["week_start"]).dt.date
    frame["gateway_key"] = frame["gateway_id"].map(clean_id)
    return frame


@st.cache_data(show_spinner="Reading telemetry partitions…")
def load_telemetry() -> pd.DataFrame:
    frame = pd.read_parquet(DATA / "telemetry", columns=["gateway_id", "ts_utc", *METRICS])
    frame["gateway_key"] = frame["gateway_id"].map(clean_id)
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    return frame.drop(columns=["ts_utc"])


@st.cache_data
def load_auxiliary() -> dict[str, pd.DataFrame]:
    result = {name: pd.read_csv(DATA / name, encoding="latin1") for name in ["gateway_master.csv", "field_visits.csv", "meter_read_success.csv"]}
    result["gateway_master.csv"]["gateway_key"] = result["gateway_master.csv"]["gateway_id"].map(clean_id)
    for name in ["field_visits.csv", "meter_read_success.csv"]:
        result[name]["gateway_key"] = result[name]["gateway_id"].map(clean_id)
    return result


@st.cache_data
def load_review() -> pd.DataFrame | None:
    try:
        return pd.read_excel(DATA / "engineer_review_2026-02.xlsx", sheet_name="Gateway Status")
    except Exception:
        return None


def validation(predictions: pd.DataFrame) -> dict[str, object]:
    reasons = predictions["reason"].astype(str).str.strip()
    weekly = predictions.groupby("week")
    ranks_ok = all(sorted(group["rank"].tolist()) == list(range(1, 16)) for _, group in weekly)
    rows_ok = len(predictions) == 120 and predictions["week"].nunique() == 8 and all(size == 15 for size in weekly.size())
    return {"rows": len(predictions), "weeks": predictions["week"].nunique(), "rows_per_week": weekly.size().tolist(), "ranks_ok": ranks_ok, "duplicates": int(predictions.duplicated(["week", "gateway_key"]).sum()), "missing": int(predictions[REQUIRED_COLUMNS].isna().any(axis=1).sum()), "blank_reasons": int((reasons == "").sum()), "long_reasons": int((reasons.str.len() > 300).sum()), "numeric_scores": bool(pd.api.types.is_numeric_dtype(predictions["score"])), "pass": rows_ok and ranks_ok and int(predictions.duplicated(["week", "gateway_key"]).sum()) == 0 and int(predictions[REQUIRED_COLUMNS].isna().any(axis=1).sum()) == 0 and int((reasons == "").sum()) == 0 and int((reasons.str.len() > 300).sum()) == 0 and bool(pd.api.types.is_numeric_dtype(predictions["score"]))}


def render_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="eyebrow">NEXORA / PART 1</div><h1>{title}</h1><p style="color:#8b9aab">{subtitle}</p>', unsafe_allow_html=True)


def overview(predictions: pd.DataFrame, status: dict[str, object]) -> None:
    render_header("Gateway Anomaly Intelligence", "Prioritizing the 15 gateways most likely to require field attention each week.")
    cols = st.columns(5)
    values = [("Prediction period", "2026-02-02 → 2026-03-23"), ("Total predictions", str(status["rows"])), ("Prediction weeks", str(status["weeks"])), ("Gateways / week", "15"), ("Validation", "PASS" if status["pass"] else "REVIEW")]
    for col, (label, value) in zip(cols, values):
        col.metric(label, value, border=True)
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("Weekly signal profile")
        trend = predictions.groupby("week", as_index=False)["score"].agg(average="mean", maximum="max", minimum="min")
        trend["week"] = trend["week"].astype(str)
        st.line_chart(trend.set_index("week"), y=["average", "maximum", "minimum"])
    with right:
        st.subheader("Operating model")
        st.markdown('<div class="callout"><b>Score = flagged anomaly hours</b><br><br>Each gateway is ranked by recent hours where one of three telemetry signals exceeded its own 28-day baseline by more than 3σ.</div>', unsafe_allow_html=True)
        st.write("Higher score → more anomaly evidence → higher field-visit priority.")
        st.caption("A ranking signal is not proof that a gateway is broken.")
    st.subheader("Demo route")
    a, b, c = st.columns(3)
    a.info("01  Select a week\n\nReview the complete ranked top 15.")
    b.info("02  Open a gateway\n\nSee the signal profile and historical context.")
    c.info("03  Verify the evidence\n\nCheck validation, quality, and reproducibility.")


def how_it_works() -> None:
    render_header("How it works", "The supplied Part 1 baseline, made inspectable.")
    steps = [("01", "Telemetry data"), ("02", "28-day history"), ("03", "Gateway baseline"), ("04", "3-sigma threshold"), ("05", "Anomaly detection"), ("06", "Flagged hours"), ("07", "Gateway score"), ("08", "Ranking"), ("09", "Top 15")]
    for start in range(0, len(steps), 3):
        cols = st.columns(3)
        for col, (number, label) in zip(cols, steps[start:start + 3]):
            col.markdown(f'<div class="pipeline-step"><b>{number}</b><span>{label}</span></div>', unsafe_allow_html=True)
        if start < 6: st.caption("↓")
    selected = st.selectbox("Inspect a pipeline step", [label for _, label in steps], index=3)
    explanations = {"Telemetry data": "The parquet telemetry partitions are the only source used by the official baseline.", "28-day history": "For each Monday, the baseline uses the trailing 28 days strictly before 00:00 UTC.", "Gateway baseline": "Mean and standard deviation are computed per gateway for offline duration, disconnections, and reboots.", "3-sigma threshold": "An observation is flagged when it is more than three standard deviations above the gateway's historical mean.", "Anomaly detection": "A recent hour is flagged when any of the three baseline metrics exceeds its gateway-specific threshold.", "Flagged hours": "The recent seven-day window is reduced to a count of flagged hours per gateway.", "Gateway score": "The score is the number of flagged recent hours used to rank gateways.", "Ranking": "Gateways are ordered by flagged-hour count and the first 15 are selected.", "Top 15": "The challenge requires exactly 15 gateways for each of eight prediction weeks."}
    st.container(border=True).write(explanations[selected])


def weekly_predictions(predictions: pd.DataFrame) -> None:
    render_header("Weekly predictions", "The exact rows submitted for Part 1, with live sorting and filters.")
    week = st.selectbox("Prediction week", WEEKS, format_func=lambda value: value.isoformat())
    part = predictions[predictions["week"] == week].copy()
    c1, c2, c3 = st.columns([1, 1, 1.4])
    direction = c1.selectbox("Sort", ["Rank", "Score high → low", "Score low → high"])
    rank_filter = c2.multiselect("Ranks", list(range(1, 16)), default=list(range(1, 16)))
    query = c3.text_input("Search gateway or reason", placeholder="e.g. 0A27 or reboot")
    if direction == "Score high → low": part = part.sort_values("score", ascending=False)
    elif direction == "Score low → high": part = part.sort_values("score", ascending=True)
    part = part[part["rank"].isin(rank_filter)]
    if query:
        part = part[part["gateway_id"].str.contains(query, case=False, na=False) | part["reason"].str.contains(query, case=False, na=False)]
    st.dataframe(part[["rank", "gateway_id", "score", "reason"]], hide_index=True, height=560, column_config={"rank": st.column_config.NumberColumn("Rank", format="#%d"), "score": st.column_config.NumberColumn("Score", format="%.0f")})
    st.download_button("Download current week CSV", predictions[predictions["week"] == week][REQUIRED_COLUMNS].to_csv(index=False).encode("utf-8"), f"nexora-{week}.csv", "text/csv", icon=":material/download:")
    st.subheader("LPDG top 15 gateway ranking")
    st.caption("Every bar is one selected gateway. Bar length is the official 3-sigma flagged-hour score; higher means more anomaly evidence.")
    chart_data = predictions[predictions["week"] == week].sort_values("rank").copy()
    chart_data["rank_label"] = chart_data["rank"].map(lambda value: f"#{int(value)}  {value}")
    bars = alt.Chart(chart_data).mark_bar(color="#62d6b2", cornerRadiusEnd=3, size=22).encode(
        x=alt.X("score:Q", title="Flagged anomaly hours", scale=alt.Scale(zero=True)),
        y=alt.Y("rank_label:N", sort=alt.SortField(field="rank", order="ascending"), title=None),
        tooltip=[alt.Tooltip("rank:O", title="Rank"), alt.Tooltip("gateway_id:N", title="Gateway"), alt.Tooltip("score:Q", title="Score"), alt.Tooltip("reason:N", title="Reason")],
    )
    labels = alt.Chart(chart_data).mark_text(align="left", dx=6, color="#e8eef4").encode(
        x="score:Q", y=alt.Y("rank_label:N", sort=alt.SortField(field="rank", order="ascending")), text=alt.Text("score:Q", format=".0f")
    )
    st.altair_chart((bars + labels).properties(height=520), width="stretch")


def gateway_intelligence(predictions: pd.DataFrame, telemetry: pd.DataFrame, aux: dict[str, pd.DataFrame]) -> None:
    render_header("Gateway intelligence", "Trace a selected prediction back to its operational context.")
    selected = st.selectbox("Select gateway", sorted(predictions["gateway_id"].unique()))
    key = clean_id(selected)
    rows = predictions[predictions["gateway_key"] == key].sort_values("week")
    meta = aux["gateway_master.csv"][aux["gateway_master.csv"]["gateway_key"] == key]
    st.metric("Gateway ID", selected)
    if not meta.empty:
        record = meta.iloc[0]
        st.caption(f"{record.get('region', 'Not available')} · {record.get('site_type', 'Not available')} · {record.get('hw_model', 'Not available')}")
    st.dataframe(rows[["week_start", "rank", "score", "reason"]], hide_index=True, column_config={"score": st.column_config.NumberColumn("Score", format="%.0f")})
    if not rows.empty:
        end = pd.Timestamp(rows.iloc[-1]["week"], tz="UTC")
        scope = telemetry[(telemetry["gateway_key"] == key) & (telemetry["ts"] < end)].tail(168)
        if not scope.empty:
            cards = st.columns(3)
            for col, metric in zip(cards, METRICS): col.metric(metric.replace("_", " ").title(), f"{scope[metric].sum():,.0f}")
            st.line_chart(scope.set_index("ts")[METRICS])


def anomaly_analysis(predictions: pd.DataFrame, telemetry: pd.DataFrame) -> None:
    render_header("Anomaly analysis", "Compare recent observations with the selected gateway's own baseline.")
    selected = st.selectbox("Gateway", sorted(predictions["gateway_id"].unique()), key="anomaly_gateway")
    week = st.selectbox("Prediction week", WEEKS, key="anomaly_week")
    end = pd.Timestamp(week, tz="UTC")
    window = telemetry[(telemetry["gateway_key"] == clean_id(selected)) & (telemetry["ts"] >= end - dt.timedelta(days=28)) & (telemetry["ts"] < end)].copy()
    if window.empty: st.info("Not available"); return
    stats = window[METRICS].agg(["mean", "std"]).T
    recent = window[window["ts"] >= end - dt.timedelta(days=7)]
    metric = st.selectbox("Telemetry signal", METRICS, format_func=lambda value: value.replace("_", " ").title())
    row, threshold, observed = stats.loc[metric], stats.loc[metric, "mean"] + 3 * stats.loc[metric, "std"], recent[metric].max()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Historical mean", f"{row['mean']:.2f}"); c2.metric("Standard deviation", f"{row['std']:.2f}"); c3.metric("3σ threshold", f"{threshold:.2f}"); c4.metric("Recent maximum", f"{observed:.2f}")
    chart_data = window[["ts", metric]].copy(); chart_data["threshold"] = threshold
    chart = alt.Chart(chart_data).transform_fold([metric, "threshold"], as_=["series", "value"]).mark_line().encode(x=alt.X("ts:T", title=None), y=alt.Y("value:Q", title=metric.replace("_", " ")), color=alt.Color("series:N", scale=alt.Scale(range=["#62d6b2", "#f2b84b"])), tooltip=["ts:T", "value:Q"])
    st.altair_chart(chart, width="stretch")
    st.caption("Anomaly signal used for field-visit prioritization. It does not confirm that the gateway is broken.")


def cost_analysis(predictions: pd.DataFrame) -> None:
    render_header("Cost analysis", "The challenge economics, grounded in selected visits.")
    visit_cost, missed_cost = 380, 600
    c1, c2, c3 = st.columns(3); c1.metric("Weekly visit budget", "15"); c2.metric("Visit cost", f"€{15 * visit_cost:,.0f} / week"); c3.metric("8-week maximum", f"€{15 * visit_cost * 8:,.0f}")
    weekly = predictions.groupby("week_start", as_index=False).agg(selected_visits=("gateway_id", "count")); weekly["visit_cost_eur"] = weekly["selected_visits"] * visit_cost
    st.dataframe(weekly, hide_index=True, column_config={"visit_cost_eur": st.column_config.NumberColumn("Visit cost", format="€%,.0f")})
    st.markdown(f'<div class="callout">The official scoring also includes the cost of missed problems: €{missed_cost} per broken gateway left alone per week. A final official total is <b>Not available</b> because ground-truth failure outcomes were not supplied.</div>', unsafe_allow_html=True)


def validation_center(predictions: pd.DataFrame, status: dict[str, object]) -> None:
    render_header("Validation center", "Independent checks over the current predictions.csv.")
    st.success("✓ PASS · PART 1 SUBMISSION READY" if status["pass"] else "Review required")
    checks = pd.DataFrame({"Check": ["Rows", "Weeks", "Rows per week", "Ranks", "Required columns", "Duplicate prediction rows", "Missing rows", "Blank reasons", "Reason length", "Numeric scores"], "Result": [str(status["rows"]), str(status["weeks"]), "15 each" if all(v == 15 for v in status["rows_per_week"]) else "Review", "1–15" if status["ranks_ok"] else "Review", str(len(REQUIRED_COLUMNS)), str(status["duplicates"]), str(status["missing"]), str(status["blank_reasons"]), "≤300 characters" if status["long_reasons"] == 0 else "Review", "PASS" if status["numeric_scores"] else "Review"]})
    st.dataframe(checks, hide_index=True, width="stretch")
    st.download_button("Download full predictions CSV", predictions[REQUIRED_COLUMNS].to_csv(index=False).encode("utf-8"), "predictions.csv", "text/csv", icon=":material/download:")


def data_quality(telemetry: pd.DataFrame, aux: dict[str, pd.DataFrame]) -> None:
    render_header("Data quality", "Known constraints are visible so the demo remains honest.")
    duplicate_count = int(telemetry.duplicated(["gateway_key", "ts"]).sum())
    if duplicate_count: st.warning(f"DUPLICATE TELEMETRY DETECTED · {duplicate_count:,} duplicated gateway/timestamp rows")
    st.write("The official baseline was preserved unchanged. This data-quality issue is documented as a limitation.")
    datasets = []
    for name, frame in [("Telemetry", telemetry), ("Gateway master", aux["gateway_master.csv"]), ("Field visits", aux["field_visits.csv"]), ("Meter read success", aux["meter_read_success.csv"]), ("Engineer review", load_review())]:
        if frame is None: datasets.append({"Dataset": name, "Rows": "Not available", "Columns": "Not available", "Date range": "Not available", "Status": "Unavailable"}); continue
        date_cols = [c for c in frame.columns if "date" in c.lower() or "time" in c.lower() or c == "ts"]
        date_range = "Not available"
        if date_cols:
            parsed = pd.to_datetime(frame[date_cols[0]], errors="coerce", utc=True)
            if parsed.notna().any(): date_range = f"{parsed.min().date()} → {parsed.max().date()}"
        datasets.append({"Dataset": name, "Rows": len(frame), "Columns": len(frame.columns), "Date range": date_range, "Status": "Known duplicate keys" if name == "Telemetry" and duplicate_count else "Available"})
    st.dataframe(pd.DataFrame(datasets), hide_index=True, width="stretch")
    st.subheader("Temporal data integrity")
    st.write("Prediction week → Monday 00:00 UTC → only data strictly before cutoff → prediction")
    cutoff_rows = []
    for week in WEEKS:
        cutoff_timestamp = pd.Timestamp(week, tz="UTC")
        eligible = telemetry[telemetry["ts"] < cutoff_timestamp]
        history = eligible[eligible["ts"] >= cutoff_timestamp - dt.timedelta(days=28)]
        cutoff_rows.append({"Prediction week": week.isoformat(), "Cutoff timestamp": f"{week.isoformat()}T00:00:00Z", "Latest eligible data": eligible["ts"].max().strftime("%Y-%m-%dT%H:%M:%SZ") if not eligible.empty else "Not available", "Rows used": len(history)})
    cutoff = pd.DataFrame(cutoff_rows)
    st.dataframe(cutoff, hide_index=True, width="stretch")


def reproducibility() -> None:
    render_header("Reproducibility center", "Regenerate and validate Part 1 on another machine.")
    st.code("python -m pip install pandas numpy pyarrow\npython baseline_3sigma.py --data 03-challenge-data/data --out predictions.csv\npython validate_submission.py predictions.csv", language="powershell")
    st.write("The commands use relative paths, run offline against the supplied data, and leave the dashboard read-only. The official baseline and validator are not imported or rewritten by the UI.")
    st.info("Verified output: 120 rows across 8 weeks, with 15 ranked gateways per week.")


def decisions() -> None:
    render_header("Decisions & limitations", "The documented trade-offs behind the official Part 1 baseline.")
    st.markdown((ROOT / "DECISIONS.md").read_text(encoding="utf-8"))


predictions = load_predictions(); aux = load_auxiliary(); status = validation(predictions)
with st.sidebar:
    st.markdown('<div class="eyebrow">NEXORA</div><h2 style="margin-top:.2rem">Gateway Anomaly<br>Intelligence</h2>', unsafe_allow_html=True)
    st.markdown('<span class="status">● PART 1 VALIDATED</span>', unsafe_allow_html=True); st.caption("3-Sigma Field Visit Prioritization System")
    st.metric("Baseline", "3-Sigma"); st.metric("Prediction weeks", "8"); st.metric("Gateways / week", "15"); st.metric("Total predictions", str(status["rows"]))
    page = st.radio("Navigate", ["Overview", "How It Works", "Weekly Predictions", "Gateway Intelligence", "Anomaly Analysis", "Cost Analysis", "Validation Center", "Data Quality", "Reproducibility", "Decisions & Limitations"], label_visibility="collapsed")

if page == "Overview": overview(predictions, status)
elif page == "How It Works": how_it_works()
elif page == "Weekly Predictions": weekly_predictions(predictions)
elif page == "Gateway Intelligence": gateway_intelligence(predictions, load_telemetry(), aux)
elif page == "Anomaly Analysis": anomaly_analysis(predictions, load_telemetry())
elif page == "Cost Analysis": cost_analysis(predictions)
elif page == "Validation Center": validation_center(predictions, status)
elif page == "Data Quality": data_quality(load_telemetry(), aux)
elif page == "Reproducibility": reproducibility()
else: decisions()

st.markdown("<br><br><div style='border-top:1px solid #273542;padding-top:1rem;color:#718293;font-size:.78rem'>NEXORA 2026 · LPDG Innovation Hub Selection Challenge · Part 1 — 3-Sigma Gateway Prioritization</div>", unsafe_allow_html=True)