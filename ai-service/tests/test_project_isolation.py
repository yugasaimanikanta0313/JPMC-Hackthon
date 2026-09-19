from app.retrieval.hybrid_retriever import Chunk, HybridRetriever

def test_p001_never_retrieves_p002_private_knowledge():
    r = HybridRetriever([Chunk("P001","a","public","shared deployment"), Chunk("P002","b","private","shared deployment secret")])
    results = r.search("P001", "deployment")
    assert results
    assert all(chunk.project_id == "P001" for chunk, _ in results)

def test_unverified_chunks_are_excluded():
    r = HybridRetriever([Chunk("P001","a","draft","deployment", verified=False)])
    assert r.search("P001", "deployment") == []

