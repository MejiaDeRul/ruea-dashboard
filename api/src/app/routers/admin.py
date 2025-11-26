from fastapi import APIRouter, File, UploadFile, Depends, BackgroundTasks, HTTPException, Form
from ..core.security import require_admin
from ..services.etl import run_refresh_from_files, run_refresh_from_workbook
import json

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.post("/refresh")
async def refresh(background: BackgroundTasks,
                  ruea: UploadFile | None = File(None),
                  comercializacion: UploadFile | None = File(None),
                  indicadores: UploadFile | None = File(None),
                  nodos: UploadFile | None = File(None),
                  _=Depends(require_admin)):
    files = {k: v for k, v in {
        "ruea": ruea, "comercializacion": comercializacion,
        "indicadores": indicadores, "nodos": nodos
    }.items() if v is not None}
    if not files:
        raise HTTPException(400, "No files provided")

    # leer los bytes ahora y pasarlos al worker
    bin_files = {name: await f.read() for name, f in files.items()}

    result = {"status": "scheduled"}

    def job():
        run_refresh_from_files(bin_files)

    background.add_task(job)
    return result

@router.post("/refresh-xlsx")
async def refresh_xlsx(
    file: UploadFile,
    sheet_map: str = Form('{"ruea":"GENERAL"}'),
    header_rows: str = Form('{"ruea":1}'),
    _=Depends(require_admin)
):
    # Parseo robusto
    try:
        sheet_map_dict = json.loads(sheet_map) if isinstance(sheet_map, str) else sheet_map
    except Exception:
        sheet_map_dict = {"ruea": "GENERAL"}
    try:
        header_rows_dict = json.loads(header_rows) if isinstance(header_rows, str) else header_rows
    except Exception:
        header_rows_dict = {"ruea": 1}

    # Solo procesaremos 'ruea' por ahora, si está mapeado
    if "ruea" not in sheet_map_dict:
        raise HTTPException(400, "sheet_map debe incluir 'ruea' → nombre de la hoja (p. ej. GENERAL)")

    file_bytes = await file.read()
    result = run_refresh_from_workbook(
        file_bytes=file_bytes,
        sheet_map=sheet_map_dict,
        header_rows=header_rows_dict,
        modules_to_process=["ruea"]  # por ahora sólo GENERAL→ruea
    )
    return result
