import random

import streamlit as st


OPPONENTS = {
    "😎 Chill Rookie": {
        "accuracy": 0.45,
        "description": "laid-back and still learning. a good warm-up.",
        "correct": [
            "okayyy, I see you 👀",
            "nice one. don't get too comfortable.",
            "you got that one. respect.",
        ],
        "wrong": [
            "I might actually have a chance here 😭",
            "rough one. shake it off.",
            "not gonna lie, I thought you'd get that.",
        ],
    },

    "😤 Competitive Rival": {
        "accuracy": 0.68,
        "description": "competitive, confident, and not giving you easy points.",
        "correct": [
            "fine. that was clean.",
            "you're keeping up... for now.",
            "okay, maybe you actually studied.",
        ],
        "wrong": [
            "that's the opening I needed 😤",
            "you can't be giving me free rounds.",
            "scoreboard is looking real nice right now.",
        ],
    },

    "👹 Final Boss": {
        "accuracy": 0.85,
        "description": "knows the material and expects you to keep up.",
        "correct": [
            "acceptable. the next one won't be so easy.",
            "impressive. let's see if you can do it again.",
            "you survived that one.",
        ],
        "wrong": [
            "you came unprepared.",
            "one mistake is all I need.",
            "perhaps you should have studied longer.",
        ],
    },
}


def reset_battle():
    st.session_state["battle_questions"] = []
    st.session_state["battle_index"] = 0
    st.session_state["battle_player_score"] = 0
    st.session_state["battle_ai_score"] = 0
    st.session_state["battle_answered"] = False
    st.session_state["battle_history"] = []
    st.session_state["battle_streak"] = 0
    st.session_state["battle_best_streak"] = 0
    st.session_state["battle_lives"] = 3
    st.session_state["battle_correct"] = 0
    st.session_state["battle_opponent"] = "😤 Competitive Rival"
    st.session_state["battle_last_ai_correct"] = False


def render(get_backend, call_model, parse_json, T, IS_DARK):

    st.markdown("""
    <div style="margin-top: 1rem;">
        <h2>⚔️ Study Battles</h2>
        <p>battle an AI rival using questions generated from what you're studying.</p>
    </div>
    """, unsafe_allow_html=True)

    # --------------------------------
    # Initialize state
    # --------------------------------

    defaults = {
        "battle_questions": [],
        "battle_index": 0,
        "battle_player_score": 0,
        "battle_ai_score": 0,
        "battle_answered": False,
        "battle_history": [],
        "battle_difficulty": "medium",
        "battle_streak": 0,
        "battle_best_streak": 0,
        "battle_lives": 3,
        "battle_correct": 0,
        "battle_opponent": "😤 Competitive Rival",
        "battle_last_ai_correct": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # --------------------------------
    # Battle setup
    # --------------------------------

    if not st.session_state["battle_questions"]:

        st.subheader("enter the arena")

        subject = st.text_input(
            "what are you studying?",
            placeholder="linear algebra, data structures, biology..."
        )

        c1, c2 = st.columns(2)

        with c1:
            difficulty = st.select_slider(
                "question difficulty",
                options=["easy", "medium", "hard"],
                value="medium"
            )

        with c2:
            question_count = st.selectbox(
                "battle length",
                [5, 10],
                format_func=lambda x: f"{x} rounds"
            )

        opponent_name = st.selectbox(
            "choose your opponent",
            list(OPPONENTS.keys()),
            index=1
        )

        opponent = OPPONENTS[opponent_name]

        st.info(
            f"**{opponent_name}** — {opponent['description']} "
            f"Estimated accuracy: {int(opponent['accuracy'] * 100)}%."
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
                st.warning(
                    "paste some study material so gemma knows what to quiz you on."
                )
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
- Base every question on the provided study material.
- Each question must have exactly 4 choices.
- Only one choice can be correct.
- Make the incorrect choices believable.
- Give a short educational explanation.
- Difficulty should actually match {difficulty}.
- Do not reveal the answer inside the question.
- Include the main topic being tested.

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
                        st.error(
                            "gemma didn't create any questions. try again."
                        )
                        return

                    # Reset old game data
                    st.session_state["battle_questions"] = questions
                    st.session_state["battle_index"] = 0
                    st.session_state["battle_player_score"] = 0
                    st.session_state["battle_ai_score"] = 0
                    st.session_state["battle_answered"] = False
                    st.session_state["battle_history"] = []
                    st.session_state["battle_difficulty"] = difficulty

                    st.session_state["battle_streak"] = 0
                    st.session_state["battle_best_streak"] = 0
                    st.session_state["battle_lives"] = 3
                    st.session_state["battle_correct"] = 0
                    st.session_state["battle_opponent"] = opponent_name

                    st.rerun()

                except Exception as e:
                    st.error(f"couldn't create the battle: {e}")

        if not backend:
            st.caption(
                "add your gemini api key in the sidebar to start a battle."
            )

        return

    # --------------------------------
    # Active battle data
    # --------------------------------

    questions = st.session_state["battle_questions"]
    index = st.session_state["battle_index"]

    opponent_name = st.session_state["battle_opponent"]
    opponent = OPPONENTS[opponent_name]

    # Battle ends if questions are finished OR player loses all lives
    battle_finished = (
        index >= len(questions)
        or st.session_state["battle_lives"] <= 0
    )

    # --------------------------------
    # Results screen
    # --------------------------------

    if battle_finished:

        st.subheader("🏆 battle over")

        player = st.session_state["battle_player_score"]
        ai = st.session_state["battle_ai_score"]

        if st.session_state["battle_lives"] <= 0:
            st.error("💀 you ran out of lives!")

        c1, c2 = st.columns(2)

        c1.metric("🧑 you", player)
        c2.metric(opponent_name, ai)

        if player > ai:
            st.success(f"🏆 you defeated {opponent_name}!")
        elif player < ai:
            st.error(f"{opponent_name} wins this one.")
        else:
            st.info("🤝 it's a draw.")

        st.divider()

        # Stats
        answered = len(st.session_state["battle_history"])
        correct = st.session_state["battle_correct"]

        accuracy = (
            correct / answered * 100
            if answered
            else 0
        )

        st.subheader("battle stats")

        s1, s2, s3, s4 = st.columns(4)

        s1.metric(
            "accuracy",
            f"{accuracy:.0f}%"
        )

        s2.metric(
            "correct",
            f"{correct}/{answered}"
        )

        s3.metric(
            "best streak",
            f"🔥 {st.session_state['battle_best_streak']}"
        )

        s4.metric(
            "lives left",
            f"❤️ {st.session_state['battle_lives']}"
        )

        st.divider()

        # Review
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

        # Topics to review
        missed = [
            result
            for result in st.session_state["battle_history"]
            if not result["correct"]
        ]

        if missed:
            st.subheader("🧠 topics to review")

            topics = []

            for result in missed:
                if result["topic"] not in topics:
                    topics.append(result["topic"])

            for topic in topics:
                st.write(f"- {topic}")

        if st.button(
            "⚔️ battle again",
            type="primary"
        ):
            reset_battle()
            st.rerun()

        return

    # --------------------------------
    # Current round
    # --------------------------------

    q = questions[index]
    total = len(questions)

    st.progress(
        index / total,
        text=f"round {index + 1} of {total}"
    )

    # Lives + streak
    top1, top2 = st.columns(2)

    lives = st.session_state["battle_lives"]
    streak = st.session_state["battle_streak"]

    top1.markdown(
        f"### {'❤️' * lives}{'🖤' * (3 - lives)}"
    )

    if streak >= 2:
        top2.markdown(
            f"### 🔥 {streak} answer streak"
        )
    else:
        top2.markdown("### 🔥 build your streak")

    # Scoreboard
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
            opponent_name,
            st.session_state["battle_ai_score"]
        )

    st.divider()

    st.caption(
        f"round {index + 1} • "
        f"{q.get('topic', 'study material')}"
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

    # --------------------------------
    # Answer submission
    # --------------------------------

    if not st.session_state["battle_answered"]:

        if st.button(
            "lock it in 🔒",
            type="primary"
        ):

            if selected is None:
                st.warning("pick an answer first.")
                return

            correct_index = int(q["answer"])
            correct = selected == correct_index

            points = 0

            # -------------------------
            # Player scoring
            # -------------------------

            if correct:

                st.session_state["battle_correct"] += 1
                st.session_state["battle_streak"] += 1

                streak = st.session_state["battle_streak"]

                # Streak multiplier
                if streak >= 5:
                    multiplier = 2.0
                elif streak >= 3:
                    multiplier = 1.5
                elif streak >= 2:
                    multiplier = 1.25
                else:
                    multiplier = 1.0

                points = int(100 * multiplier)

                st.session_state["battle_player_score"] += points

                st.session_state["battle_best_streak"] = max(
                    st.session_state["battle_best_streak"],
                    streak
                )

            else:

                st.session_state["battle_streak"] = 0

                st.session_state["battle_lives"] = max(
                    0,
                    st.session_state["battle_lives"] - 1
                )

            # -------------------------
            # AI turn
            # -------------------------

            ai_correct = (
                random.random()
                < opponent["accuracy"]
            )

            if ai_correct:
                st.session_state["battle_ai_score"] += 100

            st.session_state["battle_last_ai_correct"] = ai_correct

            # -------------------------
            # Save round
            # -------------------------

            st.session_state["battle_history"].append({
                "question": q["question"],
                "topic": q.get("topic", "general"),
                "correct": correct,
                "player_answer": choices[selected],
                "correct_answer": choices[correct_index],
                "explanation": q.get("explanation", ""),
                "points": points,
                "ai_correct": ai_correct,
            })

            st.session_state["battle_answered"] = True

            st.rerun()

    # --------------------------------
    # Round result
    # --------------------------------

    else:

        result = st.session_state["battle_history"][-1]

        if result["correct"]:

            st.success(
                f"🔥 correct! +{result['points']} points"
            )

            streak = st.session_state["battle_streak"]

            if streak == 2:
                st.toast(
                    "🔥 2 streak — 1.25x multiplier!"
                )

            elif streak == 3:
                st.toast(
                    "🔥 3 streak — 1.5x multiplier!"
                )

            elif streak >= 5:
                st.toast(
                    "🔥 ON FIRE — 2x multiplier!"
                )

        else:

            st.error(
                f"❌ not quite — the answer was "
                f"**{result['correct_answer']}**"
            )

            st.caption("you lost a life ❤️")

        st.info(result["explanation"])

        # AI result
        if result["ai_correct"]:
            st.warning(
                f"{opponent_name} got the question right. +100"
            )
        else:
            st.success(
                f"{opponent_name} missed the question."
            )

        # Opponent reaction
        if result["correct"]:
            reaction = random.choice(
                opponent["correct"]
            )
        else:
            reaction = random.choice(
                opponent["wrong"]
            )

        st.markdown(
            f"### 💬 {opponent_name}\n"
            f"> {reaction}"
        )

        if st.session_state["battle_lives"] <= 0:

            button_text = "see battle results 💀"

        elif index == total - 1:

            button_text = "see battle results 🏆"

        else:

            button_text = "next round →"

        if st.button(
            button_text,
            type="primary"
        ):

            st.session_state["battle_index"] += 1
            st.session_state["battle_answered"] = False

            st.rerun()