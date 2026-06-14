import json
import shutil
import re
import threading
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.responses import FileResponse

import markdown
from typing import Optional, Dict, Any
from pathlib import Path
from pygments import highlight
from pygments.lexers import get_lexer_for_filename, ClassNotFound, TextLexer
from pygments.formatters import HtmlFormatter

from nptmpl.core.metadata import TemplateMetadata, MetadataManager
from nptmpl.core.engine import FileSystemEngine
from nptmpl.core.metadata import Version
from nptmpl.server.db import DatabaseManager
from nptmpl.server.auth import get_api_key
from nptmpl.server.inspector import TarballInspector
from nptmpl.server.deps import get_db, get_storage
from nptmpl.server.ui_utils import fix_markdown_paths
from nptmpl.server.ws import manager


router = APIRouter(prefix="/api/v1/templates")
download_router = APIRouter(prefix="/archive")
inspect_router = APIRouter(prefix="/api/v1")

logger = logging.getLogger("nptmpl.server.api")

push_lock = threading.Lock()

SAFE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")

def validate_safe_path_component(name: str) -> str:
    """Ensures a string is safe to be used as a directory or file name."""
    if not SAFE_NAME_REGEX.match(name) and not Version.is_valid(name):
        raise HTTPException(status_code=400, detail=f"Invalid path component: {name}")
    return name

def _cleanup_empty_parents(storage: Path, group: str, name: str):
    """Helper to remove template and group directories if they become empty."""
    template_dir = storage / group / name
    if template_dir.exists() and not any(template_dir.iterdir()):
        shutil.rmtree(template_dir)
    
    group_dir = storage / group
    if group_dir.exists() and not any(group_dir.iterdir()):
        shutil.rmtree(group_dir)

@download_router.get("/download/{group}/{name}/{version}/{filename}")
async def download_template_archive(
    group: str,
    name: str,
    version: str,
    filename: str,
    db: DatabaseManager = Depends(get_db),
    storage: Path = Depends(get_storage)
) -> FileResponse:
    group, name = validate_safe_path_component(group), validate_safe_path_component(name)
    if not Version.is_valid(version): 
        raise HTTPException(status_code=400, detail="Invalid version format")
    
    file_path = storage / group / name / version / "data.tar.gz"
    if not file_path.exists() or not FileSystemEngine._is_safe_path(storage, file_path):
        raise HTTPException(status_code=404, detail="Archive not found")
    
    db.increment_download(group, name)
    template = db.get_template(group, name)
    if template:
        await manager.broadcast({
            "type": "traffic_update",
            "group": group,
            "name": name,
            "count": template["download_count"]
        })

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-cache"
    }
    return FileResponse(file_path, media_type="application/gzip", filename=filename, headers=headers)

@router.get("/{group}/{name}/download")
async def download_template(
    group: str, name: str, v: Optional[str] = None,
    db: DatabaseManager = Depends(get_db),
    storage: Path = Depends(get_storage)
) -> FileResponse:
    group, name = validate_safe_path_component(group), validate_safe_path_component(name)
    if v and not Version.is_valid(v):
        raise HTTPException(status_code=400, detail="Invalid version format")
    
    if not v:
        template = db.get_template(group, name)
        if not template or not template["versions"]:
            raise HTTPException(status_code=404, detail="Template not found")
        
        version = template["versions"][0]["version"]
    else:
        version = v
        
    file_path = storage / group / name / version / "data.tar.gz"
    if not file_path.exists() or not FileSystemEngine._is_safe_path(storage, file_path):
        raise HTTPException(status_code=404, detail="Archive not found")
    
    return FileResponse(file_path, media_type="application/gzip", filename=f"{group}_{name}_{version}.tar.gz")

@router.get("")
async def list_templates(
    q: Optional[str] = None, lang: Optional[str] = None, tag: Optional[str] = None,
    license: Optional[str] = None, author: Optional[str] = None, sort: str = "added_date",
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    
    templates = db.list_templates(
        query=q, language=lang, tag=tag, 
        license=license, author=author, sort_by=sort
    )
    
    return {
        "templates": [
            {"target": f"{t['group_name']}/{t['name']}", "version": t["version"], "metadata": t} 
            for t in templates
        ]
    }

@router.get("/{group}/{name}")
async def get_template(group: str, name: str, clone: bool = False, db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    group, name = validate_safe_path_component(group), validate_safe_path_component(name)
    if clone:
        db.increment_download(group, name)
        template = db.get_template(group, name)
        if template:
            await manager.broadcast({
                "type": "traffic_update",
                "group": template["group_name"],
                "name": template["name"],
                "count": template["download_count"]
            })
    else:
        template = db.get_template(group, name)
        
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "target": f"{template['group_name']}/{template['name']}", 
        "version": template["versions"][0]["version"], 
        "metadata": template
    }

@router.post("/push", include_in_schema=False)
async def push_template(
    metadata_json: str = Form(...), tarball: UploadFile = File(...), overwrite: str = Form("false"),
    db: DatabaseManager = Depends(get_db), storage: Path = Depends(get_storage), _token: str = Depends(get_api_key)
):
    with push_lock:
        should_overwrite = overwrite.lower() == "true"
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")
        
        target = metadata.get("target", "")
        if "/" not in target:
            raise HTTPException(status_code=400, detail="Target must be in group/name format")
        
        group, name = target.split("/", 1)
        version = metadata.get("version", "")
        group, name = validate_safe_path_component(group), validate_safe_path_component(name)
        if not Version.is_valid(version):
            raise HTTPException(status_code=400, detail="Invalid version format")
        
        version_dir = storage / group / name / version
        if not FileSystemEngine._is_safe_path(storage, version_dir):
            raise HTTPException(status_code=400, detail="Invalid path components detected")
        
        if version_dir.exists() and not should_overwrite:
            template = db.get_template(group, name)
            is_registered = False
            if template:
                for v in template.get("versions", []):
                    if v["version"] == version:
                        is_registered = True
                        break
            if is_registered:
                raise HTTPException(status_code=409, detail=f"Version {version} already exists")
            else:
                shutil.rmtree(version_dir)
        try:
            if version_dir.exists() and should_overwrite: shutil.rmtree(version_dir)
            version_dir.mkdir(parents=True, exist_ok=False)
        except (FileExistsError, OSError) as e:
            if not should_overwrite and isinstance(e, FileExistsError):
                raise HTTPException(status_code=409, detail=f"Version {version} already exists")
            raise HTTPException(status_code=500, detail=f"FileSystem failure: {e}")
        
        tarball_path = version_dir / "data.tar.gz"
        try:
            with open(tarball_path, "wb") as f:
                while chunk := tarball.file.read(1024 * 1024): 
                    f.write(chunk)
        except Exception as e:
            shutil.rmtree(version_dir)
            _cleanup_empty_parents(storage, group, name)
            raise HTTPException(status_code=500, detail=f"Failed to save tarball: {e}")

        if not TarballInspector.verify_integrity(tarball_path):
            shutil.rmtree(version_dir)
            _cleanup_empty_parents(storage, group, name)
            raise HTTPException(status_code=400, detail="Corrupted or invalid tarball")

        try:
            meta_obj = TemplateMetadata.from_dict(metadata)
            MetadataManager.save(version_dir, meta_obj)

            readme = TarballInspector.extract_readme(tarball_path)
            db.add_template_version(metadata, readme)
            
            await manager.broadcast({
                "type": "registry_update",
                "action": "push",
                "target": f"{group}/{name}",
                "version": version
            })
        except Exception as e:
            shutil.rmtree(version_dir)
            _cleanup_empty_parents(storage, group, name)
            logger.error(f"Failed to finalize template push: {e}")
            raise HTTPException(status_code=500, detail=f"Internal Server Error during finalization: {e}")

        return {
            "message": "Template pushed successfully", 
            "target": f"{group}/{name}", 
            "version": version
        }

@router.delete("/{group}/{name}/{version}", include_in_schema=False)
async def delete_version(
    group: str, name: str, version: str,
    db: DatabaseManager = Depends(get_db), storage: Path = Depends(get_storage), _token: str = Depends(get_api_key)
):
    with push_lock:
        group, name = validate_safe_path_component(group), validate_safe_path_component(name)
        
        if not Version.is_valid(version):
            raise HTTPException(status_code=400, detail="Invalid version format")
        version_dir = storage / group / name / version
        
        if not FileSystemEngine._is_safe_path(storage, version_dir):
            raise HTTPException(status_code=400, detail="Unsafe path")
        
        is_template_fully_deleted = db.delete_version(group, name, version)
        if version_dir.exists():
            shutil.rmtree(version_dir)
        _cleanup_empty_parents(storage, group, name)
        
        await manager.broadcast({
            "type": "registry_update",
            "action": "delete",
            "target": f"{group}/{name}",
            "version": version
        })
        
        return {"message": f"Version {version} deleted"}

@inspect_router.get("/inspect/{group}/{name}/{version}")
async def inspect_file(request: Request, group: str, name: str, version: str, path: str = Query(...)):
    """Returns the content and syntax-highlighted HTML for a file inside a template archive."""
    group, name = validate_safe_path_component(group), validate_safe_path_component(name)
    
    if not Version.is_valid(version): 
        raise HTTPException(status_code=400, detail="Invalid version format")
    
    storage = request.app.state.storage_path
    archive_path = storage / group / name / version / "data.tar.gz"
    
    if not archive_path.exists() or not FileSystemEngine._is_safe_path(storage, archive_path):
        raise HTTPException(status_code=404, detail="Archive not found")
    
    content = TarballInspector.get_file_content(archive_path, path)
    
    if content is None: 
        raise HTTPException(status_code=404, detail="File not found")
    
    is_md = path.lower().endswith(".md")
    if is_md:
        html = markdown.markdown(
            fix_markdown_paths(content), 
            extensions=['fenced_code', 'tables', 'toc', 'codehilite'],
            extension_configs={'codehilite': 
                {'css_class': 'highlight', 'guess_lang': False}
            }
        )
    else:
        try:
            lexer = get_lexer_for_filename(path)
        except ClassNotFound:
            lexer = TextLexer()
        html = highlight(content, lexer, HtmlFormatter(style='monokai', cssclass="highlight"))
    return {
        "content": content, 
        "html_content": html, 
        "is_markdown": is_md
    }
