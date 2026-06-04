import os
import yaml
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger("nptmpl.config")

class ConfigError(Exception):
    """Base exception for configuration related errors."""
    pass

class ConfigManager:
    """
    Manages application configuration, storage path resolution, and metadata schema.
    
    Precedence: 
    1. CLI Argument (--config)
    2. Environment Variable (NPTMPL_CONFIG_PATH)
    3. Configuration File (cwd -> xdg -> home)
    4. Defaults
    """

    DEFAULT_STORE_PATH = Path.home() / ".nptmpl" / "db"
    
    SCHEMA = {
        "core": {
            "store_path": {
                "env": "NPTMPL_STORE_PATH",
                "default": str(DEFAULT_STORE_PATH),
                "description": "Path to the template registry database and files.",
                "type": str
            },
            "auth_token": {
                "env": "NPTMPL_AUTH_TOKEN",
                "description": "Token for authenticating with remote registries (push/delete).",
                "type": str
            },
            "ignore": {
                "default": [],
                "description": "Global list of pathspec patterns to ignore during template addition.",
                "type": list
            },
            "public_url": {
                "description": "Public-facing URL of the registry (used in clone hints).",
                "type": str
            }
        },
        "server": {
            "admin": {
                "username": {
                    "env": "NPTMPL_ADMIN_USER",
                    "default": "admin",
                    "description": "Username for the Web UI admin dashboard.",
                    "type": str
                },
                "password": {
                    "env": "NPTMPL_ADMIN_PASS",
                    "default": "admin",
                    "description": "Password for the Web UI admin dashboard.",
                    "type": str
                }
            },
            "ui": {
                "title": {
                    "default": "nptmpl Registry",
                    "description": "The title displayed in the browser tab and site header.",
                    "type": str
                },
                "theme_color": {
                    "default": "emerald-500",
                    "description": "Tailwind CSS color name for UI accents.",
                    "options": ["blue-500", "emerald-500", "rose-500", "amber-500", "violet-500", "cyan-500", "teal-500", "slate-500", "lime-500", "green-500"],
                    "type": str
                },
                "logo_text": {
                    "default": "nptmpl_registry",
                    "description": "Branding text shown next to the logo.",
                    "type": str
                },
                "author_name": {
                    "default": "Author Name",
                    "description": "Name of the registry owner shown in the About page.",
                    "type": str
                },
                "github_url": {
                    "default": "https://github.com",
                    "description": "Link to the owner's GitHub profile.",
                    "type": str
                },
                "linkedin_url": {
                    "default": "",
                    "description": "Link to the owner's LinkedIn profile.",
                    "type": str
                }
            }
        },
        "defaults": {
            "author": {"description": "Default author name for new templates.", "type": str},
            "email": {"description": "Default email for new templates.", "type": str},
            "license": {"default": "MIT", "description": "Default license for new templates.", "type": str}
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config_data = {}
        self.config_file_used: Optional[Path] = None
        self._load_config(config_path)

    def _get_config_locations(self) -> List[Path]:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        xdg_path = Path(xdg_config) / "nptmpl" / "config.yaml" if xdg_config else Path.home() / ".config" / "nptmpl" / "config.yaml"

        return [
            xdg_path,
            Path.home() / ".nptmpl" / "config.yaml",
            Path.cwd() / "config.yaml"
        ]

    def _load_config(self, manual_path: Optional[str]) -> None:
        # Precedence: CLI Arg > Env Var > Standard Locations
        env_path = os.environ.get("NPTMPL_CONFIG_PATH")
        
        locations = []
        if manual_path:
            locations.append(Path(manual_path))
        if env_path:
            locations.append(Path(env_path))
            
        if not locations:
            locations = self._get_config_locations()
        
        for loc in locations:
            if loc.exists() and loc.is_file():
                try:
                    with open(loc, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data is not None:
                            if not isinstance(data, dict):
                                raise ConfigError(f"Malformed config file at {loc}: Expected a YAML dictionary.")
                            self.config_data = data
                            self.config_file_used = loc
                            break
                except yaml.YAMLError as e:
                     raise ConfigError(f"Malformed config file at {loc}: {e}")
                except ConfigError:
                     raise
                except Exception as e:
                    logger.warning(f"Failed to load config from {loc}: {e}")

    def get(self, key_path: str) -> Any:
        """Retrieves a configuration value following the precedence rules."""
        parts = key_path.split(".")
        meta = self.SCHEMA
        for p in parts:
            meta = meta.get(p, {})
        
        # Environment Variable
        env_var = meta.get("env")
        if env_var and os.environ.get(env_var):
            return os.environ.get(env_var)
        
        # Config File
        val = self.config_data
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break
        
        if val is not None:
            return val
            
        # Default
        return meta.get("default")

    def get_store_path(self) -> Path:
        path_str = self.get("core.store_path")
        return self._resolve_path(path_str, "Configuration")

    def get_ui_config(self) -> Dict[str, Any]:
        return {
            "title": self.get("server.ui.title"),
            "theme_color": self.get("server.ui.theme_color"),
            "logo_text": self.get("server.ui.logo_text"),
            "github_url": self.get("server.ui.github_url"),
            "linkedin_url": self.get("server.ui.linkedin_url"),
            "author_name": self.get("server.ui.author_name"),
        }

    def get_admin_credentials(self) -> Tuple[str, str]:
        return self.get("server.admin.username"), self.get("server.admin.password")

    def get_init_defaults(self) -> Dict[str, Any]:
        return self.config_data.get("defaults", {})

    def get_auth_token(self) -> Optional[str]:
        return self.get("core.auth_token")

    def get_global_ignore(self) -> List[str]:
        return self.get("core.ignore") or []

    def get_public_url(self) -> Optional[str]:
        return self.get("core.public_url")

    @staticmethod
    def get_schema() -> Dict[str, Any]:
        return ConfigManager.SCHEMA

    def _resolve_path(self, path_str: str, source_label: str) -> Path:
        """Expands environment variables, user (~) and validates a path string."""
        if not path_str:
             return self.DEFAULT_STORE_PATH.resolve()
             
        expanded_vars = os.path.expandvars(path_str)
        path = Path(expanded_vars).expanduser()

        if not path.is_absolute():
             if not path_str.startswith("~") and not path_str.startswith("$"):
                  raise ConfigError(f"Relative path detected in {source_label}: '{path_str}'. Only absolute paths are allowed.")
             path = path.resolve()

        return path.resolve()
