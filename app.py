"""
SyllabuStrat 📡
drop in all your syllabi -> gemma 4 pulls out every graded thing -> see which weeks will actually hurt.
run:  streamlit run app.py
"""

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
import time
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
RAMP_LIGHT = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


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
        return [("image", page.get_pixmap(dpi=110).tobytes("jpeg", jpg_quality=82), "image/jpeg")
                for page in list(doc)[:6]]
    return [("image", data, mime)]


GRADE_WORDS = re.compile(
    r"%|percent|points?|grade|grading|exam|midterm|final|quiz|project|paper|essay|homework|hw\b|assignment|"
    r"problem set|pset|lab|presentation|due|deadline|week|wk\b|schedule|monday|tuesday|wednesday|thursday|"
    r"friday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/\d{1,2}", re.I)


def focus_text(text: str) -> str:
    """keep only the lines about grades, deadlines and dates (plus a line of context). less to read = faster."""
    lines = text.splitlines()
    keep = set()
    for i, line in enumerate(lines):
        if GRADE_WORDS.search(line):
            keep.update({i - 1, i, i + 1})
    focused = "\n".join(lines[i] for i in sorted(keep) if 0 <= i < len(lines))
    return focused[:9000] if len(focused) > 800 else text[:9000]  # tiny result = filter missed, send the start


POLICY_WORDS = re.compile(
    r"late|drop|lowest|attend|absen|policy|cumulative|final|exam|regrade|make-?up|extension|collab|curve|"
    r"office hours|grade|grading|%|due|accommodat|calculator|notes|cheat sheet|participation", re.I)


def policy_text(text: str) -> str:
    """for 'ask your syllabi': keep policy + grading lines so every syllabus fits in one request."""
    lines = text.splitlines()
    keep = set()
    for i, line in enumerate(lines):
        if POLICY_WORDS.search(line):
            keep.update({i - 1, i, i + 1})
    focused = "\n".join(lines[i] for i in sorted(keep) if 0 <= i < len(lines))
    return (focused if len(focused) > 600 else text)[:6000]


def shrink_image(data: bytes, mime: str, max_side: int = 1600) -> tuple[bytes, str]:
    """phone photos are huge; gemma reads a 1600px jpeg just as well, and it uploads way faster."""
    try:
        doc = pymupdf.open(stream=data, filetype=mime.split("/")[-1])
        rect = doc[0].rect
        zoom = min(1.0, max_side / max(rect.width, rect.height))
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pix.tobytes("jpeg", jpg_quality=82), "image/jpeg"
    except Exception:
        return data, mime


def fast_parts(parts: list[tuple]) -> list[tuple]:
    out = []
    for p in parts:
        if p[0] == "text":
            out.append(("text", "SYLLABUS (grading and schedule lines only):\n" + focus_text(p[1])))
        else:
            out.append(("image", *shrink_image(p[1], p[2])))
    return out


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
    # the free tier allows ~16k input tokens per minute PER MODEL. when we hit it, wait the time google
    # asks for, and spread load onto the other gemma 4 model (it has its own separate quota)
    models = [GEMINI_MODEL, "gemma-4-31b-it"]
    use_minimal = True
    for attempt in range(6):
        model = models[attempt % 2] if attempt >= 1 else models[0]
        cfg = types.GenerateContentConfig(temperature=0.1, **(
            {"thinking_config": types.ThinkingConfig(thinking_level="MINIMAL")} if use_minimal else {}))
        try:
            resp = client.models.generate_content(model=model, contents=contents + [prompt], config=cfg)
            break
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = re.search(r"retry in ([\d.]+)s", msg)
                time.sleep(min(float(wait.group(1)) + 1, 20) if wait else 5 * (attempt + 1))
                continue
            if use_minimal and "thinking" in msg.lower():  # model/sdk doesn't take the setting
                use_minimal = False
                continue
            raise
    else:
        raise RuntimeError("google's free tier is maxed out right now. wait a minute and scan again, "
                           "or upload fewer syllabi at once.")
    # gemma 4 sends its "thinking" as separate parts; keep only the real answer
    parts_out = resp.candidates[0].content.parts or []
    answer = "".join(p.text or "" for p in parts_out if not getattr(p, "thought", False))
    return answer or resp.text


def extract(data: bytes, mime: str, week1: date, n_weeks: int, backend: str, _key: str) -> dict:
    """plain function (no streamlit calls) so we can run several syllabi at the same time."""
    parts, prompt = fast_parts(file_to_parts(data, mime)), build_prompt(week1, n_weeks)
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
            "exact_date": due is not None,  # false = we only know the week, so don't flag same-day clashes
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
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SyllabuStrat//EN", "CALSCALE:GREGORIAN"]

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


SAMPLE_POLICIES = {
    "DSC 80": "Late policy: projects accepted up to 2 days late with 10% off per day; labs are not accepted late. "
              "Your lowest lab score is dropped. The final exam is cumulative. Office hours: Tue/Thu 2-4pm.",
    "COGS 108": "Group final project, groups of 4-5. Assignments may be submitted up to 24 hours late for 25% off. "
                "No exams. Attendance in discussion section counts toward participation.",
    "MATH 181A": "No late homework, but the lowest 2 homework scores are dropped. Midterms are not cumulative; "
                 "the final is cumulative and can replace your lowest midterm if it is higher.",
    "ECON 100A": "Problem sets are due Fridays at 11:59pm; no late work. The final covers the whole course. "
                 "Calculators allowed on exams, no notes.",
}


@st.cache_data(show_spinner=False)
def ask_syllabi(question: str, _sources: list, backend: str, _key: str, _sig: str) -> str:
    parts = []
    for course, course_parts in _sources:
        parts.append(("text", f"\n===== SYLLABUS FOR {course} ====="))
        parts += [("text", policy_text(p[1])) if p[0] == "text" else p for p in course_parts]
    prompt = f"""You have the syllabi above for a student's classes. Answer their question using ONLY what the
syllabi say. Be brief and direct, casual lowercase tone. Name the class for each fact, like "DSC 80: ...".
If the syllabi don't say, answer "your syllabi don't say" for that class and suggest asking the instructor.

Question: {question}"""
    return call_model(backend, _key, parts, prompt)


# ---------------------------------------------------------------- ui
st.set_page_config(page_title="SyllabuStrat", page_icon="📡", layout="wide")

# ---- light + dark: pick colors from whatever theme streamlit is showing (system setting or the ⋮ menu)
try:
    IS_DARK = st.context.theme.type == "dark"
except Exception:
    IS_DARK = False
T = {  # page tokens
    "ink": "#e6edf7", "paper": "#141a24", "rule": "#243149", "margin": "#7d3a3a", "muted": "#9aa8bb",
    "ribbon": "#e05a59", "alert_bg": "#3a2023", "plank": "#c8d3e3", "empty": "#2a3446", "surface": "#0f141c",
} if IS_DARK else {
    "ink": "#13233d", "paper": "#ffffff", "rule": "#dbe6f3", "margin": "#e3a5a5", "muted": "#5d6b7e",
    "ribbon": "#b8302f", "alert_bg": "#fbefee", "plank": "#13233d", "empty": "#a8b3c2", "surface": "#ffffff",
}
# sequential ramp: low values recede toward the background in both modes
RAMP = (["#16233a", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"] if IS_DARK
        else RAMP_LIGHT)
# class colors: same 8 hues in the same order, stepped for each background
COURSE_COLORS = (["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"] if IS_DARK
                 else ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"])
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,500;7..72,700&family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700&display=swap');
:root { /*TOKENS*/ }
.stApp p, .stApp li, .stApp label, .stApp button, .cwr * { font-family: 'Bricolage Grotesque', system-ui, sans-serif; }
.stApp h1, .stApp h2, .stApp h3, .cwr-serif { font-family: 'Literata', Georgia, serif !important; color: var(--ink); }
.stApp h2, .stApp h3 { font-weight: 700; letter-spacing: -0.01em; }
.cwr-hero h1 { font-size: clamp(2.2rem, 5vw, 3.4rem); line-height: 1.05; font-weight: 700; letter-spacing: -0.02em;
  margin: 0 0 .5rem; padding: 0; max-width: 18ch; }
.cwr-hero p { font-size: 1.1rem; color: var(--muted); max-width: 60ch; margin: 0 0 1.2rem; }
.cwr-steps { color: var(--muted); padding-left: 1.2rem; margin: .5rem 0 0; }
.cwr-steps li { margin: .2rem 0; }
.stApp .cwr-next, .stApp .cwr-next * { font-family: 'Literata', Georgia, serif !important; }
.stApp .cwr-next { font-size: clamp(1.25rem, 2.4vw, 1.75rem); font-weight: 500;
  line-height: 1.3; color: var(--ink); max-width: 38ch; margin: .6rem 0 1rem; }
.stApp .cwr-next b { font-weight: 700; }
/* the notebook page the shelf sits on: ruled lines + a margin rule */
.cwr-page { background-color: var(--paper);
  background-image: linear-gradient(to right, transparent 46px, var(--margin) 46px, var(--margin) 48px, transparent 48px),
                    repeating-linear-gradient(to bottom, transparent 0 27px, var(--rule) 27px 28px);
  border: 1px solid var(--rule); border-radius: 6px; padding: 18px 14px 10px 60px; overflow-x: auto; }
.cwr-shelf { display: flex; align-items: stretch; min-height: 270px; gap: 10px; min-width: 640px; }
.cwr-week { flex: 1 0 44px; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; position: relative; }
.cwr-week.past { opacity: .4; }
.cwr-total { font-size: .85rem; font-weight: 700; color: var(--ink); margin-bottom: 4px; }
.cwr-stack { width: 100%; max-width: 64px; display: flex; flex-direction: column-reverse; gap: 2px; }
.cwr-book { border-radius: 3px 3px 2px 2px; color: #fff; font-size: .62rem; font-weight: 600; line-height: 1.1;
  display: flex; align-items: center; justify-content: center; overflow: hidden; white-space: nowrap; padding: 0 3px; }
.cwr-plank { width: 100%; height: 5px; background: var(--plank); border-radius: 2px; margin-top: 2px; }
.cwr-wk { font-size: .8rem; font-weight: 600; color: var(--muted); margin-top: 5px; }
.cwr-week.now .cwr-wk { color: var(--ink); }
.cwr-ribbon { position: absolute; top: -19px; right: 4px; width: 12px; height: 26px; background: var(--ribbon);
  clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 78%, 0 100%); }
.cwr-key { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 10px 0 0; font-size: .85rem; color: var(--ink); }
.cwr-key span { display: inline-flex; align-items: center; gap: 6px; }
.cwr-key i { width: 12px; height: 12px; border-radius: 2px; display: inline-block; }
.cwr-alerts { list-style: none; padding: 10px 14px; margin: 0 0 14px; border-left: 4px solid var(--ribbon);
  background: var(--alert_bg); border-radius: 0 6px 6px 0; color: var(--ink); max-width: 72ch; }
.cwr-alerts li { margin: 3px 0; font-size: .95rem; }
.cwr-alerts li::before { content: "⚠️ "; }
.cwr-note { font-size: .85rem; color: var(--muted); margin: 8px 0 0; }
</style>
<div class="cwr-hero">
  <h1>📡 SyllabuStrat</h1>
  <p><b>how heavy is your quarter, really?</b> drop in every syllabus. gemma 4 pulls out each exam, paper, and project with its weight, then stacks
     them week by week so you can see where the work piles up before it does.</p>
</div>
""".replace("/*TOKENS*/", " ".join(f"--{k}:{v};" for k, v in T.items())), unsafe_allow_html=True)

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
    st.session_state["sources"] = [(c, [("text", t)]) for c, t in SAMPLE_POLICIES.items()]
    st.session_state["qa"] = []

if go:
    backend, key = get_backend()
    if not backend:
        st.warning("add a gemini api key (or the digitalocean backup) in the sidebar first")
        st.stop()
    rows, bar = [], st.progress(0.0, text=f"gemma is reading {len(files)} syllabi at once...")
    cache = st.session_state.setdefault("scan_cache", {})  # don't re-scan files we've already read
    jobs, sources = {}, []  # sources = what each syllabus said, kept for "ask your syllabi"
    with ThreadPoolExecutor(max_workers=3) as pool:  # gentle on the free-tier rate limit
        for f in files:
            data = f.getvalue()
            ck = (hashlib.md5(data).hexdigest(), week1, n_weeks, backend)
            if ck in cache:
                rows += to_rows(cache[ck], f.name.rsplit(".", 1)[0])
                sources.append((cache[ck].get("course") or f.name, file_to_parts(data, f.type)))
                continue
            jobs[pool.submit(extract, data, f.type, week1, n_weeks, backend, key)] = (f, ck, data)
        done = len(files) - len(jobs)
        for fut in as_completed(jobs):
            f, ck, data = jobs[fut]
            try:
                cache[ck] = fut.result()
                rows += to_rows(cache[ck], f.name.rsplit(".", 1)[0])
                sources.append((cache[ck].get("course") or f.name, file_to_parts(data, f.type)))
            except Exception as e:  # one bad syllabus shouldn't kill the rest
                st.error(f"couldn't read {f.name}: {e}")
            done += 1
            bar.progress(done / len(files), text=f"read {done}/{len(files)}: {f.name}")
    bar.empty()
    if rows:
        st.session_state["df"] = fill_weeks(pd.DataFrame(rows), week1, n_weeks)
        st.session_state["sources"], st.session_state["qa"] = sources, []
        n_courses = len({r["course"] for r in rows})
        st.toast(f"found {len(rows)} graded things across {n_courses} class{'es' if n_courses != 1 else ''}", icon="📡")

if "df" not in st.session_state:
    st.markdown("""<ol class="cwr-steps">
      <li>set the monday of week 1 in the sidebar</li>
      <li>drop in your syllabi (pdfs, screenshots, or phone photos all work)</li>
      <li>hit scan, then check what gemma found</li></ol>""", unsafe_allow_html=True)
    st.caption("no syllabi handy? try the sample data to see a full quarter.")
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
            "exact_date": st.column_config.CheckboxColumn("exact date?"),
        },
    )
df = fill_weeks(edited, week1, n_weeks)
dated = df.dropna(subset=["week"])
undated = df[df["week"].isna()]

# ---- the bookshelf: each graded item is a book, its thickness is how much of the grade it's worth
course_list = sorted(df["course"].unique())
color_of = {c: COURSE_COLORS[i % len(COURSE_COLORS)] for i, c in enumerate(course_list)}
week_load = dated.groupby("week")["weight_pct"].sum()
cur = (date.today() - week1).days // 7 + 1
cur = cur if 1 <= cur <= n_weeks + 1 else None
px_per_pct = 220 / max(week_load.max() if not week_load.empty else 0, 1)


def load_word(total: float) -> str:
    """turn a week's summed weight into a plain word. scaled by class count so 3 classes vs 5 feels the same."""
    share = total / max(len(course_list), 1)  # roughly: % of the whole quarter decided that week
    if share <= 0: return ""
    if share < 3: return "light"
    if share < 7: return "busy"
    if share < 12: return "heavy"
    return "brutal"


def describe(items: pd.DataFrame, limit: int = 4) -> str:
    """'the DSC 80 midterm, the MATH 181A midterm 1, and the ECON 100A problem set 3'"""
    names = [f"{r.course} {r.title.lower()}" for r in items.sort_values("weight_pct", ascending=False).itertuples()]
    extra = len(names) - limit
    names = names[:limit] + ([f"{extra} more"] if extra > 0 else [])
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f"{',' if len(names) > 2 else ''} and {names[-1]}"


def esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


cols_html = []
for w in range(1, n_weeks + 2):
    items = dated[dated["week"] == w].sort_values("weight_pct", ascending=False)
    books = []
    for r in items.itertuples():
        pct = float(r.weight_pct) if pd.notna(r.weight_pct) else 0
        h = max(6, pct * px_per_pct)
        label = esc(r.course.split()[0] if h < 30 else r.course) if h >= 16 else ""
        books.append(f'<div class="cwr-book" style="height:{h:.0f}px;background:{color_of[r.course]}" '
                     f'title="{esc(r.course)} {esc(r.title)}: worth {pct:g}% of your {esc(r.course)} grade">{label}</div>')
    total = float(week_load.get(w, 0) or 0)
    cls = "cwr-week" + (" now" if w == cur else "") + (" past" if cur and w < cur else "")
    cols_html.append(
        f'<div class="{cls}">{"<div class=cwr-ribbon title=this&nbsp;week></div>" if w == cur else ""}'
        f'<div class="cwr-total">{load_word(total)}</div>'
        f'<div class="cwr-stack">{"".join(books)}</div><div class="cwr-plank"></div>'
        f'<div class="cwr-wk">{week_label(w, n_weeks)}</div></div>')

upcoming = week_load[(week_load.index >= (cur or 1)) & (week_load.index <= n_weeks)]
headline = "nothing big left before finals. good time to get ahead on those."
if not upcoming.empty and upcoming.max() > 0:
    heavy_w = int(upcoming.idxmax())
    prep_day = week1 + timedelta(weeks=max(1, heavy_w - lead) - 1)
    prep = ("start studying now." if prep_day <= date.today()
            else f"start studying by {prep_day.strftime('%A, %B %-d').lower()}.")
    word = load_word(float(upcoming[heavy_w]))
    lead_in = (f"<b>{week_label(heavy_w, n_weeks)}</b> is a {word} week" if word not in ("", "light")
               else f"your biggest week ahead is <b>{week_label(heavy_w, n_weeks)}</b>, and it's light")
    headline = f"{lead_in}: {esc(describe(dated[dated['week'] == heavy_w]))}. {prep}"

# ---- collision alerts: big things that land on top of each other
big = dated[dated["type"].isin(BIG_TYPES)].copy()
alerts = []
exact = big[big["exact_date"].fillna(False).astype(bool)].sort_values("due")
for day, grp in exact.groupby("due"):
    if grp["course"].nunique() > 1:
        what = " and ".join(f"{r.course} {r.title}" for r in grp.itertuples())
        alerts.append(f"{what} are both on {pd.Timestamp(day).strftime('%a, %b %-d').lower()}.")
dues = list(exact[["due", "course", "title"]].itertuples(index=False))
seen = set()
for i, a in enumerate(dues):
    window = [b for b in dues[i:] if (b.due - a.due).days <= 2]
    if len(window) >= 3 and window[-1].due not in seen and window[0].due != window[-1].due:
        seen.add(window[-1].due)
        alerts.append(f"{len(window)} big deadlines within 48 hours, "
                      f"{pd.Timestamp(a.due).strftime('%b %-d').lower()} to "
                      f"{pd.Timestamp(window[-1].due).strftime('%b %-d').lower()}: "
                      + ", ".join(f"{b.course} {b.title}" for b in window) + ".")
loose = big[~big["exact_date"].fillna(False).astype(bool) & (big["type"] == "exam") & (big["week"] <= n_weeks)]
for w, grp in loose.groupby("week"):
    if grp["course"].nunique() > 1:
        alerts.append(f"{grp['course'].nunique()} exams in {week_label(int(w), n_weeks)} "
                      f"({', '.join(grp['course'].unique())}). the syllabi don't give exact days, so check canvas.")
alerts_html = "".join(f"<li>{esc(a)}</li>" for a in alerts)

key = "".join(f'<span><i style="background:{color_of[c]}"></i>{esc(c)}</span>' for c in course_list)
st.markdown(f'<div class="cwr"><div class="cwr-next">{headline}</div>'
            f'{f"<ul class=cwr-alerts>{alerts_html}</ul>" if alerts else ""}'
            f'<div class="cwr-page"><div class="cwr-shelf">{"".join(cols_html)}</div></div>'
            f'<div class="cwr-key">{key}</div>'
            f'<p class="cwr-note">each block is one graded item, sized by how much of its class grade it\'s worth, so tall stacks are the weeks that matter most. '
            f'hover a block to see what it is.{" the red bookmark marks this week." if cur else ""}</p></div>',
            unsafe_allow_html=True)

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
cells = base.mark_rect(cornerRadius=4, stroke=T["surface"], strokeWidth=2).encode(
    color=alt.Color("weight:Q", title="% of that class's grade",
                    scale=alt.Scale(domain=[0, vmax], range=RAMP)),
    tooltip=[alt.Tooltip("course:N"), alt.Tooltip("label:N", title="week"),
             alt.Tooltip("weight:Q", title="% of grade", format=".0f"), alt.Tooltip("items:N", title="due")],
)
labels = base.mark_text(fontSize=12).encode(
    text=alt.Text("weight:Q", format=".0f"),
    color=alt.condition(alt.datum.weight > vmax * 0.5, alt.value("#0d1626" if IS_DARK else "#ffffff"), alt.value("#e6edf7" if IS_DARK else "#1f1f1f")),
).transform_filter(alt.datum.weight > 0)

st.subheader("class by class")
st.altair_chart((cells + labels).properties(height=60 * len(courses) + 40), width="stretch")

# ---- crunch weeks callout
totals = dated.groupby("week").agg(weight=("weight_pct", "sum"), n_courses=("course", "nunique"),
                                   items=("title", "count")).sort_values("weight", ascending=False)
mid_term = totals[totals.index <= n_weeks]  # finals week is always brutal; flag the sneaky ones
st.subheader("your three heaviest weeks")
cols = st.columns(3)
for col, (w, r) in zip(cols, mid_term.head(3).iterrows()):
    w = int(w)
    with col:
        st.metric(week_label(w, n_weeks), load_word(r["weight"]) or "light",
                  help="based on how much of each class's grade is due that week")
        prep = max(1, w - lead)
        st.caption(f"{int(r['items'])} things across {int(r['n_courses'])} class"
                   f"{'es' if r['n_courses'] > 1 else ''}. start studying **week {prep}**")
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

# ---- ask your syllabi
st.subheader("ask your syllabi")
sources = st.session_state.get("sources", [])
backend, key = get_backend()
if not sources:
    st.caption("scan your syllabi above, then ask anything: late policies, drops, what's on the final.")
else:
    st.caption(f"gemma reads all {len(sources)} syllabi to answer. try one of these, or ask your own.")
    examples = ["which classes accept late work?", "can i drop any scores?", "which finals are cumulative?"]
    picked = None
    for col, q in zip(st.columns(len(examples)), examples):
        if col.button(q, key=f"ex-{q}", width="stretch"):
            picked = q
    with st.form("ask", clear_on_submit=True, border=False):
        c_q, c_b = st.columns([5, 1])
        typed = c_q.text_input("your question", placeholder="is attendance required in any of my classes?",
                               label_visibility="collapsed")
        asked = c_b.form_submit_button("ask", width="stretch", disabled=not backend)
    question = picked or (typed.strip() if asked else "")
    if question:
        if not backend:
            st.warning("add a gemini api key in the sidebar to ask questions")
        else:
            sig = "|".join(c for c, _ in sources)
            with st.spinner("gemma is reading your syllabi..."):
                try:
                    answer = ask_syllabi(question, sources, backend, key, sig)
                    st.session_state.setdefault("qa", []).insert(0, (question, answer))
                except Exception as e:
                    st.error(f"gemma couldn't answer that: {e}")
    for q, a in st.session_state.get("qa", []):
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant", avatar="📚"):
            st.markdown(a)

# ---- calendar export
st.download_button("📅 add to my calendar (.ics)", make_ics(df, lead), "syllabustrat.ics", "text/calendar")

with tab_todo:
    # ---- Interactive Weekly Survival To-Do List Tab
    st.subheader("✅ Weekly Survival To-Do List")
    available_weeks = sorted([int(w) for w in dated["week"].dropna().unique()])
    if available_weeks:
        selected_w = st.selectbox(
            "Choose a week to plan your attack:", 
            options=available_weeks, 
            format_func=lambda w: week_label(w, n_weeks),
            key="todo_week_selector"
        )
        week_items = dated[dated["week"] == selected_w]
        st.markdown(f"**Tasks for {week_label(selected_w, n_weeks)}**")
        
        completed_count = 0
        total_tasks = len(week_items)
        
        if total_tasks > 0:
            for idx, r in week_items.iterrows():
                key = f"todo_{selected_w}_{idx}_{r['course']}_{r['title']}"
                
                weight_str = f" — *({r['weight_pct']:g}% of grade)*" if pd.notna(r['weight_pct']) else ""
                type_str = f"[{r['type']}] " if pd.notna(r['type']) else ""
                
                checked = st.checkbox(
                    f"**{r['course']}**: {type_str}{r['title']}{weight_str}", 
                    key=key
                )
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
