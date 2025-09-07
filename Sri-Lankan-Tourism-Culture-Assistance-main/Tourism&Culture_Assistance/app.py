import streamlit as st
from rag.rag_chain import answer_query, client

st.set_page_config(page_title="Custom Travel Assistant", layout="wide")

st.title("🌍 Custom Travel Assistant")
st.write("Ask about visa rules, itineraries, transport, or places to visit.")

query = st.text_input("Your travel question:")

if query:
    with st.spinner("Fetching best answer..."):
        res = answer_query(query)

        st.subheader("Answer")
        st.write(res["result"])

        with st.expander("Sources"):
            for doc in res["source_documents"]:
                title = doc.metadata.get("title", "Unknown")
                snippet = doc.page_content[:200]

                st.markdown(f"**{title}**: {snippet}...")

                images = doc.metadata.get("images", [])
                if images:
                    st.image(images, use_column_width=True)

        client.close()
