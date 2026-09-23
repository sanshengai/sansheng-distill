"""Exercise collect's real CLI; fixtures and prior outputs stay in system temp."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'deep_retell.py'


class CollectSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='retell-collect-')
        self.book = Path(self.temp.name) / 'book'
        self.raw = self.book / '_deepread'
        self.responses = self.raw / 'responses'
        self.responses.mkdir(parents=True)
        self.formal = self.book / 'deepread.json'
        self.prior = b'{"prior": "must survive"}\n'
        self.formal.write_bytes(self.prior)
        self.unit = {'no': 1, 'part': '章', 'title': '节', 'kind': 'narrative', 'text': '这是原文中的完整一段内容。'}
        self.section = {'title': '合法标题', 'paragraphs': ['这是转述中的完整一段内容。'], 'covers': ['P1'], 'quote': ''}
        self.dump(self.raw / 'units.json', [self.unit])
        self.dump(self.responses / 'u001.response.txt', {'sections': [self.section]})

    def tearDown(self):
        self.temp.cleanup()

    def dump(self, path, data):
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def cli(self):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), 'collect', str(self.book),
                               '--out-dir', str(self.responses), '--book', '测试书', '--author', '作者'],
                              capture_output=True, text=True)

    def rejected(self, expected):
        proc = self.cli()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(self.formal.read_bytes(), self.prior)
        diagnosis = json.loads((self.raw / 'collect-diagnostics.json').read_text())
        self.assertFalse(diagnosis['formal_output_replaced'])
        self.assertIn(expected, [x['code'] for x in diagnosis['issues']])
        self.assertEqual(list(self.book.glob('.collect-*.tmp')), [])

    def test_valid_string_is_one_paragraph_without_lost_characters(self):
        text = '完整单段字符串，不应该变成一行一个字。'
        self.section['paragraphs'] = text
        self.dump(self.responses / 'u001.response.txt', {'sections': [self.section]})
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(self.formal.read_text())
        self.assertEqual(output['units'][0]['sections'][0]['paragraphs'], [text])

    def test_bad_rewrite_response_falls_back_but_is_recorded(self):
        rw = self.raw / 'responses-rw'; rw.mkdir()
        (rw / 'u001.response.txt').write_text('{"sections": [坏掉的 JSON', encoding='utf-8')
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        diagnosis = json.loads((self.raw / 'collect-diagnostics.json').read_text())
        self.assertEqual([(w['code'], w['unit'], w['fell_back_to']) for w in diagnosis['warnings']],
                         [('rewrite_response_invalid', 1, 'responses')])
        self.assertIn('已退回上一轮 1 节', result.stdout)

    def test_thousands_space_is_not_unsupported_but_fabricated_number_is(self):
        self.unit['text'] = '当年员工增加到7 000人，土地储备6 202亩。'
        self.dump(self.raw / 'units.json', [self.unit])
        self.section['paragraphs'] = ['员工增加到7000人，土地储备6202亩，另有8000人待岗。']
        self.dump(self.responses / 'u001.response.txt', {'sections': [self.section]})
        self.assertEqual(self.cli().returncode, 0)
        check = json.loads(self.formal.read_text())['units'][0]['check']
        self.assertEqual(check['unsupported_numbers'], ['8000'])

    def test_missing_later_unit_preserves_all_prior_bytes(self):
        self.dump(self.raw / 'units.json', [self.unit, {**self.unit, 'no': 2}])
        self.rejected('missing_response')

    def test_bad_json_preserves_prior_bytes(self):
        (self.responses / 'u001.response.txt').write_text('not json')
        self.rejected('bad_json')

    def test_empty_or_malformed_or_duplicate_units(self):
        for data in ([], {}, [self.unit, self.unit], [{**self.unit, 'text': ''}]):
            with self.subTest(data=data):
                self.dump(self.raw / 'units.json', data)
                self.rejected('invalid_units')

    def test_empty_sections_and_nonobjects(self):
        for data in ({'sections': []}, {'sections': [None]}, {'sections': ['正文']}, []):
            with self.subTest(data=data):
                self.dump(self.responses / 'u001.response.txt', data)
                self.rejected('invalid_sections')

    def test_empty_or_object_or_fragmented_paragraphs(self):
        for paras in ([], '', '  ', [''], ['正文', None], {'text': '正文'}, [{'text': '正文'}], list('二十多个汉字被错误拆成单独的段落必须阻断处理过程')):
            with self.subTest(paras=paras):
                self.dump(self.responses / 'u001.response.txt', {'sections': [{**self.section, 'paragraphs': paras}]})
                self.rejected('invalid_sections')

    def test_metadata_and_unmerged_prose_are_not_silently_dropped(self):
        for sec in ({'skipped': [{'id': 'P1', 'why': '不适用'}]},
                    {**self.section, 'skipped': []}, {**self.section, 'paragraphs2': ['遗漏正文']}):
            with self.subTest(sec=sec):
                self.dump(self.responses / 'u001.response.txt', {'sections': [sec]})
                self.rejected('invalid_sections')

    def test_malformed_auxiliary_fields_preserve_output(self):
        for key, value in (('covers', 'P1'), ('covers', [{}]), ('quote', {}), ('keywords', [None])):
            self.dump(self.responses / 'u001.response.txt', {'sections': [{**self.section, key: value}]})
            self.rejected('invalid_sections')

    def test_failed_atomic_replace_keeps_prior_output(self):
        spec = importlib.util.spec_from_file_location('retell_collect_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.os, 'replace', side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):
                module._atomic_collect_json(str(self.formal), {'new': 'candidate'})
        self.assertEqual(self.formal.read_bytes(), self.prior)
        self.assertEqual(list(self.book.glob('.collect-*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
