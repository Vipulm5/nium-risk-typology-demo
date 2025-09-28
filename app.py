# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Risk & Typology Scoring", layout="wide")
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

    # Country risk
    country_score = 0
    if sender in HIGH_RISK_COUNTRIES or receiver in HIGH_RISK_COUNTRIES:
        country_score = 50
        reasons.append(f"High-risk / sanctioned country: {sender} -> {receiver}")
    elif sender in MEDIUM_RISK_COUNTRIES or receiver in MEDIUM_RISK_COUNTRIES:
        country_score = 20
        reasons.append(f"Medium-risk country: {sender} -> {receiver}")
    risk_points += country_score

    # Amount risk
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

    # Final risk
    score = min(100, risk_points)
    if score < 30:
        level = "Low"
    elif score < 60:
        level = "Medium"
    else:
        level = "High"

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
    left, right = st.columns([2,3])
    with left:
        st.markdown(f"<h1 style='font-size:80px;text-align:center;'>{int(res['score'])}</h1>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align:center;'>{res['level']}</h3>", unsafe_allow_html=True)
        st.progress(int(res["score"])/100)
    with right:
        st.markdown("### Sub-scores")
        sub = res.get("sub_scores", {})
        c1, c2 = st.columns(2)
        c1.metric("Country Risk", sub.get("country",0))
        c2.metric("Amount Risk", sub.get("amount",0))
        c1, c2 = st.columns(2)
        c1.metric("Purpose Risk", sub.get("purpose",0))
        c2.metric("Cross-border Risk", sub.get("cross_border",0))
    st.markdown("### Likely Typologies")
    for t in res["typologies"]:
        st.success(f"- {t}")
    st.markdown("### Explanation")
    st.info(res["explanation"])

# ---------------- Tabs ----------------
tab1, tab2, tab3 = st.tabs(["Sample Dataset", "Upload CSV", "Manual Input"])

# ---------------- Sample Dataset ----------------
with tab1:
    if df_sample.empty:
        st.warning("No sample CSV found.")
    else:
        choice_sample = st.selectbox("Select Transaction ID (Sample)", options=["-- choose --"] + df_sample["tx_id"].tolist(), key="sample_select")
        if choice_sample != "-- choose --":
            tx = df_sample[df_sample["tx_id"] == choice_sample].iloc[0].to_dict()
            if st.button("Score Transaction", key="score_sample"):
                res = compute_risk_and_typology(tx)
                display_result(tx, res)

# ---------------- Upload CSV ----------------
with tab2:
    uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

    if uploaded_file is not None:
        df_uploaded = pd.read_csv(uploaded_file)
        df_uploaded.columns = df_uploaded.columns.str.strip()
        if "tx_id" not in df_uploaded.columns:
            df_uploaded.insert(0, "tx_id", [f"TX_{i+1}" for i in range(len(df_uploaded))])

        st.write("### Uploaded Transactions")
        st.dataframe(df_uploaded)

        # Score all transactions
        scores = []
        for _, row in df_uploaded.iterrows():
            tx = row.to_dict()
            res = compute_risk_and_typology(tx)
            scores.append({
                "tx_id": tx.get("tx_id"),
                "risk_score": res["score"],
                "risk_level": res["level"],
                "typologies": "|".join(res["typologies"]),
                "explanation": res["explanation"]
            })
        df_scores = pd.DataFrame(scores)
        st.write("### Scored Transactions")
        st.dataframe(df_scores)

        # Chart preview in Streamlit
        st.subheader("Risk Distribution")
        fig, ax = plt.subplots()
        df_scores['risk_level'].value_counts().reindex(["High","Medium","Low"], fill_value=0).plot(kind='bar', ax=ax, color=['red','orange','green'])
        ax.set_xlabel("Risk Level")
        ax.set_ylabel("Number of Transactions")
        st.pyplot(fig)

        # Download Excel with scores
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_scores.to_excel(writer, sheet_name='Scores', index=False)

            # Add chart to Excel
            workbook  = writer.book
            worksheet = writer.sheets['Scores']
            chart_data = df_scores['risk_level'].value_counts().reindex(["High","Medium","Low"], fill_value=0)
            chart_df = pd.DataFrame({'Risk Level': chart_data.index, 'Count': chart_data.values})
            chart_df.to_excel(writer, sheet_name='ChartData', index=False)

            chart = workbook.add_chart({'type': 'column'})
            chart.add_series({
                'categories': ['ChartData', 1, 0, len(chart_df), 0],
                'values':     ['ChartData', 1, 1, len(chart_df), 1],
                'name':       'Risk Distribution'
            })
            chart.set_title({'name': 'Risk Distribution'})
            chart.set_x_axis({'name': 'Risk Level'})
            chart.set_y_axis({'name': 'Count'})
            worksheet.insert_chart('H2', chart)

        output.seek(0)
        st.download_button(
            label="Download Excel Report",
            data=output,
            file_name="risk_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Single transaction scoring
        choice_csv = st.selectbox(
            "Select a transaction to view detailed score",
            options=["-- choose --"] + df_uploaded["tx_id"].tolist(),
            key="csv_select"
        )
        if choice_csv != "-- choose --":
            tx = df_uploaded[df_uploaded["tx_id"] == choice_csv].iloc[0].to_dict()
            res = compute_risk_and_typology(tx)
            display_result(tx, res)
