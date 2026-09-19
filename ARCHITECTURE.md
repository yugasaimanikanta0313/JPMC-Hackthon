# Architecture

```text
React/Vite UI -> Spring Boot API -> MongoDB Atlas
                     |                | vector + text indexes
                     +-> Storage      |
                     +-> FastAPI AI --+
                           |-> BGE embeddings
                           |-> Ollama (routine)
                           +-> Gemini (complex fallback)
```

Every knowledge query carries `projectId`. Retrieval combines vector and keyword scores, filters by project and verification state, reranks evidence, and validates confidence. Unsupported answers become structured mentor escalations. A verified reusable mentor answer is ingested as project knowledge.

