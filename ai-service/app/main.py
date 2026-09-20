from __future__ import annotations
import hashlib,secrets,smtplib,json,zipfile,threading,time
from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
from urllib.parse import urlparse
import bcrypt,httpx,jwt
import boto3
from botocore.exceptions import ClientError
from bson import ObjectId
from fastapi import FastAPI,HTTPException,Depends,Request,UploadFile,File,Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
from app.config import get_settings
from app.models.schemas import AskRequest,IngestRequest
from app.rag.rag_service import RagService
from app.retrieval.hybrid_retriever import Chunk,HybridRetriever
from app.services.github_app import GitHubAppClient
from app.services.ingestion import antivirus_scan,safe_archive_entry,chunk_document,analyze_image,configure_embeddings

s=get_settings();configure_embeddings(s.gemini_api_key,s.gemini_embedding_model);mongo=MongoClient(s.mongodb_uri,serverSelectionTimeoutMS=8000);db=mongo.get_default_database()
app=FastAPI(title="Barabari Unified API",version="1.0",docs_url="/api/docs")
app.add_middleware(CORSMiddleware,allow_origins=[s.frontend_url,"http://localhost:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
rag=RagService(HybridRetriever([],db),s);github_app=GitHubAppClient(s)
def now():return datetime.now(timezone.utc)
def oid(x):
 try:return ObjectId(str(x))
 except:raise HTTPException(404,"Not found")
def clean(x):
 if isinstance(x,ObjectId):return str(x)
 if isinstance(x,datetime):return x.isoformat()
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,dict):return {("id" if k=="_id" else k):clean(v) for k,v in x.items() if k!="password_hash"}
 return x
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
def invitation_token_filter(value):return {"$or":[{"token_hash":digest(value)},{"tokenHash":digest(value)}]}
def ph(x):return bcrypt.hashpw(x.encode(),bcrypt.gensalt()).decode()
def token(u,t="access"):return jwt.encode({"sub":str(u["_id"]),"role":u["role"],"type":t,"exp":now()+(timedelta(minutes=s.jwt_access_minutes) if t=="access" else timedelta(days=s.jwt_refresh_days))},s.jwt_secret,algorithm="HS256")
def auth(u):return {"user":clean(u),"accessToken":token(u),"refreshToken":token(u,"refresh")}
def user(r:Request):
 try:
  raw=r.headers.get("authorization","").removeprefix("Bearer ")
  if db.revoked_tokens.find_one({"token_hash":digest(raw),"expires_at":{"$gt":now()}}):raise ValueError("revoked")
  p=jwt.decode(raw,s.jwt_secret,algorithms=["HS256"]);u=db.users.find_one({"_id":oid(p["sub"]),"active":True})
 except:raise HTTPException(401,"Authentication required")
 if not u:raise HTTPException(401,"Account unavailable")
 return u
def roles(*allowed):
 def d(u=Depends(user)):
  if u["role"] not in allowed:raise HTTPException(403,"Not permitted")
  return u
 return d
def access(pid,u):
 if u["role"]!="core_admin" and not db.project_members.find_one({"project_id":pid,"user_id":str(u["_id"]),"active":True}):raise HTTPException(403,"No project access")
def email(to,subject,body):
 if not s.smtp_host:return
 m=EmailMessage();m["From"]=s.smtp_username;m["To"]=to;m["Subject"]=subject;m.set_content(body)
 with smtplib.SMTP(s.smtp_host,s.smtp_port,timeout=20) as c:c.starttls();c.login(s.smtp_username,s.smtp_password);c.send_message(m)
def s3():
 if s.storage_provider.lower()!="s3" or not s.aws_s3_bucket:return None
 return boto3.client("s3",region_name=s.aws_region,aws_access_key_id=s.aws_access_key_id,aws_secret_access_key=s.aws_secret_access_key)
def remove_expired_archives():
 while True:
  try:
   for ticket in db.tickets.find({"artifacts.files.expires_at":{"$lte":now()}}):
    for item in ticket.get("artifacts",{}).get("files",[]):
     expiry=item.get("expires_at")
     if expiry and (expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry)<=now():
      if item.get("s3_key") and s3():s3().delete_object(Bucket=s.aws_s3_bucket,Key=item["s3_key"])
      elif item.get("storage_path"):Path(item["storage_path"]).unlink(missing_ok=True)
      db.tickets.update_one({"_id":ticket["_id"]},{"$pull":{"artifacts.files":{"storage_id":item["storage_id"]}}})
  except Exception:pass
  time.sleep(3600)
def backfill_project_knowledge():
 try:
  for project_doc in db.projects.find({}):
   pid=str(project_doc["_id"]);content="\n".join([project_doc.get("summary",""),project_doc.get("requirement_analysis",""),*project_doc.get("expected_deliverables",[]),*project_doc.get("acceptance_criteria",[])])
   if content.strip():chunk_document(db,pid,f"project:{pid}",project_doc.get("name","Project requirements"),content,"requirements",True,repository=project_doc.get("repository_url"),verification_status="project_owner",access_scope="project",embedding_model=s.embedding_model)
  for ticket_doc in db.tickets.find({"status":"CLOSED"}):
   resolution=ticket_doc.get("reviewer_feedback") or ticket_doc.get("ai_resolution",{}).get("rag_response")
   if resolution:chunk_document(db,ticket_doc["project_id"],f"ticket:{ticket_doc['_id']}",ticket_doc.get("title","Resolved ticket"),"\n".join([ticket_doc.get("description",""),resolution]),"verified_resolution",True,verification_status="closed_ticket",access_scope="project",embedding_model=s.embedding_model)
  for knowledge_doc in db.knowledge.find({}):
   content=knowledge_doc.get("content") or knowledge_doc.get("description") or knowledge_doc.get("text") or ""
   if content:chunk_document(db,str(knowledge_doc.get("project_id")),f"knowledge:{knowledge_doc['_id']}",knowledge_doc.get("title","Knowledge point"),content,"knowledge",True,verification_status="existing_knowledge",access_scope="project",embedding_model=s.embedding_model)
  for ticket_doc in db.tickets.find({"status":"OPEN","ai_resolution.status":"ESCALATED"}):
   tid=str(ticket_doc["_id"])
   if not db.escalations.find_one({"ticket_id":tid,"status":{"$in":["open","claimed"]}}):
    mentor=choose_mentor(ticket_doc.get("category","Developer"),ticket_doc.get("skills",[]))
    db.escalations.insert_one({"ticket_id":tid,"project_id":ticket_doc["project_id"],"student_id":ticket_doc["student_id"],"question":ticket_doc["title"],"reason":ticket_doc.get("ai_resolution",{}).get("rag_response","AI confidence was insufficient"),"specialty":ticket_doc.get("category","Developer"),"status":"open","assigned_mentor_id":str(mentor["user_id"]) if mentor else None,"packet":{"description":ticket_doc.get("description"),"diagnostic_context":ticket_doc.get("diagnostic_context"),"artifacts":ticket_doc.get("artifacts"),"ai_resolution":ticket_doc.get("ai_resolution")},"created_at":now()})
    notify_reviewer_team(tid,ticket_doc["title"],ticket_doc.get("category","Developer"),mentor.get("user_id") if mentor else None)
 except Exception:pass
class Login(BaseModel):email:EmailStr;password:str
class Invite(BaseModel):
 email:EmailStr
 role:str
 primary_category:str|None=None
 categories:list[str]=[]
 skills:list[str]=[]
 max_capacity:int=Field(default=5,ge=1,le=50)
class Accept(BaseModel):
 name:str
 password:str=Field(min_length=10)
 primary_category:str|None=None
 categories:list[str]=[]
 skills:list[str]=[]
 max_capacity:int=Field(default=5,ge=1,le=50)
class Project(BaseModel):name:str;summary:str="";stakeholder_name:str="";stakeholder_organization:str="";requirement_analysis:str="";expected_deliverables:list[str]=[];acceptance_criteria:list[str]=[];tech_stack:list[str]=[];repository_url:str|None=None

@app.on_event("startup")
def start():
 mongo.admin.command("ping")
 for collection,key in ((db.users,"email"),(db.invitations,"token_hash")):
  if key not in {k for i in collection.list_indexes() for k in i.get("key",{})}:collection.create_index(key)
 for old in db.invitations.find({"tokenHash":None,"token_hash":{"$type":"string"}},{"token_hash":1}):
  db.invitations.update_one({"_id":old["_id"]},{"$set":{"tokenHash":old["token_hash"]}})
 if s.bootstrap_admin_password:
  db.users.update_one({"email":s.bootstrap_admin_email.lower()},{"$set":{"name":s.bootstrap_admin_name,"email":s.bootstrap_admin_email.lower(),"password_hash":ph(s.bootstrap_admin_password),"role":"core_admin","specialty":"platform","active":True,"email_verified":True},"$setOnInsert":{"created_at":now()}},upsert=True)
 threading.Thread(target=remove_expired_archives,daemon=True,name="zip-expiry-cleaner").start()
 threading.Thread(target=backfill_project_knowledge,daemon=True,name="knowledge-backfill").start()
 try:
  existing=[x.get("name") for x in db.document_chunks.list_search_indexes()]
  if "project_vector_index" not in existing:db.document_chunks.create_search_index(SearchIndexModel(definition={"fields":[{"type":"vector","path":"embedding","numDimensions":384,"similarity":"cosine"},{"type":"filter","path":"project_id"}]},name="project_vector_index",type="vectorSearch"))
 except Exception:pass
@app.get("/health")
def health():return {"status":"UP","backend":"FastAPI","database":"MongoDB Atlas","ai_provider":s.ai_provider,"ollama_model":s.ollama_model,"gemini_fallback":bool(s.gemini_api_key)}
@app.post("/api/v1/ask")
async def direct_ask(x:AskRequest,u=Depends(user)):
 access(x.project_id,u);x.user_id=str(u["_id"]);return await rag.ask(x)
@app.post("/api/v1/auth/login")
def login(x:Login):
 u=db.users.find_one({"email":x.email.lower(),"active":True})
 if not u or not u.get("password_hash") or not bcrypt.checkpw(x.password.encode(),u["password_hash"].encode()):raise HTTPException(401,"Invalid email or password")
 return auth(u)
@app.get("/api/v1/auth/me")
def me(u=Depends(user)):return clean(u)
@app.post("/api/v1/auth/refresh")
def refresh(x:dict):
 try:p=jwt.decode(x.get("refreshToken") or x.get("refresh_token") or "",s.jwt_secret,algorithms=["HS256"])
 except:raise HTTPException(401,"Refresh token invalid or expired")
 if p.get("type")!="refresh":raise HTTPException(401,"Refresh token required")
 u=db.users.find_one({"_id":oid(p["sub"]),"active":True})
 if not u:raise HTTPException(401,"Account unavailable")
 return {"accessToken":token(u),"refreshToken":token(u,"refresh")}
@app.post("/api/v1/auth/logout",status_code=204)
def logout(r:Request,u=Depends(user)):
 raw=r.headers.get("authorization","").removeprefix("Bearer ");db.revoked_tokens.insert_one({"token_hash":digest(raw),"expires_at":now()+timedelta(minutes=s.jwt_access_minutes),"created_at":now()});return None
@app.post("/api/v1/auth/forgot-password")
def forgot(x:dict):
 u=db.users.find_one({"email":x.get("email","").lower()})
 if u:
  t=secrets.token_urlsafe(32);db.password_resets.insert_one({"token_hash":digest(t),"user_id":str(u["_id"]),"expires_at":now()+timedelta(hours=1),"used":False});email(u["email"],"Reset Barabari password",f"{s.frontend_url}/reset-password?token={t}")
 return {"message":"If the account exists, a reset link has been sent."}
@app.post("/api/v1/auth/reset-password")
def reset(x:dict):
 r=db.password_resets.find_one({"token_hash":digest(x.get("token","")),"used":False,"expires_at":{"$gt":now()}})
 if not r:raise HTTPException(400,"Reset link invalid or expired")
 if len(x.get("password",""))<10:raise HTTPException(400,"Password must have at least 10 characters")
 db.users.update_one({"_id":oid(r["user_id"])},{"$set":{"password_hash":ph(x["password"])}});db.password_resets.update_one({"_id":r["_id"]},{"$set":{"used":True}});return {"message":"Password changed. Sign in now."}
@app.post("/api/v1/invitations")
def invite(x:Invite,u=Depends(roles("core_admin"))):
 if x.role not in ["student","core_reviewer"]:raise HTTPException(400,"Use student or core_reviewer")
 t=secrets.token_urlsafe(32);token_digest=digest(t);d={**x.model_dump(),"email":x.email.lower(),"token_hash":token_digest,"tokenHash":token_digest,"status":"pending","expires_at":now()+timedelta(days=7),"created_at":now()};r=db.invitations.insert_one(d);email(x.email,"You are invited to Barabari",f"Verify and set your password: {s.frontend_url}/invite/{t}");return clean({"_id":r.inserted_id,**d})
@app.get("/api/v1/invitations")
def invites(u=Depends(roles("core_admin"))):return clean(list(db.invitations.find().sort("created_at",-1)))
@app.get("/api/v1/invitations/{t}")
def get_invite(t:str):
 x=db.invitations.find_one({**invitation_token_filter(t),"status":"pending","expires_at":{"$gt":now()}})
 if not x:raise HTTPException(404,"Invitation invalid, expired, or used")
 return clean(x)
@app.post("/api/v1/invitations/{t}/accept")
def accept(t:str,x:Accept):
 i=db.invitations.find_one({**invitation_token_filter(t),"status":"pending","expires_at":{"$gt":now()}})
 if not i:raise HTTPException(400,"Invitation invalid or expired")
 specialty=i.get("specialty")
 if i["role"]=="core_reviewer":
  primary_cat=x.primary_category or i.get("primary_category") or "Developer"
  specialty=primary_cat
 d={"name":x.name,"email":i["email"],"password_hash":ph(x.password),"role":i["role"],"specialty":specialty,"active":True,"email_verified":True,"created_at":now()};r=db.users.insert_one(d);d["_id"]=r.inserted_id
 if i["role"]=="core_reviewer":
  primary_cat=x.primary_category or i.get("primary_category") or "Developer"
  cats=x.categories if x.categories else (i.get("categories") or [primary_cat])
  skills_list=x.skills if x.skills else (i.get("skills") or [])
  cap=x.max_capacity if x.max_capacity else i.get("max_capacity",5)
  db.mentor_profiles.update_one({"user_id":str(r.inserted_id)},{"$set":{"user_id":str(r.inserted_id),"name":x.name,"email":i["email"],"primary_category":primary_cat,"categories":cats,"skills":skills_list,"max_capacity":cap,"current_active_tickets":0,"is_available":True,"total_resolved_tickets":0,"updated_at":now()},"$setOnInsert":{"created_at":now()}},upsert=True)
 db.invitations.update_one({"_id":i["_id"]},{"$set":{"status":"accepted"}});return auth(d)
@app.post("/api/v1/invitations/{iid}/revoke")
def revoke(iid:str,u=Depends(roles("core_admin"))):db.invitations.update_one({"_id":oid(iid)},{"$set":{"status":"revoked"}});return {"status":"revoked"}

@app.get("/api/v1/users")
def users(u=Depends(roles("core_admin"))):return clean(list(db.users.find()))
@app.patch("/api/v1/users/me")
async def update_me(r:Request,u=Depends(user)):
 b=await r.json();allowed={k:b[k] for k in ("name","timezone","preferences") if k in b};allowed["updated_at"]=now();db.users.update_one({"_id":u["_id"]},{"$set":allowed});return clean(db.users.find_one({"_id":u["_id"]}))
@app.get("/api/v1/users/{uid}")
def get_user(uid:str,u=Depends(roles("core_reviewer","core_admin"))):
 target=db.users.find_one({"_id":oid(uid)})
 if not target:raise HTTPException(404,"User not found")
 return clean(target)
@app.get("/api/v1/projects")
def projects(u=Depends(user)):
 ids=[oid(v["project_id"]) for v in db.project_members.find({"user_id":str(u["_id"]),"active":True})];return clean(list(db.projects.find({} if u["role"]=="core_admin" else {"_id":{"$in":ids}})))
@app.get("/api/v1/projects/{pid}")
def get_project(pid:str,u=Depends(user)):
 access(pid,u);p=db.projects.find_one({"_id":oid(pid)})
 if not p:raise HTTPException(404,"Project not found")
 p["metrics"]={"requirements":db.requirements.count_documents({"project_id":pid}),"tasks":db.tasks.count_documents({"project_id":pid}),"open_escalations":db.escalations.count_documents({"project_id":pid,"status":{"$in":["open","claimed"]}})};return clean(p)
@app.post("/api/v1/projects")
def project(x:Project,u=Depends(roles("student","core_admin"))):
 d={**x.model_dump(),"status":"active","health":100,"created_by":str(u["_id"]),"student_editable":u["role"]=="student","created_at":now(),"updated_at":now()};r=db.projects.insert_one(d);d["_id"]=r.inserted_id
 if u["role"]=="student":db.project_members.insert_one({"project_id":str(r.inserted_id),"user_id":str(u["_id"]),"role":"student_owner","active":True,"created_at":now()})
 chunk_document(db,str(r.inserted_id),f"project:{r.inserted_id}",x.name,"\n".join([x.summary,x.requirement_analysis,*x.expected_deliverables,*x.acceptance_criteria]),"requirements",True,repository=x.repository_url,access_scope="project")
 return clean(d)
@app.patch("/api/v1/projects/{pid}")
def edit_project(pid:str,x:Project,u=Depends(roles("student","core_admin"))):
 current=db.projects.find_one({"_id":oid(pid)})
 if not current:raise HTTPException(404,"Project not found")
 if u["role"]!="core_admin" and current.get("created_by")!=str(u["_id"]):raise HTTPException(403,"Students may edit only projects they created")
 update={**x.model_dump(),"updated_at":now()};db.projects.update_one({"_id":current["_id"]},{"$set":update})
 chunk_document(db,pid,f"project:{pid}",x.name,"\n".join([x.summary,x.requirement_analysis,*x.expected_deliverables,*x.acceptance_criteria]),"requirements",True,repository=x.repository_url,access_scope="project")
 return clean({**current,**update})
@app.delete("/api/v1/projects/{pid}",status_code=204)
def delete_project(pid:str,u=Depends(roles("student","core_admin"))):
 project_doc=db.projects.find_one({"_id":oid(pid)})
 if not project_doc:raise HTTPException(404,"Project not found")
 if u["role"]!="core_admin" and project_doc.get("created_by")!=str(u["_id"]):raise HTTPException(403,"Students may delete only projects they created")
 # Remove uploaded objects before deleting their metadata. A project deletion is
 # intentionally cascading so its private evidence cannot remain retrievable.
 for ticket_doc in db.tickets.find({"project_id":pid},{"artifacts.files":1}):
  for item in ticket_doc.get("artifacts",{}).get("files",[]):
   try:
    if item.get("s3_key") and s3():s3().delete_object(Bucket=item.get("s3_bucket") or s.aws_s3_bucket,Key=item["s3_key"])
    elif item.get("storage_path"):Path(item["storage_path"]).unlink(missing_ok=True)
   except Exception:pass
 for collection in (db.project_members,db.requirements,db.documents,db.questions,db.decisions,db.escalations,db.knowledge,db.issues,db.tasks,db.work,db.tickets,db.question_attempts,db.document_chunks,db.repository_syncs):
  collection.delete_many({"project_id":pid})
 db.projects.delete_one({"_id":project_doc["_id"]})
 return None
@app.post("/api/v1/projects/{pid}/members")
def member(pid:str,x:dict,u=Depends(roles("core_admin"))):db.project_members.update_one({"project_id":pid,"user_id":x["user_id"]},{"$set":{**x,"project_id":pid,"active":True}},upsert=True);return {"status":"added"}
@app.get("/api/v1/projects/{pid}/members")
def members(pid:str,u=Depends(user)):access(pid,u);return clean(list(db.project_members.find({"project_id":pid,"active":True})))
@app.delete("/api/v1/projects/{pid}/members/{uid}",status_code=204)
def remove_member(pid:str,uid:str,u=Depends(roles("core_admin"))):db.project_members.update_one({"project_id":pid,"user_id":uid},{"$set":{"active":False,"updated_at":now()}});return None
def routes(name):
 async def ls(pid:str,u=Depends(user)):access(pid,u);return clean(list(db[name].find({"project_id":pid}).sort("created_at",-1)))
 async def add(pid:str,r:Request,u=Depends(user)):
  access(pid,u);d=await r.json();d.update({"project_id":pid,"created_by":str(u["_id"]),"created_at":now()})
  if name=="questions":
   if u["role"]!="student":raise HTTPException(403,"Only students submit guidance questions")
   result=await rag.ask(AskRequest(project_id=pid,user_id=str(u["_id"]),question=d.get("question") or d.get("title", ""),mode=d.get("mode"),conversation_id=d.get("conversation_id"),attempted_solutions=d.get("attempted_solutions",[]),context_overrides=d.get("context_overrides",{})));d.update({"mode":result.mode,"ai_response":result.model_dump(),"status":"needs_escalation" if result.needs_escalation else "guidance_ready"})
  elif name=="knowledge" and u["role"] not in {"core_reviewer","core_admin"}:raise HTTPException(403,"Only the core team publishes verified knowledge")
  elif name=="escalations" and u["role"]!="student":raise HTTPException(403,"Only students submit escalations")
  elif name=="decisions":d.update({"status":"proposed","proposed_by":str(u["_id"])})
  elif name=="requirements":d.update({"status":d.get("status","draft"),"version":d.get("version",1)})
  elif name=="tasks":d.update({"status":d.get("status","todo"),"prerequisite_task_ids":d.get("prerequisite_task_ids",[])})
  z=db[name].insert_one(d);d["_id"]=z.inserted_id
  if name=="knowledge":chunk_document(db,pid,f"knowledge:{z.inserted_id}",d.get("title","Knowledge"),d.get("content") or d.get("description", ""),"knowledge",True,verification_status="core_team_verified" if u["role"]!="student" else "student_provided",access_scope="project")
  return clean(d)
 app.add_api_route(f"/api/v1/projects/{{pid}}/{name}",ls,methods=["GET"],name="list_"+name);app.add_api_route(f"/api/v1/projects/{{pid}}/{name}",add,methods=["POST"],name="add_"+name)
for c in ["requirements","documents","questions","decisions","escalations","knowledge","issues","tasks"]:routes(c)

# Master contract detail routes and workflow engines.
def owned(collection,item_id,u):
 item=collection.find_one({"_id":oid(item_id)})
 if not item:raise HTTPException(404,"Record not found")
 access(item["project_id"],u);return item
@app.get("/api/v1/requirements/{rid}")
def requirement_detail(rid:str,u=Depends(user)):return clean(owned(db.requirements,rid,u))
@app.patch("/api/v1/requirements/{rid}")
async def requirement_update(rid:str,r:Request,u=Depends(roles("core_reviewer","core_admin"))):
 item=owned(db.requirements,rid,u);b=await r.json();previous={k:item.get(k) for k in ("title","text","status","acceptance_criteria","affected_components")};db.requirement_versions.insert_one({"project_id":item["project_id"],"requirement_id":rid,"snapshot":previous,"changed_by":str(u["_id"]),"created_at":now()});b["updated_at"]=now();db.requirements.update_one({"_id":item["_id"]},{"$set":b});return clean(db.requirements.find_one({"_id":item["_id"]}))
@app.post("/api/v1/requirements/{rid}/analyze")
async def requirement_analyze(rid:str,u=Depends(user)):
 item=owned(db.requirements,rid,u);text=item.get("text") or item.get("description") or "";prompt=f"Convert this client requirement into plain English. Return a concise summary, missing details, acceptance criteria, and affected components. Requirement: {text}"
 try:analysis,_=await rag.gateway.generate_text(prompt)
 except Exception:analysis="AI analysis unavailable; core review required."
 db.requirements.update_one({"_id":item["_id"]},{"$set":{"analysis":analysis,"updated_at":now()}});return {"analysis":analysis}
@app.post("/api/v1/projects/{pid}/requirements/check-understanding")
async def check_understanding(pid:str,r:Request,u=Depends(roles("student"))):
 access(pid,u);b=await r.json();rid=b.get("requirement_id");req=db.requirements.find_one({"_id":oid(rid),"project_id":pid}) if rid else db.requirements.find_one({"project_id":pid,"status":{"$in":["confirmed","active","changed"]}})
 if not req:raise HTTPException(404,"Requirement not found")
 prompt=f"Compare the client requirement with the student's understanding. Identify exact omissions, contradictions, and safe next steps. REQUIREMENT: {req.get('text') or req.get('description')} STUDENT: {b.get('understanding','')}"
 try:analysis,_=await rag.gateway.generate_text(prompt)
 except Exception:analysis="Automated comparison unavailable; request core review."
 conflict=any(word in analysis.lower() for word in ("conflict","contradict","missing","omit"));record={"project_id":pid,"requirement_id":str(req["_id"]),"student_id":str(u["_id"]),"understanding":b.get("understanding"),"analysis":analysis,"mismatch":conflict,"created_at":now()};z=db.understanding_checks.insert_one(record);record["_id"]=z.inserted_id;return clean(record)
@app.post("/api/v1/projects/{pid}/requirements/compare")
async def compare_requirement(pid:str,r:Request,u=Depends(roles("core_reviewer","core_admin"))):
 access(pid,u);b=await r.json();current="\n".join((x.get("text") or x.get("description") or "") for x in db.requirements.find({"project_id":pid,"status":{"$ne":"deprecated"}}));prompt=f"Compare existing requirements against the new client communication. List changes, conflicts, and impacted components. EXISTING: {current} NEW: {b.get('communication','')}"
 try:analysis,_=await rag.gateway.generate_text(prompt)
 except Exception:analysis="Automated impact analysis unavailable."
 return {"analysis":analysis,"requires_core_decision":True}

@app.get("/api/v1/documents/{did}")
def document_detail(did:str,u=Depends(user)):return clean(owned(db.documents,did,u))
@app.get("/api/v1/documents/{did}/status")
def document_status(did:str,u=Depends(user)):
 item=owned(db.documents,did,u);return {"document_id":did,"status":item.get("index_status","indexed"),"chunks":db.document_chunks.count_documents({"document_id":did})}
@app.delete("/api/v1/documents/{did}",status_code=204)
def document_delete(did:str,u=Depends(roles("core_reviewer","core_admin"))):
 item=owned(db.documents,did,u);db.document_chunks.delete_many({"project_id":item["project_id"],"document_id":did});db.documents.delete_one({"_id":item["_id"]});return None
@app.post("/api/v1/documents/{did}/reindex")
def document_reindex(did:str,u=Depends(roles("core_reviewer","core_admin"))):
 item=owned(db.documents,did,u);count=chunk_document(db,item["project_id"],did,item.get("title","Document"),item.get("content",""),item.get("source_type","document"),True,verification_status="core_reindexed",access_scope="project");return {"status":"indexed","chunks":count}

@app.get("/api/v1/questions/{qid}")
def question_detail(qid:str,u=Depends(user)):return clean(owned(db.questions,qid,u))
@app.post("/api/v1/questions/{qid}/attempts")
async def question_attempt(qid:str,r:Request,u=Depends(roles("student"))):
 q=owned(db.questions,qid,u);b=await r.json();attempt={"project_id":q["project_id"],"question_id":qid,"student_id":str(u["_id"]),"content":b.get("content") or b.get("attempt"),"created_at":now()};result=await rag.ask(AskRequest(project_id=q["project_id"],user_id=str(u["_id"]),question=q.get("question") or q.get("title",""),mode="GUIDE",attempted_solutions=[attempt["content"]]));attempt["evaluation"]=result.model_dump();z=db.question_attempts.insert_one(attempt);attempt["_id"]=z.inserted_id;return clean(attempt)
@app.post("/api/v1/questions/{qid}/continue")
def question_continue(qid:str,u=Depends(roles("student"))):
 q=owned(db.questions,qid,u);tasks=list(db.tasks.find({"project_id":q["project_id"],"status":{"$in":["todo","in_progress"]}}));blocked={str(v) for t in db.tasks.find({"project_id":q["project_id"],"status":{"$ne":"done"}}) for v in t.get("blocks",[])};return clean({"can_continue":True,"suggested_unblocked_tasks":[t for t in tasks if str(t["_id"]) not in blocked]})
@app.post("/api/v1/questions/{qid}/feedback")
async def question_feedback(qid:str,r:Request,u=Depends(roles("student"))):q=owned(db.questions,qid,u);b=await r.json();db.questions.update_one({"_id":q["_id"]},{"$set":{"feedback":b,"updated_at":now()}});return {"status":"recorded"}
@app.post("/api/v1/questions/{qid}/escalate")
async def question_escalate(qid:str,r:Request,u=Depends(roles("student"))):
 q=owned(db.questions,qid,u);b=await r.json();d={"project_id":q["project_id"],"student_id":str(u["_id"]),"question_id":qid,"question":q.get("question") or q.get("title"),"reason":b.get("reason","Student requested core review"),"status":"open","packet":{"attempts":clean(list(db.question_attempts.find({"question_id":qid}))),"exact_decision_required":b.get("exact_decision_required")},"created_at":now()};z=db.escalations.insert_one(d);d["_id"]=z.inserted_id;return clean(d)
@app.get("/api/v1/questions/{qid}/similar")
def similar_questions(qid:str,u=Depends(user)):
 q=owned(db.questions,qid,u);terms=set((q.get("question") or q.get("title","")).lower().split());rows=[]
 for item in db.questions.find({"project_id":q["project_id"],"_id":{"$ne":q["_id"]}}).limit(100):
  score=len(terms&set((item.get("question") or item.get("title","")).lower().split()))/max(len(terms),1)
  if score>.2:rows.append({**clean(item),"similarity":score})
 return sorted(rows,key=lambda x:x["similarity"],reverse=True)[:10]

@app.get("/api/v1/decisions/{did}")
def decision_detail(did:str,u=Depends(user)):return clean(owned(db.decisions,did,u))
@app.patch("/api/v1/decisions/{did}")
async def decision_update(did:str,r:Request,u=Depends(roles("core_reviewer","core_admin"))):
 item=owned(db.decisions,did,u);b=await r.json();status=b.get("status",item.get("status","proposed"))
 if status not in {"proposed","confirmed","rejected","superseded"}:raise HTTPException(400,"Invalid decision status")
 b.update({"status":status,"confirmed_by":str(u["_id"]) if status=="confirmed" else None,"updated_at":now()});db.decisions.update_one({"_id":item["_id"]},{"$set":b});db.audit_logs.insert_one({"action":"DECISION_"+status.upper(),"project_id":item["project_id"],"entity_id":did,"actor_id":str(u["_id"]),"created_at":now()})
 if status=="confirmed":chunk_document(db,item["project_id"],f"decision:{did}",b.get("title",item.get("title","Confirmed decision")),b.get("rationale",item.get("rationale",item.get("description",""))),"decision",True,verification_status="human_confirmed",access_scope="project")
 return clean(db.decisions.find_one({"_id":item["_id"]}))
@app.post("/api/v1/decisions/{did}/conflicts/check")
async def decision_conflict(did:str,r:Request,u=Depends(user)):
 item=owned(db.decisions,did,u);b=await r.json();result=await rag.ask(AskRequest(project_id=item["project_id"],user_id=str(u["_id"]),question=f"Check this proposed change against decision {item.get('title')}: {b.get('proposed_change','')}",mode="DECISION"));return result
@app.get("/api/v1/escalations/{eid}")
def escalation_detail(eid:str,u=Depends(user)):return clean(owned(db.escalations,eid,u))
@app.patch("/api/v1/escalations/{eid}")
async def escalation_update(eid:str,r:Request,u=Depends(user)):
 item=owned(db.escalations,eid,u)
 if u["role"]=="student" and item.get("student_id")!=str(u["_id"]):raise HTTPException(403,"Not your escalation")
 if item.get("status") not in {"draft","open"}:raise HTTPException(409,"Only draft/open escalation can be edited")
 b=await r.json();b["updated_at"]=now();db.escalations.update_one({"_id":item["_id"]},{"$set":b});return clean(db.escalations.find_one({"_id":item["_id"]}))
@app.post("/api/v1/escalations/{eid}/submit")
def escalation_submit(eid:str,u=Depends(roles("student"))):
 item=owned(db.escalations,eid,u);db.escalations.update_one({"_id":item["_id"]},{"$set":{"status":"open","submitted_at":now()}});notify_reviewer_team(eid,item.get("question","Escalation"),item.get("specialty","Developer"));return {"status":"open"}
@app.post("/api/v1/escalations/{eid}/withdraw")
def escalation_withdraw(eid:str,u=Depends(roles("student"))):
 item=owned(db.escalations,eid,u)
 if item.get("student_id")!=str(u["_id"]):raise HTTPException(403,"Not your escalation")
 db.escalations.update_one({"_id":item["_id"]},{"$set":{"status":"withdrawn","updated_at":now()}});return {"status":"withdrawn"}
@app.get("/api/v1/core/queue/{eid}")
def core_queue_detail(eid:str,u=Depends(roles("core_reviewer","core_admin"))):return clean(owned(db.escalations,eid,u))
@app.post("/api/v1/core/escalations/{eid}/request-info")
async def request_info(eid:str,r:Request,u=Depends(roles("core_reviewer","core_admin"))):
 item=owned(db.escalations,eid,u);b=await r.json();db.escalations.update_one({"_id":item["_id"]},{"$set":{"status":"awaiting_student_info","info_request":b.get("message"),"handled_by":str(u["_id"]),"updated_at":now()}});db.notifications.insert_one({"user_id":item.get("student_id"),"type":"ESCALATION_INFO_REQUESTED","escalation_id":eid,"message":b.get("message"),"read":False,"created_at":now()});return {"status":"awaiting_student_info"}

@app.get("/api/v1/knowledge/{kid}")
def knowledge_detail(kid:str,u=Depends(user)):return clean(owned(db.knowledge,kid,u))
@app.post("/api/v1/knowledge/{kid}/feedback")
async def knowledge_feedback(kid:str,r:Request,u=Depends(user)):
 item=owned(db.knowledge,kid,u);b=await r.json();helpful=bool(b.get("helpful"));db.knowledge_feedback.update_one({"knowledge_id":kid,"user_id":str(u["_id"])},{"$set":{"project_id":item["project_id"],"helpful":helpful,"comment":b.get("comment"),"updated_at":now()}},upsert=True);return {"status":"recorded"}
@app.post("/api/v1/projects/{pid}/knowledge/search")
async def knowledge_search(pid:str,r:Request,u=Depends(user)):
 access(pid,u);b=await r.json();matches=rag.retriever.search(pid,b.get("query",""),limit=min(int(b.get("limit",10)),25));return clean([{"document_id":c.document_id,"title":c.title,"content":c.content,"score":score,"metadata":c.metadata} for c,score in matches])

def build_clusters(pid):
 questions=list(db.questions.find({"project_id":pid}))+list(db.tickets.find({"project_id":pid}));groups={}
 for q in questions:
  text=(q.get("question") or q.get("title") or "").lower();key=" ".join(sorted({w for w in text.split() if len(w)>4})[:5]) or "uncategorized";groups.setdefault(key,[]).append(q)
 db.issue_clusters.delete_many({"project_id":pid});records=[]
 for key,items in groups.items():
  if len(items)>1:records.append({"project_id":pid,"label":key,"count":len(items),"question_ids":[str(x["_id"]) for x in items],"status":"active","created_at":now()})
 if records:db.issue_clusters.insert_many(records)
 return records
@app.get("/api/v1/projects/{pid}/issues/clusters")
def issue_clusters(pid:str,u=Depends(roles("core_reviewer","core_admin"))):access(pid,u);return clean(list(db.issue_clusters.find({"project_id":pid}).sort("count",-1)))
@app.get("/api/v1/issue-clusters/{cid}")
def issue_cluster(cid:str,u=Depends(roles("core_reviewer","core_admin"))):return clean(owned(db.issue_clusters,cid,u))
@app.post("/api/v1/projects/{pid}/issues/recluster")
def issue_recluster(pid:str,u=Depends(roles("core_reviewer","core_admin"))):access(pid,u);records=build_clusters(pid);return {"status":"complete","clusters":len(records)}
@app.get("/api/v1/projects/{pid}/issues/recurring")
def recurring_issues(pid:str,u=Depends(roles("core_reviewer","core_admin"))):access(pid,u);return clean(list(db.issue_clusters.find({"project_id":pid,"count":{"$gte":2}}).sort("count",-1)))

@app.get("/api/v1/tasks/{tid}")
def task_detail(tid:str,u=Depends(user)):return clean(owned(db.tasks,tid,u))
@app.patch("/api/v1/tasks/{tid}")
async def task_update(tid:str,r:Request,u=Depends(user)):
 item=owned(db.tasks,tid,u);b=await r.json()
 if b.get("status") and b["status"] not in {"todo","in_progress","blocked","done"}:raise HTTPException(400,"Invalid task status")
 b["updated_at"]=now();db.tasks.update_one({"_id":item["_id"]},{"$set":b});return clean(db.tasks.find_one({"_id":item["_id"]}))
@app.post("/api/v1/tasks/{tid}/dependencies")
async def task_dependencies(tid:str,r:Request,u=Depends(user)):
 item=owned(db.tasks,tid,u);b=await r.json();dependency_id=b.get("task_id")
 if not db.tasks.find_one({"_id":oid(dependency_id),"project_id":item["project_id"]}):raise HTTPException(404,"Dependency task not found")
 db.tasks.update_one({"_id":item["_id"]},{"$addToSet":{"prerequisite_task_ids":dependency_id},"$set":{"updated_at":now()}});return {"status":"added"}
@app.get("/api/v1/tasks/{tid}/blockers")
def task_blockers(tid:str,u=Depends(user)):
 item=owned(db.tasks,tid,u);ids=[oid(x) for x in item.get("prerequisite_task_ids",[])];return clean(list(db.tasks.find({"_id":{"$in":ids},"status":{"$ne":"done"}})))
@app.get("/api/v1/projects/{pid}/continue-options")
def continue_options(pid:str,u=Depends(roles("student"))):
 access(pid,u);tasks=list(db.tasks.find({"project_id":pid,"status":{"$in":["todo","in_progress"]}}));result=[]
 for task_doc in tasks:
  prerequisites=[oid(x) for x in task_doc.get("prerequisite_task_ids",[])];blocked=bool(prerequisites and db.tasks.find_one({"_id":{"$in":prerequisites},"status":{"$ne":"done"}}))
  if not blocked:result.append(task_doc)
 return clean({"can_continue":bool(result),"suggested_unblocked_tasks":result})

@app.get("/api/v1/jobs/{jid}")
def job_status(jid:str,u=Depends(user)):return clean(owned(db.jobs,jid,u))
def reindex_project(pid,u):
 access(pid,u);job={"project_id":pid,"type":"reindex","status":"running","created_by":str(u["_id"]),"created_at":now()};z=db.jobs.insert_one(job);job["_id"]=z.inserted_id
 try:
  project_doc=db.projects.find_one({"_id":oid(pid)});count=chunk_document(db,pid,f"project:{pid}",project_doc.get("name","Project"),"\n".join([project_doc.get("summary",""),project_doc.get("requirement_analysis","")]),"requirements",True,verification_status="project_owner",access_scope="project");db.jobs.update_one({"_id":z.inserted_id},{"$set":{"status":"complete","chunks":count,"completed_at":now()}})
 except Exception as exc:db.jobs.update_one({"_id":z.inserted_id},{"$set":{"status":"failed","error":str(exc),"completed_at":now()}})
 return clean(db.jobs.find_one({"_id":z.inserted_id}))
@app.post("/api/v1/projects/{pid}/rebuild-context")
def rebuild_context(pid:str,u=Depends(roles("core_reviewer","core_admin"))):return reindex_project(pid,u)
@app.post("/api/v1/projects/{pid}/reindex")
def reindex(pid:str,u=Depends(roles("core_reviewer","core_admin"))):return reindex_project(pid,u)

def project_metrics(pid):
 tickets=db.tickets.count_documents({"project_id":pid});resolved=db.tickets.count_documents({"project_id":pid,"status":"CLOSED"});ai=db.tickets.count_documents({"project_id":pid,"ai_resolution.status":"RESOLVED_BY_AI"});return {"tickets":tickets,"resolved":resolved,"open":tickets-resolved,"self_resolution_rate":round(ai/max(tickets,1)*100,1),"knowledge_items":db.knowledge.count_documents({"project_id":pid})}
@app.get("/api/v1/projects/{pid}/analytics/overview")
def project_analytics(pid:str,u=Depends(user)):access(pid,u);return project_metrics(pid)
@app.get("/api/v1/projects/{pid}/analytics/issues")
def project_issue_analytics(pid:str,u=Depends(roles("core_reviewer","core_admin"))):access(pid,u);return {"by_category":list(db.tickets.aggregate([{"$match":{"project_id":pid}},{"$group":{"_id":"$category","count":{"$sum":1}}},{"$sort":{"count":-1}}])),"clusters":clean(list(db.issue_clusters.find({"project_id":pid}).sort("count",-1)))}
@app.get("/api/v1/core/analytics/recurring-issues")
def recurring_analytics(u=Depends(roles("core_reviewer","core_admin"))):return clean(list(db.issue_clusters.find({"count":{"$gte":2}}).sort("count",-1).limit(50)))
@app.get("/api/v1/core/analytics/escalations")
def escalation_analytics(u=Depends(roles("core_reviewer","core_admin"))):return {"open":db.escalations.count_documents({"status":{"$in":["open","claimed"]}}),"closed":db.escalations.count_documents({"status":{"$in":["resolved","closed"]}})}
@app.get("/api/v1/core/analytics/knowledge-reuse")
def knowledge_reuse(u=Depends(roles("core_reviewer","core_admin"))):
 total=db.tickets.count_documents({});ai=db.tickets.count_documents({"ai_resolution.status":"RESOLVED_BY_AI"});return {"tickets":total,"ai_resolved":ai,"self_resolution_rate":round(ai/max(total,1)*100,1),"knowledge_chunks":db.document_chunks.count_documents({"verified":True})}

MAX_UPLOAD_BYTES=50*1024*1024
ALLOWED_UPLOADS={".png",".jpg",".jpeg",".webp",".gif",".txt",".md",".pdf",".zip",".py",".js",".jsx",".ts",".tsx",".java",".json",".yaml",".yml",".log",".html",".css",".sql"}
def choose_mentor(category:str,skills:list[str]):
 pipeline=[{"$match":{"is_available":True,"categories":category,"$expr":{"$lt":["$current_active_tickets","$max_capacity"]}}},{"$addFields":{"skill_matches":{"$size":{"$setIntersection":["$skills",skills]}}}},{"$sort":{"skill_matches":-1,"current_active_tickets":1}},{"$limit":1}]
 return next(db.mentor_profiles.aggregate(pipeline),None)
def notify_reviewer_team(ticket_id,title,category,preferred=None):
 recipients=[str(preferred)] if preferred else [str(x["user_id"]) for x in db.mentor_profiles.find({"is_available":True,"categories":category},{"user_id":1})]
 if not recipients:recipients=[str(x["_id"]) for x in db.users.find({"role":"core_admin","active":True},{"_id":1})]
 for recipient in set(recipients):db.notifications.insert_one({"user_id":recipient,"type":"TICKET_ESCALATED","ticket_id":ticket_id,"title":title,"category":category,"read":False,"created_at":now()})
@app.post("/api/v1/tickets")
async def create_ticket(project_id:str=Form(...),title:str=Form(...),category:str=Form(...),sub_category:str=Form(""),description:str=Form(...),client_requirement_ref:str=Form(""),repository_url:str=Form(""),branch_or_pr:str=Form(""),commit_hash:str=Form(""),skills:str=Form("[]"),network_logs:str=Form("{}"),requirement_text:str=Form(""),operating_system:str=Form(""),runtime_versions:str=Form(""),steps_to_reproduce:str=Form(""),expected_behavior:str=Form(""),actual_behavior:str=Form(""),error_messages:str=Form(""),relevant_file_paths:str=Form(""),dependency_manifest:str=Form(""),related_issue_urls:str=Form(""),attempted_solutions:str=Form(""),files:list[UploadFile]=File(default=[]),u=Depends(roles("student"))):
 access(project_id,u)
 parsed_skills=json.loads(skills or "[]");parsed_logs=json.loads(network_logs or "{}")
 root=Path(s.local_storage_path).resolve()/"tickets";root.mkdir(parents=True,exist_ok=True);stored=[];context=[]
 total=0
 for upload in files:
  data=await upload.read();total+=len(data)
  if total>MAX_UPLOAD_BYTES:raise HTTPException(413,"Combined attachments cannot exceed 50 MB")
  ext=Path(upload.filename or "").suffix.lower()
  if ext not in ALLOWED_UPLOADS:raise HTTPException(415,f"Unsupported attachment type: {ext or 'unknown'}")
  kind="image" if ext in {".png",".jpg",".jpeg",".webp",".gif"} else "archive" if ext==".zip" else "document"
  if kind=="image" and len(data)>=1024*1024:raise HTTPException(413,f"{upload.filename}: each image must be smaller than 1 MB")
  if kind=="archive" and len(data)>=50*1024*1024:raise HTTPException(413,f"{upload.filename}: each ZIP must be smaller than 50 MB")
  if kind=="archive":
   try:item_scan=antivirus_scan(data)
   except ValueError as exc:raise HTTPException(422,str(exc)) from exc
  storage_id=secrets.token_hex(12);safe=f"{storage_id}{ext}";path=root/safe
  key=f"temporary-zips/{project_id}/{safe}" if kind=="archive" else f"tickets/{project_id}/{kind}s/{safe}"
  item={"storage_id":storage_id,"original_name":upload.filename,"content_type":upload.content_type,"size_bytes":len(data),"kind":kind}
  if kind=="archive":item["antivirus_scan"]=item_scan
  cloud=s3()
  if cloud:
   try:cloud.put_object(Bucket=s.aws_s3_bucket,Key=key,Body=data,ContentType=upload.content_type or "application/octet-stream",Metadata={"project-id":project_id,"temporary":"true" if kind=="archive" else "false"})
   except ClientError as exc:raise HTTPException(503,"S3 upload is not authorized. Grant this application's AWS identity s3:PutObject and s3:DeleteObject for the configured bucket.") from exc
   item.update({"storage_provider":"s3","s3_bucket":s.aws_s3_bucket,"s3_key":key,"file_url":f"s3://{s.aws_s3_bucket}/{key}"})
  else:path.write_bytes(data);item.update({"storage_provider":"local","storage_path":str(path)})
  if kind=="archive":item["expires_at"]=now()+timedelta(hours=24)
  if ext in {".txt",".md",".py",".js",".jsx",".ts",".tsx",".java",".json",".yaml",".yml",".log",".html",".css",".sql"}:
   extracted=data[:500000].decode("utf-8","ignore");context.append(extracted)
   chunk_document(db,project_id,f"upload:{storage_id}",upload.filename or safe,extracted,"logs" if ext==".log" else "source_code",True,path=upload.filename,language=ext.lstrip("."),verification_status="student_provided",access_scope="project")
  if kind=="image":
   analysis,processor=await analyze_image(s,data,upload.content_type or "image/png","Analyze this project-support screenshot. Extract visible errors, UI behavior, architecture information, and concrete debugging clues.")
   item["analysis_processor"]=processor
   if analysis:
    item["image_analysis"]=analysis;context.append(analysis)
    chunk_document(db,project_id,f"image:{storage_id}",upload.filename or "Screenshot analysis",analysis,"image_analysis",True,path=upload.filename,verification_status="ai_extracted",access_scope="project")
  if ext==".pdf":
   try:context.append("\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(data)).pages)[:1000000])
   except Exception:item["extraction_warning"]="PDF text extraction failed; original file retained"
  if ext==".zip":
   try:
    with zipfile.ZipFile(BytesIO(data)) as z:
     entries=[i for i in z.infolist() if not i.is_dir()]
     if len(entries)>2000:raise HTTPException(413,"ZIP contains more than 2,000 files")
     expanded=sum(i.file_size for i in entries)
     if expanded>250*1024*1024:raise HTTPException(413,"ZIP expands beyond the 250 MB safety limit")
     item["archive_entries"]=[i.filename for i in entries][:500];item["expanded_size_bytes"]=expanded
     for entry in entries:
      suffix=Path(entry.filename).suffix.lower()
      if safe_archive_entry(entry):
       extracted=z.read(entry)[:2_000_000].decode("utf-8","ignore");context.append(extracted)
       chunk_document(db,project_id,f"zip:{storage_id}:{entry.filename}",entry.filename,extracted,"readme" if Path(entry.filename).name.lower().startswith("readme") else "source_code",True,path=entry.filename,language=suffix.lstrip("."),verification_status="student_provided",access_scope="project")
   except zipfile.BadZipFile:raise HTTPException(400,f"{upload.filename} is not a valid ZIP archive")
  stored.append(item)
 req=AskRequest(project_id=project_id,user_id=str(u["_id"]),question="\n".join([title,description,requirement_text,steps_to_reproduce,expected_behavior,actual_behavior,error_messages,runtime_versions,relevant_file_paths,dependency_manifest,*context])[:4000],attempted_solutions=[x.strip() for x in attempted_solutions.splitlines() if x.strip()])
 result=await rag.ask(req);status="RESOLVED_BY_AI" if result.decision=="ANSWER" else "ESCALATED";mentor=None
 if status=="ESCALATED":mentor=choose_mentor(category,parsed_skills)
 ticket={"student_id":str(u["_id"]),"project_id":project_id,"title":title,"category":category,"sub_category":sub_category,"skills":parsed_skills,"description":description,"client_requirement_ref":client_requirement_ref,"requirement_analysis":{"text":requirement_text},"diagnostic_context":{"operating_system":operating_system,"runtime_versions":runtime_versions,"steps_to_reproduce":steps_to_reproduce,"expected_behavior":expected_behavior,"actual_behavior":actual_behavior,"error_messages":error_messages,"attempted_solutions":attempted_solutions},"artifacts":{"files":stored,"network_logs":parsed_logs,"code_references":{"repository_url":repository_url,"branch_or_pr":branch_or_pr,"commit_hash":commit_hash,"relevant_file_paths":[x.strip() for x in relevant_file_paths.split(",") if x.strip()],"dependency_manifest":dependency_manifest,"related_issue_urls":[x.strip() for x in related_issue_urls.split(",") if x.strip()]}},"ai_resolution":{"status":status,"rag_response":result.answer or result.escalation_reason,"confidence_score":result.confidence,"evidence":[e.model_dump() for e in result.evidence]},"status":"AWAITING_STUDENT_CONFIRMATION" if status=="RESOLVED_BY_AI" else "OPEN","assigned_mentor_id":str(mentor["user_id"]) if mentor else None,"reviewer_feedback":None,"student_feedback":None,"created_at":now(),"updated_at":now()}
 r=db.tickets.insert_one(ticket);ticket["_id"]=r.inserted_id
 if status=="ESCALATED":db.escalations.insert_one({"ticket_id":str(r.inserted_id),"project_id":project_id,"student_id":str(u["_id"]),"question":title,"reason":result.escalation_reason or "AI confidence was insufficient","specialty":category,"status":"open","assigned_mentor_id":str(mentor["user_id"]) if mentor else None,"packet":{"description":description,"diagnostic_context":ticket["diagnostic_context"],"artifacts":ticket["artifacts"],"ai_resolution":ticket["ai_resolution"]},"created_at":now()})
 if mentor:
  db.mentor_profiles.update_one({"_id":mentor["_id"]},{"$inc":{"current_active_tickets":1},"$set":{"updated_at":now()}})
 if status=="ESCALATED":notify_reviewer_team(str(r.inserted_id),title,category,mentor.get("user_id") if mentor else None)
 return clean(ticket)
@app.get("/api/v1/tickets")
def list_tickets(u=Depends(user)):
 q={"student_id":str(u["_id"])} if u["role"]=="student" else ({"assigned_mentor_id":str(u["_id"])} if u["role"]=="core_reviewer" else {})
 return clean(list(db.tickets.find(q).sort("created_at",-1)))
@app.post("/api/v1/tickets/{tid}/feedback")
def ticket_feedback(tid:str,x:dict,u=Depends(roles("student"))):
 ticket=db.tickets.find_one({"_id":oid(tid),"student_id":str(u["_id"])})
 if not ticket:raise HTTPException(404,"Ticket not found")
 solved=bool(x.get("solved"));comment=str(x.get("comment","")).strip();feedback={"solved":solved,"comment":comment,"created_at":now()}
 if solved:
  resolution=ticket.get("ai_resolution",{}).get("rag_response","")
  db.tickets.update_one({"_id":ticket["_id"]},{"$set":{"status":"CLOSED","student_feedback":feedback,"updated_at":now()}})
  chunk_document(db,ticket["project_id"],f"ticket:{tid}",ticket["title"],"\n".join([ticket.get("description",""),resolution,comment]),"verified_resolution",True,verification_status="student_confirmed",access_scope="project")
  return {"status":"CLOSED","message":"Resolution confirmed and added to project knowledge"}
 mentor=choose_mentor(ticket["category"],ticket.get("skills",[]))
 update={"status":"OPEN","student_feedback":feedback,"ai_resolution.status":"STUDENT_REJECTED","updated_at":now()}
 if mentor:update["assigned_mentor_id"]=str(mentor["user_id"])
 db.tickets.update_one({"_id":ticket["_id"]},{"$set":update})
 escalation={"ticket_id":tid,"project_id":ticket["project_id"],"student_id":ticket["student_id"],"question":ticket["title"],"reason":comment or "Student reported that the AI answer did not solve the issue","specialty":ticket["category"],"status":"open","assigned_mentor_id":str(mentor["user_id"]) if mentor else None,"packet":{"description":ticket.get("description"),"diagnostic_context":ticket.get("diagnostic_context"),"artifacts":ticket.get("artifacts"),"ai_resolution":ticket.get("ai_resolution")},"created_at":now()}
 existing=db.escalations.find_one({"ticket_id":tid,"status":{"$in":["open","claimed"]}})
 if not existing:db.escalations.insert_one(escalation)
 if mentor:
  db.mentor_profiles.update_one({"_id":mentor["_id"]},{"$inc":{"current_active_tickets":1},"$set":{"updated_at":now()}})
 notify_reviewer_team(tid,ticket["title"],ticket["category"],mentor.get("user_id") if mentor else None)
 return {"status":"ESCALATED","assigned":bool(mentor),"message":"Sent to the matching core reviewer"}
@app.post("/api/v1/projects/{pid}/questions/ask")
async def ask(pid:str,r:Request,u=Depends(roles("student"))):
 access(pid,u);b=await r.json();q=b.get("question","");n=db.question_attempts.count_documents({"project_id":pid,"student_id":str(u["_id"]),"question":q,"resolved":False});a=await rag.ask(AskRequest(project_id=pid,user_id=str(u["_id"]),question=q,attempted_solutions=b.get("attempted_solutions",[])));db.question_attempts.insert_one({"project_id":pid,"student_id":str(u["_id"]),"question":q,"answer":a.model_dump(),"resolved":a.decision=="ANSWER","created_at":now()})
 if a.decision!="ANSWER" and n>=1:
  sp=b.get("specialty","developer");e={"project_id":pid,"student_id":str(u["_id"]),"question":q,"specialty":sp,"status":"open","rag_failures":n+1,"packet":{"attempts":b.get("attempted_solutions",[])},"created_at":now()};z=db.escalations.insert_one(e);a.escalation_reason=f"Escalated to {sp} core team: {z.inserted_id}"
 return a
@app.get("/api/v1/core/queue")
def queue(u=Depends(roles("core_reviewer","core_admin"))):
 q={"status":{"$in":["open","claimed"]}}
 if u["role"]!="core_admin":
  profile=db.mentor_profiles.find_one({"user_id":str(u["_id"])}) or {};q["specialty"]={"$in":profile.get("categories",[profile.get("primary_category")])}
 return clean(list(db.escalations.find(q).sort("created_at",1)))
def update_core_escalation(eid,status,x,u):
 item=db.escalations.find_one({"_id":oid(eid)})
 if not item:raise HTTPException(404,"Escalation not found")
 db.escalations.update_one({"_id":item["_id"]},{"$set":{"status":status,"response":x.get("response"),"handled_by":str(u["_id"]),"updated_at":now()}});return {"status":status}
@app.post("/api/v1/core/escalations/{eid}/claim")
def claim_core_escalation(eid:str,x:dict={},u=Depends(roles("core_reviewer","core_admin"))):return update_core_escalation(eid,"claimed",x,u)
@app.post("/api/v1/core/escalations/{eid}/respond")
def respond_core_escalation(eid:str,x:dict={},u=Depends(roles("core_reviewer","core_admin"))):return update_core_escalation(eid,"resolved",x,u)
@app.post("/api/v1/core/escalations/{eid}/close")
def close_core_escalation(eid:str,x:dict={},u=Depends(roles("core_reviewer","core_admin"))):return update_core_escalation(eid,"closed",x,u)
@app.post("/api/v1/escalations/{eid}/resolve")
def resolve_escalation(eid:str,x:dict,u=Depends(roles("core_reviewer","core_admin"))):
 escalation=db.escalations.find_one({"_id":oid(eid)})
 if not escalation:raise HTTPException(404,"Escalation not found")
 response=str(x.get("response","")).strip()
 if not response:raise HTTPException(400,"Reviewer resolution is required")
 db.escalations.update_one({"_id":escalation["_id"]},{"$set":{"status":"closed","response":response,"handled_by":str(u["_id"]),"updated_at":now()}})
 if escalation.get("ticket_id"):
  db.tickets.update_one({"_id":oid(escalation["ticket_id"])},{"$set":{"status":"CLOSED","reviewer_feedback":response,"updated_at":now()}})
  ticket_doc=db.tickets.find_one({"_id":oid(escalation["ticket_id"])})
  if ticket_doc:chunk_document(db,ticket_doc["project_id"],f"ticket:{ticket_doc['_id']}",ticket_doc["title"],"\n".join([ticket_doc.get("description",""),response]),"verified_resolution",True,verification_status="core_reviewer_confirmed",access_scope="project")
 profile=db.mentor_profiles.find_one({"user_id":str(u["_id"])})
 if profile:db.mentor_profiles.update_one({"_id":profile["_id"]},{"$inc":{"current_active_tickets":-1,"total_resolved_tickets":1},"$set":{"updated_at":now()}})
 return {"status":"CLOSED","knowledge_indexed":True}
@app.post("/api/v1/ingest")
def ingest(x:IngestRequest,u=Depends(roles("core_reviewer","core_admin"))):
 access(x.project_id,u);count=chunk_document(db,x.project_id,x.document_id,x.title,x.content,"knowledge",x.verified,verification_status="core_team_verified",access_scope="project")
 return {"status":"INGESTED","chunks":count}
@app.get("/api/v1/analytics/overview")
def analytics(u=Depends(roles("core_reviewer","core_admin"))):return {"activeProjects":db.projects.count_documents({"status":"active"}),"users":db.users.count_documents({}),"openEscalations":db.escalations.count_documents({"status":{"$in":["open","claimed"]}}),"resolvedEscalations":db.escalations.count_documents({"status":{"$in":["resolved","closed"]}})}
@app.get("/api/v1/integrations")
def integrations(u=Depends(roles("core_admin"))):return {"mongodb":"CONNECTED","ai_provider":s.ai_provider,"ollama_model":s.ollama_model,"gemini":"ENABLED_FALLBACK" if s.gemini_api_key else "NEEDS_CONFIGURATION","embedding_model":s.gemini_embedding_model,"authentication":"INVITATION_AND_PASSWORD_ONLY","github_app":"ENABLED" if github_app.configured else "NEEDS_APP_ID_PRIVATE_KEY_INSTALLATION_ID_AND_WEBHOOK_SECRET","vision_ocr":"ENABLED" if s.google_cloud_vision_api_key else "GEMINI_PRIMARY_NO_VISION_FALLBACK","smtp":bool(s.smtp_host)}

def repo_parts(url):
 path=urlparse(url).path.strip("/").removesuffix(".git").split("/")
 if len(path)<2:raise HTTPException(400,"A valid GitHub owner/repository URL is required")
 return path[0],path[1]
async def sync_github_files(project_id,repository_url,sha,paths=None,source_type="source_code"):
 if not github_app.configured:raise HTTPException(503,"GitHub App is not configured. Add GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_INSTALLATION_ID and GITHUB_WEBHOOK_SECRET.")
 owner,repo=repo_parts(repository_url);tree_info=await github_app.repository_tree(owner,repo,sha)
 tree=[x for x in tree_info.get("tree",[]) if x.get("type")=="blob" and github_app.eligible(x["path"],x.get("size",0))]
 if paths is not None:tree=[x for x in tree if x["path"] in paths]
 indexed=0
 for entry in tree[:1000]:
  content=await github_app.source_file(owner,repo,entry["path"],sha)
  if not content:continue
  suffix=Path(entry["path"]).suffix.lower().lstrip(".")
  kind="readme" if Path(entry["path"]).name.lower().startswith("readme") else "configuration" if Path(entry["path"]).name.lower() in {"package.json","requirements.txt","pyproject.toml","dockerfile","docker-compose.yml"} else source_type
  indexed+=chunk_document(db,project_id,f"github:{owner}/{repo}:{entry['path']}",entry["path"],content,kind,True,repository=f"{owner}/{repo}",commit_sha=sha,path=entry["path"],language=suffix,verification_status="github_app",access_scope="project")
 return {"files":len(tree),"chunks":indexed,"truncated":bool(tree_info.get("truncated")),"commit_sha":sha}

@app.post("/api/v1/projects/{pid}/github/sync")
async def github_sync(pid:str,x:dict,u=Depends(roles("student","core_admin"))):
 access(pid,u);project=db.projects.find_one({"_id":oid(pid)});repository=x.get("repository_url") or project.get("repository_url")
 result=await sync_github_files(pid,repository,x.get("commit_sha") or x.get("ref") or "HEAD")
 db.repository_syncs.insert_one({"project_id":pid,"repository_url":repository,**result,"created_at":now()});return result

@app.post("/api/v1/github/webhook")
async def github_webhook(request:Request):
 body=await request.body()
 if not github_app.configured:raise HTTPException(503,"GitHub App is not configured")
 if not github_app.verify_webhook(body,request.headers.get("x-hub-signature-256","")):raise HTTPException(401,"Invalid webhook signature")
 event=request.headers.get("x-github-event");payload=json.loads(body);repository=payload.get("repository",{}).get("html_url","");projects=list(db.projects.find({"repository_url":{"$in":[repository,repository+".git"]}}));results=[]
 if event=="push":
  changed=set();removed=set()
  for commit in payload.get("commits",[]):changed.update(commit.get("added",[]));changed.update(commit.get("modified",[]));removed.update(commit.get("removed",[]))
  for project in projects:
   pid=str(project["_id"])
   for path in removed:db.document_chunks.delete_many({"project_id":pid,"repository":repo_parts(repository)[0]+"/"+repo_parts(repository)[1],"path":path})
   results.append(await sync_github_files(pid,repository,payload.get("after"),changed))
 elif event=="pull_request" and payload.get("action") in {"opened","synchronize","reopened"}:
  owner,repo=repo_parts(repository);number=payload["number"];files=await github_app.request("GET",f"/repos/{owner}/{repo}/pulls/{number}/files?per_page=100")
  for project in projects:
   pid=str(project["_id"])
   for item in files:
    patch=item.get("patch")
    if patch:chunk_document(db,pid,f"github-pr:{owner}/{repo}:{number}:{item['filename']}",f"PR #{number}: {item['filename']}",patch,"pr_diff",True,repository=f"{owner}/{repo}",commit_sha=payload["pull_request"]["head"]["sha"],path=item["filename"],language=Path(item["filename"]).suffix.lstrip("."),verification_status="github_app",access_scope="project")
   results.append({"pull_request":number,"files":len(files)})
 return {"event":event,"projects":len(projects),"results":results}
