from kagent.agent.symbol_index import build_symbol_index, find_symbols


def test_build_symbol_index_extracts_python_symbols(tmp_path):
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text(
        "\n".join(
            [
                "import os",
                "from pathlib import Path",
                "",
                "class Runner:",
                "    def run(self):",
                "        pass",
                "",
                "async def load():",
                "    return Path('.')",
            ]
        ),
        encoding="utf-8",
    )

    symbols = build_symbol_index(tmp_path)
    by_name = {(symbol.name, symbol.kind): symbol for symbol in symbols}

    assert by_name[("Runner", "class")].line == 4
    assert by_name[("run", "method")].container == "Runner"
    assert by_name[("load", "function")].line == 8
    assert by_name[("os", "import")].module == "os"
    assert by_name[("Path", "import")].module == "pathlib"


def test_find_symbols_exact_and_fuzzy(tmp_path):
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text(
        "def manage_context(): pass\nclass ContextManager: pass\n",
        encoding="utf-8",
    )

    exact = find_symbols(tmp_path, "manage_context")
    fuzzy = find_symbols(tmp_path, "Context", exact=False)

    assert exact[0]["name"] == "manage_context"
    assert {item["name"] for item in fuzzy} == {"manage_context", "ContextManager"}


def test_find_symbols_filters_kind(tmp_path):
    package = tmp_path / "kagent"
    package.mkdir()
    (package / "module.py").write_text(
        "class Service: pass\ndef Service(): pass\n",
        encoding="utf-8",
    )

    matches = find_symbols(tmp_path, "Service", kind="class")

    assert len(matches) == 1
    assert matches[0]["kind"] == "class"


def test_build_symbol_index_extracts_javascript_and_typescript_symbols(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.ts").write_text(
        "\n".join(
            [
                "import { createRoot } from 'react-dom/client';",
                "export interface AppProps { title: string }",
                "export type Route = string;",
                "export class AppShell {}",
                "export function renderApp() {}",
                "export const loadData = async () => true;",
            ]
        ),
        encoding="utf-8",
    )

    symbols = build_symbol_index(tmp_path)
    by_name = {(symbol.name, symbol.kind): symbol for symbol in symbols}

    assert by_name[("client", "import")].module == "react-dom/client"
    assert by_name[("AppProps", "interface")].line == 2
    assert by_name[("Route", "type")].line == 3
    assert by_name[("AppShell", "class")].line == 4
    assert by_name[("renderApp", "function")].line == 5
    assert by_name[("loadData", "function")].line == 6


def test_build_symbol_index_extracts_go_rust_and_java_symbols(tmp_path):
    go_dir = tmp_path / "goapp"
    rust_dir = tmp_path / "rustapp" / "src"
    java_dir = tmp_path / "javaapp"
    go_dir.mkdir()
    rust_dir.mkdir(parents=True)
    java_dir.mkdir()
    (go_dir / "service.go").write_text(
        "\n".join(
            [
                'import "fmt"',
                "type Server struct {}",
                "func NewServer() *Server { return nil }",
                "func (s *Server) Start() {}",
            ]
        ),
        encoding="utf-8",
    )
    (rust_dir / "lib.rs").write_text(
        "\n".join(
            [
                "use crate::config::Config;",
                "pub struct Runner;",
                "pub enum Mode { Fast }",
                "pub fn run() {}",
            ]
        ),
        encoding="utf-8",
    )
    (java_dir / "Service.java").write_text(
        "\n".join(
            [
                "import java.util.List;",
                "public class Service {",
                "  public void start() {}",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    symbols = build_symbol_index(tmp_path)
    by_name = {(symbol.name, symbol.kind): symbol for symbol in symbols}

    assert by_name[("fmt", "import")].module == "fmt"
    assert by_name[("Server", "struct")].line == 2
    assert by_name[("NewServer", "function")].line == 3
    assert by_name[("Start", "method")].line == 4
    assert by_name[("Config", "import")].module == "crate::config::Config"
    assert by_name[("Runner", "struct")].line == 2
    assert by_name[("Mode", "enum")].line == 3
    assert by_name[("run", "function")].line == 4
    assert by_name[("List", "import")].module == "java.util.List"
    assert by_name[("Service", "class")].line == 2
    assert by_name[("start", "method")].line == 3
