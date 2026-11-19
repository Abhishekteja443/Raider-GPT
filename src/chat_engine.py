import json
import ollama
import threading
from src.query_router import route_query
from src.prompt_builder import build_system_prompt
from src import gpt_backend
from src import kg_lookup
from src import logger

conversation_history = []
history_lock = threading.Lock()
MAX_TOKENS_PER_MESSAGE = 500
MAX_CONTEXT_TOKENS = 2000 
NUM_CTX = 10000           # total Ollama window: system + history + KG + RAG + query


def count_tokens_approximate(text: str) -> int:
    return len(text) // 4


def manage_conversation_history(max_tokens: int = MAX_CONTEXT_TOKENS):
    global conversation_history

    total_tokens = sum(count_tokens_approximate(msg.get("content", "")) for msg in conversation_history)

    while total_tokens > max_tokens and len(conversation_history) > 1:
        if len(conversation_history) >= 2:
            removed_msg = conversation_history.pop(0)
            total_tokens -= count_tokens_approximate(removed_msg.get("content", ""))
            logger.info(f"Removed message from history to manage tokens. Total: {total_tokens}")


def build_context_message(kg_text: str, relevant_text: str) -> str:
    """Combine KG and RAG context into one neutral, unlabeled-source message."""
    parts = [p for p in (kg_text, relevant_text) if p]
    if not parts:
        return ""

    instruction = (
        "Use the reference information below to answer the user's question. "
        "Combine all of it into one natural, complete answer. "
        "Reference information that is structured (lists, names, numbers) is "
        "the most reliable; if two pieces conflict, prefer the structured one. "
        "Never mention or hint at where the information came from: do not "
        "say 'according to', 'the knowledge graph', 'KG', 'the context', "
        "'the passages', 'the documents' or 'the sources'. Just state the "
        "facts directly as if you know them. "
        "If the reference information does not contain the answer, say you "
        "don't have that information instead of guessing."
    )
    return instruction + "\n\nReference information:\n\n" + "\n\n".join(parts)


def stream_chat_response(query: str):
    global conversation_history

    try:
        if not query or not isinstance(query, str):
            logger.warning("Invalid query received")
            yield "Error: Invalid query", None
            return

        if len(query) > 5000:
            logger.warning("Query exceeds maximum length")
            yield "Error: Query is too long", None
            return

        route = route_query(query)

        if route == "meta":
            response = (
                "I do not have persistent memory or awareness of documents. "
                "I only see information provided to me during this conversation."
            )
            with history_lock:
                conversation_history.append({"role": "user", "content": query})
                conversation_history.append({"role": "assistant", "content": response})
                manage_conversation_history()
            yield response, None
            return

        relevant_text = ""
        source_url = None
        kg_text = ""
        kg_id = None

        if route != "chitchat":
            # --- RAG retrieval ---
            try:
                relevant_text, source_url = gpt_backend.retrieve_relevant_chunks(query, 5)
                if relevant_text:
                    logger.info(f"Retrieved context from: {source_url}")
            except Exception as e:
                logger.error(f"Error retrieving chunks: {e}")
                relevant_text = ""
                source_url = "Unknown"

            # --- KG retrieval (matched against competency questions) ---
            kg_text, kg_id = kg_lookup.retrieve_kg_context(query)
            if kg_text:
                logger.info(f"Added KG context from {kg_id} (~{count_tokens_approximate(kg_text)} tokens)")

        system_prompt = build_system_prompt(route)
        context_message = build_context_message(kg_text, relevant_text)

        with history_lock:
            manage_conversation_history()

            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)

            if context_message:
                messages.append({"role": "system", "content": context_message})

            messages.append({"role": "user", "content": query})

        # Rough size check so overflow shows up in logs instead of failing silently
        est_tokens = sum(count_tokens_approximate(m["content"]) for m in messages)
        logger.info(f"Estimated prompt size: ~{est_tokens} tokens (num_ctx={NUM_CTX})")
        if est_tokens > NUM_CTX * 0.9:
            logger.warning("Prompt is close to or over the context window; output may be truncated")

        response_text = ""

        try:
            for chunk in ollama.chat(
                model="llama3.2:3b",
                messages=messages,
                options={"temperature": 0.5, "num_ctx": NUM_CTX},
                stream=True
            ):
                if "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    response_text += content
                    yield content, source_url
        except Exception as e:
            logger.error(f"LLM streaming error: {e}", exc_info=True)
            error_msg = "Error generating response. Please try again."
            yield error_msg, None
            response_text = error_msg

        with history_lock:
            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": response_text})
            manage_conversation_history()

    except Exception as e:
        logger.error(f"Unexpected error in stream_chat_response: {e}", exc_info=True)
        yield "An unexpected error occurred. Please try again.", None