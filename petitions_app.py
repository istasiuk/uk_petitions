import requests
import pandas as pd
import streamlit as st

all_rows = []
page = 1

while True:
    url = f"https://petition.parliament.uk/petitions.json?page={page}&state=all"
    print(f"Fetching page {page}...")
    response = requests.get(url)
    data = response.json()

    petitions = data.get("data", [])

    for petition in petitions:
        attrs = petition.get("attributes", {})
        links = petition.get("links", {})
        response = attrs.get("government_response") or {}
        debate = attrs.get("debate") or {}
        departments = attrs.get("departments", [])

        all_rows.append({"id": petition.get("id"),
                         "link": links.get("self"),
                         "name": attrs.get("action"),
                         "state": attrs.get("state"),
                         "signatures": attrs.get("signature_count"),
                         "created_at": attrs.get("created_at"),
                         "rejected_at": attrs.get("rejected_at"),
                         "opened_at": attrs.get("opened_at"),
                         "closed_at": attrs.get("closed_at"),
                         "response_threshold_reached_at": attrs.get("response_threshold_reached_at"),
                         "government_response_at": attrs.get("government_response_at"),
                         "debate_threshold_reached_at": attrs.get("debate_threshold_reached_at"),
                         "scheduled_debate_date": attrs.get("scheduled_debate_date"),
                         "debate_outcome_at": attrs.get("debate_outcome_at"),
                         "response": response.get("summary"),
                         "debate_url": debate.get("video_url"),
                         "department": departments[0].get("name") if departments else None
        })

    next_link = data.get("links", {}).get("next")
    if not next_link:
        break

    page += 1

df = pd.DataFrame(all_rows,
                  columns=["id", "link", "name", "state", "signatures",
                           "created_at", "rejected_at", "opened_at",
                           "closed_at", "response_threshold_reached_at",
                           "government_response_at", "debate_threshold_reached_at",
                           "scheduled_debate_date", "debate_outcome_at",
                           "debate_url", "department"])

# Streamlit UI
st.title("UK Parliament Petitions")
st.dataframe(df)