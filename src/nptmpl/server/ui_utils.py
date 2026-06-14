import re
import random

from nptmpl.core.config import ConfigManager


THEME_COLORS = {
    "blue-500": {"hex": "#3794ff", "glow": "rgba(55, 148, 255, 0.4)"},
    "emerald-500": {"hex": "#00ff41", "glow": "rgba(0, 255, 65, 0.4)"},
    "rose-500": {"hex": "#ff37a1", "glow": "rgba(255, 55, 161, 0.4)"},
    "amber-500": {"hex": "#ffb337", "glow": "rgba(255, 179, 55, 0.4)"},
    "violet-500": {"hex": "#a137ff", "glow": "rgba(161, 55, 255, 0.4)"},
    "cyan-500": {"hex": "#37f4ff", "glow": "rgba(55, 244, 255, 0.4)"},
    "teal-500": {"hex": "#37ffcb", "glow": "rgba(55, 255, 203, 0.4)"},
    "slate-500": {"hex": "#64748b", "glow": "rgba(100, 116, 139, 0.4)"},
    "lime-500": {"hex": "#a3e635", "glow": "rgba(163, 230, 53, 0.4)"},
    "green-500": {"hex": "#22c55e", "glow": "rgba(34, 197, 94, 0.4)"},
    "random": {"hex": None, "glow": None},
}

def get_site_meta(config: ConfigManager) -> dict:
    """Builds the metadata context for templates, incorporating dynamic UI settings."""
    ui_cfg = config.get_ui_config()
    color_key = ui_cfg.get("theme_color", "emerald-500").lower()
    
    if color_key == "random":
        choices = [k for k in THEME_COLORS.keys() if k != "random"]
        color_key = random.choice(choices)
        
    color_data = THEME_COLORS.get(color_key, THEME_COLORS["emerald-500"])
    ui_cfg["theme_hex"] = color_data["hex"]
    ui_cfg["theme_glow"] = color_data["glow"]
    ui_cfg["theme_color"] = color_key
    ui_cfg["public_url"] = config.get_public_url()
    return ui_cfg

def fix_markdown_paths(content: str) -> str:
    """Rewrites relative paths in markdown to work within the Web UI architecture."""
    
    content = content.replace('src="src/nptmpl/server/static/media/', 'src="/static/media/')
    content = content.replace('](src/nptmpl/server/static/media/', '](/static/media/')
    
    content = content.replace('src="media/', 'src="/static/media/')
    content = content.replace('src="docs/', 'src="/docs/')
    content = re.sub(r'!\[(.*?)\]\(media/(.*?)\)', r'![\1](/static/media/\2)', content)
    content = re.sub(r'\[(.*?)\]\(docs/(.*?)\)', r'[\1](/docs/\2)', content)
    return content
