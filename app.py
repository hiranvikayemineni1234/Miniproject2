# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date

st.set_page_config(page_title="AI Study Schedule Planner", page_icon="📅", layout="centered")

st.title("📅 AI Study Schedule Planner")

st.markdown("""
Enter topics and basic preferences, then click **Generate Schedule**.
This simple planner balances topics by difficulty and priority.  
""")

# --- Inputs ---
with st.form("planner_form"):
    topics_input = st.text_area(
        "Enter topics (one per line). Optionally add difficulty and priority after a comma.\n"
        "Examples:\n"
        "- Calculus, hard, priority\n"
        "- Biology, medium\n"
        "- History\n",
        height=160
    )
    col1, col2 = st.columns(2)
    with col1:
        exam_date = st.date_input("Exam date", min_value=date.today() + timedelta(days=1))
    with col2:
        daily_hours = st.number_input("Hours available per day", min_value=1.0, max_value=12.0, value=3.0, step=0.5)
    include_weekends = st.checkbox("Include weekends in study plan?", value=True)
    submitted = st.form_submit_button("Generate Schedule")

# --- Helper functions ---
def parse_topics(text_block):
    """
    Parses lines into list of dicts: {"name":..., "difficulty": 1/2/3, "priority": True/False}
    difficulty mapping: easy->1, medium->2, hard->3
    """
    lines = [l.strip() for l in text_block.splitlines() if l.strip()]
    topics = []
    for ln in lines:
        parts = [p.strip().lower() for p in ln.split(",")]
        name = parts[0].title()
        difficulty = 2  # default medium
        priority = False
        if len(parts) > 1:
            for token in parts[1:]:
                if token in ("easy", "e"):
                    difficulty = 1
                elif token in ("medium", "m"):
                    difficulty = 2
                elif token in ("hard", "h"):
                    difficulty = 3
                elif token in ("priority", "p", "important"):
                    priority = True
                # allow "hard, priority" etc.
        topics.append({"name": name, "difficulty": difficulty, "priority": priority})
    return topics

def generate_schedule(topics, exam_date, daily_hours, include_weekends=True):
    """
    topics: list of dicts {"name","difficulty","priority"}
    exam_date: datetime.date (exclusive) -> study until day before exam
    daily_hours: float
    """
    today = date.today()
    if exam_date <= today:
        raise ValueError("Exam date must be in the future.")
    # Build study days list
    study_days = []
    d = today
    while d < exam_date:
        if include_weekends or d.weekday() < 5:  # 0=Mon,6=Sun
            study_days.append(d)
        d += timedelta(days=1)
    total_days = len(study_days)
    if total_days == 0:
        raise ValueError("No study days available (check exam date / weekend option).")

    # Weights: base 1 * difficulty * (2 if priority)
    weights = []
    for t in topics:
        w = 1.0 * t["difficulty"]
        if t["priority"]:
            w *= 2.0
        weights.append(w)
    sum_w = sum(weights)
    total_available_hours = total_days * daily_hours

    # Total hours per topic (proportional)
    remaining_hours = {}
    for t, w in zip(topics, weights):
        allocated = (w / sum_w) * total_available_hours
        # round to 0.5 hours
        allocated = round(allocated * 2) / 2.0
        if allocated < 0.5:
            allocated = 0.5
        remaining_hours[t["name"]] = allocated

    # Allocate per day greedily: each day fill up to daily_hours by topic with most remaining hours
    schedule_rows = []
    for day in study_days:
        hours_left = daily_hours
        # avoid infinite loop: if all remaining < tiny threshold, break
        while hours_left >= 0.25 and any(h > 0.249 for h in remaining_hours.values()):
            # pick topic with max remaining hours
            topic = max(remaining_hours.items(), key=lambda x: x[1])[0]
            if remaining_hours[topic] < 0.25:
                break
            alloc = min(remaining_hours[topic], hours_left)
            # round allocation to nearest 0.25 for nicer splitting
            alloc = round(alloc * 4) / 4.0
            if alloc <= 0:
                break
            schedule_rows.append({
                "Date": day.strftime("%Y-%m-%d"),
                "Topic": topic,
                "Hours": alloc
            })
            remaining_hours[topic] = round((remaining_hours[topic] - alloc) * 4) / 4.0
            hours_left = round((hours_left - alloc) * 4) / 4.0
            # if hours_left tiny, break
            if hours_left < 0.25:
                break

    df = pd.DataFrame(schedule_rows)
    if df.empty:
        # fallback: assign 1 topic per day, even if hours small
        rows = []
        topic_names = list(remaining_hours.keys())
        ti = 0
        for day in study_days:
            rows.append({"Date": day.strftime("%Y-%m-%d"), "Topic": topic_names[ti % len(topic_names)], "Hours": daily_hours})
            ti += 1
        df = pd.DataFrame(rows)

    # Optionally: aggregate multiple rows per date into combined entry
    df = df.groupby(["Date", "Topic"], as_index=False).sum()
    return df, remaining_hours, total_available_hours

# --- Main flow on submit ---
if submitted:
    try:
        topics = parse_topics(topics_input)
        if len(topics) == 0:
            st.warning("Please enter at least one topic (one per line).")
        else:
            df, remaining, total_available_hours = generate_schedule(topics, exam_date, daily_hours, include_weekends)
            st.subheader("📋 Generated Study Plan")
            st.write(f"Study days: **{len(df['Date'].unique())}**  •  Total hours available: **{total_available_hours:.1f}**")
            st.dataframe(df)
            st.markdown("### 🔁 Topic completion snapshot (remaining hours)")
            rem_df = pd.DataFrame([{"Topic": k, "Remaining Hours": v} for k, v in remaining.items()])
            st.table(rem_df)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, "study_plan.csv", "text/csv")

            # Small tips
            st.info("Tip: mark very hard topics as `hard, priority` to get more time automatically.")
    except Exception as e:
        st.error(f"Error: {e}")

# Footer
st.markdown("---")
st.caption("Built with ❤️ — quick & simple AI planner (rule-based).")
