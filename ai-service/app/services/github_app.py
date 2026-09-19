import base64
import hashlib
import hmac
import time
from pathlib import PurePosixPath

import httpx
import jwt

SOURCE_SUFFIXES={".md",".txt",".py",".js",".jsx",".ts",".tsx",".java",".go",".rs",".cs",".php",".rb",".json",".yaml",".yml",".toml",".xml",".html",".css",".scss",".sql",".sh",".ps1"}
EXCLUDED_PARTS={"node_modules","vendor","dist","build","target","coverage",".git",".next","__pycache__","generated","min"}

class GitHubAppClient:
    def __init__(self,settings):self.settings=settings
    @property
    def configured(self):return bool(self.settings.github_app_id and self.settings.github_app_private_key and self.settings.github_app_installation_id and self.settings.github_webhook_secret)
    def verify_webhook(self,body:bytes,signature:str):
        expected="sha256="+hmac.new(self.settings.github_webhook_secret.encode(),body,hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected,signature or "")
    def app_jwt(self):
        key=self.settings.github_app_private_key.replace("\\n","\n")
        return jwt.encode({"iat":int(time.time())-60,"exp":int(time.time())+540,"iss":self.settings.github_app_id},key,algorithm="RS256")
    async def installation_token(self):
        headers={"Authorization":"Bearer "+self.app_jwt(),"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        async with httpx.AsyncClient(timeout=30) as client:
            response=await client.post(f"https://api.github.com/app/installations/{self.settings.github_app_installation_id}/access_tokens",headers=headers)
            response.raise_for_status();return response.json()["token"]
    async def request(self,method,path,**kwargs):
        token=await self.installation_token();headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.request(method,"https://api.github.com"+path,headers=headers,**kwargs);response.raise_for_status();return response.json()
    async def repository_tree(self,owner,repo,sha):
        return await self.request("GET",f"/repos/{owner}/{repo}/git/trees/{sha}?recursive=1")
    async def source_file(self,owner,repo,path,ref):
        item=await self.request("GET",f"/repos/{owner}/{repo}/contents/{path}?ref={ref}")
        if item.get("encoding")=="base64":return base64.b64decode(item["content"]).decode("utf-8","ignore")
        return ""
    @staticmethod
    def eligible(path,size=0):
        p=PurePosixPath(path)
        return p.suffix.lower() in SOURCE_SUFFIXES and size<=750_000 and not any(part.lower() in EXCLUDED_PARTS for part in p.parts)
