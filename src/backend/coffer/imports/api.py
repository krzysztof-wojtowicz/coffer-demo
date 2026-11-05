from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from coffer.accounts.deps import CurrentUser
from coffer.core.db import DbSession
from coffer.imports import service
from coffer.imports.banks import BANKS
from coffer.imports.parser import ImportEncodingError, ImportFormatError
from coffer.imports.schemas import BankOut, CommitIn, CommitOut, ImportPreviewOut

router = APIRouter(prefix="/api/imports", tags=["imports"])

NOT_FOUND = "Nie znaleziono podglądu importu"


@router.get("/banks", response_model=list[BankOut])
def get_banks(user: CurrentUser) -> list[BankOut]:
    return [BankOut(id=b.id, name=b.name) for b in BANKS.values()]


@router.post("", response_model=ImportPreviewOut, status_code=201)
def upload(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    bank: str = Form(...),
) -> ImportPreviewOut:
    if bank not in BANKS:
        raise HTTPException(status_code=422, detail="Nieobsługiwany bank")
    content = file.file.read(service.MAX_FILE_BYTES + 1)
    try:
        return service.create_preview(db, user.id, bank, file.filename or "import.csv", content)
    except service.FileTooLargeError:
        raise HTTPException(status_code=422, detail="Plik jest za duży (maks. 1 MB)") from None
    except service.EmptyImportError:
        raise HTTPException(status_code=422, detail="Plik nie zawiera transakcji") from None
    except (ImportFormatError, ImportEncodingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/{draft_id}", response_model=ImportPreviewOut)
def get_import(draft_id: str, user: CurrentUser, db: DbSession) -> ImportPreviewOut:
    try:
        return service.get_preview(db, user.id, draft_id)
    except service.DraftNotFoundError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None


@router.post("/{draft_id}/commit", response_model=CommitOut)
def commit_import(draft_id: str, data: CommitIn, user: CurrentUser, db: DbSession) -> CommitOut:
    try:
        return service.commit(db, user.id, draft_id, data)
    except service.DraftNotFoundError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None
    except service.UnknownCategoryError:
        raise HTTPException(status_code=422, detail="Nieznana kategoria") from None


@router.delete("/{draft_id}", status_code=204)
def delete_import(draft_id: str, user: CurrentUser, db: DbSession) -> Response:
    try:
        service.discard(db, user.id, draft_id)
    except service.DraftNotFoundError:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from None
    return Response(status_code=204)
