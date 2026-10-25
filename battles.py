import json
import random
import re

import streamlit as st


def render(get_backend, call_model, parse_json, T, IS_DARK):

    st.markdown("""
    <div style="margin-top: 1rem;">
        <h2>⚔️ Study Battles</h2>
        <p>battle an AI opponent using questions made from what you're studying.</p>
    </div>
    """, unsafe_allow_html=True)

    # -----------------------------
    # Initialize battle state
    # -----------------------------

    if "battle_questions" not in st.session_state:
        st.session_state["battle_questions"] = []

    if "battle_index" not in st.session_state:
        st.session_state["battle_index"] = 0

    if "battle_player_score" not in st.session_state:
        st.session_state["battle_player_score"] = 0

    if "battle_ai_score" not in st.session_state:
        st.session_state["battle_ai_score"] = 0

    if "battle_answered" not in st.session_state:
        st.session_state["battle_answered"] = False

    if "battle_history" not in st.session_state:
        st.session_state["battle_history"] = []

    if "battle_difficulty" not in st.session_state:
        st.session_state["battle_difficulty"] = "medium"

    # -----------------------------
    # No active battle
    # -----------------------------

    if not st.session_state["battle_questions"]:

        st.subheader("start a battle")

        subject = st.text_input(
            "what are you studying?",
            placeholder="linear algebra, data structures, biology..."
        )

        difficulty = st.select_slider(
            "difficulty",
            options=["easy", "medium", "hard"],
            value="medium"
        )

        question_count = st.selectbox(
            "battle length",
            [5, 10],
            format_func=lambda x: f"{x} rounds"
        )

        notes = st.text_area(
            "paste your notes or study material",
            placeholder=(
                "paste lecture notes, a study guide, textbook text, "
                "or anything you want gemma to quiz you on..."
            ),
            height=220
        )

        backend, key = get_backend()

        if st.button(
            "⚔️ start battle",
            type="primary",
            disabled=not backend
        ):

            if not subject.strip():
                st.warning("tell me what subject you're studying first.")
                return

            if not notes.strip():
                st.warning("paste some study material so gemma knows what to quiz you on.")
                return

            prompt = f"""
You are creating a competitive study game.

Create exactly {question_count} multiple choice questions.

SUBJECT:
{subject}

DIFFICULTY:
{difficulty}

STUDY MATERIAL:
{notes[:15000]}

Rules:

- Base the questions on the provided study material.
- Each question must have exactly 4 choices.
- Only one choice can be correct.
- Make wrong choices believable.
- Give a short explanation.
- Difficulty should actually match {difficulty}.
- Do not reveal the answer inside the question.

Return ONLY JSON in this format:

{{
  "questions": [
    {{
      "question": "question here",
      "choices": [
        "choice 1",
        "choice 2",
        "choice 3",
        "choice 4"
      ],
      "answer": 0,
      "explanation": "short explanation",
      "topic": "topic name"
    }}
  ]
}}

answer must be the index of the correct choice: 0, 1, 2, or 3.
"""

            with st.spinner("gemma is building the arena..."):

                try:
                    result = call_model(
                        backend,
                        key,
                        [("text", notes[:15000])],
                        prompt
                    )

                    data = parse_json(result)

                    questions = data.get("questions", [])

                    if not questions:
                        st.error("gemma didn't create any questions. try again.")
                        return

                    st.session_state["battle_questions"] = questions
                    st.session_state["battle_index"] = 0
                    st.session_state["battle_player_score"] = 0
                    st.session_state["battle_ai_score"] = 0
                    st.session_state["battle_answered"] = False
                    st.session_state["battle_history"] = []
                    st.session_state["battle_difficulty"] = difficulty

                    st.rerun()

                except Exception as e:
                    st.error(f"couldn't create the battle: {e}")

        if not backend:
            st.caption("add your gemini api key in the sidebar to start a battle.")

        return

    # -----------------------------
    # Active battle
    # -----------------------------

    questions = st.session_state["battle_questions"]
    index = st.session_state["battle_index"]

    # -----------------------------
    # Battle finished
    # -----------------------------

    if index >= len(questions):

        st.subheader("🏆 battle over")

        player = st.session_state["battle_player_score"]
        ai = st.session_state["battle_ai_score"]

        c1, c2 = st.columns(2)

        c1.metric("you", player)
        c2.metric("AI opponent", ai)

        if player > ai:
            st.success("🏆 you beat the AI!")
        elif player < ai:
            st.error("🤖 the AI got you this time.")
        else:
            st.info("🤝 draw.")

        st.divider()

        st.subheader("battle review")

        for i, result in enumerate(
            st.session_state["battle_history"],
            start=1
        ):

            icon = "✅" if result["correct"] else "❌"

            with st.expander(
                f"{icon} round {i} — {result['topic']}"
            ):

                st.write(result["question"])

                st.write(
                    f"**your answer:** {result['player_answer']}"
                )

                st.write(
                    f"**correct answer:** {result['correct_answer']}"
                )

                st.caption(result["explanation"])

        if st.button("⚔️ battle again", type="primary"):

            st.session_state["battle_questions"] = []
            st.session_state["battle_index"] = 0
            st.session_state["battle_player_score"] = 0
            st.session_state["battle_ai_score"] = 0
            st.session_state["battle_answered"] = False
            st.session_state["battle_history"] = []

            st.rerun()

        return

    # -----------------------------
    # Current round
    # -----------------------------

    q = questions[index]

    total = len(questions)

    st.progress(
        index / total,
        text=f"round {index + 1} of {total}"
    )

    player_col, middle_col, ai_col = st.columns([2, 1, 2])

    with player_col:
        st.metric(
            "🧑 you",
            st.session_state["battle_player_score"]
        )

    with middle_col:
        st.markdown(
            "<h3 style='text-align:center'>VS</h3>",
            unsafe_allow_html=True
        )

    with ai_col:
        st.metric(
            "🤖 AI",
            st.session_state["battle_ai_score"]
        )

    st.divider()

    st.caption(
        f"round {index + 1} • {q.get('topic', 'study material')}"
    )

    st.subheader(q["question"])

    choices = q["choices"]

    selected = st.radio(
        "choose your answer",
        range(len(choices)),
        format_func=lambda x: choices[x],
        index=None,
        disabled=st.session_state["battle_answered"],
        key=f"battle_question_{index}"
    )

    # -----------------------------
    # Submit answer
    # -----------------------------

    if not st.session_state["battle_answered"]:

        if st.button("lock it in 🔒", type="primary"):

            if selected is None:
                st.warning("pick an answer first.")
                return

            correct_index = int(q["answer"])
            correct = selected == correct_index

            if correct:
                st.session_state["battle_player_score"] += 100

            difficulty = st.session_state["battle_difficulty"]

            ai_accuracy = {
                "easy": 0.45,
                "medium": 0.65,
                "hard": 0.82
            }

            ai_correct = (
                random.random()
                < ai_accuracy.get(difficulty, 0.65)
            )

            if ai_correct:
                st.session_state["battle_ai_score"] += 100

            st.session_state["battle_history"].append({
                "question": q["question"],
                "topic": q.get("topic", "general"),
                "correct": correct,
                "player_answer": choices[selected],
                "correct_answer": choices[correct_index],
                "explanation": q.get("explanation", "")
            })

            st.session_state["battle_answered"] = True

            st.rerun()

    # -----------------------------
    # Show result
    # -----------------------------

    else:

        result = st.session_state["battle_history"][-1]

        if result["correct"]:
            st.success("🔥 correct! +100")
        else:
            st.error(
                f"not quite — the answer was "
                f"**{result['correct_answer']}**"
            )

        st.info(result["explanation"])

        if index == total - 1:
            button_text = "see battle results 🏆"
        else:
            button_text = "next round →"

        if st.button(button_text, type="primary"):

            st.session_state["battle_index"] += 1
            st.session_state["battle_answered"] = False

            st.rerun()