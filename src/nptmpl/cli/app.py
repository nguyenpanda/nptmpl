import argparse
import sys
import logging
import getpass
import os
import yaml
import webbrowser
import threading
import time
from datetime import datetime
from typing import List, Optional, Dict, Union, Tuple, Any
from pathlib import Path
import argcomplete
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from nptmpl import __version__ as app_version
from nptmpl.core.store import TemplateStore
from nptmpl.core.metadata import MetadataManager, Version, TemplateMetadata
from nptmpl.core.config import ConfigManager
from nptmpl.core.models import Template
from nptmpl.core.remote.resolver import TargetResolver, TargetType
from nptmpl.core.remote.base import RemoteTransport
from nptmpl.core.remote.ssh import SshTransport
from nptmpl.core.errors import (
    NptmplError, 
    TemplateNotFoundError, 
    DestinationNotEmptyError,
    AuthenticationError,
    NetworkError,
    ValidationError
)
from nptmpl.cli.utils import display_table, display_detail, confirm

logger = logging.getLogger("nptmpl.cli")
console = Console()

from nptmpl.server.sync import SqliteRegistrySynchronizer

class CLIApp:
    """
    Presentation layer for terminal input, output, and command orchestration.
    """

    def __init__(self, args: Optional[List[str]] = None):
        self.parser = self._setup_parser()
        cli_args = args if args is not None else sys.argv[1:]
        
        if not cli_args:
            self.parser.print_help()
            sys.exit(0)

        self.parsed_args = self.parser.parse_args(cli_args)
        
        try:
            self.config_manager = ConfigManager(config_path=self.parsed_args.config)
            self.store_path = self.config_manager.get_store_path()
            self.global_ignore = self.config_manager.get_global_ignore()
            self.auth_token = self.config_manager.get_auth_token()
            
            # Inject synchronizer to keep core decoupled from server details
            sync = SqliteRegistrySynchronizer()
            self.store = TemplateStore(self.store_path, global_ignore=self.global_ignore, synchronizer=sync)
        except Exception as e:
            console.print(f"[bold red]Initialization Error:[/bold red] {e}")
            sys.exit(1)

    def _setup_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="nptmpl",
            description="nptmpl - A Professional Local Template Manager.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        
        parser.add_argument("--version", action="version", version=f"nptmpl {app_version}")
        parser.add_argument("--config", help="Path to a custom config.yaml file")

        subparsers = parser.add_subparsers(dest="command", required=True, title="Available Commands", metavar="<command>")

        # Init
        init_parser = subparsers.add_parser("init", help="Initialize a new template directory")
        init_parser.add_argument("path", nargs="?", default=".", help="Directory to initialize")

        # Edit
        edit_parser = subparsers.add_parser("edit", help="Edit template metadata interactively")
        edit_parser.add_argument("target", nargs="?", default=".", help="Template identifier or local path")

        # Add
        add_parser = subparsers.add_parser("add", help="Add a template to the local registry")
        add_parser.add_argument("source_dir", help="Source directory or remote URL")
        add_parser.add_argument("target", nargs="?", help="Registry identifier <group>/<name>")
        add_parser.add_argument("--overwrite", action="store_true", help="Replace existing version")

        # Update
        update_parser = subparsers.add_parser("update", help="Add a new version to a template")
        update_parser.add_argument("target", help="Template to update").completer = self._template_completer
        update_parser.add_argument("source_dir", help="Source for new version")

        # Clone
        clone_parser = subparsers.add_parser("clone", help="Clone template with variable injection")
        clone_parser.add_argument("target", help="Template identifier or remote URL").completer = self._template_completer
        clone_parser.add_argument("dest_dir", help="Destination path")
        clone_parser.add_argument("--var", "-v", action="append", help="Set variables (key=value)")
        clone_parser.add_argument("--no-hooks", action="store_true", help="Disable post-clone hooks")

        # Push
        push_parser = subparsers.add_parser("push", help="Push template to remote registry")
        push_parser.add_argument("target", help="Local template identifier").completer = self._template_completer
        push_parser.add_argument("remote_url", help="Remote URL or SSH URI")
        push_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing version on remote")

        # List
        list_parser = subparsers.add_parser("list", aliases=["ls"], help="List templates")
        list_parser.add_argument("target", nargs="?", default=None, help="Filter by template").completer = self._template_completer
        list_parser.add_argument("--language", "-l", help="Filter by language")
        list_parser.add_argument("--author", "-a", help="Filter by author")
        list_parser.add_argument("--tag", "-t", help="Filter by tag")
        list_parser.add_argument("--remote", help="Query remote registry")

        # Search
        search_parser = subparsers.add_parser("search", help="Search across templates")
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument("--remote", help="Search remote registry")

        # Detail
        detail_parser = subparsers.add_parser("detail", help="View template details")
        detail_parser.add_argument("target", help="Template identifier").completer = self._template_completer
        detail_parser.add_argument("--remote", help="View remote details")

        # Remove
        remove_parser = subparsers.add_parser("remove", aliases=["rm"], help="Delete from registry")
        remove_parser.add_argument("target", help="Template or version to delete").completer = self._template_completer

        # Doctor
        subparsers.add_parser("doctor", help="Run system diagnostics")

        # Serve
        serve_parser = subparsers.add_parser("serve", help="Start nptmpl server")
        serve_parser.add_argument("--host", default="0.0.0.0")
        serve_parser.add_argument("--port", type=int, default=9090)
        serve_parser.add_argument("--storage")
        serve_parser.add_argument("--reindex", action="store_true")
        serve_parser.add_argument("--enable-docs", action="store_true")
        serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

        # Path
        path_parser = subparsers.add_parser(name="path", help="Show system paths")
        path_parser.add_argument("target", nargs="?", help="Template identifier")
        path_parser.add_argument("--show-config", action="store_true", help="Show current config file path")
        path_parser.add_argument("--show-store", action="store_true", help="Show current store root path")

        # UI
        ui_parser = subparsers.add_parser("ui", help="Launch local web UI")
        ui_parser.add_argument("--port", type=int, default=8000)
        ui_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

        # Config
        config_parser = subparsers.add_parser("config", help="Manage configuration")
        config_subparsers = config_parser.add_subparsers(dest="config_command", required=True, title="Config Actions")
        
        config_subparsers.add_parser("show", help="Show effective configuration and source")
        
        config_edit = config_subparsers.add_parser("edit", help="Edit configuration interactively")
        config_edit.add_argument("path", nargs="?", default="current", help="Config file path (default: current active)")
        
        config_init = config_subparsers.add_parser("init", help="Create a new config.yaml")
        config_init.add_argument("path", nargs="?", default="config.yaml", help="Destination path")

        argcomplete.autocomplete(parser)
        return parser

    def _template_completer(self, prefix: str, **kwargs) -> List[str]:
        results = []
        if not self.store_path.exists():
            return results
        for group_dir in self.store_path.iterdir():
            if not group_dir.is_dir() or group_dir.name.startswith("."):
                continue
            for name_dir in group_dir.iterdir():
                if not name_dir.is_dir():
                    continue
                target = f"{group_dir.name}/{name_dir.name}"
                if target.startswith(prefix):
                    results.append(target)
        return results

    def run(self) -> None:
        try:
            handler_name = f"_handle_{self.parsed_args.command.replace('-', '_')}"
            handler = getattr(self, handler_name, None)
            
            if handler:
                handler(self.parsed_args)
            elif self.parsed_args.command in ("ls", "list"):
                self._handle_list(self.parsed_args)
            elif self.parsed_args.command in ("rm", "remove"):
                self._handle_remove(self.parsed_args)
            else:
                console.print(f"[bold red]Error:[/bold red] Command '{self.parsed_args.command}' not implemented.")
                sys.exit(1)

        except (NptmplError, FileNotFoundError, FileExistsError, PermissionError, OSError) as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/yellow]")
            sys.exit(1)
        except Exception as e:
            logger.exception("Unexpected error")
            console.print(f"[bold red]Unexpected error:[/bold red] {e}")
            sys.exit(1)

    def _handle_init(self, args: argparse.Namespace) -> None:
        defaults = self.config_manager.get_init_defaults()
        MetadataManager.create_default(Path(args.path), defaults=defaults)

    def _handle_edit(self, args: argparse.Namespace) -> None:
        target = args.target
        local_path = Path(target)
        if (local_path / ".nptmpl").exists():
            MetadataManager.edit_interactive(local_path)
        else:
            try:
                template_obj, version, _ = self.store.get_template_details(target)
                MetadataManager.edit_interactive(template_obj.get_version_path(version))
                self.store.cache.rebuild()
            except TemplateNotFoundError:
                console.print(f"[bold red]Error:[/bold red] '{target}' is not a valid local path or template.")
                sys.exit(1)

    def _handle_add(self, args: argparse.Namespace) -> None:
        target_type, context, remote_target = TargetResolver.resolve(args.source_dir, auth_token=self.auth_token)

        if target_type in (TargetType.HTTP, TargetType.SSH):
            remote = self._ensure_auth(context)
            self.store.clone_template(remote_target, ".", remote=remote)
        else:
            if args.overwrite:
                try:
                    self.store.get_template_details(args.target)
                    if not confirm(f"Warning: Overwrite '{args.target}'?"):
                        return
                except TemplateNotFoundError:
                    pass
            self.store.add_template(args.source_dir, args.target, overwrite=args.overwrite)

    def _handle_update(self, args: argparse.Namespace) -> None:
        self.store.update_template(args.target, args.source_dir)

    def _handle_clone(self, args: argparse.Namespace) -> None:
        target_type, context, remote_target = TargetResolver.resolve(args.target, auth_token=self.auth_token)

        variables = {}
        if args.var:
            for v in args.var:
                if "=" in v:
                    k, val = v.split("=", 1)
                    variables[k] = val

        if target_type in (TargetType.HTTP, TargetType.SSH):
            remote = self._ensure_auth(context)
            try:
                self.store.clone_template(remote_target, args.dest_dir, variables=variables, remote=remote)
            except DestinationNotEmptyError as e:
                if confirm(f"{e} Overwrite?"):
                    self.store.clone_template(remote_target, args.dest_dir, variables=variables, force=True, remote=remote)
        else:
            _, _, metadata = self.store.get_template_details(args.target)
            self._prompt_variables(metadata, variables)
            try:
                self.store.clone_template(args.target, args.dest_dir, variables=variables)
            except DestinationNotEmptyError as e:
                if confirm(f"{e} Overwrite?"):
                    self.store.clone_template(args.target, args.dest_dir, variables=variables, force=True)

    def _ensure_auth(self, transport: RemoteTransport) -> RemoteTransport:
        if isinstance(transport, SshTransport):
            if not transport.password:
                try:
                    transport._connect()
                except AuthenticationError:
                    transport.password = getpass.getpass(f"Password for {transport.user}@{transport.host}: ")
                except NetworkError as e:
                     if "Manual verification required" in str(e):
                         console.print(f"[bold yellow]Security Warning:[/bold yellow] {e}")
                         if not confirm("Trust this host?"):
                             raise NetworkError("Operation aborted by user due to untrusted host.")
                         
                         import paramiko
                         transport.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                         return self._ensure_auth(transport)
                     raise
        return transport

    def _prompt_variables(self, metadata: TemplateMetadata, variables: Dict[str, str]) -> None:
        if metadata.variables:
            for var_name, var_desc in metadata.variables.items():
                if var_name not in variables:
                    val = input(f"Variable '{var_name}' ({var_desc}): ")
                    variables[var_name] = val

    def _handle_push(self, args: argparse.Namespace) -> None:
        _, context, _ = TargetResolver.resolve(args.remote_url, auth_token=self.auth_token)
        if not isinstance(context, RemoteTransport):
            console.print("[bold red]Error:[/bold red] Invalid remote URL.")
            sys.exit(1)
        remote = self._ensure_auth(context)
        self.store.push_template(args.target, remote, overwrite=args.overwrite)

    def _handle_list(self, args: argparse.Namespace) -> None:
        filters = {}
        if args.language: filters["languages"] = args.language
        if args.author: filters["author"] = args.author
        if args.tag: filters["tags"] = args.tag

        if args.remote:
            target_type, context, _ = TargetResolver.resolve(args.remote, auth_token=self.auth_token)
            if target_type in (TargetType.HTTP, TargetType.SSH):
                remote = self._ensure_auth(context)
                results = remote.list_templates(args.target)
                converted = []
                for t, v, m in results:
                    g, n = t.split("/", 1)
                    converted.append((Template(g, n, self.store_path), Version(v), TemplateMetadata.from_dict(m)))
                display_table(converted, f"Remote Registry: {args.remote}")
            else:
                console.print("[bold red]Error:[/bold red] Invalid remote URL.")
        else:
            results = self.store.list_templates(args.target, filter_dict=filters)
            display_table(results, "Template Registry")

    def _handle_search(self, args: argparse.Namespace) -> None:
        if args.remote:
            target_type, context, _ = TargetResolver.resolve(args.remote, auth_token=self.auth_token)
            if target_type in (TargetType.HTTP, TargetType.SSH):
                remote = self._ensure_auth(context)
                results = remote.list_templates(args.query)
                converted = []
                for t, v, m in results:
                    g, n = t.split("/", 1)
                    converted.append((Template(g, n, self.store_path), Version(v), TemplateMetadata.from_dict(m)))
                display_table(converted, f"Search results on remote: {args.remote}")
        else:
            results = self.store.search_templates(args.query)
            display_table(results, f"Search results for: {args.query}")

    def _handle_detail(self, args: argparse.Namespace) -> None:
        if args.remote:
            target_type, context, _ = TargetResolver.resolve(args.remote, auth_token=self.auth_token)
            if target_type in (TargetType.HTTP, TargetType.SSH):
                remote = self._ensure_auth(context)
                target, version, metadata_dict = remote.get_details(args.target)
                g, n = target.split("/", 1)
                display_detail(
                    Template(g, n, self.store_path), 
                    Version(version), 
                    TemplateMetadata.from_dict(metadata_dict)
                )
        else:
            template, version, metadata = self.store.get_template_details(args.target)
            display_detail(template, version, metadata)

    def _handle_remove(self, args: argparse.Namespace) -> None:
        target = args.target
        group, name, version_str = self.store._parse_target(target)
        template = Template(group, name, self.store_path)

        if not template.exists():
            console.print(f"[bold red]Error:[/bold red] Template '{template}' not found.")
            sys.exit(1)

        if version_str:
            if confirm(f"Remove version {version_str} of '{template}'?"):
                self.store.remove_template(target)
        else:
            if confirm(f"Remove template '{template}' and ALL versions?"):
                self.store.remove_template(target)

    def _handle_doctor(self, args: argparse.Namespace) -> None:
        console.print("[bold cyan]Running system diagnostics...[/bold cyan]\n")
        results = self.store.doctor()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Check")
        table.add_column("Result")
        table.add_column("Status", justify="center")

        for check, msg, ok in results:
            status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
            table.add_row(check, msg, status)
        console.print(table)

    def _handle_serve(self, args: argparse.Namespace) -> None:
        from nptmpl.server.main import start_server
        storage = args.storage or str(self.store_path / "server")
        start_server(args.host, args.port, storage, 
            reindex=args.reindex, 
            enable_docs=args.enable_docs, 
            reload=args.reload, 
            config=self.config_manager
        )

    def _handle_path(self, args: argparse.Namespace) -> None:
        if args.show_config:
            if self.config_manager.config_file_used:
                print(self.config_manager.config_file_used)
        elif args.show_store:
            print(self.store_path)
        elif args.target:
            template_obj, version, _ = self.store.get_template_details(args.target)
            print(template_obj.get_version_path(version))
        else:
            print(self.store_path)

    def _handle_ui(self, args: argparse.Namespace) -> None:
        from nptmpl.server.main import start_server
        port = args.port
        host = "127.0.0.1"
        url = f"http://{host}:{port}"

        def open_browser():
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=open_browser, daemon=True).start()
        console.print(f"[bold cyan] Launching nptmpl Local UI at {url}...[/bold cyan]")
        start_server(host, port, str(self.store_path), reload=args.reload, config=self.config_manager)

    def _handle_config(self, args: argparse.Namespace) -> None:
        if args.config_command == "init":
            self._config_init(args.path)
        elif args.config_command == "edit":
            self._config_edit(args.path)
        elif args.config_command == "show":
            schema = ConfigManager.get_schema()
            table = Table(title="Effective Configuration", show_header=True, header_style="bold magenta", expand=True)
            table.add_column("Property", style="bold cyan")
            table.add_column("Value", style="green")
            table.add_column("Source", style="yellow")
            table.add_column("Description", style="dim white")

            for section, options in schema.items():
                if isinstance(list(options.values())[0], dict) and "description" not in list(options.values())[0]:
                    for subs, subopts in options.items():
                        for k, meta in subopts.items():
                            key = f"{section}.{subs}.{k}"
                            val, source = self._get_val_and_source(key, meta)
                            table.add_row(key, str(val), source, meta.get("description", ""))
                else:
                    for k, meta in options.items():
                        key = f"{section}.{k}"
                        val, source = self._get_val_and_source(key, meta)
                        table.add_row(key, str(val), source, meta.get("description", ""))
            
            console.print(table)
            if self.config_manager.config_file_used:
                console.print(f"\n[bold blue]Config File:[/bold blue] {self.config_manager.config_file_used}")

    def _get_val_and_source(self, key: str, meta: Dict[str, Any]) -> Tuple[Any, str]:
        env_var = meta.get("env")
        if env_var and os.environ.get(env_var):
            return os.environ.get(env_var), f"Env ({env_var})"
        
        parts = key.split(".")
        val = self.config_manager.config_data
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                val = None
                break
        
        if val is not None:
            return val, "File"
            
        return meta.get("default", "N/A"), "Default"

    def _config_init(self, target: str) -> None:
        path = Path(target)
        if path.is_dir(): path = path / "config.yaml"
        if path.exists() and not confirm(f"Overwrite {path}?"): return

        defaults = {}
        schema = ConfigManager.get_schema()
        for section, options in schema.items():
            if "description" not in list(options.values())[0]:
                defaults[section] = {subs: {k: v.get("default", "") for k, v in subopts.items()} for subs, subopts in options.items()}
            else:
                defaults[section] = {k: v.get("default", "") for k, v in options.items()}

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# nptmpl Configuration File\n# Generated automatically.\n\n")
            yaml.dump(defaults, f, sort_keys=False)
        console.print(f"[bold green]Success:[/bold green] Initialized config at {path}")

    def _config_edit(self, target: str) -> None:
        import questionary
        path = self.config_manager.config_file_used if target == "current" else Path(target)
        if not path or not path.exists():
            console.print(f"[bold red]Error:[/bold red] Config file not found.")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        schema = ConfigManager.get_schema()
        new_data = {}

        for section, options in schema.items():
            new_data[section] = {}
            if "description" not in list(options.values())[0]:
                for subs, subopts in options.items():
                    new_data[section][subs] = {}
                    for k, meta in subopts.items():
                        current = data.get(section, {}).get(subs, {}).get(k, meta.get("default", ""))
                        if "options" in meta:
                            val = questionary.select(f"{section}.{subs}.{k}", choices=meta['options'], default=current).ask()
                        else:
                            val = questionary.text(f"{section}.{subs}.{k}", default=str(current)).ask()
                        new_data[section][subs][k] = val
            else:
                for k, meta in options.items():
                    current = data.get(section, {}).get(k, meta.get("default", ""))
                    if "options" in meta:
                        val = questionary.select(f"{section}.{k}", choices=meta['options'], default=current).ask()
                    else:
                        val = questionary.text(f"{section}.{k}", default=str(current)).ask()
                    new_data[section][k] = val

        if questionary.confirm("Save changes?").ask():
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(new_data, f, sort_keys=False)
            console.print("[bold green]Configuration updated.[/bold green]")
