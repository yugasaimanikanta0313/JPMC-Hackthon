import base64
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime,timezone
from pathlib import PurePosixPath

import httpx
from functools import lru_cache

TEXT_SUFFIXES={".txt",".md",".py",".js",".jsx",".ts",".tsx",".java",".go",".rs",".cs",".php",".rb",".json",".yaml",".yml",".toml",".xml",".html",".css",".scss",".sql",".sh",".ps1",".log"}
EXCLUDED_PARTS={"node_modules","vendor","dist","build","target","coverage",".git",".next","__pycache__","generated"}
LANGUAGE_ALIASES={"py":"python","js":"javascript","jsx":"javascript","ts":"typescript","tsx":"tsx","java":"java","go":"go","rs":"rust","cs":"c_sharp","php":"php","rb":"ruby","html":"html","css":"css","json":"json","yaml":"yaml","yml":"yaml","sql":"sql","sh":"bash"}

@lru_cache(maxsize=2)
def embedding_model(name):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)

def embedding(text,model_name="BAAI/bge-small-en-v1.5"):
    try:return embedding_model(model_name).encode(text[:8000],normalize_embeddings=True).tolist()
    except Exception:return None

def safe_archive_entry(info,max_file_size=2_000_000):
    path=PurePosixPath(info.filename.replace("\\","/"))
    compressed=max(info.compress_size,1)
    return (not path.is_absolute() and ".." not in path.parts and not any(p.lower() in EXCLUDED_PARTS for p in path.parts)
            and path.suffix.lower() in TEXT_SUFFIXES and info.file_size<=max_file_size and info.file_size/compressed<=100)

def antivirus_scan(data:bytes):
    executable=shutil.which("clamscan")
    if executable:
        result=subprocess.run([executable,"--no-summary","-"],input=data,capture_output=True,timeout=90)
        if result.returncode==1:raise ValueError("Malware detected in uploaded archive")
        if result.returncode>1:raise ValueError("Antivirus scan failed")
        return {"status":"CLEAN","engine":"ClamAV"}
    defender=Path(r"C:\Program Files\Windows Defender\MpCmdRun.exe")
    if defender.exists():
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(delete=False,suffix=".zip") as handle:handle.write(data);temporary=handle.name
            result=subprocess.run([str(defender),"-Scan","-ScanType","3","-File",temporary,"-DisableRemediation"],capture_output=True,timeout=120)
            if result.returncode not in {0}:raise ValueError("Antivirus rejected the uploaded archive or could not complete the scan")
            return {"status":"CLEAN","engine":"Microsoft Defender"}
        finally:
            if temporary:Path(temporary).unlink(missing_ok=True)
    raise ValueError("Antivirus service is unavailable; ZIP upload was rejected")

def chunks(text:str,max_chars=5000,overlap=400):
    text=text.strip();result=[];start=0
    while start<len(text):
        end=min(len(text),start+max_chars);piece=text[start:end]
        if end<len(text):
            boundary=max(piece.rfind("\n\n"),piece.rfind("\n"),piece.rfind("}"))
            if boundary>max_chars//2:end=start+boundary+1;piece=text[start:end]
        result.append(piece);start=max(end-overlap,start+1)
    return result

def syntax_chunks(text,language):
    alias=LANGUAGE_ALIASES.get((language or "").lower())
    if not alias:return chunks(text)
    try:
        from tree_sitter_language_pack import get_parser
        tree=get_parser(alias).parse(text.encode());pieces=[]
        interesting={"function_definition","function_declaration","method_definition","method_declaration","class_definition","class_declaration","interface_declaration","lexical_declaration"}
        stack=list(tree.root_node.children)
        while stack:
            node=stack.pop(0)
            if node.type in interesting and node.end_byte-node.start_byte<=20_000:pieces.append(text.encode()[node.start_byte:node.end_byte].decode("utf-8","ignore"))
            elif node.child_count:stack.extend(node.children)
        return pieces or chunks(text)
    except Exception:return chunks(text)

def chunk_document(db,project_id,document_id,title,content,source_type="knowledge",verified=False,**metadata):
    db.document_chunks.delete_many({"project_id":project_id,"document_id":document_id})
    records=[]
    access_scope=metadata.get("access_scope","project")
    pieces=syntax_chunks(content,metadata.get("language")) if source_type=="source_code" else chunks(content)
    for index,piece in enumerate(pieces):
        record={"project_id":project_id,"document_id":document_id,"chunk_index":index,"title":title,"content":piece,"source_type":source_type,"verified":verified,"access_scope":access_scope,"repository":metadata.get("repository"),"commit_sha":metadata.get("commit_sha"),"path":metadata.get("path"),"language":metadata.get("language"),"verification_status":metadata.get("verification_status","verified" if verified else "unverified"),"metadata":metadata,"content_hash":hashlib.sha256(piece.encode()).hexdigest(),"created_at":datetime.now(timezone.utc)}
        vector=embedding(piece,metadata.get("embedding_model","BAAI/bge-small-en-v1.5"))
        if vector:record["embedding"]=vector
        records.append(record)
    if records:db.document_chunks.insert_many(records)
    return len(records)

async def analyze_image(settings,data:bytes,mime_type:str,prompt:str):
    if settings.gemini_api_key:
        body={"contents":[{"parts":[{"text":prompt},{"inline_data":{"mime_type":mime_type,"data":base64.b64encode(data).decode()}}]}],"generationConfig":{"temperature":0.1}}
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        async with httpx.AsyncClient(timeout=90) as client:
            response=await client.post(url,json=body)
            if response.is_success:
                result=response.json();return result["candidates"][0]["content"]["parts"][0]["text"],"gemini_multimodal"
    if settings.google_cloud_vision_api_key:
        body={"requests":[{"image":{"content":base64.b64encode(data).decode()},"features":[{"type":"TEXT_DETECTION"},{"type":"DOCUMENT_TEXT_DETECTION"}]}]}
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(f"https://vision.googleapis.com/v1/images:annotate?key={settings.google_cloud_vision_api_key}",json=body)
            if response.is_success:
                annotations=response.json()["responses"][0].get("textAnnotations",[])
                return (annotations[0].get("description","") if annotations else ""),"cloud_vision_ocr"
    return "","unavailable"
