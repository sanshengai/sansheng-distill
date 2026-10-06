"""Exercise the dispatch boundary: rejected jobs never reach the runner."""
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import run_book_wave as wave


def plan():
    return {'run_id': 'sample', 'book_contract': {'schema': 'book-wave-contract-v1',
            'book_facts': 'accept_as_source', 'review_mode': 'production_only', 'exceptions': []},
            'jobs': [{'job_id': 'ch01', 'book_id': 'book-a', 'operation': 'write',
                      'task': '根据本章来源写连续正文，保留关键案例。'}]}


class BookWaveTests(unittest.TestCase):
    def run_rejected(self, data):
        with tempfile.TemporaryDirectory() as d:
            manifest = Path(d) / 'input.json'
            manifest.write_text(json.dumps(data), encoding='utf-8')
            with patch.object(wave.subprocess, 'run') as runner:
                rc = wave.main(['--manifest', str(manifest), '--dry-run'])
                self.assertEqual(rc, 2)
                runner.assert_not_called()

    def test_empty_input_and_missing_contract_never_dispatch(self):
        for data in [{}, {'run_id': 'x', 'jobs': []}, dict(plan(), jobs=[])]:
            with self.subTest(data=data):
                self.run_rejected(data)

    def test_production_mode_rejects_content_review(self):
        data = plan(); data['jobs'][0]['operation'] = 'content_review'
        self.run_rejected(data)

    def test_review_requires_user_authorization(self):
        data = plan(); data['book_contract']['review_mode'] = 'requested_review'
        data['jobs'][0]['operation'] = 'content_review'
        self.run_rejected(data)
        data['book_contract']['review_authorization'] = '用户要求一次关键案例遗漏检查'
        self.assertEqual(len(wave.compile_manifest(data)['jobs']), 1)

    def test_external_check_rejects_unspecified_and_incomplete_exception(self):
        data = plan(); data['jobs'][0]['operation'] = 'external_check'
        self.run_rejected(data)
        data['jobs'][0]['exception_id'] = 'updated-guideline'
        data['book_contract']['exceptions'] = [{'id': 'updated-guideline', 'kind': 'dated_update',
            'claim': '原书明确提及的旧用品要求', 'source_location': '第3章，用品段',
            'change_reason': '发现当前标准已有修改', 'current_source': 'https://example.org/current-standard'}]
        self.assertEqual(len(wave.compile_manifest(data)['jobs']), 1)
        for field in ['claim', 'source_location', 'change_reason', 'current_source']:
            bad = copy.deepcopy(data); del bad['book_contract']['exceptions'][0][field]
            self.run_rejected(bad)

    def test_repair_requires_real_issue_and_duplicate_job_rejected(self):
        data = plan(); data['jobs'][0]['operation'] = 'targeted_repair'
        self.run_rejected(data)
        data['jobs'][0]['issue'] = '第2章JSON响应断尾，未形成正文'
        self.assertEqual(len(wave.compile_manifest(data)['jobs']), 1)
        data['jobs'].append(copy.deepcopy(data['jobs'][0]))
        self.run_rejected(data)

    def test_existing_runner_receives_constraints_and_hashes_match(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = Path(d) / 'input.json'; manifest.write_text(json.dumps(plan()), encoding='utf-8')
            output = Path(d) / 'results'; runner = Path(d) / 'fake_runner.py'
            runner.write_text('''import sys,json,hashlib
from pathlib import Path
args=sys.argv[1:]
def opt(k): return args[args.index(k)+1]
p=json.loads(Path(opt('--manifest')).read_text())
assert set(p)=={'run_id','jobs'}
assert set(p['jobs'][0])=={'job_id','task'}
assert '禁止内容审阅' in p['jobs'][0]['task']
assert '不得逐条查真假' in p['jobs'][0]['task']
o=Path(opt('--output-dir')); o.mkdir()
for j in p['jobs']:
 (o/(j['job_id']+'.meta.json')).write_text(json.dumps({'task_sha256':hashlib.sha256(j['task'].encode()).hexdigest()}))
''', encoding='utf-8')
            rc = wave.main(['--manifest', str(manifest), '--project-runner', str(runner),
                           '--output-dir', str(output), '--gateway', 'coding', '--model', 'chosen-model', '--max-workers', '2'])
            self.assertEqual(rc, 0)
            receipt = json.loads((output / 'book-wave-execution.json').read_text())
            meta = json.loads((output / 'ch01.meta.json').read_text())
            self.assertEqual(receipt['jobs'][0]['task_sha256'], meta['task_sha256'])
            self.assertEqual(receipt['manifest_sha256'], hashlib.sha256(manifest.read_bytes()).hexdigest())
            # Mutation on the actual invocation path, not just a helper assertion.
            data = plan(); data['jobs'][0]['operation'] = 'content_review'
            manifest.write_text(json.dumps(data))
            with patch.object(wave.subprocess, 'run') as network:
                self.assertEqual(wave.main(['--manifest', str(manifest), '--project-runner', str(runner),
                    '--output-dir', str(Path(d)/'mutated-results'), '--gateway', 'coding', '--model', 'chosen-model', '--max-workers', '2']), 2)
                network.assert_not_called()
                self.assertFalse((Path(d)/'mutated-results').exists())

    def test_explicit_provider_config_and_overwrite_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = Path(d) / 'input.json'; manifest.write_text(json.dumps(plan()))
            runner = Path(d) / 'runner.py'; runner.write_text('raise RuntimeError("must not run")')
            out = Path(d) / 'results'; out.mkdir()
            with patch.object(wave.subprocess, 'run') as network:
                self.assertEqual(wave.main(['--manifest', str(manifest), '--project-runner', str(runner), '--output-dir', str(out)]), 2)
                self.assertEqual(wave.main(['--manifest', str(manifest), '--project-runner', str(runner), '--output-dir', str(out),
                    '--gateway', 'coding', '--model', 'chosen-model', '--max-workers', '2']), 2)
                network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
