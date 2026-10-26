# 📡 SyllabuStrat

**A syllabus-to-calendar tool that shows you deadlines. SyllabuStrat shows you which weeks will actually hurt.**

---

## **💡 The Problem & The Solution**

Every college student gets 4 to 5 syllabi at the start of the term and never lines them up. As a result, Week 5 sneaks up on you—landing you with two midterms and a problem set worth 45% of your grades all at once. 

**SyllabuStrat** solves this. Drop in all your syllabi, and it uses **Gemma 4** to pull out every exam, project, quiz, and paper, complete with how much each one is worth. Instead of a messy pile of dots on a calendar, you get a heatmap of your term weighted by actual grade impact.

---

## **✨ What It Does**

* **Universal Ingestion:** Reads any syllabus format—text PDFs, scanned PDFs, screenshots, or phone photos.
* **Smart Extraction:** Extracts every graded item with its due date (or week) and weight. Shared categories split automatically (e.g., *“midterms 30%, 2 midterms”* becomes 15% each).
* **Editable Table:** Lets you review and fix any extracted details in an interactive table before they hit the chart.
* **Weighted Heatmap:** A classes × weeks grid where darker shades mean more of your grade is due. Hover to see what's due.
* **🔥 Crunch Weeks:** Highlights your 3 worst weeks of the term, plus when to start prepping for each.
* **🧠 Gemma Game Plan:** One click generates a week-by-week and day-by-day survival plan for your worst week, prioritized by grade weight.
* **📅 Calendar Export:** Generates a `.ics` file with every due date, plus proactive "start prepping" reminders for major exams and projects.

---

## **🛠️ Built With**

* **AI & Models:** 
  * **Gemma 4** (open weights) through the Gemini API for multimodal extraction and planning.
  * **Gemma 4 31B** on DigitalOcean serverless inference as a backup path.
  * `main.py` for the original Gemma smoke test.
* **Frameworks & Libraries:** Streamlit, Altair, PyMuPDF, Pandas.

---

## **🔒 Why Gemma?**

Syllabi and grades are personal. Because Gemma is open-weight, this entire pipeline can run locally on a student's own laptop with zero data leaving their device—a privacy standard that is impossible with closed models.

---

## **🚀 Run It**

```bash
python -m venv venv && source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # Then paste your Gemini API key (or DigitalOcean backup) into .env
python -m streamlit run app
```
---

## **✨ Features**

### 📅 Plan My Quarter

Upload one or more course syllabi and let Gemma analyze them.

SyllabuStrat can:

- Extract exams, quizzes, projects, papers, presentations, and homework
- Identify due dates and course-grade weights
- Organize assignments by week
- Visualize workload across the quarter
- Highlight upcoming crunch weeks
- Generate an AI-powered game plan
- Create weekly study checklists
- Let students ask questions about their syllabi
- Track assignment completion
- Export important dates to a calendar

The goal is to make it immediately obvious **which weeks are going to be the hardest before they happen**.

---

### 🎧 Study a Chapter

Upload textbook material and turn a chapter into easier-to-digest study resources.

Using Gemma, SyllabuStrat can transform course material into:

- 🎙️ Podcast-style study content
- 🖥️ Study slides
- 📚 More digestible explanations of textbook material

This gives students another way to learn when simply rereading a textbook isn't working.

---

### ⚔️ Study Battles

Turn your notes or study material into a competitive quiz game.

Gemma generates multiple-choice questions directly from the material you provide.

#### 🤖 VS AI

Battle an AI opponent while studying.

Choose between opponents with different skill levels and personalities:

- 😎 **Chill Rookie** — a relaxed warm-up opponent
- 😤 **Competitive Rival** — a more challenging opponent
- 👹 **Final Boss** — the toughest opponent

Battles include:

- ❤️ Lives
- 🔥 Answer streaks
- ✨ Streak score multipliers
- 💬 Opponent reactions and trash talk
- 📊 Accuracy and battle statistics
- 📚 Post-battle question review

The longer your streak, the more points each correct answer is worth.

#### 👥 Local 1v1

Challenge a friend on the same device.

Both players answer the **same Gemma-generated questions**, but Player 1's answer stays hidden until Player 2 locks in their answer.

Each player has their own:

- Score
- ❤️ Lives
- 🔥 Streak
- Streak multiplier
- Accuracy
- Battle statistics

After both players answer, the correct answer and explanation are revealed.

This turns studying into a head-to-head game while preventing the second player from seeing the first player's answer.

---
