import yaml
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def generate_realistic_templates(base_path: Path):
    """
    Generates a massive, realistic library of templates (120+ versions) 
    grouped by domain, with multiple versions per project.
    """
    if base_path.exists():
        shutil.rmtree(base_path)
    base_path.mkdir(parents=True)

    project_types = [
        # Web
        {"group": "web", "name": "flask-api", "langs": ["python", "sql"], "tags": ["backend", "rest"]},
        {"group": "web", "name": "django-web", "langs": ["python", "html", "css"], "tags": ["backend", "framework"]},
        {"group": "web", "name": "react-app", "langs": ["typescript", "css"], "tags": ["frontend", "ui"]},
        {"group": "web", "name": "vue-starter", "langs": ["javascript", "html"], "tags": ["frontend", "framework"]},
        {"group": "web", "name": "nextjs-fullstack", "langs": ["typescript", "react"], "tags": ["frontend", "ssr"]},
        {"group": "web", "name": "express-server", "langs": ["javascript"], "tags": ["backend", "nodejs"]},
        
        # AI/ML
        {"group": "ai", "name": "pytorch-cv", "langs": ["python"], "tags": ["ml", "vision"]},
        {"group": "ai", "name": "tensorflow-nlp", "langs": ["python"], "tags": ["ml", "text"]},
        {"group": "ai", "name": "scikit-analysis", "langs": ["python"], "tags": ["data-science", "stats"]},
        {"group": "ai", "name": "huggingface-diffusers", "langs": ["python"], "tags": ["generative", "ai"]},
        {"group": "ai", "name": "jupyter-data-viz", "langs": ["python", "ipynb"], "tags": ["notebook", "viz"]},
        
        # C++ / Systems
        {"group": "cpp", "name": "cmake-lib", "langs": ["cpp", "cmake"], "tags": ["systems", "library"]},
        {"group": "cpp", "name": "qt-desktop", "langs": ["cpp", "ui"], "tags": ["desktop", "gui"]},
        {"group": "cpp", "name": "cuda-kernels", "langs": ["cuda", "cpp"], "tags": ["gpu", "parallel"]},
        {"group": "cpp", "name": "bazel-build", "langs": ["cpp", "starlark"], "tags": ["build-system"]},
        
        # Mobile
        {"group": "mobile", "name": "flutter-cross", "langs": ["dart"], "tags": ["mobile", "android", "ios"]},
        {"group": "mobile", "name": "react-native-ui", "langs": ["typescript", "react"], "tags": ["mobile", "ui"]},
        {"group": "mobile", "name": "swift-ios", "langs": ["swift"], "tags": ["ios", "apple"]},
        {"group": "mobile", "name": "kotlin-android", "langs": ["kotlin"], "tags": ["android", "google"]},

        # CLI
        {"group": "cli", "name": "python-click", "langs": ["python"], "tags": ["tool", "cli"]},
        {"group": "cli", "name": "rust-clap", "langs": ["rust"], "tags": ["systems", "binary"]},
        {"group": "cli", "name": "go-cobra", "langs": ["go"], "tags": ["utility", "fast"]},
        {"group": "cli", "name": "node-commander", "langs": ["javascript"], "tags": ["node", "tool"]},

        # Cloud/DevOps
        {"group": "cloud", "name": "terraform-aws", "langs": ["hcl"], "tags": ["infra", "aws"]},
        {"group": "cloud", "name": "k8s-manifests", "langs": ["yaml"], "tags": ["containers", "devops"]},
        {"group": "cloud", "name": "docker-compose-stack", "langs": ["docker"], "tags": ["local-dev"]},
        {"group": "cloud", "name": "ansible-playbooks", "langs": ["yaml"], "tags": ["automation"]},

        # Rust/Go
        {"group": "rust", "name": "cargo-bin", "langs": ["rust"], "tags": ["systems"]},
        {"group": "rust", "name": "wasm-lib", "langs": ["rust", "wasm"], "tags": ["web", "high-perf"]},
        {"group": "go", "name": "gin-api", "langs": ["go"], "tags": ["backend", "rest"]},
        {"group": "go", "name": "fiber-web", "langs": ["go"], "tags": ["fast", "http"]},

        # Java/JVM
        {"group": "java", "name": "spring-boot-app", "langs": ["java"], "tags": ["enterprise", "backend"]},
        {"group": "java", "name": "maven-library", "langs": ["java"], "tags": ["library"]},
        {"group": "java", "name": "scala-spark", "langs": ["scala"], "tags": ["big-data"]},

        # Embedded
        {"group": "embedded", "name": "arduino-uno", "langs": ["ino"], "tags": ["iot", "hardware"]},
        {"group": "embedded", "name": "esp32-idf", "langs": ["c", "cpp"], "tags": ["wifi", "iot"]},
        {"group": "embedded", "name": "stm32-cube", "langs": ["c"], "tags": ["industrial"]},

        # Graphics/Game
        {"group": "graphics", "name": "opengl-raw", "langs": ["c", "glsl"], "tags": ["graphics", "low-level"]},
        {"group": "graphics", "name": "vulkan-engine", "langs": ["cpp", "spirv"], "tags": ["rendering", "next-gen"]},
        {"group": "graphics", "name": "raylib-game", "langs": ["c"], "tags": ["game-dev", "simple"]},
        {"group": "graphics", "name": "unity-3d", "langs": ["c#"], "tags": ["game-engine", "unity"]},

        # Docs
        {"group": "docs", "name": "latex-thesis", "langs": ["latex"], "tags": ["academic"]},
        {"group": "docs", "name": "mkdocs-material", "langs": ["markdown"], "tags": ["documentation"]}
    ]

    total_versions = 0
    for proj in project_types:
        # Generate 3 versions for each project
        versions = ["1.0.0", "1.1.0", "2.0.0"]
        
        for ver in versions:
            src_dir_name = f"{proj['group']}_{proj['name']}_{ver}"
            proj_path = base_path / src_dir_name
            proj_path.mkdir(parents=True)

            # Metadata
            metadata = {
                "name": proj["name"],
                "version": ver,
                "author": f"Panda {proj['group'].capitalize()} Team",
                "email": f"team-{proj['group']}@panda-library.org",
                "description": f"Standard {proj['name']} template for professional {proj['group']} projects. Version {ver}.",
                "languages": proj["langs"],
                "license": "MIT",
                "tags": proj["tags"] + ["official", "starter"],
                "variables": {
                    "project_name": f"Name for the {proj['name']} instance",
                    "author_name": "Primary developer name"
                },
                "hooks": [
                    f"echo 'Setting up {proj['name']} v{ver}...'"
                ],
                "ignore": [".git/", "node_modules/", "venv/", "build/", "dist/", "*.log", ".env"]
            }

            # Added date: spread out over time
            days_ago = total_versions * 2
            metadata["added_date"] = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")

            with open(proj_path / ".nptmpl", "w", encoding="utf-8") as f:
                yaml.dump(metadata, f, sort_keys=False)

            # Dummy files with placeholders
            (proj_path / "README.md").write_text(
                f"# {{{{ project_name }}}}\n"
                f"Version: {ver}\n"
                f"Author: {{{{ author_name }}}}\n"
                "Generated using nptmpl."
            )
            (proj_path / "config.json").write_text('{"version": "' + ver + '", "app": "{{ project_name }}"}')
            
            # Specific files based on group
            if proj["group"] == "web":
                file_name = "main.js" if "javascript" in proj["langs"] else "main.py"
                (proj_path / file_name).write_text("// {{ project_name }} initialization")
            elif proj["group"] == "cpp":
                (proj_path / "main.cpp").write_text("#include <iostream>\n// Author: {{ author_name }}\nint main() { return 0; }")
            elif proj["group"] == "rust":
                (proj_path / "Cargo.toml").write_text('[package]\nname = "{{ project_name }}"\nauthors = ["{{ author_name }}"]')
            
            total_versions += 1

    print(f"Generated {total_versions} realistic project templates in {base_path}")

if __name__ == "__main__":
    base = Path("tests/data/realistic_templates")
    generate_realistic_templates(base)
