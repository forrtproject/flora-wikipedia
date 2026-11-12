"""Shared review store (issue #10): build config and the Supabase schema."""
import pathlib
import shutil
import subprocess
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent  # editing-support/
sys.path.insert(0, str(ROOT))

import build_site  # noqa: E402

SUPA = ROOT / 'supabase'


class StoreConfig(unittest.TestCase):
    def test_local_only_without_values(self):
        with mock.patch.dict('os.environ', {}, clear=True), mock.patch.object(build_site, 'STORE_ENV', ROOT / 'missing.env'):
            self.assertIn('window.FLORA_STORE = null;', build_site.store_config())

    def test_values_from_private_file_and_env(self):
        env = SUPA / 'tmp-test.env'
        env.write_text('# comment\nFLORA_SUPABASE_URL="https://abc.supabase.co"\nFLORA_SUPABASE_ANON_KEY=sb_publishable_file\n')
        try:
            with mock.patch.dict('os.environ', {'FLORA_SUPABASE_ANON_KEY': 'sb_publishable_env'}, clear=True), \
                    mock.patch.object(build_site, 'STORE_ENV', env):
                cfg = build_site.store_config()
        finally:
            env.unlink()
        self.assertIn('"url": "https://abc.supabase.co"', cfg)
        self.assertIn('"anonKey": "sb_publishable_env"', cfg)  # the environment wins over the file

    def test_no_keys_in_repository_site(self):
        self.assertFalse((ROOT / 'site' / 'config.js').exists(), 'config.js is generated at build time, not committed')


@unittest.skipUnless(shutil.which('node') and (SUPA / 'node_modules' / '@electric-sql' / 'pglite').exists(),
                     'PGlite not installed (cd editing-support/supabase && npm i --no-save @electric-sql/pglite)')
class Schema(unittest.TestCase):
    def test_schema_on_pglite(self):
        r = subprocess.run(['node', 'test_schema.mjs'], cwd=SUPA, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)


if __name__ == '__main__':
    unittest.main()
