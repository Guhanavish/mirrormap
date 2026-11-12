"""MCP protocol, input, safety boundary, and all handler regression tests."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projectmirror.core import AuditError
from projectmirror import mcp

ROOT = Path(__file__).resolve().parents[1]


def rpc(method: str, params=None, mid=7):
    obj = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        obj["params"] = params
    return mcp.dispatch(obj)


def call(name: str, args=None, mid=7):
    return rpc("tools/call", {"name": name, "arguments": args if args is not None else {}}, mid)


class MCPProtocolTests(unittest.TestCase):
    def test_initialize(self):
        response = rpc("initialize", {"protocolVersion": mcp.PROTOCOL})
        self.assertEqual(response["result"]["protocolVersion"], mcp.PROTOCOL)
        self.assertEqual(response["result"]["serverInfo"]["name"], "mirrormap")
        self.assertEqual(response["id"], 7)

    def test_ping(self):
        self.assertEqual(rpc("ping")["result"], {})

    def test_list_includes_exact_allowlisted_tools_and_schemas(self):
        tools = rpc("tools/list")["result"]["tools"]
        self.assertEqual({t["name"] for t in tools},
                         {"mirrormap_doctor", "mirrormap_audit", "mirrormap_read_report"})
        self.assertTrue(all(t["inputSchema"]["additionalProperties"] is False for t in tools))
        self.assertEqual(next(t for t in tools if t["name"] == "mirrormap_audit")["inputSchema"]["required"], ["repo"])

    def test_doctor_does_not_need_repo_allowlist(self):
        with patch.dict(os.environ, {"MIRRORMAP_ALLOWED_ROOTS": ""}):
            answer = call("mirrormap_doctor")
        obj = json.loads(answer["result"]["content"][0]["text"])
        self.assertTrue(obj["checks"])

    def test_notification_is_silent(self):
        self.assertIsNone(mcp.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(mcp.dispatch({"jsonrpc": "2.0", "method": "unknown", "params": {}}))

    def test_invalid_request_objects(self):
        cases = [None, [], 2, {"jsonrpc": "1.0", "id": 9, "method": "ping"},
                 {"jsonrpc": "2.0", "id": True, "method": "ping"},
                 {"jsonrpc": "2.0", "id": [], "method": "ping"},
                 {"jsonrpc": "2.0", "id": 8}, {"jsonrpc": "2.0", "id": 9, "method": None}]
        for obj in cases:
            with self.subTest(obj=obj):
                self.assertEqual(mcp.dispatch(obj)["error"]["code"], -32600)

    def test_explicit_null_id_is_a_request(self):
        self.assertIn("result", mcp.dispatch({"jsonrpc": "2.0", "id": None, "method": "ping"}))

    def test_unknown_method(self):
        self.assertEqual(rpc("not/a/method")["error"]["code"], -32601)

    def test_malformed_call_params(self):
        for params in (None, "string", [], 4):
            with self.subTest(params=params):
                response = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params})
                self.assertEqual(response["error"]["code"], -32602)

    def test_unknown_tool_and_invalid_name(self):
        self.assertEqual(call("not-a-tool")["error"]["code"], -32602)
        self.assertEqual(rpc("tools/call", {"name": 123})["error"]["code"], -32602)

    def test_schema_validation_for_every_tool(self):
        cases = [
            ("mirrormap_doctor", {"repo": "/tmp"}),
            ("mirrormap_audit", {}),
            ("mirrormap_audit", {"repo": 13}),
            ("mirrormap_audit", {"repo": ""}),
            ("mirrormap_audit", {"repo": "/tmp", "mode": "unrecognized"}),
            ("mirrormap_audit", {"repo": "/tmp", "mode": 10}),
            ("mirrormap_audit", {"repo": "/tmp", "spec": 13}),
            ("mirrormap_audit", {"repo": "/tmp", "junit": {"path": "/tmp/xml"}}),
            ("mirrormap_audit", {"repo": "/tmp", "out": []}),
            ("mirrormap_audit", {"repo": "/tmp", "base": None}),
            ("mirrormap_audit", {"repo": "/tmp", "apply": True}),
            ("mirrormap_read_report", {}),
            ("mirrormap_read_report", {"out": ""}),
            ("mirrormap_read_report", {"out": "/tmp", "name": "../../etc/passwd"}),
            ("mirrormap_read_report", {"out": "/tmp", "name": 10}),
        ]
        for name, args in cases:
            with self.subTest(name=name, args=args):
                self.assertEqual(call(name, args)["error"]["code"], -32602)

    def test_serve_handles_parse_errors_oversize_and_notifications(self):
        cases = ['{broken json\n', 'x' * (mcp.MAX_MESSAGE_CHARS + 1) + '\n',
                 json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + '\n',
                 json.dumps({"jsonrpc": "2.0", "method": "ping", "id": 3}) + '\n']
        with patch('sys.stdin', io.StringIO(''.join(cases))), patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(mcp.serve(), 0)
            messages = [json.loads(s) for s in out.getvalue().splitlines()]
        self.assertEqual(len(messages), 3)
        self.assertEqual([x["error"]["code"] for x in messages[:2]], [-32700, -32600])
        self.assertEqual(messages[-1]["id"], 3)


class MCPSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.allowed = self.root / "approved"
        self.allowed.mkdir()
        self.repo = self.allowed / "app"
        self.repo.mkdir()
        (self.repo / "auth.py").write_text("def login():\n    return True\n", encoding="utf-8")
        self.spec = self.repo / "requirements.md"
        self.spec.write_text("- [REQ.auth.login] User login\n  - [AC.auth.login.valid] Login succeeds\n", encoding="utf-8")
        self.outside = self.root / "outside"
        self.outside.mkdir()
        self.report_dir = self.outside / "audit"
        env_patch = patch.dict(os.environ, {"MIRRORMAP_ALLOWED_ROOTS": str(self.allowed)})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def test_audit_is_read_only_and_reports_unknown(self):
        before = (self.repo / "auth.py").read_bytes()
        result = call("mirrormap_audit", {"repo": str(self.repo), "spec": str(self.spec),
                                          "mode": "deep", "out": str(self.report_dir)})
        self.assertNotIn("error", result)
        obj = json.loads(result["result"]["content"][0]["text"])
        self.assertEqual(obj["counts"], {"unknown": 1})
        self.assertTrue((self.report_dir / "dashboard.html").is_file())
        self.assertEqual(before, (self.repo / "auth.py").read_bytes())
        self.assertFalse((self.repo / "audit").exists())

    def test_reject_repo_outside_allowlist(self):
        result = call("mirrormap_audit", {"repo": str(self.outside)})
        self.assertTrue(result["result"]["isError"])
        self.assertIn("MIRRORMAP_ALLOWED_ROOTS", result["result"]["content"][0]["text"])

    def test_reject_empty_allowlist(self):
        with patch.dict(os.environ, {"MIRRORMAP_ALLOWED_ROOTS": ""}):
            result = call("mirrormap_audit", {"repo": str(self.repo)})
        self.assertTrue(result["result"]["isError"])

    def test_reject_spec_outside_allowlist(self):
        spec = self.outside / "spec.md"
        spec.write_text("- [REQ.thing] Thing\n")
        result = call("mirrormap_audit", {"repo": str(self.repo), "spec": str(spec)})
        self.assertTrue(result["result"]["isError"])

    def test_reject_junit_outside_allowlist(self):
        xml = self.outside / "results.xml"
        xml.write_text('<testsuite><testcase name="test" /></testsuite>')
        result = call("mirrormap_audit", {"repo": str(self.repo), "junit": str(xml)})
        self.assertTrue(result["result"]["isError"])

    def test_reject_output_inside_repo(self):
        result = call("mirrormap_audit", {"repo": str(self.repo), "out": str(self.repo / "reports")})
        self.assertTrue(result["result"]["isError"])
        self.assertFalse((self.repo / "reports").exists())

    def test_read_report_rejects_untrusted_manifest(self):
        self.report_dir.mkdir()
        (self.report_dir / "audit-manifest.json").write_text('{"project": {"repo": "' + str(self.outside) + '"}}')
        result = call("mirrormap_read_report", {"out": str(self.report_dir)})
        self.assertTrue(result["result"]["isError"])

    def test_read_report_valid_and_name_filter(self):
        self.test_audit_is_read_only_and_reports_unknown()
        for name in ["audit-report.md", "remediation-plan.md", "mindmap.mmd"]:
            with self.subTest(name=name):
                result = call("mirrormap_read_report", {"out": str(self.report_dir), "name": name})
                obj = json.loads(result["result"]["content"][0]["text"])
                self.assertTrue(obj["report"])
                self.assertFalse(obj["truncated"])

    def test_read_report_truncation_is_character_accurate(self):
        self.test_audit_is_read_only_and_reports_unknown()
        (self.report_dir / "audit-report.md").write_text("⚡" * (mcp.MAX_REPORT_CHARS + 3), encoding="utf-8")
        response = call("mirrormap_read_report", {"out": str(self.report_dir)})
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertTrue(content["truncated"])
        self.assertEqual(len(content["report"]), mcp.MAX_REPORT_CHARS)

    def test_read_report_refuses_symlink(self):
        self.test_audit_is_read_only_and_reports_unknown()
        link = self.report_dir / "audit-report.md"
        link.unlink()
        try:
            link.symlink_to(self.repo / "auth.py")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        response = call("mirrormap_read_report", {"out": str(self.report_dir)})
        self.assertTrue(response["result"]["isError"])
        self.assertIn("symlink", response["result"]["content"][0]["text"].lower())


if __name__ == "__main__":
    unittest.main()
