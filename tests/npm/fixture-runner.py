"""Test-only interpreter bridge for npx -> Python installer E2E.

Injects synthetic pinned-source fixtures; NEVER used for production install.
The npm tarball contains the real production install.py, not this harness.
"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

if len(sys.argv)<2 or Path(sys.argv[1]).name!='install.py':
    raise SystemExit('fixture runner expects packaged install.py')
release=Path(sys.argv[1]).resolve().parent
source_tests=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(release))
sys.path.insert(1,str(source_tests))
import install
import test_install
blob, fake_skills, fake_helpers, _=test_install.make_fixture()
with TemporaryDirectory() as d:
    fake_zip=Path(d)/'superpowers-fixture.zip'
    fake_zip.write_bytes(blob)
    args=sys.argv[2:]+['--upstream-zip',str(fake_zip)]
    with patch.object(install,'EXPECTED_SKILLS',fake_skills), \
         patch.object(install,'EXPECTED_HELPERS',fake_helpers), \
         patch.object(install.architect,'load_package',return_value=test_install.make_arch_fixture()):
        raise SystemExit(install.main(args))
