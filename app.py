# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
from fpdf import FPDF

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
    remitter_type = tx.get("account_type","Individual").lower()
    beneficiary_type = tx.get("beneficiary_account_type","Individual").lower()
    purpose = tx.get("purpose","").strip().lower()

    # ---------------- Country risk ----------------
    country_score = 0
    if sender in HIGH_RISK_COUNTRIES or receiver in HIGH_RISK_COUNTRIES:
        country_score = 50
        reasons.append(f"High-risk / sanctioned country: {sender} -> {receiver}")
    elif sender in MEDIUM_RISK_COUNTRIES or receiver in MEDIUM_RISK_COUNTRIES:
        country_score = 20
        reasons.append(f"Medium-risk country: {sender} -> {receiver}")
    risk_points += country_score

    # ---------------- Amount risk ----------------
    amount_score = 0
    thresholds = {
        "individual-individual": (10000, 5000),
        "individual-company": (15000, 7000),
        "company-individual": (20000, 10000),
        "company-company": (50000, 20000)
    }
    key = f"{remitter_type}-{beneficiary_type}"
    high_thresh, med_thresh = thresholds.get(key, (10000, 5000))

    if amount > high_thresh:
        amount_score = 20
        reasons.append(f"High amount ({amount} USD) for {remitter_type.title()} → {beneficiary_type.title()}")
    elif amount > med_thresh:
        amount_score = 10
        reasons.append(f"Medium amount ({amount} USD) for {remitter_type.title()} → {beneficiary_type.title()}")
    risk_points += amount_score

    # ---------------- Purpose risk ----------------
    purpose_score = 0
    if any(hrp.lower() in purpose for hrp in HIGH_RISK_PURPOSES):
        purpose_score = 20
        reasons.append(f"High-risk purpose detected: {purpose}")
    risk_points += purpose_score

    # ---------------- Cross-border ----------------
    cross_border_score = 0
    if sender != receiver:
        cross_border_score = 10
        reasons.append("Cross-border transaction")
    risk_points += cross_border_score

    # ---------------- Final risk ----------------
    score = min(100, risk_points)
    if score < 30:
        level, emoji = "Low", "Low"
    elif score < 60:
        level, emoji = "Medium", "Medium"
    else:
        level, emoji = "High", "High"

    # ---------------- Typologies ----------------
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
    st.markdown("## Transaction Risk Overview")

    # ---------------- Main score ----------------
    left, right = st.columns([2,3])

    # Left: Big total score
    with left:
        st.markdown(
            f"<h1 style='font-size:80px;text-align:center;'>{int(res['score'])}</h1>",
            unsafe_allow_html=True
        )
        st.markdown(f"<h3 style='text-align:center;'>{res['level']}</h3>", unsafe_allow_html=True)
        st.progress(int(res["score"])/100)

    # Right: Sub-scores
    with right:
        st.markdown("### Sub-scores")
        sub = res.get("sub_scores", {})
        c1, c2 = st.columns(2)
        c1.metric("Country Risk", sub.get("country",0))
        c2.metric("Amount Risk", sub.get("amount",0))
        c1, c2 = st.columns(2)
        c1.metric("Purpose Risk", sub.get("purpose",0))
        c2.metric("Cross-border Risk", sub.get("cross_border",0))

    # Typologies
    st.markdown("### Likely Typologies")
    for t in res["typologies"]:
        st.success(f"- {t}")

    # Explanation
    st.markdown("### Explanation")
    st.info(res["explanation"])

# ---------------- PDF Generation (demo-safe, no emojis) ----------------
def generate_pdf(df_scores):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Transaction Risk Scoring Report", ln=True, align="C")
    pdf.ln(10)

    # Risk distribution chart
    fig, ax = plt.subplots(figsize=(6,4))
    risk_counts = df_scores['risk_level'].value_counts().reindex(["High","Medium","Low"], fill_value=0)
    risk_counts.plot(kind='bar', ax=ax, color=['red','orange','green'])
    plt.title("Risk Distribution")
    plt.ylabel("Number of Transactions")
    plt.tight_layout()
    
    # Save chart to temp file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        fig.savefig(tmpfile.name, bbox_inches='tight')
        tmpfile_path = tmpfile.name
    plt.close(fig)
    pdf.image(tmpfile_path, x=30, w=150)
    pdf.ln(10)

    # Top typologies (replace non-Latin characters)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Top Typologies", ln=True)
    typology_series = df_scores["typologies"].str.split("|").explode()
    top_typologies = typology_series.value_counts().head(10)
    
    pdf.set_font("Arial", "", 12)
    for t, count in top_typologies.items():
        safe_t = t.encode('latin1', 'ignore').decode('latin1')  # remove any emoji / special chars
        pdf.cell(0, 8, f"{safe_t} — {count} occurrences", ln=True)
    
    pdf_output = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(pdf_output.name)
    pdf_output.seek(0)
    return pdf_output.name

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

        # Single transaction scoring
        choice_upload = st.selectbox(
            "Select Transaction ID", 
            options=["-- choose --"] + df_uploaded["tx_id"].tolist(),
            key="upload_select"
        )
        if choice_upload != "-- choose --":
            tx_single = df_uploaded[df_uploaded["tx_id"] == choice_upload].iloc[0].to_dict()
            if st.button("Score Selected Transaction", key="score_upload_single"):
                res_single = compute_risk_and_typology(tx_single)
                display_result(tx_single, res_single)

        # Batch scoring
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
        
        st.markdown("### Top 10 Transactions by Risk Score")
        st.dataframe(df_scores.sort_values("risk_score", ascending=False).head(10))
        
        # Risk distribution chart
        st.markdown("### Risk Distribution")
        risk_counts = df_scores["risk_level"].value_counts().reindex(["High","Medium","Low"], fill_value=0)
        st.bar_chart(risk_counts)

        # Top Typologies
        st.markdown("### Top Typologies")
        typology_series = df_scores["typologies"].str.split("|").explode()
        top_typologies = typology_series.value_counts().head(5)
        st.table(top_typologies)

        # Download scored CSV
        st.download_button(
            "Download Full Scored CSV",
            df_scores.to_csv(index=False).encode("utf-8"),
            file_name="scored_transactions.csv",
            mime="text/csv"
        )

        # ---------------- Download PDF ----------------
        pdf_file_path = generate_pdf(df_scores)
        with open(pdf_file_path, "rb") as f:
            st.download_button("Download Risk Report PDF", f, file_name="risk_report.pdf")

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
        # Compute risk and typology
        res = compute_risk_and_typology(tx)
        # Add sub-scores to transaction dict for display if needed
        for k, v in res.get("sub_scores", {}).items():
            tx[f"{k}_risk"] = v
        # Display the result
        display_result(tx, res)

