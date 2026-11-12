"""Opt-in, non-executing collection of existing JUnit XML test report evidence.

Reports are NOT proof that an acceptance criterion is met. Without a reviewed
mapping to explicit criterion IDs and a matching revision, outputs remain
candidates, not verification nodes. We never execute source or test runners.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .core import AuditError, SCHEMA, now, validate_nodes

MAX_REPORTS = 60
MAX_BYTES = 4_000_000
MAX_CASES = 25000


def _report_paths(sources: list[str | Path]) -> list[Path]:
    found: dict[str, Path] = {}
    for source in sources:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise AuditError(f"JUnit source not found: {path}")
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = [f for f in path.rglob('*.xml') if f.is_file() and not f.is_symlink()]
        else:
            raise AuditError(f"Invalid JUnit source: {path}")
        for file in candidates:
            if file.is_symlink() or file.suffix.lower() != '.xml':
                raise AuditError(f"Expected non-symlink XML test report: {file}")
            found[str(file.resolve())] = file.resolve()
    if len(found) > MAX_REPORTS:
        raise AuditError(f"Too many JUnit XML files; maximum is {MAX_REPORTS}")
    return [found[k] for k in sorted(found)]


def _test_cases(path: Path) -> tuple[list[dict], str]:
    try:
        size = path.stat().st_size
        if size > MAX_BYTES:
            raise AuditError(f"JUnit report too large (>{MAX_BYTES} bytes): {path}")
        raw = path.read_bytes()
    except OSError as ex:
        raise AuditError(f"Cannot read JUnit XML report at {path}: {ex}") from ex
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', raw, flags=re.I):
        raise AuditError(f"DTD/entity declarations are not permitted in JUnit input: {path}")
    sha = hashlib.sha256(raw).hexdigest()
    try:
        tree = ET.fromstring(raw)
    except ET.ParseError as ex:
        raise AuditError(f"Malformed JUnit XML: {path}: {ex}") from ex
    tag = tree.tag.rsplit('}', 1)[-1]
    if tag not in {'testsuite', 'testsuites'}:
        raise AuditError(f"JUnit root must be testsuite or testsuites: {path}")
    tests = []
    for case in tree.iter():
        if case.tag.rsplit('}', 1)[-1] != 'testcase':
            continue
        name, classname = case.attrib.get('name', '').strip(), case.attrib.get('classname', '').strip()
        if not name or len(name) > 350 or len(classname) > 350:
            raise AuditError(f"JUnit test requires reasonable name/classname: {path}")
        names = [child.tag.rsplit('}', 1)[-1] for child in case]
        status = 'failed' if ('failure' in names or 'error' in names) else 'inconclusive' if 'skipped' in names else 'passed'
        key = f"{classname}::{name}" if classname else name
        tests.append({'key': key, 'result': status,
                      'report': str(path), 'sha256': sha,
                      'test_id': 'junit.' + hashlib.sha256((str(path) + '\0' + key).encode()).hexdigest()[:20]})
        if len(tests) > MAX_CASES:
            raise AuditError(f"JUnit report exceeds {MAX_CASES} cases")
    return tests, sha


def collect_junit(sources: list[str | Path], *, manifest_revision: str | None,
                  intent: dict, reviewed_mapping: dict | None = None) -> tuple[dict, dict]:
    """Return (candidate evidence inventory, curated verification-map).

    Mapping format: {"reviewed": true, "revision": "exact-SHA",
    "tests": [{"key":"module.Test::test_foo", "requirement_id":"REQ.foo",
               "criteria_ids":["AC.foo"]}]}
    This is a reviewer declaration, not a cryptographic attestation of test run provenance.
    """
    reqs = validate_nodes(intent, 'intent-map', 'intent')
    by_req = {r['id']: r for r in reqs}
    paths = _report_paths(sources)
    all_cases: list[dict] = []
    reports: list[dict] = []
    for file in paths:
        cases, sha = _test_cases(file)
        all_cases.extend(cases)
        if len(all_cases) > MAX_CASES:
            raise AuditError(f"Total JUnit tests exceed {MAX_CASES}")
        reports.append({'path': str(file), 'sha256': sha, 'cases': len(cases)})
    occurrences: dict[str, list[dict]] = {}
    for case in all_cases:
        occurrences.setdefault(case['key'], []).append(case)
    warnings = ["JUnit files are imported, never executed. Results alone do not establish accepted behavior or current-revision provenance."]
    verified_nodes = []
    mapping = reviewed_mapping
    if mapping is not None:
        if not isinstance(mapping, dict) or mapping.get('reviewed') is not True:
            raise AuditError('JUnit mappings require reviewed: true; no automatic identity guessing')
        if mapping.get('revision') != manifest_revision or not manifest_revision:
            raise AuditError('JUnit mapping revision must match the exact nonempty git HEAD of this audit')
        mappings = mapping.get('tests')
        if not isinstance(mappings, list):
            raise AuditError('JUnit mapping requires a tests array')
        seen = set()
        for entry in mappings:
            if not isinstance(entry, dict) or not isinstance(entry.get('key'), str):
                raise AuditError('JUnit mapping entry needs a test key')
            key = entry['key']
            if key in seen:
                raise AuditError(f'Duplicate reviewed test mapping: {key}')
            seen.add(key)
            req_id = entry.get('requirement_id')
            if req_id not in by_req:
                raise AuditError(f'JUnit mapping refers to unknown requirement: {req_id}')
            criteria_ids = entry.get('criteria_ids')
            known = {x['id'] for x in by_req[req_id].get('acceptance_criteria', [])}
            if not isinstance(criteria_ids, list) or not criteria_ids or any(x not in known for x in criteria_ids):
                raise AuditError(f'JUnit mapping requires known acceptance criterion IDs for {req_id}')
            if key not in occurrences:
                raise AuditError(f'Reviewed JUnit mapping test not found: {key}')
            if len(occurrences[key]) != 1:
                raise AuditError(f'Ambiguous JUnit test key in multiple reports: {key}')
            case = occurrences[key][0]
            verified_nodes.append({
                'id': 'verify.' + case['test_id'], 'map': 'verification', 'kind': 'test_observation',
                'title': key, 'requirement_id': req_id,
                'criteria_ids': sorted(set(criteria_ids)),
                'result': case['result'], 'revision': manifest_revision,
                'evidence': [f"JUnit XML {case['report']} sha256:{case['sha256'][:16]} testcase:{key}"],
                'provenance': 'user_reviewed_mapping_with_declared_revision',
            })
        warnings.append('Reviewed mapping asserts revision and criteria linkage; MirrorMap cannot independently attest when the JUnit suite ran or what assertions it contains.')
    out = {'schema_version': SCHEMA, 'collected_at': now(), 'reports': reports,
           'cases': all_cases, 'unique_keys': len(occurrences), 'mapped_cases': len(verified_nodes),
           'warnings': warnings, 'limits': {'max_reports': MAX_REPORTS, 'max_bytes_per_report': MAX_BYTES, 'max_cases': MAX_CASES}}
    verification = {'schema_version': SCHEMA, 'nodes': verified_nodes}
    validate_nodes(verification, 'verification-map', 'verification')
    return out, verification
