# Local Release Scripts

## Usage

```bash
# Quick CI/CD setup check
./scripts/test_release_setup.sh

# Full local build and install test
./scripts/build-local.sh
```

| Aspect                | build-local.sh                                 | test_release_setup.sh                      |
|-----------------------|------------------------------------------------|--------------------------------------------|
| Purpose               | Full build of the package                      | CI/CD setup validation                     |
| What it does          | Builds wheel + sdist for upload                | Checks that configuration is correct        |
| Installs dependencies | ✅ Yes (`pip install build setuptools-scm`)     | ❌ No, assumes already present              |
| Runs python -m build  | ✅ Yes, real build                             | ✅ Yes, with PRETEND_VERSION                |
| Tests install         | ✅ Yes, in isolated venv                        | ❌ No, only checks wheel contents           |
| Import test           | ✅ Yes, imports and checks `__version__`        | ❌ No                                       |
| Output                | Ready-to-upload: `dist/*.whl` + `dist/*.tar.gz`| ✅ Confirms setup is OK                     |
| When to use           | Before manual release                          | Before git push (quick check)              |

- Use **test_release_setup.sh** for a quick pre-push or CI/CD check (validates config, build, wheel contents).
- Use **build-local.sh** for a full local build and install test (validates build, installs in venv, checks import).
