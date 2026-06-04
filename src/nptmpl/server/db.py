import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional


logger = logging.getLogger("nptmpl.db")

class DatabaseManager:
    """Manages SQLite storage for template metadata and analytics with high-concurrency (WAL)."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    author TEXT NOT NULL,
                    email TEXT,
                    description TEXT,
                    languages TEXT, -- JSON list
                    license TEXT,
                    url TEXT,
                    added_date TEXT,
                    tags TEXT, -- JSON list
                    download_count INTEGER DEFAULT 0,
                    UNIQUE(group_name, name)
                );

                CREATE TABLE IF NOT EXISTS versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    version TEXT NOT NULL,
                    added_date TEXT NOT NULL,
                    readme_content TEXT,
                    FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE CASCADE,
                    UNIQUE(template_id, version)
                );
                
                CREATE INDEX IF NOT EXISTS idx_templates_group_name ON templates(group_name);
                CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name);
                CREATE INDEX IF NOT EXISTS idx_versions_template_id ON versions(template_id);
            """)

    def add_template_version(self, metadata: Dict[str, Any], readme: Optional[str] = None) -> None:
        with self._get_connection() as conn:
            group, name = metadata["target"].split("/", 1)
            conn.execute("""
                INSERT INTO templates (group_name, name, author, email, description, languages, license, url, added_date, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_name, name) DO UPDATE SET
                    author=excluded.author, email=excluded.email, description=excluded.description,
                    languages=excluded.languages, license=excluded.license, url=excluded.url, tags=excluded.tags
            """, (
                group, name, metadata["author"], metadata.get("email"),
                metadata["description"], json.dumps(metadata["languages"]),
                metadata.get("license"), metadata.get("url"),
                metadata.get("added_date"), json.dumps(metadata.get("tags", []))
            ))

            template_id = conn.execute("SELECT id FROM templates WHERE group_name=? AND name=?", (group, name)).fetchone()[0]
            conn.execute("""
                INSERT INTO versions (template_id, version, added_date, readme_content)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(template_id, version) DO UPDATE SET
                    added_date=excluded.added_date,
                    readme_content=excluded.readme_content
            """, (template_id, metadata["version"], metadata["added_date"], readme))

    def list_templates(self, query: Optional[str] = None, language: Optional[str] = None,
                       tag: Optional[str] = None, license: Optional[str] = None,
                       author: Optional[str] = None, sort_by: str = "added_date") -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            sql = """
                WITH latest_versions AS (
                    SELECT template_id, version, added_date,
                           ROW_NUMBER() OVER (PARTITION BY template_id ORDER BY id DESC) as rn
                    FROM versions
                )
                SELECT t.*, lv.version as latest_version, lv.added_date as version_added_date
                FROM templates t
                LEFT JOIN latest_versions lv ON t.id = lv.template_id AND lv.rn = 1
                WHERE 1=1
            """
            params = []
            if query:
                sql += " AND (t.group_name LIKE ? OR t.name LIKE ? OR t.description LIKE ? OR t.author LIKE ? OR t.tags LIKE ?)"
                p = f"%{query}%"
                params.extend([p, p, p, p, p])

            if language: sql += " AND t.languages LIKE ?"; params.append(f'%"{language}"%')
            if tag: sql += " AND t.tags LIKE ?"; params.append(f'%"{tag}"%')
            if license: sql += " AND t.license = ?"; params.append(license)
            if author: sql += " AND t.author = ?"; params.append(author)

            sort_map = {"added_date": "t.added_date DESC", "clones": "t.download_count DESC", "name": "t.name ASC", "author": "t.author ASC"}
            sql += f" ORDER BY {sort_map.get(sort_by, 't.added_date DESC')}"

            rows = conn.execute(sql, params).fetchall()
            return [{**dict(r), "languages": json.loads(r["languages"]), "tags": json.loads(r["tags"]), "version": r["latest_version"] or "0.0.0"} for r in rows]

    def get_template(self, group: str, name: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM templates WHERE group_name=? AND name=?", (group, name)).fetchone()
            if not row: return None
            d = dict(row)
            d["languages"], d["tags"] = json.loads(d["languages"]), json.loads(d["tags"])
            v_rows = conn.execute("SELECT version, added_date, readme_content FROM versions WHERE template_id=? ORDER BY id DESC", (d["id"],)).fetchall()
            d["versions"] = [dict(v) for v in v_rows]
            d["version"] = d["versions"][0]["version"] if d["versions"] else "0.0.0"
            return d

    def get_related_templates(self, group: str, name: str, limit: int = 4) -> List[Dict[str, Any]]:
        current = self.get_template(group, name)
        if not current: return []
        with self._get_connection() as conn:
            conditions, params = [], [current["id"]]
            for lang in current["languages"]: conditions.append("languages LIKE ?"); params.append(f'%"{lang}"%')
            for tag in current["tags"]: conditions.append("tags LIKE ?"); params.append(f'%"{tag}"%')
            sql = "SELECT * FROM templates WHERE id != ? AND (" + " OR ".join(conditions) + ") ORDER BY download_count DESC LIMIT ?" if conditions else "SELECT * FROM templates WHERE id != ? ORDER BY download_count DESC LIMIT ?"
            params.append(limit)
            return [{**dict(r), "languages": json.loads(r["languages"]), "tags": json.loads(r["tags"])} for r in conn.execute(sql, params).fetchall()]

    def get_filter_options(self) -> Dict[str, List[str]]:
        with self._get_connection() as conn:
            authors = [r[0] for r in conn.execute("SELECT DISTINCT author FROM templates").fetchall()]
            licenses = [r[0] for r in conn.execute("SELECT DISTINCT license FROM templates WHERE license IS NOT NULL").fetchall()]
            langs, tags = set(), set()
            for row in conn.execute("SELECT languages, tags FROM templates").fetchall():
                for l in json.loads(row[0]): langs.add(l)
                for t in json.loads(row[1]): tags.add(t)
            return {"authors": sorted(authors), "licenses": sorted(licenses), "languages": sorted(list(langs)), "tags": sorted(list(tags))}

    def increment_download(self, group: str, name: str) -> None:
        with self._get_connection() as conn:
            conn.execute("UPDATE templates SET download_count = download_count + 1 WHERE group_name=? AND name=?", (group, name))

    def delete_version(self, group: str, name: str, version: str) -> bool:
        """
        Deletes a specific version of a template.
        Returns True if the entire template was deleted, False otherwise.
        """
        with self._get_connection() as conn:
            template = conn.execute("SELECT id FROM templates WHERE group_name=? AND name=?", (group, name)).fetchone()
            if not template:
                return False
                
            template_id = template[0]
            conn.execute("DELETE FROM versions WHERE template_id=? AND version=?", (template_id, version))
            
            count = conn.execute("SELECT COUNT(*) FROM versions WHERE template_id=?", (template_id,)).fetchone()[0]
            if count == 0:
                conn.execute("DELETE FROM templates WHERE id=?", (template_id,))
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            res = conn.execute("SELECT COUNT(*), SUM(download_count) FROM templates").fetchone()
            return {
                "total_templates": res[0], "total_clones": res[1] or 0,
                "recent": [dict(r) for r in conn.execute("SELECT group_name, name, added_date FROM templates ORDER BY added_date DESC LIMIT 5").fetchall()],
                "top": [dict(r) for r in conn.execute("SELECT group_name, name, download_count FROM templates ORDER BY download_count DESC LIMIT 5").fetchall()]
            }
