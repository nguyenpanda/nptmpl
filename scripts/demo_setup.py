import subprocess
import shutil
import os
from pathlib import Path

def run_demo():
    demo_root = Path("nptmpl_demo_env")
    store_path = demo_root / "store"
    src_data = Path("tests/data/realistic_templates")
    
    if demo_root.exists():
        shutil.rmtree(demo_root)
    demo_root.mkdir()
    
    env = os.environ.copy()
    env["NPTMPL_STORE_PATH"] = str(store_path.absolute())
    env["PYTHONPATH"] = "src"

    def nptmpl(*args):
        cmd = ["python3", "-m", "nptmpl.cli"] + list(args)
        subprocess.run(cmd, env=env, check=True)

    print("Starting Professional nptmpl Demo Setup...\n")

    projects = {}
    for item in src_data.iterdir():
        if not item.is_dir():
            continue
        parts = item.name.split("_")
        group = parts[0]
        name = parts[1]
        version = parts[2]
        
        target = f"{group}/{name}"
        if target not in projects:
            projects[target] = []
        projects[target].append((version, item))

    for target, versions in projects.items():
        versions.sort(key=lambda x: [int(p) for p in x[0].split(".")])
        
        v0_str, v0_path = versions[0]
        print(f"Adding initial template: {target} @{v0_str}")
        nptmpl("add", str(v0_path), target)
        
        for v_str, v_path in versions[1:]:
            print(f"Updating template: {target} to @{v_str}")
            nptmpl("update", target, str(v_path))

    print("\n✅ Demo environment ready!")
    print(f"Registry stored at: {store_path}")
    print("\nTry these commands:")
    print(f"  export NPTMPL_STORE_PATH={store_path.absolute()}")
    print("  nptmpl list")
    print("  nptmpl search web")
    print("  nptmpl detail web/flask-api")
    print("  nptmpl clone web/flask-api ./my-app")

if __name__ == "__main__":
    run_demo()
