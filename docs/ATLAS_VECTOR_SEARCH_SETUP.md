# Atlas Vector Search

Create a vector index on `document_chunks.embedding` with 384 dimensions and cosine similarity. Add filter fields for `projectId`, `verified`, `documentType`, and `version`. Retrieval must apply `projectId` before ranking; the automated P001/P002 isolation test is mandatory.

