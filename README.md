# 📡 SyllabuStrat

**Plan your quarter. Study smarter. Battle your friends.**

SyllabuStrat is an AI-powered study companion built with **Gemma 4** that helps students turn scattered course material into an organized plan for the quarter and interactive ways to study.

Instead of manually digging through syllabi, textbooks, and notes, students can use SyllabuStrat to understand when their busiest weeks are coming, generate study material from textbook chapters, and test their knowledge through competitive Study Battles.

---

## ✨ Features

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

## 🧠 How Gemma 4 Is Used

Gemma is the intelligence behind SyllabuStrat.

It transforms unstructured academic material into useful study tools throughout the app.

### 1. Syllabus Understanding

Gemma reads syllabus content and extracts important information such as:

- Assignments
- Exams
- Projects
- Due dates
- Grade weights
- Course information

### 2. Study Planning

After understanding a student's courses, SyllabuStrat uses that information to help identify difficult weeks and create actionable study plans.

### 3. Textbook Transformation

Gemma helps transform textbook chapters into alternative study formats such as podcast-style content and study slides.

### 4. Study Battles

Gemma turns a student's notes into competitive multiple-choice questions.

For each question, Gemma generates:

- The question
- Four answer choices
- The correct answer
- An explanation
- The topic being tested

Questions are grounded in the study material supplied by the student so the battle stays relevant to what they are actually learning.

---

## 🛠️ Built With

- **Python**
- **Streamlit**
- **Gemma 4**
- **Google Gemini API**
- **DigitalOcean Serverless Inference** as a backup Gemma backend
- **PyMuPDF** for PDF processing
- **Pandas**
- **Altair**
- **python-dotenv**

---

## 🚀 Running SyllabuStrat Locally

### 1. Clone the Repository

```bash
git clone git@github.com:pfaber4556/Hacktoberfest-hackathon.git
cd Hacktoberfest-hackathon
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Add Your API Key

Create a `.env` file in the project directory:

```env
GEMINI_API_KEY=your_key_here
```

SyllabuStrat can also use a DigitalOcean-hosted Gemma model as a backup:

```env
MODEL_ACCESS_KEY=your_key_here
```

> ⚠️ Never commit your `.env` file or API keys to GitHub.

### 5. Start the App

```bash
python3 -m streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal.

---

## 🎮 How to Use Study Battles

1. Open **⚔️ Study Battles**
2. Choose **🤖 VS AI** or **👥 Local 1v1**
3. Enter the subject you're studying
4. Choose a question difficulty
5. Choose the number of rounds
6. Paste your notes or study material
7. Start the battle
8. Gemma generates questions based on your material
9. Compete, build streaks, protect your lives, and review what you missed

---

## 💡 Why We Built It

College students often have all the information they need to succeed, but that information is scattered across syllabi, textbooks, assignments, notes, and calendars.

SyllabuStrat brings those pieces together.

Instead of using AI simply to answer questions for students, SyllabuStrat uses AI to help students **plan, learn, practice, and compete**.

The idea is simple:

> **Know what's coming. Learn the material. Prove you know it.**

---

## 🔮 What's Next

We're continuing to explore ways to make studying more interactive and personalized.

Possible future features include:

- 🌐 Online 1v1 Study Battles
- ⏱️ Timed battle rounds
- 🧠 Personalized Gemma post-battle study reports
- 🏆 Leaderboards and achievements
- 🔥 Long-term study streaks
- 👥 Multiplayer study rooms
- 🎯 Adaptive question difficulty based on performance

---

## 📡 SyllabuStrat

**Turn your semester into a strategy.**
