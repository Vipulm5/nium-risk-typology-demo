# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Risk & Typology Scoring Demo", layout="wide")
st.title("🔎 Risk & Typology Scoring — Demo")
st.markdown("Use sample dataset or enter transaction manually. Demo uses dummy data only.")

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
TYPOS = [
    "Structuring / Smurfing", "Layering / Cross-border structuring", "Funnel account",
    "Trade-based money laundering", "Cross-border retail remittance", "Crypto transaction"
]

# ---------------- Risk calculation ----------------
def compute_risk_and_typology(tx):
    risk_points = 0
    reasons = []

    sender = tx.get("remitter_country","").strip()
    receiver = tx.get("beneficiary_country","").strip()
    amount = float(tx.get("amount_usd") or 0)
    purpose = tx.get("purpose","").strip().lower()
    acct_type = tx.get("account_type","Individual").lower()

    # Country risk
    if sender in HIGH_RISK_COUNTRIES or receiver in HIGH_RISK_COUNTRIES:
        risk_points += 50
        reasons.append(f"High-risk / sanctioned country: {sender} -> {receiver}")
    elif sender in MEDIUM_RISK_COUNTRIES or receiver in MEDIUM_RISK_COUNTRIES:
        risk_points += 20
        reasons.append(f"Medium-risk country: {sender} -> {receiver}")

    # Amount thresholds differ for Individuals vs Companies
    if acct_type == "individual":
        if amount > 10000: risk_points += 20; reasons.append("Large amount (>10,000 USD) for individual")
        elif amount > 5000: risk_points += 10; reasons.append("Medium amount (5,000–10,000 USD) for individual")
    else:  # Company
        if amount > 50000: risk_points += 20; reasons.append("Large amount (>50,000 USD) for company")
        elif amount > 20000: risk_points += 10; reasons.append("Medium amount (20,000–50,000 USD) for company")

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
    if amount > 5000 and sender != receiver and acct_type=="individual":
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
        return df
    except Exception as e:
        st.error(f"Could not load sample file: {e}")
        return pd.DataFrame()

df = load_sample()

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

    # DOWNLOAD BUTTON MUST BE OUTSIDE FORM
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

tx = None
df_uploaded = pd.DataFrame()

# ---------------- Sample dataset ----------------
if mode == "Use sample dataset":
    if df.empty:
        st.warning("No sample CSV found.")
    else:
        choice_sample = st.selectbox(
    "Select Transaction ID (Sample)", 
    options=["-- choose --"] + df["tx_id"].tolist(),
    key="select_sample_tx"
)

        if choice != "-- choose --":
            tx = df[df["tx_id"] == choice].iloc[0].to_dict()
    if st.button("Score Transaction") and tx is not None:
        res = compute_risk_and_typology(tx)
        display_result(tx, res)

# ---------------- CSV upload ----------------
elif mode == "Upload CSV":
    uploaded_file = st.file_uploader("Upload your transactions CSV", type=["csv"])
    if uploaded_file:
        try:
            df_uploaded = pd.read_csv(uploaded_file, dtype=str)
            df_uploaded.columns = df_uploaded.columns.str.strip()
            st.success(f"Uploaded {len(df_uploaded)} transactions successfully!")
            
            choice_upload = st.selectbox(
    "Select Transaction ID (Uploaded CSV)", 
    options=["-- choose --"] + df_uploaded["tx_id"].tolist(),
    key="select_upload_tx"
)

            if choice != "-- choose --":
                tx = df_uploaded[df_uploaded["tx_id"] == choice].iloc[0].to_dict()
            
            if st.button("Score Transaction") and tx is not None:
                res = compute_risk_and_typology(tx)
                display_result(tx, res)
            
            # Display uploaded dataset
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
            # Select only existing columns
            cols_to_show = ["tx_id","remitter_name","remitter_country",
                            "beneficiary_name","beneficiary_country",
                            "purpose","amount_usd","account_type","demo_score"]
            cols_to_show = [c for c in cols_to_show if c in df_uploaded.columns]
            st.dataframe(df_uploaded[cols_to_show].sort_values("demo_score", ascending=False))

        except Exception as e:
            st.error(f"Error reading CSV: {e}")

# ---------------- Manual input ----------------
else:
    # ... your existing manual input form here ...
    pass

# ---------------- Sample dataset ----------------
if mode == "Use sample dataset":
    if df.empty:
        st.warning("No sample CSV found.")
    else:
        choice = st.selectbox("Select Transaction ID", options=["-- choose --"] + df["tx_id"].tolist())
        if choice != "-- choose --":
            tx = df[df["tx_id"] == choice].iloc[0].to_dict()
    if st.button("Score Transaction") and tx is not None:
        res = compute_risk_and_typology(tx)
        display_result(tx, res)

# ---------------- CSV upload ----------------
elif mode == "Upload CSV":
    uploaded_file = st.file_uploader(
    "Upload your transactions CSV", 
    type=["csv"], 
    key="upload_csv"
)

    if uploaded_file:
        try:
            df_uploaded = pd.read_csv(uploaded_file, dtype=str)
            df_uploaded.columns = df_uploaded.columns.str.strip()
            st.success(f"Uploaded {len(df_uploaded)} transactions successfully!")
            
            choice = st.selectbox("Select Transaction ID", options=["-- choose --"] + df_uploaded["tx_id"].tolist())
            if choice != "-- choose --":
                tx = df_uploaded[df_uploaded["tx_id"] == choice].iloc[0].to_dict()
            
            if st.button("Score Transaction") and tx is not None:
                res = compute_risk_and_typology(tx)
                display_result(tx, res)
            
            # Display uploaded dataset
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
            # Select only existing columns
            cols_to_show = ["tx_id","remitter_name","remitter_country",
                            "beneficiary_name","beneficiary_country",
                            "purpose","amount_usd","account_type","demo_score"]
            cols_to_show = [c for c in cols_to_show if c in df_uploaded.columns]
            st.dataframe(df_uploaded[cols_to_show].sort_values("demo_score", ascending=False))

        except Exception as e:
            st.error(f"Error reading CSV: {e}")

# ---------------- Manual input ----------------
else:
    # ... your existing manual input form here ...
    pass


# ---------------- Dataset mode ----------------
if mode.startswith("Use sample"):
    if df.empty:
        st.warning("No transactions.csv found.")
    else:
        choice = st.selectbox("Select Transaction ID", options=["-- choose --"] + df["tx_id"].tolist())
        if choice != "-- choose --":
            tx = df[df["tx_id"] == choice].iloc[0].to_dict()
    if st.button("Score Transaction") and tx is not None:
        res = compute_risk_and_typology(tx)
        display_result(tx, res)

# ---------------- Manual input mode ----------------
else:
    with st.form("manual_form"):
        st.subheader("Remitter Details")
        r1, r2 = st.columns(2)
        with r1:
            remitter_name = st.text_input("Name", "John Doe")
            remitter_address = st.text_input("Address", "123 Main Street")
            remitter_country = st.selectbox("Country", MAJOR_COUNTRIES, index=MAJOR_COUNTRIES.index("India"))
        with r2:
            purpose = st.text_input("Purpose of Transfer", "Family Support")
            amount_usd = st.number_input("Amount (USD)", min_value=0.0, value=5000.0, step=100.0)
            account_type = st.selectbox("Account Type", ["Individual", "Company"], index=0)

        st.subheader("Beneficiary Details")
        b1, b2 = st.columns(2)
        with b1:
            beneficiary_name = st.text_input("Name", "Jane Doe")
            beneficiary_address = st.text_input("Address", "456 Elm Street")
        with b2:
            beneficiary_country = st.selectbox("Country", MAJOR_COUNTRIES, index=MAJOR_COUNTRIES.index("USA"))

        submitted = st.form_submit_button("Score Transaction")

    if submitted:
        tx = {
            "tx_id": "MANUAL_TX_001",
            "remitter_name": remitter_name,
            "remitter_address": remitter_address,
            "remitter_country": remitter_country,
            "purpose": purpose,
            "amount_usd": amount_usd,
            "account_type": account_type,
            "beneficiary_name": beneficiary_name,
            "beneficiary_address": beneficiary_address,
            "beneficiary_country": beneficiary_country
        }
        res = compute_risk_and_typology(tx)
        display_result(tx, res)

# ---------------- Dataset table ----------------
# ---------------- Dataset table ----------------
if not df.empty:
    st.markdown("---")
    st.markdown("### Sample Dataset (simulated Metabase)")

    def score_row(row):
        simple_tx = {
            "remitter_country": row.get("remitter_country",""),
            "beneficiary_country": row.get("beneficiary_country",""),
            "amount_usd": float(row.get("amount_usd",0)),
            "purpose": row.get("purpose",""),
            "account_type": row.get("account_type","Individual")
        }
        return compute_risk_and_typology(simple_tx)["score"]

    df["demo_score"] = df.apply(score_row, axis=1)

    # Select only columns that exist
    cols_to_show = ["tx_id","remitter_name","remitter_country",
                    "beneficiary_name","beneficiary_country",
                    "purpose","amount_usd","account_type","demo_score"]
    cols_to_show = [c for c in cols_to_show if c in df.columns]

    st.dataframe(df[cols_to_show].sort_values("demo_score", ascending=False))
