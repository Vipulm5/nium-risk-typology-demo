# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Risk & Typology Scoring Demo", layout="wide")
st.title("🔎 Risk & Typology Scoring — Demo")
st.markdown("Pick a transaction (simulated Metabase) or paste details. Demo uses only dummy data.")

HIGH_RISK_CORRIDORS = {"Afghanistan", "North Korea", "Iran", "Syria"}

def compute_risk_and_typology(tx):
    risk_points = 0
    reasons = []
    sender = (tx.get("sender_country") or "").strip()
    receiver = (tx.get("receiver_country") or "").strip()
    amount = float(tx.get("amount") or 0)
    prev_tx = int(tx.get("prev_tx_7d") or 0)
    entity = (tx.get("entity_type") or "").strip().lower()

    if sender in HIGH_RISK_CORRIDORS or receiver in HIGH_RISK_CORRIDORS:
        risk_points += 50; reasons.append("High-risk corridor")
    if amount > 10000:
        risk_points += 20; reasons.append("Large amount (>10,000 USD)")
    elif amount > 5000:
        risk_points += 10; reasons.append("Medium-large amount (5,000–10,000 USD)")
    if prev_tx > 5:
        risk_points += 15; reasons.append(f"High frequency: {prev_tx} tx in 7d")
    if entity == "high-risk industry":
        risk_points += 20; reasons.append("High-risk industry")
    if sender != receiver and amount > 10000:
        risk_points += 10; reasons.append("Large cross-border amount")

    score = min(100, risk_points)
    if score < 30:
        level, emoji = "Low", "🟢"
    elif score < 60:
        level, emoji = "Medium", "🟠"
    else:
        level, emoji = "High", "🔴"

    typologies = []
    if amount > 10000 and (sender in HIGH_RISK_CORRIDORS or receiver in HIGH_RISK_CORRIDORS):
        typologies.append("Potential layering / cross-border structuring")
    if prev_tx > 5 and amount < 10000:
        typologies.append("Structuring / Smurfing")
    if entity == "business" and sender != receiver and amount > 5000:
        typologies.append("Potential funnel account")
    if not typologies:
        typologies.append("No clear typology detected")

    explanation = "; ".join(reasons) if reasons else "No strong drivers detected by demo rules."
    return {"score": score, "level": level, "emoji": emoji, "typologies": typologies, "explanation": explanation}

# --- load sample CSV if present in repo / same folder
@st.cache_data
def load_sample(path="transactions.csv"):
    try:
        return pd.read_csv(path, dtype={"tx_id": str})
    except:
        return pd.DataFrame()

df = load_sample()

st.sidebar.header("Mode")
mode = st.sidebar.radio("Choose:", ("Use sample dataset (simulated Metabase)", "Manual input"))

tx = None
if mode.startswith("Use sample"):
    if df.empty:
        st.warning("No transactions.csv found. Create it in the repo or switch to Manual input.")
    else:
        choice = st.selectbox("Select Transaction ID", options=["-- choose --"] + df["tx_id"].tolist())
        if choice and choice != "-- choose --":
            r = df[df["tx_id"] == choice].iloc[0]
            tx = {
                "tx_id": r["tx_id"], "sender_country": r["sender_country"],
                "receiver_country": r["receiver_country"], "amount": r["amount"],
                "prev_tx_7d": int(r["prev_tx_7d"]), "entity_type": r["entity_type"]
            }
else:
    with st.form("manual_form"):
        c1, c2 = st.columns(2)
        with c1:
            tx_id = st.text_input("Transaction ID", "TX_MANUAL_001")
            sender_country = st.text_input("Sender Country", "India")
            amount = st.number_input("Amount (USD)", min_value=0.0, value=5000.0, step=100.0)
            entity_type = st.selectbox("Entity Type", ["Individual", "Business", "High-Risk Industry"])
        with c2:
            receiver_country = st.text_input("Receiver Country", "USA")
            prev_tx = st.number_input("Previous tx (7 days)", min_value=0, value=1, step=1)
        submitted = st.form_submit_button("Load transaction")
        if submitted:
            tx = {"tx_id": tx_id, "sender_country": sender_country, "receiver_country": receiver_country,
                  "amount": amount, "prev_tx_7d": prev_tx, "entity_type": entity_type }

if st.button("Score Transaction"):
    if not tx:
        st.error("No transaction loaded. Pick one or enter manually.")
    else:
        res = compute_risk_and_typology(tx)
        c1, c2, c3 = st.columns([2,3,4])
        with c1:
            st.metric("Transaction ID", tx.get("tx_id", "—"))
            st.metric("Amount (USD)", f"{tx.get('amount', 0):,.2f}")
        with c2:
            st.metric("Risk Level", f"{res['emoji']}  {res['level']}")
            st.progress(int(res["score"]) / 100)
        with c3:
            st.metric("Risk Score (0–100)", int(res["score"]))
        st.markdown("### Likely Typologies")
        for t in res["typologies"]:
            st.write(f"- {t}")
        st.markdown("### Explanation")
        st.write(res["explanation"])

        out = pd.DataFrame([{
            "tx_id": tx.get("tx_id"), "sender_country": tx.get("sender_country"),
            "receiver_country": tx.get("receiver_country"), "amount": tx.get("amount"),
            "prev_tx_7d": tx.get("prev_tx_7d"), "entity_type": tx.get("entity_type"),
            "risk_score": res["score"], "risk_level": res["level"],
            "typologies": "|".join(res["typologies"]), "explanation": res["explanation"]
        }])
        st.download_button("Download result (CSV)", out.to_csv(index=False).encode("utf-8"),
                           file_name=f"{tx.get('tx_id')}_score.csv", mime="text/csv")

# Optional dataset view
if not df.empty:
    st.markdown("---")
    st.markdown("### Sample Dataset (simulated Metabase)")
    def score_row(r): return compute_risk_and_typology(r)["score"]
    df["demo_score"] = df.apply(score_row, axis=1)
    st.dataframe(df[["tx_id","sender_country","receiver_country","amount","prev_tx_7d","entity_type","demo_score"]].sort_values("demo_score", ascending=False))
