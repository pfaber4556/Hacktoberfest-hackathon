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
python -m streamlit run app.py
