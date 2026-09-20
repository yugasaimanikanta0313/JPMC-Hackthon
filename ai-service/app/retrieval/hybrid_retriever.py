import re
from dataclasses import dataclass,field
from app.services.ingestion import embedding

@dataclass
class Chunk:
    project_id:str
    document_id:str
    title:str
    content:str
    verified:bool=True
    metadata:dict=field(default_factory=dict)

class HybridRetriever:
    """Mongo-backed, project-filtered retrieval. Project isolation is applied before scoring."""
    def __init__(self,chunks=None,db=None):self.chunks=chunks or [];self.db=db
    def _candidates(self,project_id):
        memory=[c for c in self.chunks if c.project_id==project_id and c.verified]
        if self.db is None:return memory
        rows=self.db.document_chunks.find({"project_id":project_id,"verified":True}).sort("created_at",-1).limit(500)
        return memory+[Chunk(project_id=str(x["project_id"]),document_id=str(x.get("document_id",x.get("_id"))),title=x.get("title","Project evidence"),content=x.get("content",""),verified=True,metadata={"source_type":x.get("source_type"),"repository":x.get("repository"),"commit_sha":x.get("commit_sha"),"path":x.get("path"),"language":x.get("language"),"access_scope":x.get("access_scope","project")}) for x in rows]
    def search(self,project_id,query,limit=8):
        priorities={"decision":1.0,"requirements":.92,"requirement":.92,"architecture":.86,"document":.82,"knowledge":.78,"verified_resolution":.76,"source_code":.68,"logs":.64,"general":.5}
        def rank(chunk,score):return min(1.0,score*.78+priorities.get((chunk.metadata.get("source_type") or "general").lower(),.55)*.22)
        terms=set(re.findall(r"[a-z0-9_./-]+",query.lower()));scored=[]
        if self.db is not None:
            vector=embedding(query,task_type="RETRIEVAL_QUERY")
            if vector:
                try:
                    rows=list(self.db.document_chunks.aggregate([{"$vectorSearch":{"index":"project_vector_index","path":"embedding","queryVector":vector,"numCandidates":100,"limit":limit,"filter":{"project_id":project_id}}},{"$match":{"verified":True}},{"$set":{"vector_score":{"$meta":"vectorSearchScore"}}}]))
                    if rows:
                        ranked=[]
                        for x in rows:
                            c=Chunk(project_id=project_id,document_id=str(x.get("document_id",x.get("_id"))),title=x.get("title","Project evidence"),content=x.get("content",""),verified=True,metadata={"source_type":x.get("source_type"),"repository":x.get("repository"),"commit_sha":x.get("commit_sha"),"path":x.get("path"),"language":x.get("language"),"access_scope":x.get("access_scope","project"),"status":x.get("status")})
                            ranked.append((c,rank(c,float(x.get("vector_score",0)))))
                        return sorted(ranked,key=lambda row:row[1],reverse=True)[:limit]
                except Exception:pass
        for chunk in self._candidates(project_id):
            text=(chunk.title+" "+chunk.content).lower();words=set(re.findall(r"[a-z0-9_./-]+",text))
            coverage=len(terms & words)/max(len(terms),1)
            long_terms=[t for t in terms if len(t)>3]
            phrase=sum(1 for t in long_terms if t in text)/max(len(long_terms),1)
            score=min(1.0,coverage*.65+phrase*.35)
            if score>0:scored.append((chunk,rank(chunk,score)))
        return sorted(scored,key=lambda row:row[1],reverse=True)[:limit]
    def add(self,chunk):self.chunks.append(chunk)
