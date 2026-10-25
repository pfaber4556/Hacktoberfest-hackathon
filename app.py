"""
crunch week radar 📡
drop in all your syllabi -> gemma 4 pulls out every graded thing -> see which weeks will actually hurt.
run:  streamlit run app.py
"""

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

import altair as alt
import pandas as pd
import pymupdf
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # reads keys from a local .env file (never committed)

# gemma 4 31B, hosted on digitalocean serverless inference (openai-compatible api)
DO_BASE_URL = "https://inference.do-ai.run/v1"
DO_MODEL = "gemma-4-31B-it"
# fallback: gemma 4 through the gemini api (only if you have a working google key)
GEMINI_MODEL = "gemma-4-26b-a4b-it"
TYPES = ["exam", "quiz", "project", "homework", "paper", "presentation", "other"]
BIG_TYPES = {"exam", "project", "paper", "presentation"}  # things worth a "start prepping" reminder
# one-hue sequential ramp (light = chill, dark = crunch)
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


# ---------------------------------------------------------------- gemma
def build_prompt(week1: date, n_weeks: int) -> str:
    return f"""You are reading a college course syllabus. Week 1 starts on Monday {week1.isoformat()}.
The term has {n_weeks} weeks of instruction; week {n_weeks + 1} is finals week.

Extract EVERY graded item: exams, midterms, finals, quizzes, projects, papers, presentations, homework.
Rules:
- Use an exact date (YYYY-MM-DD) if the syllabus gives one. Infer the year from the term start.
- If it only says "week 5" or "5th week", leave due as null and set week to 5.
- weight_pct = percent of the FINAL course grade for that ONE item. If a category is shared
  ("Midterms 30%, 2 midterms"), split it evenly (15 each) and set weight_estimated to true.
  Recurring items ("weekly quizzes 10%") can be one row with the total weight and week null.
- If no weight is stated, use null. Never invent dates.
- type must be one of: {", ".join(TYPES)}

Reply with ONLY valid JSON:
{{"course": "short course code like COGS 9",
  "items": [{{"title": "Midterm 1", "type": "exam", "due": "YYYY-MM-DD or null",
             "week": 5, "weight_pct": 15, "weight_estimated": false}}]}}"""


def get_backend():
    """gemma 4 through the gemini api first (what the gemma prize asks for), digitalocean gemma as backup."""
    g_key = os.environ.get("GEMINI_API_KEY") or st.session_state.get("gemini_key")
    if g_key:
        return "gemini", g_key
    do_key = os.environ.get("MODEL_ACCESS_KEY") or st.session_state.get("do_key")
    if do_key:
        return "digitalocean", do_key
    return None, None


def call_model(backend: str, key: str, parts: list[tuple], prompt: str) -> str:
    return (call_digitalocean if backend == "digitalocean" else call_gemini)(key, parts, prompt)


def parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)  # models love wrapping json in ``` fences
    if not match:
        raise ValueError("gemma didn't return json, try again or use the bigger model")
    return json.loads(match.group(0))


def file_to_parts(data: bytes, mime: str) -> list[tuple]:
    """pdfs with real text -> ("text", str). scanned pdfs / screenshots -> ("image", bytes, mime)."""
    if mime == "application/pdf":
        doc = pymupdf.open(stream=data, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        if len(text.strip()) > 300:
            return [("text", f"SYLLABUS TEXT:\n{text[:25000]}")]
        # scanned pdf: render the first few pages as images
        return [("image", page.get_pixmap(dpi=130).tobytes("png"), "image/png") for page in list(doc)[:6]]
    return [("image", data, mime)]


def call_digitalocean(key: str, parts: list[tuple], prompt: str) -> str:
    from openai import OpenAI

    content = []
    for p in parts:
        if p[0] == "text":
            content.append({"type": "text", "text": p[1]})
        else:
            b64 = base64.b64encode(p[1]).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:{p[2]};base64,{b64}"}})
    content.append({"type": "text", "text": prompt})
    client = OpenAI(base_url=DO_BASE_URL, api_key=key)
    resp = client.chat.completions.create(
        model=DO_MODEL, temperature=0.1, messages=[{"role": "user", "content": content}]
    )
    return resp.choices[0].message.content


def call_gemini(key: str, parts: list[tuple], prompt: str) -> str:
    from google import genai
    from google.genai import types

    contents = [p[1] if p[0] == "text" else types.Part.from_bytes(data=p[1], mime_type=p[2]) for p in parts]
    # keep the client in a variable: if only .models is referenced, python closes the client mid-request
    client = genai.Client(api_key=key)
    try:
        # MINIMAL thinking = way faster. pulling dates out of a syllabus doesn't need deep reasoning
        fast = types.GenerateContentConfig(
            temperature=0.1, thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"))
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=contents + [prompt], config=fast)
    except Exception:
        # older sdk / model that doesn't accept the setting -> normal (slower) call
        resp = client.models.generate_content(
            model=GEMINI_MODEL, contents=contents + [prompt],
            config=types.GenerateContentConfig(temperature=0.1),
        )
    # gemma 4 sends its "thinking" as separate parts; keep only the real answer
    parts_out = resp.candidates[0].content.parts or []
    answer = "".join(p.text or "" for p in parts_out if not getattr(p, "thought", False))
    return answer or resp.text


def extract(data: bytes, mime: str, week1: date, n_weeks: int, backend: str, _key: str) -> dict:
    """plain function (no streamlit calls) so we can run several syllabi at the same time."""
    parts, prompt = file_to_parts(data, mime), build_prompt(week1, n_weeks)
    return parse_json(call_model(backend, _key, parts, prompt))


@st.cache_data(show_spinner=False)
def game_plan(context: str, backend: str, _key: str) -> str:
    prompt = """You are a chill, practical upperclassman helping a college student survive their worst week.
Using the schedule above, write a prep plan for the CRUNCH WEEK starting from the prep week.
- go week by week, then day by day for the crunch week itself
- weight time by how much each item is worth; say what to do for the big ones first
- spread the load so no single day is impossible, and flag anything to start TODAY
- under 250 words, markdown bullets, casual lowercase tone, no fluff"""
    return call_model(backend, _key, [("text", context)], prompt)





# ---------------------------------------------------------------- data wrangling
def to_rows(result: dict, fallback_name: str) -> list[dict]:
    course = (result.get("course") or fallback_name).strip()
    rows = []
    for it in result.get("items", []):
        due = it.get("due")
        try:
            due = datetime.strptime(due, "%Y-%m-%d").date() if due else None
        except (TypeError, ValueError):
            due = None
        rows.append({
            "course": course,
            "title": it.get("title") or "untitled",
            "type": it.get("type") if it.get("type") in TYPES else "other",
            "due": due,
            "week": it.get("week"),
            "weight_pct": it.get("weight_pct"),
            "estimated": bool(it.get("weight_estimated")),
        })
    return rows


def fill_weeks(df: pd.DataFrame, week1: date, n_weeks: int) -> pd.DataFrame:
    """make every row have both a week number and a due date."""
    df = df.copy()
    for i, r in df.iterrows():
        due = r["due"]
        if pd.notna(due) and due is not None:
            due = pd.Timestamp(due).date()
            df.at[i, "due"] = due
            df.at[i, "week"] = (due - week1).days // 7 + 1
        elif pd.notna(r["week"]):
            # week only -> assume friday of that week
            df.at[i, "due"] = week1 + timedelta(weeks=int(r["week"]) - 1, days=4)
    df["week"] = pd.to_numeric(df["week"], errors="coerce").clip(lower=1, upper=n_weeks + 1).round().astype("Int64")
    df["weight_pct"] = pd.to_numeric(df["weight_pct"], errors="coerce")
    return df


def week_label(w: int, n_weeks: int) -> str:
    return "finals" if w == n_weeks + 1 else f"wk {w}"


def make_ics(df: pd.DataFrame, lead_weeks: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//crunch week radar//EN", "CALSCALE:GREGORIAN"]

    def event(day: date, summary: str, uid: str):
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}@crunchweekradar",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            "SUMMARY:" + summary.replace(",", "\\,").replace(";", "\\;"),
            "END:VEVENT",
        ])

    for i, r in df.dropna(subset=["due"]).iterrows():
        w = f" ({r['weight_pct']:g}%)" if pd.notna(r["weight_pct"]) else ""
        event(r["due"], f"[{r['course']}] {r['title']}{w}", f"due-{i}")
        if r["type"] in BIG_TYPES and pd.notna(r["weight_pct"]) and r["weight_pct"] >= 10:
            event(r["due"] - timedelta(weeks=lead_weeks), f"start prepping: [{r['course']}] {r['title']}", f"prep-{i}")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


SAMPLE = [
    {"course": "DSC 80", "items": [
        {"title": "Project 1", "type": "project", "week": 3, "weight_pct": 10},
        {"title": "Midterm", "type": "exam", "week": 5, "weight_pct": 20},
        {"title": "Project 2", "type": "project", "week": 7, "weight_pct": 10},
        {"title": "Final project", "type": "project", "week": 10, "weight_pct": 15},
        {"title": "Final exam", "type": "exam", "week": 11, "weight_pct": 25},
        {"title": "Weekly labs", "type": "homework", "week": None, "weight_pct": 20}]},
    {"course": "COGS 108", "items": [
        {"title": "A1", "type": "homework", "week": 2, "weight_pct": 5},
        {"title": "Proposal", "type": "paper", "week": 4, "weight_pct": 10, "weight_estimated": True},
        {"title": "A3", "type": "homework", "week": 6, "weight_pct": 5},
        {"title": "Checkpoint", "type": "project", "week": 7, "weight_pct": 10},
        {"title": "Final project", "type": "project", "week": 11, "weight_pct": 30}]},
    {"course": "MATH 181A", "items": [
        {"title": "Quiz 1", "type": "quiz", "week": 3, "weight_pct": 5},
        {"title": "Midterm 1", "type": "exam", "week": 5, "weight_pct": 20, "weight_estimated": True},
        {"title": "Midterm 2", "type": "exam", "week": 8, "weight_pct": 20, "weight_estimated": True},
        {"title": "Final", "type": "exam", "week": 11, "weight_pct": 40}]},
    {"course": "ECON 100A", "items": [
        {"title": "Problem set 3", "type": "homework", "week": 5, "weight_pct": 5},
        {"title": "Midterm", "type": "exam", "week": 6, "weight_pct": 30},
        {"title": "Problem set 6", "type": "homework", "week": 9, "weight_pct": 5},
        {"title": "Final", "type": "exam", "week": 11, "weight_pct": 45}]},
]


# ---------------------------------------------------------------- ui
st.set_page_config(page_title="crunch week radar", page_icon="📡", layout="wide")
st.title("📡 crunch week radar")
st.caption("every syllabus in, your actual worst weeks out. weighted by how much of your grade is on the line. "
           "powered by **gemma 4** (open weights) 💎")

with st.sidebar:
    if not os.environ.get("GEMINI_API_KEY"):
        st.session_state["gemini_key"] = st.text_input("gemini api key (gemma 4)", type="password")
    with st.expander("backup: gemma 4 on digitalocean"):
        if not os.environ.get("MODEL_ACCESS_KEY"):
            st.session_state["do_key"] = st.text_input("digitalocean model access key", type="password")
    week1 = st.date_input("monday of week 1", value=date(2026, 9, 28),
                          help="double-check this against your school's academic calendar")
    n_weeks = st.number_input("weeks of instruction", 5, 20, 10, help="finals week is added after these")
    lead = st.slider("start prepping how many weeks early?", 1, 4, 2)

files = st.file_uploader("drop in your syllabi (pdf, screenshot, or photo)",
                         type=["pdf", "png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
c1, c2 = st.columns([1, 4])
go = c1.button("📡 scan syllabi", type="primary", disabled=not files)
if c2.button("try it with sample data"):
    rows = [r for c in SAMPLE for r in to_rows(c, c["course"])]
    st.session_state["df"] = fill_weeks(pd.DataFrame(rows), week1, n_weeks)

if go:
    backend, key = get_backend()
    if not backend:
        st.warning("add a gemini api key (or the digitalocean backup) in the sidebar first")
        st.stop()
    rows, bar = [], st.progress(0.0, text=f"gemma is reading {len(files)} syllabi at once...")
    cache = st.session_state.setdefault("scan_cache", {})  # don't re-scan files we've already read
    jobs = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for f in files:
            data = f.getvalue()
            ck = (hashlib.md5(data).hexdigest(), week1, n_weeks, backend)
            if ck in cache:
                rows += to_rows(cache[ck], f.name.rsplit(".", 1)[0])
                continue
            jobs[pool.submit(extract, data, f.type, week1, n_weeks, backend, key)] = (f, ck)
        done = len(files) - len(jobs)
        for fut in as_completed(jobs):
            f, ck = jobs[fut]
            try:
                cache[ck] = fut.result()
                rows += to_rows(cache[ck], f.name.rsplit(".", 1)[0])
            except Exception as e:  # one bad syllabus shouldn't kill the rest
                st.error(f"couldn't read {f.name}: {e}")
            done += 1
            bar.progress(done / len(files), text=f"read {done}/{len(files)}: {f.name}")
    bar.empty()
    if rows:
        st.session_state["df"] = fill_weeks(pd.DataFrame(rows), week1, n_weeks)

if "df" not in st.session_state:
    st.info("upload your syllabi, or hit **sample data** to see how it works")
    st.stop()

# ---- review + fix what gemma found
with st.expander("✏️ check what gemma found (edit anything that looks off)", expanded=False):
    edited = st.data_editor(
        st.session_state["df"], num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "type": st.column_config.SelectboxColumn(options=TYPES),
            "due": st.column_config.DateColumn(),
            "week": st.column_config.NumberColumn(min_value=1, max_value=n_weeks + 1, step=1),
            "weight_pct": st.column_config.NumberColumn("weight %", min_value=0, max_value=100),
            "estimated": st.column_config.CheckboxColumn("weight guessed?"),
        },
    )
df = fill_weeks(edited, week1, n_weeks)
dated = df.dropna(subset=["week"])
undated = df[df["week"].isna()]

# ---- heatmap: weeks x courses, shaded by % of course grade due
weeks = list(range(1, n_weeks + 2))
courses = sorted(df["course"].unique())
grid = (dated.groupby(["course", "week"])
        .agg(weight=("weight_pct", "sum"), items=("title", lambda s: ", ".join(s)))
        .reset_index())
full = pd.MultiIndex.from_product([courses, weeks], names=["course", "week"]).to_frame(index=False)
grid = full.merge(grid, how="left", on=["course", "week"]).fillna({"weight": 0, "items": ""})
grid["label"] = grid["week"].apply(lambda w: week_label(w, n_weeks))
order = [week_label(w, n_weeks) for w in weeks]
vmax = max(grid["weight"].max(), 1)

base = alt.Chart(grid).encode(
    x=alt.X("label:O", sort=order, title=None, axis=alt.Axis(labelAngle=0, ticks=False, domain=False)),
    y=alt.Y("course:N", title=None, axis=alt.Axis(ticks=False, domain=False)),
)
cells = base.mark_rect(cornerRadius=4, stroke="white", strokeWidth=2).encode(
    color=alt.Color("weight:Q", title="% of course grade",
                    scale=alt.Scale(domain=[0, vmax], range=RAMP)),
    tooltip=[alt.Tooltip("course:N"), alt.Tooltip("label:N", title="week"),
             alt.Tooltip("weight:Q", title="% of grade", format=".0f"), alt.Tooltip("items:N", title="due")],
)
labels = base.mark_text(fontSize=12).encode(
    text=alt.Text("weight:Q", format=".0f"),
    color=alt.condition(alt.datum.weight > vmax * 0.5, alt.value("white"), alt.value("#1f1f1f")),
).transform_filter(alt.datum.weight > 0)

st.subheader("your quarter at a glance")
st.altair_chart((cells + labels).properties(height=60 * len(courses) + 40), width="stretch")

# ---- crunch weeks callout
totals = dated.groupby("week").agg(weight=("weight_pct", "sum"), n_courses=("course", "nunique"),
                                   items=("title", "count")).sort_values("weight", ascending=False)
mid_term = totals[totals.index <= n_weeks]  # finals week is always brutal; flag the sneaky ones
st.subheader("🔥 your crunch weeks")
cols = st.columns(3)
for col, (w, r) in zip(cols, mid_term.head(3).iterrows()):
    w = int(w)
    with col:
        st.metric(week_label(w, n_weeks), f"{r['weight']:.0f}%", help="sum of course-grade % due that week")
        prep = max(1, w - lead)
        st.caption(f"{int(r['items'])} things across {int(r['n_courses'])} class"
                   f"{'es' if r['n_courses'] > 1 else ''} → start prepping **week {prep}**")
        st.markdown("\n".join(f"- {c}: {t}" for c, t in
                              dated[dated["week"] == w][["course", "title"]].itertuples(index=False)))

if not undated.empty:
    st.caption("ongoing stuff with no single due date: " +
               ", ".join(f"{r.course} {r.title}" for r in undated.itertuples()))

# ---- gemma game plan for the worst week
if not mid_term.empty:
    worst = int(mid_term.index[0])
    st.subheader(f"🧠 game plan for {week_label(worst, n_weeks)}")
    backend, key = get_backend()
    if st.button("make me a plan", disabled=not backend,
                 help=None if backend else "add a key in the sidebar to use gemma"):
        sched = dated.sort_values("week")
        context = (f"Term: week 1 starts {week1}. Crunch week: {worst} (start prepping week {max(1, worst - lead)}).\n"
                   "Schedule (course | item | type | week | due | % of course grade):\n" +
                   "\n".join(f"{r.course} | {r.title} | {r.type} | {r.week} | {r.due} | {r.weight_pct}"
                             for r in sched.itertuples() if r.week <= worst + 1))
        with st.spinner("gemma is cooking up a plan..."):
            try:
                st.markdown(game_plan(context, backend, key))
            except Exception as e:
                st.error(f"gemma couldn't make a plan: {e}")

st.subheader("Weekly Survival To-Do List")
available_weeks = sorted([int(w) for w in dated["week"].dropna().unique()])
if available_weeks:
    selected_w = st.selectbox(
        "Choose a week to plan your attack:", 
        options=available_weeks, 
        format_func=lambda w: week_label(w, n_weeks)
    )
    week_items = dated[dated["week"] == selected_w]
    st.markdown(f"**Tasks for {week_label(selected_w, n_weeks)}**")
    
    completed_count = 0
    total_tasks = len(week_items)
    
    if total_tasks > 0:
        for i, r in week_items.reset_index().iterrows():
            key = f"todo_{selected_w}_{i}_{r['course']}_{r['title']}"
            if key not in st.session_state:
                st.session_state[key] = False
            
            weight_str = f" — *({r['weight_pct']:g}% of grade)*" if pd.notna(r['weight_pct']) else ""
            type_str = f"[{r['type']}] " if pd.notna(r['type']) else ""
            
            checked = st.checkbox(
                f"**{r['course']}**: {type_str}{r['title']}{weight_str}", 
                value=st.session_state[key], 
                key=key
            )
            st.session_state[key] = checked
            if checked:
                completed_count += 1
                
        progress = completed_count / total_tasks if total_tasks > 0 else 0
        st.progress(progress, text=f"Survival Progress: {completed_count}/{total_tasks} completed")
        
        if completed_count == total_tasks and total_tasks > 0:
            st.success("🎉 You're fully prepared for this week! You've got this.")
    else:
        st.info("No graded items scheduled for this week. Enjoy the breather!")
else:
    st.info("Upload your syllabi to generate your interactive checklist.")

# ---- calendar export
st.download_button("📅 add to my calendar (.ics)", make_ics(df, lead), "crunch-week-radar.ics", "text/calendar")
