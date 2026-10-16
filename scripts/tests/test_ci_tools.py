"""Behavioral tests for documentation gates and disposable CI ownership."""
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_docs import check, heading_ids
from ci_backend import clean_environment, owned_clusters, private_directory, require_free_ports, validate_junit


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)

    def file(self, name, content, tracked=True):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        if tracked:
            subprocess.run(['git', '-C', str(self.root), 'add', '--', name], check=True, capture_output=True)
        return path

    def test_local_heading_and_directory_are_valid(self):
        self.file('guide/README.md', '# 运行说明\n\n## First step\n')
        self.file('README.md', '[guide](guide/README.md#first-step) [directory](guide/)')
        self.assertEqual(check(self.root), (2, []))

    def test_missing_file_and_heading_both_fail(self):
        self.file('guide.md', '# Guide\n')
        self.file('README.md', '[missing](absent.md) [heading](guide.md#missing)')
        _, errors = check(self.root)
        self.assertEqual(len(errors), 2)

    def test_untracked_ignored_and_external_local_paths_fail(self):
        self.file('.gitignore', 'private/\n')
        self.file('private/secret.md', 'synthetic data', tracked=False)
        self.file('draft.md', 'not shipped', tracked=False)
        self.file('README.md', '[private](private/secret.md) [draft](draft.md) [escape](../outside.md)')
        self.assertEqual(len(check(self.root)[1]), 3)

    def test_code_links_are_examples_and_archives_are_not_current_docs(self):
        self.file('openspec/changes/archive/old/validation.md', '[missing](private.md)')
        self.file('README.md', '```markdown\n[missing](missing.md)\n```\n`[inline](inline.md)`\n')
        self.assertEqual(check(self.root), (0, []))

    def test_image_and_reference_links_are_checked(self):
        self.file('image.png', 'synthetic image bytes')
        self.file('guide.md', '# 中文标题\n')
        self.file('README.md', '![image](image.png) [guide][usage]\n\n[usage]: guide.md#中文标题\n')
        self.assertEqual(check(self.root), (2, []))
        self.file('README.md', '![missing](absent.png)')
        self.assertEqual(len(check(self.root)[1]), 1)

    def test_unclosed_fence_and_undefined_reference_fail(self):
        self.file('README.md', '```python\nprint(1)')
        self.assertIn('unclosed', check(self.root)[1][0])
        self.file('README.md', '[guide][not-defined]')
        self.assertIn('undefined', check(self.root)[1][0])

    def test_headings_preserve_inline_code_but_ignore_fenced_examples(self):
        result = heading_ids('# Run `code`\n\n```markdown\n## Fake\n```\n\n## Repeat\n## Repeat\n')
        self.assertEqual(result, {'run-code', 'repeat', 'repeat-1'})


class BackendGateTests(unittest.TestCase):
    def test_report_cannot_hide_skips_errors_or_empty_results(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'tests.xml'
            for bad in ('<testsuite tests="0"/>',
                        '<testsuite><testcase><skipped/></testcase></testsuite>',
                        '<testsuite><testcase><failure/></testcase></testsuite>',
                        '<testsuite errors="1"><testcase/></testsuite>',
                        '<testsuite><error/></testsuite>'):
                with self.subTest(xml=bad):
                    report.write_text(bad, encoding='utf-8')
                    with self.assertRaises(RuntimeError):
                        validate_junit(report)
            report.write_text('<testsuite tests="1"><testcase name="real-test"/></testsuite>', encoding='utf-8')
            self.assertEqual(validate_junit(report), {'total': 1, 'failed': 0, 'skipped': 0})

    def test_occupied_port_is_preserved(self):
        with socket.socket() as owner:
            owner.bind(('127.0.0.1', 0))
            owner.listen()
            port = owner.getsockname()[1]
            with self.assertRaises(RuntimeError):
                require_free_ports((port,))
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass

    def test_inherited_database_and_application_settings_are_removed(self):
        source = {'PATH': 'runtime', 'PGPASSWORD': 'private', 'PGHOST': 'remote',
                  'SELFLORE_DATABASE_URL': 'production-placeholder', 'SELFLORE_ENV': 'prod'}
        result = clean_environment(source)
        self.assertFalse(any(k.startswith(('PG', 'SELFLORE_')) for k in result))
        self.assertEqual(source['SELFLORE_ENV'], 'prod')
        self.assertEqual(result['PATH'], 'runtime')

    def test_start_failure_stops_attempted_clusters_in_reverse_order(self):
        events = []

        class Fake:
            def __init__(self, port, fail=False):
                self.port, self.fail = port, fail

            def start(self):
                events.append(('start', self.port))
                if self.fail:
                    raise RuntimeError('synthetic start failure')

            def stop(self):
                events.append(('stop', self.port))

        with self.assertRaises(RuntimeError):
            with owned_clusters([Fake(6179), Fake(6180, fail=True)]):
                self.fail('body must not run')
        self.assertEqual(events, [('start', 6179), ('start', 6180), ('stop', 6180), ('stop', 6179)])

    def test_cleanup_attempts_all_instances_and_does_not_pass_on_failure(self):
        stopped = []

        class Fake:
            def __init__(self, port):
                self.port = port

            def start(self):
                pass

            def stop(self):
                stopped.append(self.port)
                if self.port == 6180:
                    raise OSError('synthetic cleanup failure')

        with self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
            with owned_clusters([Fake(6179), Fake(6180)]):
                pass
        self.assertEqual(stopped, [6180, 6179])

    def test_cache_cannot_escape_the_selected_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'repository'
            root.mkdir()
            outside = Path(folder) / 'outside'
            with self.assertRaises(RuntimeError):
                private_directory(outside, root)
            with self.assertRaises(RuntimeError):
                private_directory(root / '..' / 'outside', root)
            self.assertFalse(outside.exists())


if __name__ == '__main__':
    unittest.main()
