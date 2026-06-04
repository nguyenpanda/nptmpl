import os
import shutil
import stat
import tarfile
import subprocess
import logging
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, UndefinedError
import pathspec

from nptmpl.core.errors import EngineError, ExtractionError, RenderingError

logger = logging.getLogger("nptmpl.engine")

class FileSystemEngine:
    """Infrastructure layer for safe file system operations, compression, and rendering."""

    BINARY_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.pdf',
        '.zip', '.tar', '.gz', '.7z', '.rar',
        '.exe', '.dll', '.so', '.dylib', '.bin',
        '.pyc', '.pyo', '.pyd',
        '.db', '.sqlite',
        '.woff', '.woff2', '.ttf', '.otf',
        '.mp3', '.mp4', '.wav', '.mov',
    }

    @staticmethod
    def copy_template(src: Path, dst: Path) -> None:
        """Copies a template directory, preserving symlinks and permissions."""
        try:
            shutil.copytree(os.path.realpath(src), os.path.realpath(dst), symlinks=True, dirs_exist_ok=True)
        except Exception as e:
            raise EngineError(f"Failed to copy template: {e}")

    @staticmethod
    def compress_directory(src: Path, archive_path: Path, ignore_patterns: Optional[List[str]] = None) -> None:
        """Compresses a directory into a tar.gz archive, respecting pathspec."""
        all_patterns = [
            ".git/", "__pycache__/", "*.pyc", ".DS_Store", ".idea/", ".vscode/",
            "Icon*", "node_modules/", ".env", ".venv/"
        ]
        if ignore_patterns:
            all_patterns.extend(ignore_patterns)

        gitignore = src / ".gitignore"
        if gitignore.exists():
            try:
                all_patterns.extend(gitignore.read_text(encoding="utf-8").splitlines())
            except Exception:
                pass

        spec = pathspec.PathSpec.from_lines('gitignore', all_patterns)
        src_abs = os.path.abspath(src)

        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                for root, dirs, files in os.walk(src_abs, followlinks=False):
                    rel_root = os.path.relpath(root, src_abs)

                    dirs[:] = [d for d in dirs if not spec.match_file(os.path.join(rel_root, d).replace(os.sep, '/') + '/')]

                    for name in dirs + files:
                        full_path = os.path.join(root, name)
                        rel_path = os.path.join(rel_root, name).replace(os.sep, '/')
                        if rel_path.startswith("./"): rel_path = rel_path[2:]
                        
                        if name == '.nptmpl': continue
                            
                        match_path = rel_path + ('/' if os.path.isdir(full_path) else '')
                        if spec.match_file(match_path): continue

                        if os.path.islink(full_path):
                            target = os.readlink(full_path)
                            if os.path.isabs(target):
                                raise EngineError(f"Absolute symlink detected: {rel_path}")

                        tar.add(full_path, arcname=rel_path, recursive=False)
        except EngineError:
            if archive_path.exists(): archive_path.unlink()
            raise
        except Exception as e:
            if archive_path.exists(): archive_path.unlink()
            raise EngineError(f"Failed to compress directory: {e}")

    @staticmethod
    def _is_safe_path(base_dir: Path, target_path: Path) -> bool:
        """Validates that target_path is strictly within base_dir."""
        try:
            base_real = os.path.realpath(base_dir)
            target_real = os.path.realpath(target_path)
            return target_real == base_real or target_real.startswith(base_real + os.sep)
        except (OSError, ValueError):
            return False

    @staticmethod
    def _is_safe_extraction_path(base_dir: str, target_name: str) -> bool:
        """Validates that a member name in a tarball doesn't escape base_dir."""
        base_abs = os.path.abspath(base_dir)
        target_abs = os.path.normpath(os.path.join(base_abs, target_name))
        return target_abs.startswith(base_abs + os.sep) or target_abs == base_abs

    @staticmethod
    def decompress_and_render(archive_path: Path, dst: Path, variables: Dict[str, Any]) -> None:
        """Decompresses a tar.gz archive and renders contents/filenames with Jinja2."""
        if not archive_path.exists() or archive_path.stat().st_size == 0:
            raise EngineError("Archive is missing or empty")

        try:
            dst_abs = os.path.abspath(dst)
            if not os.path.exists(dst_abs): os.makedirs(dst_abs, exist_ok=True)
            if not os.access(dst_abs, os.W_OK): raise EngineError("Destination is read-only")

            with tarfile.open(archive_path, "r:gz") as tar:
                if hasattr(tarfile, 'data_filter'):
                    tar.extractall(path=dst_abs, filter='data')
                else:
                    for member in tar.getmembers():
                        if not FileSystemEngine._is_safe_extraction_path(dst_abs, member.name):
                            raise ExtractionError(f"Unsafe path detected: {member.name}")
                        
                        if member.issym() or member.islnk():
                            if os.path.isabs(member.linkname):
                                raise EngineError(f"Absolute link: {member.name}")
                    
                    tar.extractall(path=dst_abs)

            FileSystemEngine._render_tree(Path(dst_abs), variables or {})

        except (ExtractionError, RenderingError, EngineError):
            raise
        except Exception as e:
            msg = str(e)
            if "outside the destination" in msg or "Unsafe path" in msg:
                raise ExtractionError(f"Unsafe path detected: {msg}")
            if "link to an absolute path" in msg:
                raise EngineError(f"Absolute link detected: {msg}")
            raise EngineError(f"Decompression failed: {msg}")

    @staticmethod
    def _render_tree(root_path: Path, variables: Dict[str, Any]) -> None:
        """Renders all files and directories in a tree with Jinja2."""
        if not variables: return
        
        env = Environment(
            loader=FileSystemLoader(str(root_path)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )
        jinja_renderer = Environment()

        for root, dirs, files in os.walk(root_path, topdown=False):
            current_root = Path(root)

            for file in files:
                file_path = current_root / file
                
                if file_path.is_file() and not file_path.is_symlink():
                    if file_path.suffix.lower() not in FileSystemEngine.BINARY_EXTENSIONS:
                        try:
                            rel_path = file_path.relative_to(root_path)
                            template = env.get_template(rel_path.as_posix())
                            rendered_content = template.render(**variables)
                            file_path.write_text(rendered_content, encoding="utf-8")
                        except (TemplateSyntaxError, UndefinedError) as e:
                            logger.warning(f"Jinja2 error in {file_path}: {e}")
                        except Exception as e:
                            logger.debug(f"Skipping rendering for {file_path}: {e}")

                try:
                    rendered_name = jinja_renderer.from_string(file).render(**variables)
                    if rendered_name != file:
                        target_path = current_root / rendered_name
                        if not target_path.exists():
                            file_path.rename(target_path)
                        else:
                            logger.warning(f"Rename conflict: {target_path} already exists")
                except Exception as e:
                    logger.warning(f"Failed to render filename {file}: {e}")

            for d in dirs:
                dir_path = current_root / d
                if not dir_path.is_symlink():
                    try:
                        rendered_name = jinja_renderer.from_string(d).render(**variables)
                        if rendered_name != d:
                            target_path = current_root / rendered_name
                            if not target_path.exists():
                                dir_path.rename(target_path)
                            else:
                                logger.warning(f"Rename conflict: {target_path} already exists")
                    except Exception as e:
                        logger.warning(f"Failed to render directory name {d}: {e}")

    @staticmethod
    def run_hooks(cwd: Path, hooks: List[str]) -> None:
        """Runs a list of shell commands in the specified directory."""
        for hook in hooks:
            try:
                subprocess.run(hook, shell=True, cwd=cwd, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                raise EngineError(f"Post-clone hook failed: {hook}")

    @staticmethod
    def remove_directory(path: Path) -> None:
        """Safely removes a directory and its contents."""
        if not path.exists(): return

        def onerror(func: Callable, path_str: str, exc_info: tuple) -> None:
            try:
                os.chmod(path_str, stat.S_IWRITE)
                func(path_str)
            except Exception: pass

        try:
            shutil.rmtree(os.path.abspath(path), onerror=onerror)
        except Exception as e:
            raise EngineError(f"Failed to remove directory: {e}")

    @staticmethod
    def is_empty(path: Path) -> bool:
        """Checks if a directory is empty."""
        if not path.exists() or not path.is_dir(): return True
        return not any(path.iterdir())

    @staticmethod
    def ensure_directory(path: Path) -> None:
        """Ensures a directory exists."""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise EngineError(f"Failed to create directory: {e}")
