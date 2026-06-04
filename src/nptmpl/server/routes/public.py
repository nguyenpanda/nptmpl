import markdown
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.concurrency import run_in_threadpool
from pygments.formatters import HtmlFormatter

from nptmpl.core.config import ConfigManager
from nptmpl.server.db import DatabaseManager
from nptmpl.server.auth import get_config
from nptmpl.server.inspector import TarballInspector
from nptmpl.server.api import validate_safe_path_component
from nptmpl.server.ui_utils import get_site_meta, fix_markdown_paths


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

@router.get("/", response_class=HTMLResponse)
async def home(request: Request,
               q: Optional[str] = None,
               lang: Optional[str] = None,
               tag: Optional[str] = None,
               license: Optional[str] = None,
               author: Optional[str] = None,
               sort: str = "added_date",
               db: DatabaseManager = Depends(get_db),
               config: ConfigManager = Depends(get_config)):
    results = await run_in_threadpool(db.list_templates, query=q, language=lang, tag=tag, license=license, author=author, sort_by=sort)
    stats = await run_in_threadpool(db.get_stats)
    filter_options = await run_in_threadpool(db.get_filter_options)

    return templates.TemplateResponse(request, "index.html", {
        "templates": results,
        "stats": stats,
        "query": q,
        "current_filters": {"lang": lang, "tag": tag, "license": license, "author": author, "sort": sort},
        "filter_options": filter_options,
        "public_url": config.get_public_url(),
        "site_meta": get_site_meta(config)
    })

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None, config: ConfigManager = Depends(get_config)):
    return templates.TemplateResponse(request, "login.html", {
        "site_meta": get_site_meta(config),
        "error": error
    })

@router.post("/login")
async def login_submit(request: Request, 
                       username: str = Form(...), 
                       password: str = Form(...), 
                       config: ConfigManager = Depends(get_config)):
    correct_username, correct_password = config.get_admin_credentials()
    
    is_correct_username = secrets.compare_digest(username, correct_username)
    is_correct_password = secrets.compare_digest(password, correct_password)
    
    if not (is_correct_username and is_correct_password):
        return RedirectResponse(url="/login?error=invalid_credentials", status_code=303)
        
    request.session["user"] = username
    return RedirectResponse(url="/admin", status_code=303)

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@router.get("/about", response_class=HTMLResponse)
async def about(request: Request, config: ConfigManager = Depends(get_config)):
    return templates.TemplateResponse(request, "about.html", {"site_meta": get_site_meta(config)})

@router.get("/docs", response_class=HTMLResponse)
@router.get("/docs/{page_name}", response_class=HTMLResponse)
async def docs(request: Request, page_name: str = "README", config: ConfigManager = Depends(get_config)):
    current_file = Path(__file__).resolve()
    search_roots = [
        current_file.parent.parent.parent,
        current_file.parent.parent.parent.parent.parent
    ]
    
    docs_path = None
    readme_path = None
    for root in search_roots:
        if (root / "docs").exists() and (root / "docs").is_dir():
            docs_path = root / "docs"
            readme_path = root / "README.md"
            break
            
    if not docs_path:
        docs_path = Path.cwd() / "docs"
        readme_path = Path.cwd() / "README.md"

    page_name = validate_safe_path_component(page_name)
    file_to_read = readme_path if page_name.upper() == "README" else (docs_path / f"{page_name}.md")
    if not file_to_read.exists() and page_name.upper() != "README":
        file_to_read = docs_path / f"{page_name}"

    if not file_to_read or not file_to_read.exists():
        raise HTTPException(status_code=404, detail="Documentation page not found")

    try:
        def render_docs():
            with open(file_to_read, "r", encoding="utf-8") as f:
                md_content = fix_markdown_paths(f.read())
            return markdown.markdown(md_content, extensions=['fenced_code', 'tables', 'toc', 'codehilite'], 
                                    extension_configs={'codehilite': {'css_class': 'highlight', 'guess_lang': False}})
            
        html_content = await run_in_threadpool(render_docs)
        pygments_css = HtmlFormatter(style='monokai').get_style_defs('.highlight')
        
        return templates.TemplateResponse(request, "docs.html", {
            "content": html_content,
            "page_name": page_name,
            "pygments_css": pygments_css,
            "site_meta": get_site_meta(config)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rendering documentation: {e}")

@router.get("/{group}/{name}", response_class=HTMLResponse)
async def template_detail(request: Request, group: str, name: str, 
                          db: DatabaseManager = Depends(get_db),
                          config: ConfigManager = Depends(get_config)):
    group = validate_safe_path_component(group)
    name = validate_safe_path_component(name)
    template = await run_in_threadpool(db.get_template, group, name)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template["versions"] and template["versions"][0].get("readme_content"):
        def render_readme():
            md_text = fix_markdown_paths(template["versions"][0]["readme_content"])
            return markdown.markdown(md_text, extensions=['fenced_code', 'tables', 'toc', 'codehilite'],
                                    extension_configs={'codehilite': {'css_class': 'highlight', 'guess_lang': False}})
        template["versions"][0]["readme_html"] = await run_in_threadpool(render_readme)

    related = await run_in_threadpool(db.get_related_templates, group, name)
    storage = request.app.state.storage_path
    latest_ver = template["versions"][0]["version"]
    archive_path = storage / group / name / latest_ver / "data.tar.gz"

    files = await run_in_threadpool(TarballInspector.list_files, archive_path)
    files = [f for f in files if f['path'].lower() != "readme.md"]
    pygments_css = HtmlFormatter(style='monokai').get_style_defs('.highlight')

    return templates.TemplateResponse(request, "detail.html", {
        "template": template, "related": related, "files": files,
        "public_url": config.get_public_url(), "pygments_css": pygments_css,
        "site_meta": get_site_meta(config)
    })
