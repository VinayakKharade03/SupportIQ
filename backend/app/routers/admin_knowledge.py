from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.schemas.admin_knowledge import (
    KnowledgeContent,
    KnowledgeDeleteResult,
    KnowledgeList,
    KnowledgeUploadResult,
    RebuildResult,
)
from app.services import knowledge_base as kb
from app.services.permissions import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=KnowledgeList)
def list_documents():
    return kb.list_documents()


@router.post("/rebuild", response_model=RebuildResult)
def rebuild_index():
    documents, chunks = kb.rebuild_all()
    return RebuildResult(documents=documents, total_chunks=chunks)


@router.get("/{filename}", response_model=KnowledgeContent)
def get_document(filename: str):
    name = kb.normalize_filename(filename)
    return KnowledgeContent(filename=name, content=kb.read_document(name))


@router.post("", response_model=KnowledgeUploadResult, status_code=201)
def upload_document(
    response: Response,
    file: UploadFile = File(...),
    overwrite: bool = Query(False),
):
    name = kb.normalize_filename(file.filename)
    raw = file.file.read(kb.MAX_BYTES + 1)
    if len(raw) > kb.MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 200 KB)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in text:
        raise HTTPException(status_code=400, detail="File must be plain text")
    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    replaced = kb.save_document(name, text, overwrite)
    if replaced:
        response.status_code = 200
    info = kb.list_documents()
    doc = next(d for d in info["documents"] if d["filename"] == name)
    return KnowledgeUploadResult(
        replaced=replaced, document=doc, total_chunks=info["total_chunks"]
    )


@router.delete("/{filename}", response_model=KnowledgeDeleteResult)
def delete_document(filename: str):
    name = kb.normalize_filename(filename)
    kb.delete_document(name)
    info = kb.list_documents()
    return KnowledgeDeleteResult(
        deleted=name,
        total_documents=len(info["documents"]),
        total_chunks=info["total_chunks"],
    )
