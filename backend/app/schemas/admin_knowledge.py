from datetime import datetime
from typing import List

from pydantic import BaseModel


class KnowledgeDoc(BaseModel):
    filename: str
    size_bytes: int
    chunks: int
    indexed: bool
    modified_at: datetime


class KnowledgeList(BaseModel):
    documents: List[KnowledgeDoc]
    total_chunks: int
    in_sync: bool


class KnowledgeContent(BaseModel):
    filename: str
    content: str


class KnowledgeUploadResult(BaseModel):
    replaced: bool
    document: KnowledgeDoc
    total_chunks: int


class KnowledgeDeleteResult(BaseModel):
    deleted: str
    total_documents: int
    total_chunks: int


class RebuildResult(BaseModel):
    documents: int
    total_chunks: int
