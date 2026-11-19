import requests
import json
import os
import time
import re


# API endpoint
API_URL = "http://127.0.0.1:5000/chat-stream"

# Input and output files, resolved relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KG_RAG_DIR = os.getenv("KG_RAG_DIR", os.path.join(BASE_DIR, "KG_RAG"))
INPUT_FILE = os.getenv("CQS_INPUT_FILE", os.path.join(KG_RAG_DIR, "CQs.txt"))
OUTPUT_FILE = os.getenv("CQS_OUTPUT_FILE", os.path.join(KG_RAG_DIR, "rag_responses.txt"))
FAILED_FILE = os.getenv("CQS_FAILED_FILE", os.path.join(KG_RAG_DIR, "failed_cqs.txt"))

def load_cqs(file_path):
    """Read and extract all CQs from the input text file."""

    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    # Split using CQ identifiers such as CQ01:, CQ02:, etc.
    cqs = re.split(r"(?=CQ\d+\s*:)", text)

    return [
        cq.strip()
        for cq in cqs
        if re.match(r"CQ\d+\s*:", cq.strip())
    ]

def run_cq(query):
    """Send a CQ to Flask SSE endpoint and collect the complete response."""

    response_text = ""

    try:
        with requests.get(
            API_URL,
            params={"query": query},
            stream=True,
            timeout=(10, None)
        ) as response:

            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):

                if not line:
                    continue

                if line.startswith("data: "):
                    data = json.loads(line[6:])

                    if "content" in data:
                        response_text += data["content"]

                    elif "error" in data:
                        return f"ERROR: {data['error']}"

                    elif data.get("done"):
                        break

        return response_text.strip()

    except requests.RequestException as e:
        return f"ERROR: {str(e)}"

    except json.JSONDecodeError as e:
        return f"ERROR: Invalid SSE JSON: {str(e)}"


def main():

    if not os.path.exists(INPUT_FILE):
        print(f"Input file not found: {INPUT_FILE}")
        return

    cqs = load_cqs(INPUT_FILE)

    print(f"Total CQs found: {len(cqs)}")

    # Create files if they don't exist
    for path in [OUTPUT_FILE, FAILED_FILE]:
        open(path, "a", encoding="utf-8").close()

    successful = 0
    failed = 0

    for index, cq in enumerate(cqs, start=1):

        print(f"\nProcessing CQ {index}/{len(cqs)}")
        print(cq)

        answer = run_cq(cq)

        if answer.startswith("ERROR:"):

            failed += 1

            with open(FAILED_FILE, "a", encoding="utf-8") as file:
                file.write(f"{cq}\n")
                file.write(f"{answer}\n")
                file.write("--" * 10 + "\n\n")

            print(f"Failed CQ {index}: {answer}")
            continue

        with open(OUTPUT_FILE, "a", encoding="utf-8") as file:
            file.write("=" * 80 + "\n")
            file.write(f"QUERY {index}\n")
            file.write("=" * 80 + "\n\n")
            file.write(cq + "\n\n")
            file.write("RESPONSE:\n")
            file.write(answer + "\n\n")
            file.write("--" * 10 + "\n\n")

        successful += 1
        print(f"Completed CQ {index}/{len(cqs)}")

        time.sleep(2)

    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Total CQs: {len(cqs)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Results: {OUTPUT_FILE}")
    print(f"Failed queries: {FAILED_FILE}")


if __name__ == "__main__":
    main()