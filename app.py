# app.py
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Risk & Typology Scoring Demo", layout="wide")
st.title("🔎 Risk & Typology Scoring — Demo")
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
    "Hawala transfer", "Cryptocurrency exchange", "High-value cash", 
    "Suspicious payment", "Trade-based money laundering"
]

# ---------------- Risk calculation ----------------
def compute_risk_and_typology(tx):
    risk_points = 0
    reasons = []
    
    sender = tx.get("remitter_country","").strip()
    receiver = tx.get("beneficiary_country","").strip()
    amount = float(tx.get("amount_usd") or 0)
    purpose = tx.get("purpose","").strip().lower()
    remitter_type = tx.get("account_type","Individual").lower()
    beneficiary_type = tx.get("beneficiary_account_type","Individual").lower()
    
    # Country risk
    country_score = 0
    if sender in HIGH_RISK_COUNTRIES or receiver in HIGH_RISK_COUNTRIES:
        country_score = 50
        reasons.append(f"High-risk / sanctioned country: {sender} -> {receiver}")
    elif sender in MEDIUM_RISK_COUNTRIES or receiver in MEDIUM_RISK_COUNTRIES:
        country_score = 20
        reasons.append(f"Medium-risk country: {sender} -> {receiver}")
    risk_points += country_score

    # Amount risk logic based on account types
    amount_score = 0
    thresholds = {"individual-individual": (10000, 5000),
                  "individual-company": (15000, 7000),
                  "company-individual": (20000, 10000),
                  "company-company": (50000, 20000)}
    key = f"{remitter_type}-{beneficiary_type}"
    high_thresh, med_thresh = thresholds.get(key, (10000, 5000))
    
    if amount > high_thresh:
        amount_score = 20
        reasons.append(f"High amount ({amount} USD) for {remitter_type} → {beneficiary_type}")
    elif amount > med_thresh:
        amount_score = 10
        reasons.append(f"Medium amount ({amount} USD) for {remitter_type} → {beneficiary_type}")
    risk_points += amount_score

    # Purpose risk
    purpose_score = 0
    if any(hrp.lower() in purpose for hrp in HIGH_RISK_PURPOSES):
        purpose_score = 20
        reasons.append(f"High-risk purpose detected: {purpose}")
    risk_points += purpose_score

    # Cross-border
    cross_border_score = 0
    if sender != receiver:
        cross_border_score = 10
        reasons.append("Cross-border transaction")
    risk_points += cross_border_score

    # Final score
    score = min(100, risk_points)
    if score < 30:
        level, emoji = "Low", "🟢"
    elif score < 60:
        level, emoji = "Medium", "🟠"
    else:
        level, emoji = "High", "🔴"

    # Typologies
    typologies = []
    if amount > high_thresh and sender in HIGH_RISK_COUNTRIES:
        typologies.append("Layering / Cross-border structuring")
    if amount > med_thresh and sender != receiver and remitter_type=="individual":
        typologies.append("Cross-border retail remittance / funnel account")
    if "crypto" in purpose:
        typologies.append("Crypto transaction")
    if "trade" in purpose:
        typologies.append("Trade-based money laundering")
    if not typologies:
        typologies.append("No clear typology detected")
    
    explanation = "; ".join(reasons) if reasons else "No strong drivers detected by demo rules."
    
    return {
        "score": score,
        "level": level,
        "emoji": emoji,
        "typologies": typologies,
        "explanation": explanation,
        "sub_scores": {
            "country": country_score,
            "amount": amount_score,
            "purpose": purpose_score,
            "cross_border": cross_border_score
        }
    }

# ---------------- Load sample ----------------
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

# ---------------- Display helper ----------------
def display_result(tx, res):
    c1, c2, c3 = st.columns([2,3,4])
    with c1:
        st.metric("Transaction ID", tx.get("tx_id", "—"))
        st.metric("Amount (USD)", f"{float(tx.get('amount_usd',0)):,.2f}")
        st.metric("Remitter Type", tx.get("account_type","Individual"))
        st.metric("Beneficiary Type", tx.get("beneficiary_account_type","Individual"))
    with c2:
        st.metric("Risk Level", f"{res['emoji']}  {res['level']}")
        st.progress(int(res["score"])/100)
    with c3:
        st.metric("Risk Score (0–100)", int(res["score"]))
        st.write("Sub-scores:", res["sub_scores"])
    
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

# ---------------- Tabs ----------------
tab1, tab2, tab3 = st.tabs(["Sample Dataset", "Upload CSV", "Manual Input"])

# ---------------- Sample Dataset ----------------
with tab1:
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
            if st.button("Score Transaction", key="score_sample"):
                res = compute_risk_and_typology(tx)
                display_result(tx, res)

# ---------------- Upload CSV ----------------
with tab2:
    uploaded_file = st.file_uploader("Upload your transactions CSV", type=["csv"], key="upload_csv")
    if uploaded_file:
        df_uploaded = pd.read_csv(uploaded_file, dtype=str)
        df_uploaded.columns = df_uploaded.columns.str.strip()
        if "tx_id" not in df_uploaded.columns:
            df_uploaded.insert(0, "tx_id", [f"UPLOAD_{i+1}" for i in range(len(df_uploaded))])
        if "account_type" not in df_uploaded.columns: df_uploaded["account_type"] = "Individual"
        if "beneficiary_account_type" not in df_uploaded.columns: df_uploaded["beneficiary_account_type"] = "Individual"

        st.success(f"Uploaded {len(df_uploaded)} transactions successfully!")

        # ---------------- Score all transactions ----------------
        def score_tx(row):
            simple_tx = {
                "remitter_country": row.get("remitter_country",""),
                "beneficiary_country": row.get("beneficiary_country",""),
                "amount_usd": float(row.get("amount_usd",0)),
                "purpose": row.get("purpose",""),
                "account_type": row.get("account_type","Individual"),
                "beneficiary_account_type": row.get("beneficiary_account_type","Individual")
            }
            res = compute_risk_and_typology(simple_tx)
            return pd.Series({
                "risk_score": res["score"],
                "risk_level": res["level"],
                "typologies": "|".join(res["typologies"])
            })

        df_scores = df_uploaded.join(df_uploaded.apply(score_tx, axis=1))
        st.dataframe(df_scores.sort_values("risk_score", ascending=False).head(10))

        # ---------------- Risk distribution chart ----------------
        st.markdown("### Risk Distribution")
        risk_counts = df_scores["risk_level"].value_counts().reindex(["High","Medium","Low"], fill_value=0)
        st.bar_chart(risk_counts)

        # ---------------- Top Typologies ----------------
        st.markdown("### Top Typologies")
        typology_series = df_scores["typologies"].str.split("|").explode()
        top_typologies = typology_series.value_counts().head(5)
        st.table(top_typologies)

        # ---------------- Download scored CSV ----------------
        st.download_button(
            "Download Full Scored CSV",
            df_scores.to_csv(index=False).encode("utf-8"),
            file_name="scored_transactions.csv",
            mime="text/csv"
        )


# ---------------- Manual Input ----------------
with tab3:
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
            remitter_account_type = st.selectbox("Remitter Account Type", ["Individual","Company"], index=0)
        
        st.subheader("Beneficiary Details")
        b1, b2 = st.columns(2)
        with b1:
            beneficiary_name = st.text_input("Name", "Jane Doe")
            beneficiary_address = st.text_input("Address", "456 Elm Street")
        with b2:
            beneficiary_country = st.selectbox("Country", MAJOR_COUNTRIES, index=MAJOR_COUNTRIES.index("USA"))
            beneficiary_account_type = st.selectbox("Beneficiary Account Type", ["Individual","Company"], index=0)
        
        submitted = st.form_submit_button("Score Transaction")
    
    if submitted:
        tx = {
            "tx_id": "MANUAL_TX_001",
            "remitter_name": remitter_name,
            "remitter_address": remitter_address,
            "remitter_country": remitter_country,
            "purpose": purpose,
            "amount_usd": amount_usd,
            "account_type": remitter_account_type,
            "beneficiary_name": beneficiary_name,
            "beneficiary_address": beneficiary_address,
            "beneficiary_country": beneficiary_country,
            "beneficiary_account_type": beneficiary_account_type
        }
        res = compute_risk_and_typology(tx)
        display_result(tx, res)
