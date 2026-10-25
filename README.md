# 📡 SyllabuStrat
Syllabus-to-calendar tool that shows you deadlines. SyllabuStrat shows you which weeks will actually hurt.

Every college student gets 4–5 syllabi at the start of the term and never lines them up. So, week 5 sneaks up on you: two midterms and a problem set, worth 45% of your grades, all at once.

Drop in all your syllabi and SyllabuStrat uses **gemma 4** to pull out every exam, project, quiz, and paper, plus how much each one is worth. then it shows you a heatmap of your term weighted by how much of your grade is on the line, not just a pile of dots on a calendar.

## what it does

- **reads any syllabus:** text PDFs, scanned PDFs, screenshots, or phone photos
- **extracts every graded item** with its due date (or "week 5") and its weight. shared categories get split automatically, so "midterms 30%, 2 midterms" becomes 15% each
- **lets you fix anything** in an editable table before it hits the chart
- **heatmap:** classes × weeks, darker = more of your grade due. hover to see what's due
- **🔥 crunch weeks:** your 3 worst weeks of the term, plus when to start prepping for each
- **🧠 gemma game plan:** one click and gemma writes a week-by-week, then day-by-day, plan for surviving your worst week, prioritized by what's worth the most
- **📅 calendar export:** a .ics file with every due date, plus "start prepping" reminders for big exams and projects

## built with

- **gemma 4** (open weights) through the **gemini api**, used twice:
  1. **multimodal extraction:** reads PDFs, screenshots, and phone photos of syllabi into structured JSON
  2. **planning:** turns your schedule into a prep plan for your worst week
- gemma 4 31B on digitalocean serverless inference as a backup path
- `main.py` is our original gemma smoke test
- streamlit, altair, pymupdf, pandas

### why gemma
syllabi and grades are personal. because gemma is open-weight, this whole pipeline can move onto a student's own laptop with no data leaving their device. that's not possible with a closed model.

## run it

```bash
python -m venv venv && source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # then paste your gemini api key (or the digitalocean backup) into .env
python -m streamlit run app.py
```

no key yet? hit **"try it with sample data"** to see the whole flow.

## how it works

1. text PDFs are sent to gemma as text. scanned PDFs and images are sent as images.
2. gemma returns structured JSON for each course: item, type, due date or week, weight %.
3. week-only items are placed on the friday of that week, and dated items are mapped to their term week.
4. weights are summed per course per week to build the heatmap and rank the crunch weeks.

## team

made at hacktoberfest hack day @ uc san diego, oct 2026.
