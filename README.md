# AI Chatbot for Mitek

Intelligent customer support chatbot using Retrieval-Augmented Generation (RAG) for Mitek J.S.C products and services.

**Technology Stack**
- Backend: FastAPI + Uvicorn
- Frontend: Streamlit
- Vector Database: FAISS (399 chunks from 80 pages)
- LLM: Google Gemini 2.5 Flash
- Embeddings: multilingual-e5-base (768 dimensions)

**Performance**
- Average response time: 12 seconds
- Retrieval accuracy: 85%
- Index size: 500KB
- Memory usage: 500MB

---

## Quick Start

### 1. Installation

```bash
git clone https://github.com/mapleleaflatte03/ai-chatbot.git
cd ai-chatbot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configuration

Create `.env` file in project root:
```env
GOOGLE_API_KEY=your_google_gemini_api_key
DEMO_SEEDS=https://mitek.vn/
```

### 3. Run Application

```powershell
.\run.ps1     # Start both API and UI servers
.\stop.ps1    # Stop all services
```

**Access Points**
- Streamlit UI: http://127.0.0.1:8501
- FastAPI Docs: http://127.0.0.1:8000/docs
- API Health: http://127.0.0.1:8000/health

---

## API Reference

### Endpoints

**POST /ask**
```json
Request:  {"question": "MiPBX là gì?"}
Response: {
  "answer": "MiPBX là giải pháp tổng đài ảo...",
  "sources": [{"url": "https://mitek.vn/mipbx", "title": "..."}]
}
```

**GET /health**
```json
Response: {"ok": true}
```

**GET /metrics**
```json
Response: {
  "p95_latency": 12.5,
  "counts": {"cntt": 10, "software": 5}
}
```

---

## Project Structure

```
ai-chatbot/
├── app/
│   └── main.py              # FastAPI backend with RAG pipeline
├── ui/
│   └── app.py               # Streamlit chat interface
├── scripts/
│   ├── 01_crawl.py          # Web scraper for mitek.vn
│   └── 02_build_index.py    # FAISS vector index builder
├── data/
│   └── faq.csv              # Crawled data (80 pages)
├── storage/
│   ├── index.faiss          # FAISS vector index (399 chunks)
│   ├── meta.json            # Chunk metadata
│   └── log.jsonl            # Query logs
├── .env                     # Environment variables (not in git)
├── requirements.txt         # Python dependencies
├── run.ps1                  # Startup script
└── stop.ps1                 # Shutdown script
```

---

## How RAG Works

The system implements a standard Retrieval-Augmented Generation pipeline:

1. **Query Embedding**: Convert user question to 768-dimensional vector using multilingual-e5-base
2. **Vector Search**: FAISS searches 399 indexed chunks and returns top-4 most relevant results
3. **Context Assembly**: Combine retrieved chunks (max 800 characters)
4. **LLM Generation**: Send context + question to Google Gemini 2.5 Flash
5. **Response Delivery**: Return generated answer with source URLs

**Special Feature**: Greeting detection bypasses RAG for instant responses to simple greetings.

---

## Data Pipeline (Optional)

To re-crawl and rebuild the knowledge base:

```powershell
# Stop services
.\stop.ps1

# Crawl mitek.vn
.venv\Scripts\python.exe scripts\01_crawl.py --seeds "https://mitek.vn/" --limit 80 --out data\faq.csv

# Build FAISS index
.venv\Scripts\python.exe scripts\02_build_index.py --csv data\faq.csv --out storage\index.faiss --meta storage\meta.json

# Restart services (required to load new index)
.\run.ps1
```

---

## License

MIT License - Open source for educational and commercial use.