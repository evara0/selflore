import hashlib
import hmac
import importlib.util
import pathlib
import unittest
from unittest.mock import MagicMock

spec = importlib.util.spec_from_file_location('browser_reset', pathlib.Path(__file__).parents[1] / 'reset_browser_registration.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TARGET = dict(host='127.0.0.1', port='6179', dbname='selflore_dev', user='selflore_dev_app')


class BrowserRegistrationTests(unittest.TestCase):
    def test_requires_explicit_isolation_and_dsn(self):
        for env in ({}, {'SELFLORE_TEST_ISOLATED': '1'}, {'SELFLORE_TEST_APP_DSN': 'test'}):
            with self.subTest(env=env), self.assertRaises(RuntimeError):
                module.reset(env, parse=MagicMock(), connect=MagicMock())

    def test_rejects_other_targets_and_connection_overrides(self):
        for key, value in [('host', 'localhost'), ('port', '6171'), ('dbname', 'selflore_prod'),
                           ('user', 'postgres'), ('hostaddr', '192.0.2.1'), ('service', 'other'),
                           ('options', '-c role=postgres')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                module.checked_target({**TARGET, key: value})

    def test_only_deletes_the_loopback_registration_bucket(self):
        connection = MagicMock()
        db = connection.return_value.__enter__.return_value
        db.execute.return_value.fetchone.return_value = ('selflore_dev', 'selflore_dev_app')
        env = dict(SELFLORE_TEST_ISOLATED='1', SELFLORE_TEST_APP_DSN='synthetic', SELFLORE_THROTTLE_KEY='synthetic-key')
        module.reset(env, parse=lambda _: TARGET, connect=connection)
        self.assertEqual(db.execute.call_count, 2)
        key = hmac.new(b'synthetic-key', b'register-ip:127.0.0.1', hashlib.sha256).hexdigest()
        db.execute.assert_called_with('DELETE FROM app.auth_login_throttle WHERE bucket_key = %s', (key,))
        self.assertEqual(connection.call_args.kwargs['passfile'], module.os.devnull)

    def test_identity_mismatch_prevents_delete(self):
        connection = MagicMock()
        db = connection.return_value.__enter__.return_value
        db.execute.return_value.fetchone.return_value = ('selflore_prod', 'selflore_prod_app')
        with self.assertRaises(RuntimeError):
            module.reset(dict(SELFLORE_TEST_ISOLATED='1', SELFLORE_TEST_APP_DSN='synthetic'),
                         parse=lambda _: TARGET, connect=connection)
        self.assertEqual(db.execute.call_count, 1)
