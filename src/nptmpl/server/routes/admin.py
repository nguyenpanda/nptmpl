from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.concurrency import run_in_threadpool

import shutil
import tempfile
import tarfile
import yaml
from pathlib import Path

from nptmpl.server.db import DatabaseManager
from nptmpl.server.auth import get_admin_user, get_config
from nptmpl.core.config import ConfigManager
from nptmpl.server.inspector import TarballInspector
from nptmpl.core.metadata import TemplateMetadata, Version
from nptmpl.core.engine import FileSystemEngine
from nptmpl.server.api import validate_safe_path_component
from nptmpl.server.ui_utils import get_site_meta


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: DatabaseManager = Depends(get_db), 
                          config: ConfigManager = Depends(get_config),
                          _user: str = Depends(get_admin_user)):
    stats = await run_in_threadpool(db.get_stats)
    all_templates = await run_in_threadpool(db.list_templates)
    return templates.TemplateResponse(request, "admin.html", {
        "stats": stats, "templates": all_templates,
        "public_url": config.get_public_url(), "site_meta": get_site_meta(config)
    })

@router.post("/admin/upload")
async def admin_upload(request: Request, tarball: UploadFile = File(...), db: DatabaseManager = Depends(get_db), _user: str = Depends(get_admin_user)):
    storage = request.app.state.storage_path
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tar_path = tmp_path / "upload.tar.gz"
        with open(tar_path, "wb") as f:
            while chunk := await tarball.read(1024 * 1024): f.write(chunk)

        if not await run_in_threadpool(TarballInspector.verify_integrity, tar_path):
            raise HTTPException(status_code=400, detail="Invalid tar.gz archive")

        def extract_meta():
            with tarfile.open(tar_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name == ".nptmpl":
                        f = tar.extractfile(member)
                        return yaml.safe_load(f.read(1024 * 1024)) if f else None
            return None
        meta_dict = await run_in_threadpool(extract_meta)
        if not meta_dict: raise HTTPException(status_code=400, detail="Missing .nptmpl")
            
        metadata = TemplateMetadata.from_dict(meta_dict)
        db_meta = metadata.to_dict()
        group, name, version = validate_safe_path_component(meta_dict.get('group', 'default')), validate_safe_path_component(metadata.name or meta_dict['name']), metadata.version
        if not Version.is_valid(version): raise HTTPException(status_code=400, detail="Invalid version")
        db_meta['target'] = f"{group}/{name}"

        version_dir = storage / group / name / version
        if not FileSystemEngine._is_safe_path(storage, version_dir): raise HTTPException(status_code=400, detail="Invalid path")
        if version_dir.exists(): raise HTTPException(status_code=409, detail="Version already exists")

        try:
            version_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            raise HTTPException(status_code=409, detail="Version already exists")
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"FileSystem failure: {e}")

        shutil.move(str(tar_path), str(version_dir / "data.tar.gz"))
        with open(version_dir / ".nptmpl", "w", encoding="utf-8") as f: yaml.dump(meta_dict, f, sort_keys=False)

        readme = await run_in_threadpool(TarballInspector.extract_readme, version_dir / "data.tar.gz")
        await run_in_threadpool(db.add_template_version, db_meta, readme)
        return {"message": "Success", "target": f"{group}/{name}", "version": version}

@router.post("/admin/delete/{group}/{name}/{version}")
async def admin_delete(request: Request, group: str, name: str, version: str, db: DatabaseManager = Depends(get_db), _user: str = Depends(get_admin_user)):
    """Deletes a specific template version and cleans up empty directories."""
    group, name = validate_safe_path_component(group), validate_safe_path_component(name)
    if not Version.is_valid(version): raise HTTPException(status_code=400, detail="Invalid version")
    storage = request.app.state.storage_path
    version_dir = storage / group / name / version

    is_template_fully_deleted = await run_in_threadpool(db.delete_version, group, name, version)

    if FileSystemEngine._is_safe_path(storage, version_dir) and version_dir.exists():
        await run_in_threadpool(shutil.rmtree, version_dir)

    if is_template_fully_deleted:
        template_dir = storage / group / name
        if template_dir.exists() and not any(template_dir.iterdir()):
            await run_in_threadpool(shutil.rmtree, template_dir)

        group_dir = storage / group
        if group_dir.exists() and not any(group_dir.iterdir()):
            await run_in_threadpool(shutil.rmtree, group_dir)

    return RedirectResponse(url="/admin", status_code=303)
