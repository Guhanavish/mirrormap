"""Conservative framework route inventories: non-executable and non-authoritative."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from projectmirror.core import index_repo
from projectmirror.frameworks import framework_route_candidates


class FrameworkInventoryTests(unittest.TestCase):
    def test_next_app_router_patterns(self):
        examples = {
            "app/page.tsx": ("/", "page"),
            "src/app/(dashboard)/users/[id]/page.tsx": ("/users/:id", "page"),
            "app/api/orders/[...item]/route.ts": ("/api/orders/:item+", "handler"),
            "pages/index.js": ("/", "page"),
            "src/pages/api/v1/[[...slug]].ts": ("/api/v1/:slug*", "handler"),
        }
        for path, (route, kind) in examples.items():
            with self.subTest(path=path):
                nodes = framework_route_candidates(Path(path), "export default function X() {}", "ev.code.sample")
                self.assertEqual(len(nodes), 1)
                self.assertEqual(nodes[0]["route_path"], route)
                self.assertEqual(nodes[0]["route_kind"], kind)
                self.assertIn("not verified", nodes[0]["warning"])

    def test_next_ignores_special_files_and_intercepting_routes(self):
        for filename in ("pages/_app.tsx", "app/page.test.tsx", "app/@modal/(.)photo/page.tsx", "app/loading.tsx", "lib/api.ts"):
            with self.subTest(path=filename):
                self.assertEqual(framework_route_candidates(Path(filename), "", "ev.1"), [])

    def test_fastapi_declaration_only(self):
        src = '''from fastapi import FastAPI, APIRouter
app = FastAPI()
router = APIRouter()
@app.get("/health")
def health(): return {"ok": True}
@router.post("/users/{user_id}")
async def update(user_id: str): return {"id": user_id}
'''
        nodes = framework_route_candidates(Path("api/server.py"), src, "ev.code.server")
        self.assertEqual(len(nodes), 2)
        self.assertEqual([n["http_method"] for n in nodes], ["get", "post"])
        self.assertEqual(nodes[0]["locator"], "api/server.py:4")
        self.assertTrue(all(n["framework"] == "fastapi_decorator" for n in nodes))

    def test_other_decorators_are_not_mistaken_for_fastapi(self):
        src = 'from mylib import Cache\ncache = Cache()\n@cache.get("/hello")\ndef value(): pass\n'
        self.assertEqual(framework_route_candidates(Path("main.py"), src, "ev.a"), [])

    def test_dynamic_path_is_not_guessed(self):
        src = 'from fastapi import FastAPI\napp = FastAPI()\n@app.get(f"/{name}")\ndef dynamic(): pass\n'
        self.assertEqual(framework_route_candidates(Path("main.py"), src, "ev.a"), [])

    def test_codebase_index_keeps_route_evidence_and_does_not_run_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "src" / "app" / "dashboard" / "page.tsx"
            path.parent.mkdir(parents=True)
            path.write_text('throw Error("This source must never execute");\n', encoding="utf-8")
            data, info = index_repo(root)
            self.assertEqual(info["route_candidates"], 1)
            route = next(node for node in data["nodes"] if node["kind"] == "route_candidate")
            self.assertEqual(route["route_path"], "/dashboard")
            self.assertIn(route["source_refs"][0], {e["id"] for e in data["evidence"]})

    def test_repository_showcase_has_expected_static_candidates(self):
        fixture = Path(__file__).resolve().parents[1] / "examples" / "routes-demo"
        index, stats = index_repo(fixture)
        routes = sorted(node["route_path"] for node in index["nodes"] if node["kind"] == "route_candidate")
        self.assertEqual(routes, ["/api/health", "/dashboard", "/status"])
        self.assertEqual(stats["route_candidates"], 3)

    def test_routes_cli_output_is_valid_json_and_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pages").mkdir()
            (root / "pages" / "index.tsx").write_text("export default function Home(){}", encoding="utf-8")
            cmd = [sys.executable, "-m", "projectmirror", "routes", str(root)]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["candidates"][0]["route_path"], "/")
            self.assertIn("not proof", result["warning"])


if __name__ == "__main__":
    unittest.main()
