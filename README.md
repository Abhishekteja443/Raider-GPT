# Raider-GPT

Raider-GPT is a Flask-based organizational question-answering prototype. It indexes web pages supplied as direct URLs or discovered from sitemaps, retrieves relevant passages with embeddings and FAISS, and streams answers from a locally served Ollama model. It can also add matching results from a precomputed knowledge graph.

## What it does

- Scrapes page text from HTTP(S) URLs and XML sitemaps.
- Splits and deduplicates page text, generates embeddings with Ollama, and stores them in a local FAISS index.
- Combines retrieved web-page passages with relevant precomputed knowledge-graph results when answering questions.
- Streams responses to the browser using Server-Sent Events (SSE).
- Provides an administrator page for entering URLs and uploading a `.txt` file containing one URL per line.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | Flask application entry point; accepts JSON URL submissions. |
| `app2.py` | Alternate Flask entry point; supports the browser's multipart form and `.txt` URL uploads. |
| `src/` | Scraping, FAISS indexing, retrieval, query routing, prompts, and input validation. |
| `templates/`, `static/` | Login, URL-submission, and chat pages and their assets. |
| `KG_RAG/` | Competency questions, ontology/model graph files, SPARQL queries, and evaluation outputs. |
| `faiss_store/` | Local FAISS index and metadata created or loaded by the application. |
| `scraped_context.txt` | Text appended during page scraping. |
| `run_cqs.py` | Script for sending the competency questions to a running chat server. |
| `docker_file`, `start.sh` | Prototype container build and startup files. |

## Requirements

- Python 3.10 (the included container uses Python 3.10).
- [Ollama](https://ollama.com/) running locally or in the same container.
- The `llama3.2:3b` chat model and `nomic-embed-text` embedding model.
- The repository's `KG_RAG/Opus5.5/query_results.json` file for knowledge-graph retrieval.

## Setup

Create and activate a virtual environment. On Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On macOS or Linux:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in the project root. There is no `.env.example` in the repository. At minimum, set the index directory:

```dotenv
FAISS_INDEX_PATH=./faiss_store
FLASK_DEBUG=False
CORS_ORIGINS=http://localhost:5000
```

`FAISS_INDEX_PATH` is required when the application starts. `FLASK_DEBUG` and `CORS_ORIGINS` are optional; the values above match the local defaults.

Install and start Ollama, then download the models:

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
ollama serve
```

Keep Ollama running while using the application. The chat model generates answers; the embedding model is used for both page indexing and retrieval.

### Knowledge-graph data path

Knowledge-graph retrieval loads precomputed results from `KG_RAG/Opus5.5/query_results.json`. The path is currently hard-coded in `src/kg_lookup.py` to a specific Windows checkout. If your checkout is elsewhere, update the `KG_PATH` constant in that file to the local path before running the application. The file is loaded on the first applicable chat request.

## Run locally

From the repository root, start the upload-enabled app:

```bash
python app2.py
```

Open [http://localhost:5000](http://localhost:5000). The root page redirects to the login page; `/index` serves the URL-submission page and `/organization-gpt` serves the chat page.

The browser's URL form sends multipart form data, so use `app2.py` for the supplied UI. `app.py` is the alternative JSON-only URL-submission entry point. The included `start.sh` and `docker_file` currently launch `app.py`.

### Submit URLs

On the administrator page, add sitemap URLs, direct page URLs, or upload a `.txt` file with one URL per line. Blank lines and lines beginning with `#` are ignored. Submitting URLs scrapes the pages, creates embeddings, and saves the index under `FAISS_INDEX_PATH`. Open the chat page after indexing.

The equivalent JSON request to either entry point is:

```json
{
  "base_urls": ["https://example.org/sitemap.xml"],
  "extra_urls": ["https://example.org/about"]
}
```

`base_urls` are sitemap URLs. `extra_urls` are direct page URLs. In `app2.py`, form submissions may also provide these arrays as JSON-encoded form fields and include an optional `urls_file` `.txt` upload.

## HTTP endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Redirects to the login page. |
| `GET`, `POST` | `/login` | Displays the login form and handles login submissions. |
| `GET` | `/index` | Displays the URL-submission page. |
| `POST` | `/submit-urls` | Scrapes and indexes URLs from the supported request format. |
| `GET` | `/organization-gpt` | Displays the chat interface. |
| `GET` | `/chat-stream?query=...` | Streams chat response events using SSE. |
| `GET` | `/api/health` | Returns application health and FAISS index counts. |

Each chat event is a `data:` JSON payload. Response chunks include `content` and may include `source_url`; the stream ends with a `done` event. Errors may be returned in an `error` field.

## Knowledge-graph and evaluation files

`KG_RAG/` contains the competency questions, ontology, graph/query files, and saved results for the Opus 5.5 and OSS 120B model runs. The Flask application uses the precomputed Opus 5.5 `query_results.json` for lookup; it does not execute the included SPARQL queries as part of each chat request. `run_cqs.py` calls a running local chat server and has file paths that may need adjustment for another checkout.

## Tests

The repository includes a focused test for parsing URL text files. Install `pytest` in the active environment if it is not already available, then run:

```bash
python -m pytest
```

## Notes and limitations

- The FAISS index is local application data. Keep `FAISS_INDEX_PATH` stable between runs to reuse it; deleting the index files removes the stored index.
- Page ingestion fetches the URLs you submit and their sitemap entries; it does not recursively crawl each page's links.
- This is a prototype, not a production-ready private deployment. The login implementation is demo-only, and the application should not be exposed publicly without proper authentication, deployment hardening, and a review of data-handling requirements.
- The Docker setup is also a prototype. Its startup script launches `app.py`, not the multipart-upload-enabled `app2.py`; the knowledge-graph path also needs to be valid inside the container.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
