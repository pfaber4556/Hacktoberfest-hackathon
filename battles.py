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
    st.session_state["local_turn"] = 1

    st.session_state["p1_score"] = 0
    st.session_state["p2_score"] = 0

    st.session_state["p1_lives"] = 3
    st.session_state["p2_lives"] = 3

    st.session_state["p1_streak"] = 0
    st.session_state["p2_streak"] = 0

    st.session_state["p1_best_streak"] = 0
    st.session_state["p2_best_streak"] = 0

    st.session_state["p1_correct"] = 0
    st.session_state["p2_correct"] = 0

    st.session_state["p1_answer"] = None
    st.session_state["p2_answer"] = None

    st.session_state["local_round_complete"] = False
    st.session_state["local_history"] = []


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
        # Local 1v1
        "battle_mode": "🤖 VS AI",
        "p1_name": "Player 1",
        "p2_name": "Player 2",

        "local_turn": 1,

        "p1_score": 0,
        "p2_score": 0,

        "p1_lives": 3,
        "p2_lives": 3,

        "p1_streak": 0,
        "p2_streak": 0,

        "p1_best_streak": 0,
        "p2_best_streak": 0,

        "p1_correct": 0,
        "p2_correct": 0,

        "p1_answer": None,
        "p2_answer": None,

        "local_round_complete": False,
        "local_history": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # --------------------------------
    # Battle setup
    # --------------------------------

    if not st.session_state["battle_questions"]:

        st.subheader("enter the arena")

        battle_mode = st.radio(
            "battle mode",
            ["🤖 VS AI", "👥 Local 1v1"],
            horizontal=True,
        )

        st.session_state["battle_mode"] = battle_mode

        subject = st.text_input(
            "what are you studying?",
            placeholder="linear algebra, data structures, biology..."
        )

        if battle_mode == "👥 Local 1v1":
            p1_col, p2_col = st.columns(2)

            with p1_col:
                player1_name = st.text_input(
                    "player 1",
                    value="Player 1"
                )

            with p2_col:
                player2_name = st.text_input(
                    "player 2",
                    value="Player 2"
                )

            st.session_state["p1_name"] = player1_name
            st.session_state["p2_name"] = player2_name

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

        if battle_mode == "🤖 VS AI":

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

        else:

            opponent_name = None

            st.info(
                "👥 Both players answer the same questions. "
                "Player 1's answer stays hidden until Player 2 locks theirs in."
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

                    # Reset Local 1v1 state
                    st.session_state["local_turn"] = 1

                    st.session_state["p1_score"] = 0
                    st.session_state["p2_score"] = 0

                    st.session_state["p1_lives"] = 3
                    st.session_state["p2_lives"] = 3

                    st.session_state["p1_streak"] = 0
                    st.session_state["p2_streak"] = 0

                    st.session_state["p1_best_streak"] = 0
                    st.session_state["p2_best_streak"] = 0

                    st.session_state["p1_correct"] = 0
                    st.session_state["p2_correct"] = 0

                    st.session_state["p1_answer"] = None
                    st.session_state["p2_answer"] = None

                    st.session_state["local_round_complete"] = False
                    st.session_state["local_history"] = []

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
    if st.session_state["battle_mode"] == "👥 Local 1v1":
        render_local_battle()
        return

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

def local_points(streak):
    """Return points based on the player's current streak."""

    if streak >= 5:
        multiplier = 2.0
    elif streak >= 3:
        multiplier = 1.5
    elif streak >= 2:
        multiplier = 1.25
    else:
        multiplier = 1.0

    return int(100 * multiplier)


def render_local_battle():

    questions = st.session_state["battle_questions"]
    index = st.session_state["battle_index"]

    p1 = st.session_state["p1_name"]
    p2 = st.session_state["p2_name"]

    # -----------------------------
    # Battle finished
    # -----------------------------

    battle_finished = (
        index >= len(questions)
        or st.session_state["p1_lives"] <= 0
        or st.session_state["p2_lives"] <= 0
    )

    if battle_finished:

        st.subheader("🏆 battle over")

        p1_score = st.session_state["p1_score"]
        p2_score = st.session_state["p2_score"]

        c1, c2 = st.columns(2)

        c1.metric(
            f"🧑 {p1}",
            p1_score
        )

        c2.metric(
            f"🧑 {p2}",
            p2_score
        )

        if st.session_state["p1_lives"] <= 0:
            st.error(f"💀 {p1} ran out of lives!")

        if st.session_state["p2_lives"] <= 0:
            st.error(f"💀 {p2} ran out of lives!")

        if p1_score > p2_score:
            st.success(f"🏆 {p1} wins!")
        elif p2_score > p1_score:
            st.success(f"🏆 {p2} wins!")
        else:
            st.info("🤝 it's a draw!")

        st.divider()

        # -----------------------------
        # Final stats
        # -----------------------------

        answered = len(
            st.session_state["local_history"]
        )

        p1_accuracy = (
            st.session_state["p1_correct"] / answered * 100
            if answered
            else 0
        )

        p2_accuracy = (
            st.session_state["p2_correct"] / answered * 100
            if answered
            else 0
        )

        st.subheader("battle stats")

        left, right = st.columns(2)

        with left:

            st.markdown(f"### {p1}")

            st.metric(
                "accuracy",
                f"{p1_accuracy:.0f}%"
            )

            st.metric(
                "best streak",
                f"🔥 {st.session_state['p1_best_streak']}"
            )

            st.metric(
                "lives",
                f"❤️ {st.session_state['p1_lives']}"
            )

        with right:

            st.markdown(f"### {p2}")

            st.metric(
                "accuracy",
                f"{p2_accuracy:.0f}%"
            )

            st.metric(
                "best streak",
                f"🔥 {st.session_state['p2_best_streak']}"
            )

            st.metric(
                "lives",
                f"❤️ {st.session_state['p2_lives']}"
            )

        st.divider()

        # -----------------------------
        # Review
        # -----------------------------

        st.subheader("📚 battle review")

        for i, result in enumerate(
            st.session_state["local_history"],
            start=1
        ):

            with st.expander(
                f"round {i} — {result['topic']}"
            ):

                st.write(result["question"])

                if result["p1_correct"]:
                    p1_icon = "✅"
                else:
                    p1_icon = "❌"

                if result["p2_correct"]:
                    p2_icon = "✅"
                else:
                    p2_icon = "❌"

                st.write(
                    f"{p1_icon} **{p1}:** "
                    f"{result['p1_answer']}"
                )

                st.write(
                    f"{p2_icon} **{p2}:** "
                    f"{result['p2_answer']}"
                )

                st.write(
                    f"**correct answer:** "
                    f"{result['correct_answer']}"
                )

                st.caption(
                    result["explanation"]
                )

        if st.button(
            "⚔️ battle again",
            type="primary",
            key="local_battle_again"
        ):

            reset_battle()
            st.rerun()

        return

    # -----------------------------
    # Current question
    # -----------------------------

    q = questions[index]
    choices = q["choices"]
    total = len(questions)

    st.progress(
        index / total,
        text=f"round {index + 1} of {total}"
    )

    # -----------------------------
    # Scoreboard
    # -----------------------------

    left, middle, right = st.columns(
        [2, 1, 2]
    )

    with left:

        st.markdown(f"### 🧑 {p1}")

        st.metric(
            "score",
            st.session_state["p1_score"]
        )

        st.write(
            "❤️" * st.session_state["p1_lives"]
            + "🖤" * (
                3 - st.session_state["p1_lives"]
            )
        )

        st.caption(
            f"🔥 streak: "
            f"{st.session_state['p1_streak']}"
        )

    with middle:

        st.markdown(
            "<h2 style='text-align:center;'>VS</h2>",
            unsafe_allow_html=True
        )

    with right:

        st.markdown(f"### 🧑 {p2}")

        st.metric(
            "score",
            st.session_state["p2_score"]
        )

        st.write(
            "❤️" * st.session_state["p2_lives"]
            + "🖤" * (
                3 - st.session_state["p2_lives"]
            )
        )

        st.caption(
            f"🔥 streak: "
            f"{st.session_state['p2_streak']}"
        )

    st.divider()

    # -----------------------------
    # ROUND RESULTS
    # -----------------------------

    if st.session_state["local_round_complete"]:

        result = st.session_state["local_history"][-1]

        st.subheader("⚔️ round results")

        r1, r2 = st.columns(2)

        with r1:

            if result["p1_correct"]:
                st.success(
                    f"✅ {p1} +{result['p1_points']}"
                )
            else:
                st.error(
                    f"❌ {p1} lost a life"
                )

        with r2:

            if result["p2_correct"]:
                st.success(
                    f"✅ {p2} +{result['p2_points']}"
                )
            else:
                st.error(
                    f"❌ {p2} lost a life"
                )

        st.write(
            f"**Correct answer:** "
            f"{result['correct_answer']}"
        )

        st.info(
            result["explanation"]
        )

        if (
            st.session_state["p1_lives"] <= 0
            or st.session_state["p2_lives"] <= 0
        ):
            button_text = "see battle results 💀"

        elif index == total - 1:
            button_text = "see battle results 🏆"

        else:
            button_text = "next round →"

        if st.button(
            button_text,
            type="primary",
            key=f"local_next_{index}"
        ):

            st.session_state["battle_index"] += 1

            st.session_state["local_turn"] = 1

            st.session_state["p1_answer"] = None
            st.session_state["p2_answer"] = None

            st.session_state["local_round_complete"] = False

            st.rerun()

        return

    # -----------------------------
    # PLAYER 1 TURN
    # -----------------------------

    if st.session_state["local_turn"] == 1:

        st.caption(
            f"round {index + 1} • "
            f"{q.get('topic', 'study material')}"
        )

        st.subheader(
            f"🎮 {p1}'s turn"
        )

        st.warning(
            f"{p2}, look away 👀"
        )

        st.subheader(q["question"])

        selected = st.radio(
            "choose your answer",
            range(len(choices)),
            format_func=lambda x: choices[x],
            index=None,
            key=f"local_p1_{index}"
        )

        if st.button(
            "lock it in 🔒",
            type="primary",
            key=f"p1_lock_{index}"
        ):

            if selected is None:
                st.warning("pick an answer first.")
                return

            # Save only the index.
            # Do NOT reveal whether it is correct yet.
            st.session_state["p1_answer"] = selected
            st.session_state["local_turn"] = 2

            st.rerun()

        return

    # -----------------------------
    # PLAYER 2 HANDOFF
    # -----------------------------

    if st.session_state["local_turn"] == 2:

        st.subheader("🔐 answer locked")

        st.success(
            f"{p1}'s answer has been hidden."
        )

        st.markdown(
            f"""
            ### Pass the computer to {p2} 👋

            {p2}, press **I'm ready** when {p1}
            isn't looking at the screen.
            """
        )

        if st.button(
            "I'm ready ⚔️",
            type="primary",
            key=f"p2_ready_{index}"
        ):

            st.session_state["local_turn"] = 3
            st.rerun()

        return

    # -----------------------------
    # PLAYER 2 TURN
    # -----------------------------

    if st.session_state["local_turn"] == 3:

        st.caption(
            f"round {index + 1} • "
            f"{q.get('topic', 'study material')}"
        )

        st.subheader(
            f"🎮 {p2}'s turn"
        )

        st.warning(
            f"{p1}, look away 👀"
        )

        st.subheader(q["question"])

        selected = st.radio(
            "choose your answer",
            range(len(choices)),
            format_func=lambda x: choices[x],
            index=None,
            key=f"local_p2_{index}"
        )

        if st.button(
            "lock it in 🔒",
            type="primary",
            key=f"p2_lock_{index}"
        ):

            if selected is None:
                st.warning("pick an answer first.")
                return

            st.session_state["p2_answer"] = selected

            correct_index = int(q["answer"])

            p1_answer = st.session_state["p1_answer"]
            p2_answer = st.session_state["p2_answer"]

            p1_correct = (
                p1_answer == correct_index
            )

            p2_correct = (
                p2_answer == correct_index
            )

            # -----------------------------
            # Player 1 scoring
            # -----------------------------

            if p1_correct:

                st.session_state["p1_correct"] += 1
                st.session_state["p1_streak"] += 1

                p1_points = local_points(
                    st.session_state["p1_streak"]
                )

                st.session_state["p1_score"] += p1_points

                st.session_state["p1_best_streak"] = max(
                    st.session_state["p1_best_streak"],
                    st.session_state["p1_streak"]
                )

            else:

                p1_points = 0

                st.session_state["p1_streak"] = 0

                st.session_state["p1_lives"] = max(
                    0,
                    st.session_state["p1_lives"] - 1
                )

            # -----------------------------
            # Player 2 scoring
            # -----------------------------

            if p2_correct:

                st.session_state["p2_correct"] += 1
                st.session_state["p2_streak"] += 1

                p2_points = local_points(
                    st.session_state["p2_streak"]
                )

                st.session_state["p2_score"] += p2_points

                st.session_state["p2_best_streak"] = max(
                    st.session_state["p2_best_streak"],
                    st.session_state["p2_streak"]
                )

            else:

                p2_points = 0

                st.session_state["p2_streak"] = 0

                st.session_state["p2_lives"] = max(
                    0,
                    st.session_state["p2_lives"] - 1
                )

            # -----------------------------
            # Save round
            # -----------------------------

            st.session_state["local_history"].append({
                "question": q["question"],
                "topic": q.get(
                    "topic",
                    "general"
                ),
                "p1_answer": choices[p1_answer],
                "p2_answer": choices[p2_answer],
                "p1_correct": p1_correct,
                "p2_correct": p2_correct,
                "p1_points": p1_points,
                "p2_points": p2_points,
                "correct_answer": choices[correct_index],
                "explanation": q.get(
                    "explanation",
                    ""
                ),
            })

            st.session_state["local_round_complete"] = True

            st.rerun()