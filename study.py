"""
study mode: drop in a textbook chapter -> gemma 4 turns it into a 2-voice podcast + a slide deck.
the podcast plays with the browser's built-in voices, so there's no extra api or key.
"""

import hashlib
import json

import pymupdf
import streamlit as st
import streamlit.components.v1 as components

MAX_CHARS = 28000  # keeps one chapter under the free-tier limit of ~16k input tokens a minute


def chapter_parts(files, page_from: int, page_to: int) -> tuple[list[tuple], str]:
    """pdf text for the chosen pages, or photos/screenshots of pages as images."""
    parts, notes = [], []
    for f in files:
        data = f.getvalue()
        if f.type == "application/pdf":
            doc = pymupdf.open(stream=data, filetype="pdf")
            lo, hi = max(1, page_from), min(len(doc), page_to)
            text = "\n".join(doc[i].get_text() for i in range(lo - 1, hi))
            if len(text.strip()) > 300:
                if len(text) > MAX_CHARS:
                    notes.append(f"{f.name}: pages {lo}-{hi} were long, so gemma read the first part")
                parts.append(("text", f"TEXTBOOK PAGES {lo}-{hi} ({f.name}):\n{text[:MAX_CHARS]}"))
            else:  # scanned pdf
                for i in range(lo - 1, min(hi, lo + 5)):
                    parts.append(("image", doc[i].get_pixmap(dpi=110).tobytes("jpeg", jpg_quality=82), "image/jpeg"))
        else:
            parts.append(("image", data, f.type))
    return parts, "; ".join(notes)


def build_prompt(level: str, minutes: int) -> str:
    return f"""You are turning a textbook chapter (above) into study material for a college student.
Audience level: {level}. Only use facts from the chapter. Keep every key term, definition, formula and example.

Make two things:
1. "podcast": a lively two-host conversation, about {minutes} minutes when read aloud
   (~{minutes * 140} words). Hosts: "maya" (explains clearly) and "leo" (curious student who asks the
   questions a confused classmate would, and sometimes gets something slightly wrong so maya can fix it).
   Open with what the chapter is about, walk through the ideas in order, use one concrete everyday example,
   and end with a 3-point recap. Natural, warm, no cringe, no sound effects.
2. "slides": 6 to 8 slides that teach the same chapter. Each slide: a short title, 2-4 bullets
   (max 14 words each), and "visual": ONE emoji that fits the slide. Last slide is "quick check" with
   2 questions as bullets and the answers in "notes".

Reply with ONLY valid JSON:
{{"title": "chapter title",
  "podcast": [{{"speaker": "maya", "line": "..."}}, {{"speaker": "leo", "line": "..."}}],
  "slides": [{{"title": "...", "bullets": ["..."], "visual": "🧪", "notes": "optional"}}]}}"""


def esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def podcast_player(lines: list[dict], T: dict, is_dark: bool) -> str:
    data = json.dumps([{"s": l.get("speaker", "maya").lower(), "t": l.get("line", "")} for l in lines])
    accent = "#3987e5" if is_dark else "#2a78d6"
    accent2 = "#d95926" if is_dark else "#eb6834"
    return f"""
<div id="pod">
  <div class="bar">
    <button id="play">▶ play podcast</button>
    <button id="stop">■</button>
    <label>speed <select id="rate"><option>0.9</option><option selected>1</option><option>1.15</option>
      <option>1.3</option></select></label>
    <span id="status"></span>
  </div>
  <div id="lines"></div>
</div>
<style>
  body {{ margin:0; font-family: system-ui, sans-serif; color:{T['ink']}; background:transparent; }}
  .bar {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:10px; }}
  button {{ font: inherit; font-weight:600; padding:8px 14px; border-radius:8px; cursor:pointer;
    border:1px solid {T['rule']}; background:{T['paper']}; color:{T['ink']}; }}
  #play {{ background:{accent}; color:#fff; border-color:{accent}; }}
  button:focus-visible, select:focus-visible {{ outline:2px solid {accent}; outline-offset:2px; }}
  select {{ font:inherit; background:{T['paper']}; color:{T['ink']}; border:1px solid {T['rule']}; border-radius:6px; }}
  label, #status {{ font-size:.9rem; color:{T['muted']}; }}
  #lines {{ max-height:360px; overflow:auto; border:1px solid {T['rule']}; border-radius:8px;
    background:{T['paper']}; padding:6px 12px; }}
  .ln {{ padding:7px 8px; border-radius:6px; line-height:1.45; }}
  .ln b {{ text-transform:lowercase; margin-right:6px; }}
  .maya b {{ color:{accent}; }} .leo b {{ color:{accent2}; }}
  .ln.on {{ background:{T['rule']}; }}
</style>
<script>
const L = {data};
const box = document.getElementById('lines');
L.forEach((l, i) => {{
  const d = document.createElement('div'); d.className = 'ln ' + l.s; d.id = 'l' + i;
  d.innerHTML = '<b>' + l.s + '</b>'; d.appendChild(document.createTextNode(l.t)); box.appendChild(d);
}});
const synth = window.speechSynthesis; let idx = 0, playing = false, voices = [];
function loadVoices() {{
  const en = synth.getVoices().filter(v => v.lang && v.lang.startsWith('en'));
  voices = en.length ? en : synth.getVoices();
}}
loadVoices(); if (synth) synth.onvoiceschanged = loadVoices;
function voiceFor(s) {{
  if (!voices.length) return null;
  const pick = n => voices.find(v => v.name.toLowerCase().includes(n));
  return s === 'maya' ? (pick('samantha') || pick('female') || voices[0])
                      : (pick('daniel') || pick('alex') || pick('male') || voices[Math.min(1, voices.length - 1)]);
}}
function mark(i) {{
  document.querySelectorAll('.ln').forEach(e => e.classList.remove('on'));
  const el = document.getElementById('l' + i); if (el) {{ el.classList.add('on'); el.scrollIntoView({{block:'nearest'}}); }}
}}
function speak() {{
  if (!playing || idx >= L.length) {{ playing = false; document.getElementById('play').textContent = '▶ play podcast';
    document.getElementById('status').textContent = idx >= L.length ? 'done' : ''; return; }}
  const u = new SpeechSynthesisUtterance(L[idx].t); const v = voiceFor(L[idx].s); if (v) u.voice = v;
  u.rate = parseFloat(document.getElementById('rate').value); u.pitch = L[idx].s === 'maya' ? 1.1 : 0.9;
  mark(idx); document.getElementById('status').textContent = (idx + 1) + ' / ' + L.length;
  u.onend = () => {{ idx++; speak(); }}; synth.speak(u);
}}
document.getElementById('play').onclick = () => {{
  if (!synth) {{ document.getElementById('status').textContent = "this browser can't read aloud"; return; }}
  if (playing) {{ synth.pause(); playing = false; document.getElementById('play').textContent = '▶ resume'; return; }}
  if (synth.paused) {{ synth.resume(); playing = true; document.getElementById('play').textContent = '❚❚ pause'; return; }}
  if (idx >= L.length) idx = 0;
  playing = true; document.getElementById('play').textContent = '❚❚ pause'; speak();
}};
document.getElementById('stop').onclick = () => {{ playing = false; synth.cancel(); idx = 0; mark(-1);
  document.getElementById('play').textContent = '▶ play podcast'; document.getElementById('status').textContent = ''; }};
box.addEventListener('click', e => {{ const el = e.target.closest('.ln'); if (!el) return;
  synth.cancel(); idx = parseInt(el.id.slice(1)); playing = true; document.getElementById('play').textContent = '❚❚ pause'; speak(); }});
</script>"""


def slide_deck(slides: list[dict], title: str, T: dict, is_dark: bool) -> str:
    data = json.dumps(slides)
    accent = "#3987e5" if is_dark else "#2a78d6"
    return f"""
<div id="deck">
  <div id="slide"></div>
  <div class="nav"><button id="prev" aria-label="previous slide">‹</button><span id="count"></span>
    <button id="next" aria-label="next slide">›</button><button id="notes">show answers</button></div>
</div>
<style>
  body {{ margin:0; font-family: system-ui, sans-serif; color:{T['ink']}; background:transparent; }}
  #slide {{ aspect-ratio: 16/9; max-height: 420px; width:100%; box-sizing:border-box; border-radius:10px;
    border:1px solid {T['rule']}; padding: 4% 6%; display:grid; grid-template-columns: 1fr auto; gap: 4%;
    align-items:center; background-color:{T['paper']};
    background-image: linear-gradient(to right, transparent 28px, {T['margin']} 28px, {T['margin']} 30px, transparent 30px),
      repeating-linear-gradient(to bottom, transparent 0 31px, {T['rule']} 31px 32px); }}
  h2 {{ font-family: Literata, Georgia, serif; font-size: clamp(1.2rem, 3.4vw, 2rem); margin:0 0 .6em; }}
  ul {{ margin:0; padding-left:1.1em; font-size: clamp(.9rem, 2vw, 1.15rem); line-height:1.5; }}
  .vis {{ font-size: clamp(3rem, 10vw, 6.5rem); }}
  .kicker {{ font-size:.85rem; color:{T['muted']}; margin-bottom:.4em; }}
  .ans {{ margin-top:.8em; font-size:.95rem; color:{T['muted']}; display:none; }}
  .nav {{ display:flex; gap:10px; align-items:center; justify-content:center; margin-top:10px; }}
  button {{ font: inherit; font-weight:600; padding:6px 14px; border-radius:8px; cursor:pointer;
    border:1px solid {T['rule']}; background:{T['paper']}; color:{T['ink']}; }}
  button:focus-visible {{ outline:2px solid {accent}; outline-offset:2px; }}
  #count {{ color:{T['muted']}; font-size:.9rem; min-width:56px; text-align:center; }}
</style>
<script>
const S = {data}; let i = 0; const esc = s => String(s).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}})[c]);
function show() {{
  const s = S[i] || {{}}; const notes = s.notes ? '<div class="ans" id="ans">' + esc(s.notes) + '</div>' : '';
  document.getElementById('slide').innerHTML = '<div><div class="kicker">' + esc({json.dumps(title)}) + '</div><h2>' + esc(s.title || '') +
    '</h2><ul>' + (s.bullets || []).map(b => '<li>' + esc(b) + '</li>').join('') + '</ul>' + notes + '</div>' +
    '<div class="vis" aria-hidden="true">' + esc(s.visual || '') + '</div>';
  document.getElementById('count').textContent = (i + 1) + ' / ' + S.length;
  document.getElementById('notes').style.display = s.notes ? '' : 'none';
}}
document.getElementById('prev').onclick = () => {{ i = Math.max(0, i - 1); show(); }};
document.getElementById('next').onclick = () => {{ i = Math.min(S.length - 1, i + 1); show(); }};
document.getElementById('notes').onclick = () => {{ const a = document.getElementById('ans'); if (a) a.style.display = 'block'; }};
document.addEventListener('keydown', e => {{ if (e.key === 'ArrowRight') document.getElementById('next').click();
  if (e.key === 'ArrowLeft') document.getElementById('prev').click(); }});
show();
</script>"""


SAMPLE_STUDY = {
    "title": "supply, demand, and equilibrium",
    "podcast": [
        {"speaker": "maya", "line": "today's chapter is about why prices land where they do: supply, demand, and equilibrium."},
        {"speaker": "leo", "line": "okay so demand is just how much people want something, right?"},
        {"speaker": "maya", "line": "close! demand is how much people are willing and able to buy at each price. the law of demand says when price goes up, quantity demanded goes down."},
        {"speaker": "leo", "line": "and supply is the opposite? higher price, sellers make more?"},
        {"speaker": "maya", "line": "exactly. the law of supply: higher prices mean sellers are willing to supply more."},
        {"speaker": "leo", "line": "so where do they meet?"},
        {"speaker": "maya", "line": "at equilibrium, the price where quantity supplied equals quantity demanded. think boba: if a shop charges twelve dollars, lines vanish and tea goes to waste. that's a surplus."},
        {"speaker": "leo", "line": "and if it's two dollars, the line wraps around the block. shortage."},
        {"speaker": "maya", "line": "right, and both push the price back toward equilibrium. recap: demand slopes down, supply slopes up, and equilibrium is where they cross."},
    ],
    "slides": [
        {"title": "the big question", "bullets": ["why do prices land where they do?", "two forces: buyers and sellers"], "visual": "🧋"},
        {"title": "law of demand", "bullets": ["price up → quantity demanded down", "willing AND able to buy"], "visual": "📉"},
        {"title": "law of supply", "bullets": ["price up → quantity supplied up", "higher price = more reason to sell"], "visual": "📈"},
        {"title": "equilibrium", "bullets": ["where supply meets demand", "quantity supplied = quantity demanded"], "visual": "⚖️"},
        {"title": "surplus vs shortage", "bullets": ["price too high → surplus", "price too low → shortage", "both push back to equilibrium"], "visual": "🔁"},
        {"title": "quick check", "bullets": ["what happens to quantity demanded when price rises?", "what is a shortage?"],
         "visual": "✅", "notes": "it falls (law of demand). quantity demanded is greater than quantity supplied."},
    ],
}


def render(get_backend, call_model, parse_json, T: dict, is_dark: bool):
    st.subheader("study a chapter")
    st.caption("drop in a textbook chapter. gemma 4 reads it and makes a two-host podcast and a slide deck "
               "that teach the same ideas.")
    files = st.file_uploader("textbook chapter (pdf, or photos of the pages)", type=["pdf", "png", "jpg", "jpeg", "webp"],
                             accept_multiple_files=True, key="study_files")
    c1, c2, c3 = st.columns(3)
    page_from = c1.number_input("from page", 1, 2000, 1)
    page_to = c2.number_input("to page", 1, 2000, 15, help="for a whole textbook pdf, pick just one chapter")
    level = c3.selectbox("explain it for", ["first time seeing this", "exam review", "explain like i'm 12"])
    minutes = st.select_slider("podcast length", options=[2, 3, 5, 7], value=3, format_func=lambda m: f"{m} min")
    b1, b2 = st.columns([1.6, 3])
    go = b1.button("🎧 make my study set", type="primary", disabled=not files)
    if b2.button("try a sample chapter"):
        st.session_state["study"] = SAMPLE_STUDY

    if go:
        backend, key = get_backend()
        if not backend:
            st.warning("add a gemini api key in the sidebar first")
            st.stop()
        parts, note = chapter_parts(files, int(page_from), int(page_to))
        sig = hashlib.md5(b"".join(f.getvalue() for f in files) + f"{page_from}{page_to}{level}{minutes}".encode()).hexdigest()
        cache = st.session_state.setdefault("study_cache", {})
        if sig not in cache:
            with st.spinner("gemma is reading the chapter and writing your podcast + slides..."):
                try:
                    cache[sig] = parse_json(call_model(backend, key, parts, build_prompt(level, minutes)))
                except Exception as e:
                    st.error(f"gemma couldn't finish that: {e}")
                    st.stop()
        st.session_state["study"] = cache[sig]
        if note:
            st.caption(note)

    study = st.session_state.get("study")
    if not study:
        return
    st.markdown(f"### {esc(study.get('title', 'your chapter'))}")
    tab_pod, tab_slides = st.tabs(["🎧 podcast", "🖼️ slides"])
    with tab_pod:
        components.html(podcast_player(study.get("podcast", []), T, is_dark), height=470, scrolling=False)
        st.caption("uses your browser's built-in voices. click any line to jump there.")
        script = "\n\n".join(f"{l.get('speaker', '')}: {l.get('line', '')}" for l in study.get("podcast", []))
        st.download_button("download the script", script, "podcast-script.txt", "text/plain")
    with tab_slides:
        components.html(slide_deck(study.get("slides", []), study.get("title", ""), T, is_dark), height=520)
        st.caption("use the arrows or your arrow keys.")