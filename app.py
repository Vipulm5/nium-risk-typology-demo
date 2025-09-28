# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Risk & Typology Scoring Demo", layout="wide")
st.title("🔎 Risk & Typology Scoring — Demo")
st.markdown("Use sample dataset or enter transaction manually. Demo uses dummy data only.")

HIGH_RISK_CORRIDORS = {"Afghanistan", "North Korea", "Iran", "Syria"}

def compute_risk_and_typology(tx):
    """Compute risk score and typology based on simplified rules."""
    risk_points = 0
    reasons = []
    sender = (tx.get("remitter_country") or "").strip()
    receiver = (tx.get("beneficiary_country") or "").strip()
    amount = float(tx.get("amount_usd") or 0)

    if sender in HIGH_RISK_CORRIDORS or receiver in HIGH_RISK_CORRIDORS:
        risk_points += 50; reasons.append("High-risk corridor")
    if amount > 10000:
        risk_points += 20; reasons.append("Large amount (>10,000 USD)")
    elif amount > 5000:
        risk_points += 10; reasons.append("Medium-large amount (5,000–10,000 USD)")

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
    if amount < 10000 and sender != receiver:
        typologies.append("Cross-border retail remittance")
    if not typologies:
        typologies.append("No clear typology detected")

    explanation = "; ".join(reasons) if reasons else "No strong drivers detected by demo rules."
    return {"score": score, "level": level, "emoji": emoji, "typologies": typologies, "explanation": explanation}

@st.cache_data
def load_sample(path="transactions.csv"):
    try:
        df = pd.read_csv(path, dtype=str)
        df.columns = df.columns.str.strip()  # remove extra spaces
        return df
    except Exception as e:
        st.error(f"Could not load sample file: {e}")
        return pd.DataFrame()

df = load_sample()

st.sidebar.header("Mode")
mode = st.sidebar.radio("Choose:", ("Use sample dataset", "Manual input"))

tx = None

# ---------------- Sample dataset mode ----------------
if mode.startswith("Use sample"):
    if df.empty:
        st.warning("No transactions.csv found. Switch to Manual input or add the file.")
    else:
        choice = st.selectbox("Select Transaction ID", options=["-- choose --"] + df["tx_id"].tolist())
        if choice != "-- choose --":
            r = df[df["tx_id"] == choice].iloc[0]
            tx = r.to_dict()

# ---------------- Manual input mode ----------------
else:
    with st.form("manual_form"):
        st.subheader("Remitter Details")
        r1, r2 = st.columns(2)
        with r1:
            remitter_name = st.text_input("Name", "John Doe")
            remitter_address = st.text_input("Address", "123 Main Street")
            remitter_country = st.text_input("Country", "India")
            remitter_country_code = st.text_input("Country Code", "IN")
        with r2:
            purpose = st.text_input("Purpose of Transfer", "Family Support")
            amount_usd = st.number_input("Amount (USD)", min_value=0.0, value=5000.0, step=100.0)

        st.subheader("Beneficiary Details")
        b1, b2 = st.columns(2)
        with b1:
            beneficiary_name = st.text_input("Name", "Jane Doe")
            beneficiary_address = st.text_input("Address", "456 Elm Street")
        with b2:
            beneficiary_country = st.text_input("Country", "USA")
            beneficiary_country_code = st.text_input("Country Code", "US")

        submitted = st.form_submit_button("Load Transaction")
        if submitted:
            tx = {
                "tx_id": "MANUAL_TX_001",
                "remitter_name": remitter_name,
                "remitter_address": remitter_address,
                "remitter_country": remitter_country,
                "remitter_country_code": remitter_country_code,
                "purpose": purpose,
                "amount_usd": amount_usd,
                "beneficiary_name": beneficiary_name,
                "beneficiary_address": beneficiary_address,
                "beneficiary_country": beneficiary_country,
                "beneficiary_country_code": beneficiary_country_code
            }

# ---------------- Scoring & Display ----------------
if st.button("Score Transaction"):
    if not tx:
        st.error("No transaction loaded. Pick one or enter manually.")
    else:
        res = compute_risk_and_typology(tx)
        c1, c2, c3 = st.columns([2,3,4])
        with c1:
            st.metric("Transaction ID", tx.get("tx_id", "—"))
            st.metric("Amount (USD)", f"{float(tx.get('amount_usd',0)):,.2f}")
        with c2:
            st.metric("Risk Level", f"{res['emoji']}  {res['level']}")
            st.progress(int(res["score"])/100)
        with c3:
            st.metric("Risk Score (0–100)", int(res["score"]))
        st.markdown("### Likely Typologies")
        for t in res["typologies"]:
            st.write(f"- {t}")
        st.markdown("### Explanation")
        st.write(res["explanation"])

        out = pd.DataFrame([{
            **tx,
            "risk_score": res["score"],
            "risk_level": res["level"],
            "typologies": "|".join(res["typologies"]),
            "explanation": res["explanation"]
        }])
        st.download_button("Download result (CSV)", out.to_csv(index=False).encode("utf-8"),
                           file_name=f"{tx.get('tx_id')}_score.csv", mime="text/csv")

# ---------------- Dataset Table ----------------
if not df.empty:
    st.markdown("---")
    st.markdown("### Sample Dataset (simulated Metabase)")
    def score_row(row):
        simple_tx = {
            "remitter_country": row["remitter_country"],
            "beneficiary_country": row["beneficiary_country"],
            "amount_usd": row["amount_usd"]
        }
        return compute_risk_and_typology(simple_tx)["score"]
    df["demo_score"] = df.apply(score_row, axis=1)
    st.dataframe(df[[
        "tx_id","remitter_name","remitter_country","beneficiary_name","beneficiary_country","purpose","amount_usd","demo_score"
    ]].sort_values("demo_score", ascending=False))
