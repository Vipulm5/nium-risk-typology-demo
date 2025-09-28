# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Risk & Typology Scoring Demo", layout="wide")
st.title("🔎 Risk & Typology Scoring")
st.markdown("Use sample dataset, upload CSV, or enter transaction manually. Demo uses dummy data only.")

# ---------------- Country Risk ----------------
HIGH_RISK_COUNTRIES = {"Afghanistan", "North Korea", "Iran", "Syria", "Russia"}
MEDIUM_RISK_COUNTRIES = {"Pakistan", "Yemen", "Iraq", "Libya"}

MAJOR_COUNTRIES = [
    "India","USA","UK","Singapore","Germany","France","China","Russia","Afghanistan",
    "North Korea","Iran","Syria","Pakistan","Brazil","Canada","Australia","South Africa","Japan"
]

# ---------------- Typology & OFAC example lists ----------------
HIGH_RISK_PURPOSES = [
    "Hawala transfer", "Cryptocurrency exchange", "High-value cash", "Suspicious payment", "Trade-based money laundering"
]

# ---------------- Risk calculation ----------------
def compute_risk_and_typology(tx):
    risk_points = 0
    reasons = []

    sender = tx.get("remitter_country","").strip()
    receiver = tx.get("beneficiary_country","").strip()
    amount = float(tx.get("amount_usd") or 0)
    purpose = tx.get("purpose","").strip().lower()
    sender_type = tx.get("account_type","Individual").lower()
    receiver_type = tx.get("beneficiary_account_type","Individual").lower()

    # Country risk
    if sender in HIGH_RISK_COUNTRIES or receiver in HIGH_RISK_COUNTRIES:
        risk_points += 50
        reasons.append(f"High-risk / sanctioned country: {sender} -> {receiver}")
    elif sender in MEDIUM_RISK_COUNTRIES or receiver in MEDIUM_RISK_COUNTRIES:
        risk_points += 20
        reasons.append(f"Medium-risk country: {sender} -> {receiver}")

    # Amount-based risk considering sender & beneficiary type
    if sender_type == "individual" and receiver_type == "individual":
        if amount > 10000: risk_points += 20; reasons.append("High amount (>10k USD) for Individual->Individual")
        elif amount > 5000: risk_points += 10; reasons.append("Medium amount (5k-10k USD) for Individual->Individual")
    elif sender_type == "company" and receiver_type == "company":
        if amount > 100000: risk_points += 20; reasons.append("High amount (>100k USD) for Company->Company")
        elif amount > 50000: risk_points += 10; reasons.append("Medium amount (50k-100k USD) for Company->Company")
    else:  # Individual->Company or Company->Individual
        if amount > 50000: risk_points += 20; reasons.append(f"High amount (>50k USD) for {sender_type.title()}->{receiver_type.title()}")
        elif amount > 20000: risk_points += 10; reasons.append(f"Medium amount (20k-50k USD) for {sender_type.title()}->{receiver_type.title()}")

    # Purpose-based risk
    if any(hrp.lower() in purpose for hrp in HIGH_RISK_PURPOSES):
        risk_points += 20
        reasons.append(f"High-risk purpose detected: {purpose}")

    # Cross-border
    if sender != receiver:
        risk_points += 10
        reasons.append("Cross-border transaction")

    # Determine risk level
    score = min(100, risk_points)
    if score < 30:
        level, emoji = "Low", "🟢"
    elif score < 60:
        level, emoji = "Medium", "🟠"
    else:
        level, emoji = "High", "🔴"

    # Typologies
    typologies = []
    if amount > 10000 and sender in HIGH_RISK_COUNTRIES:
        typologies.append("Layering / Cross-border structuring")
    if amount > 5000 and sender != receiver and sender_type=="individual":
        typologies.append("Cross-border retail remittance / funnel account")
    if "crypto" in purpose:
        typologies.append("Crypto transaction")
    if "trade" in purpose:
        typologies.append("Trade-based money laundering")
    if not typologies:
        typologies.append("No clear typology detected")

    explanation = "; ".join(reasons) if reasons else "No strong drivers detected by demo rules."
    return {"score": score, "level": level, "emoji": emoji, "typologies": typologies, "explanation": explanation}

# ---------------- Load CSV ----------------
@st.cache_data
def load_sample(path="transactions.csv"):
    try:
        df = pd.read_csv(path, dtype=str)
        df.columns = df.columns.str.strip()
        if "tx_id" not in df.columns:
            df.insert(0, "tx_id", [f"SAMPLE_{i+1}" for i in range(len(df))])
        return df
    except:
        return pd.DataFrame()

df_sample = load_sample()
tx = None

# ---------------- Display helper ----------------
def display_result(tx, res):
    c1, c2, c3 = st.columns([2,3,4])
    with c1:
        st.metric("Transaction ID", tx.get("tx_id", "—"))
        st.metric("Amount (USD)", f"{float(tx.get('amount_usd',0)):,.2f}")
        st.metric("Account Type", tx.get("account_type", "Individual"))
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

# ---------------- Sidebar mode ----------------
st.sidebar.header("Mode")
mode = st.sidebar.radio("Choose:", ("Use sample dataset", "Upload CSV", "Manual input"))

# ---------------- Sample dataset ----------------
if mode == "Use sample dataset":
    if df_sample.empty:
        st.warning("No sample CSV found.")
    else:
        choice_sample = st.selectbox(
            "Select Transaction ID (Sample)", 
            options=["-- choose --"] + df_sample["tx_id"].tolist(),
            key="sample_select"
        )
        if choice_sample != "-- choose --":
            tx = df_sample[df_sample["tx_id"] == choice_sample].iloc[0].to_dict()
        if tx:
            if st.button("Score Transaction", key="score_sample"):
                res = compute_risk_and_typology(tx)
                display_result(tx, res)

# ---------------- CSV upload ----------------
elif mode == "Upload CSV":
    uploaded_file = st.file_uploader("Upload your transactions CSV", type=["csv"], key="upload_csv")
    if uploaded_file:
        df_uploaded = pd.read_csv(uploaded_file, dtype=str)
        df_uploaded.columns = df_uploaded.columns.str.strip()
        if "tx_id" not in df_uploaded.columns:
            df_uploaded.insert(0, "tx_id", [f"UPLOAD_{i+1}" for i in range(len(df_uploaded))])

        required_cols = ["remitter_name","remitter_country","beneficiary_name","beneficiary_country","amount_usd","purpose","account_type"]
        for col in required_cols:
            if col not in df_uploaded.columns:
                df_uploaded[col] = ""

        st.success(f"Uploaded {len(df_uploaded)} transactions successfully!")

        choice_upload = st.selectbox(
            "Select Transaction ID (Uploaded CSV)", 
            options=["-- choose --"] + df_uploaded["tx_id"].tolist(),
            key="upload_select"
        )
        if choice_upload != "-- choose --":
            tx = df_uploaded[df_uploaded["tx_id"] == choice_upload].iloc[0].to_dict()
        if tx:
            if st.button("Score Transaction", key="score_upload"):
                res = compute_risk_and_typology(tx)
                display_result(tx, res)

        # Score all uploaded
        def score_row(row):
            simple_tx = {
                "remitter_country": row.get("remitter_country",""),
                "beneficiary_country": row.get("beneficiary_country",""),
                "amount_usd": float(row.get("amount_usd",0)),
                "purpose": row.get("purpose",""),
                "account_type": row.get("account_type","Individual")
            }
            return compute_risk_and_typology(simple_tx)["score"]

        df_uploaded["demo_score"] = df_uploaded.apply(score_row, axis=1)
        cols_to_show = ["tx_id","remitter_name","remitter_country",
                        "beneficiary_name","beneficiary_country",
                        "purpose","amount_usd","account_type","demo_score"]
        cols_to_show = [c for c in cols_to_show if c in df_uploaded.columns]
        st.dataframe(df_uploaded[cols_to_show].sort_values("demo_score", ascending=False))

# ---------------- Manual input ----------------
else:
    with st.form("manual_form"):
        st.subheader("Remitter Details")
        r1, r2 = st.columns(2)

        with r1:
            remitter_name = st.text_input("Name", "John Doe", key="remitter_name")
            remitter_address = st.text_input("Address", "123 Main Street", key="remitter_address")
            remitter_country = st.selectbox(
                "Country", MAJOR_COUNTRIES, index=MAJOR_COUNTRIES.index("India"), key="remitter_country"
            )
            remitter_account_type = st.selectbox("Account Type", ["Individual", "Company"], index=0, key="remitter_type")

        with r2:
            purpose = st.text_input("Purpose of Transfer", "Family Support", key="purpose")
            amount_usd = st.number_input("Amount (USD)", min_value=0.0, value=5000.0, step=100.0, key="amount_usd")

        st.subheader("Beneficiary Details")
        b1, b2 = st.columns(2)

        with b1:
            beneficiary_name = st.text_input("Name", "Jane Doe", key="beneficiary_name")
            beneficiary_address = st.text_input("Address", "456 Elm Street", key="beneficiary_address")
            beneficiary_account_type = st.selectbox(
                "Account Type", ["Individual", "Company"], index=0, key="beneficiary_type"
            )

        with b2:
            beneficiary_country = st.selectbox(
                "Country", MAJOR_COUNTRIES, index=MAJOR_COUNTRIES.index("USA"), key="beneficiary_country"
            )

        submitted = st.form_submit_button("Score Transaction", key="manual_submit")

    # Display results OUTSIDE the form
    if submitted:
        tx = {
            "tx_id": "MANUAL_TX_001",
            "remitter_name": remitter_name,
            "remitter_address": remitter_address,
            "remitter_country": remitter_country,
            "account_type": remitter_account_type,
            "purpose": purpose,
            "amount_usd": amount_usd,
            "beneficiary_name": beneficiary_name,
            "beneficiary_address": beneficiary_address,
            "beneficiary_country": beneficiary_country,
            "beneficiary_account_type": beneficiary_account_type
        }
        res = compute_risk_and_typology(tx)
        display_result(tx, res)
