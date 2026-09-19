# RAG flow

Documents are extracted, cleaned, chunked, tagged with project and verification metadata, embedded with `BAAI/bge-small-en-v1.5`, and stored in Atlas. A query uses the same embedding model, project-filtered vector and keyword retrieval, score fusion, reranking, context construction, and evidence validation. Low confidence or high risk produces a mentor escalation. Verified reusable mentor resolutions re-enter ingestion.

