import streamlit as st
import requests

# Try to get BACKEND from secrets, fallback to default
try:
    BACKEND = st.secrets["BACKEND"]
except:
    BACKEND = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Chatbot Demo", page_icon="🤖")

tab_chat, tab_dash = st.tabs(["Chatbot FAQ", "Dashboard"])

with tab_chat:
    st.header("Chatbot FAQ")
    q = st.text_input("Câu hỏi")
    if st.button("Hỏi") and q:
        try:
            r = requests.post(f"{BACKEND}/ask", json={"question": q}, timeout=60)
            r.raise_for_status()
            data = r.json()
            st.subheader("Trả lời")
            st.write(data.get("answer", ""))
            st.subheader("Nguồn")
            for s in data.get("sources", []):
                st.write(f"- [{s['title']}]({s['url']})")
        except Exception as e:
            st.error(f"Lỗi: {e}")

with tab_dash:
    st.header("Dashboard")
    try:
        r = requests.get(f"{BACKEND}/metrics", timeout=10)
        r.raise_for_status()
        m = r.json()
        st.metric("P95 latency (s)", f"{m.get('p95_latency', 0):.2f}")
        st.write("Phân bổ chủ đề:", m.get("counts", {}))
    except Exception as e:
        st.warning(f"Chưa có số liệu: {e}")
