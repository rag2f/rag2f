#!/bin/bash
# Quick verification script for release automation setup

set -e

echo "🧪 Testing Release Automation Setup"
echo "===================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Check files exist
echo "1. Checking required files..."
files_to_check=(
    "NEXT_VERSION"
    ".github/workflows/ci-dev-testpypi.yml"
    ".github/workflows/release-tags.yml"
)

for file in "${files_to_check[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file MISSING"
        exit 1
    fi
done

# Check pyproject.toml configuration
echo ""
echo "2. Validating pyproject.toml..."

# Check dynamic version
if grep -q 'dynamic.*=.*\[.*"version".*\]' pyproject.toml; then
    echo -e "  ${GREEN}✓${NC} dynamic version configured"
else
    echo -e "  ${RED}✗${NC} dynamic version NOT configured"
    exit 1
fi

# Check setuptools-scm
if grep -q 'setuptools-scm' pyproject.toml; then
    echo -e "  ${GREEN}✓${NC} setuptools-scm in build-system"
else
    echo -e "  ${RED}✗${NC} setuptools-scm NOT in build-system"
    exit 1
fi

# Check local_scheme
if grep -q 'local_scheme.*=.*"no-local-version"' pyproject.toml; then
    echo -e "  ${GREEN}✓${NC} local_scheme = no-local-version"
else
    echo -e "  ${RED}✗${NC} local_scheme NOT configured"
    exit 1
fi

# Check src layout
if grep -q 'where.*=.*\[.*"src".*\]' pyproject.toml; then
    echo -e "  ${GREEN}✓${NC} src layout configured"
else
    echo -e "  ${RED}✗${NC} src layout NOT configured"
    exit 1
fi

# Check package structure
echo ""
echo "3. Validating package structure..."

if [ -d "src/rag2f" ]; then
    echo -e "  ${GREEN}✓${NC} Package directory exists"
else
    echo -e "  ${RED}✗${NC} Package directory NOT found"
    exit 1
fi

if [ -f "src/rag2f/__init__.py" ]; then
    echo -e "  ${GREEN}✓${NC} Package __init__.py exists"
else
    echo -e "  ${RED}✗${NC} Package __init__.py NOT found"
    exit 1
fi

# Validate __init__.py in all packages (IMPORTANT CHECK)
echo ""
echo "4. Validating __init__.py in all packages..."

missing_init=()
while IFS= read -r -d '' dir; do
    if [ ! -f "$dir/__init__.py" ]; then
        missing_init+=("$dir")
    else
        echo -e "  ${GREEN}✓${NC} $(echo "$dir" | sed 's|^src/||') has __init__.py"
    fi
done < <(find src -type d -exec sh -c '[ -n "$(find "$1" -maxdepth 1 -name "*.py" -print -quit)" ]' _ {} \; -print0)

if [ ${#missing_init[@]} -gt 0 ]; then
    echo -e "  ${RED}✗${NC} Missing __init__.py in:"
    printf '    - %s\n' "${missing_init[@]}"
    exit 1
fi

# Check version imports in __init__.py
if grep -q "__version__" "src/rag2f/__init__.py"; then
    echo -e "  ${GREEN}✓${NC} Version exports in __init__.py"
else
    echo -e "  ${RED}✗${NC} Version exports NOT in __init__.py"
    exit 1
fi

# Test setuptools-scm
echo ""
echo "5. Testing setuptools-scm..."

if command -v python3 &> /dev/null; then
    VERSION=$(python3 -m setuptools_scm 2>&1 || echo "ERROR")
    if [ "$VERSION" != "ERROR" ]; then
        echo -e "  ${GREEN}✓${NC} setuptools-scm works: $VERSION"
    else
        echo -e "  ${RED}✗${NC} setuptools-scm failed"
        exit 1
    fi
else
    echo "  ⚠️  Python not found, skipping"
fi

# Test build
echo ""
echo "6. Testing package build..."

if [ -d "dist" ]; then
    rm -rf dist/
fi

export SETUPTOOLS_SCM_PRETEND_VERSION_FOR_RAG2F=0.1.0.dev999
python3 -m build > /dev/null 2>&1 || {
    echo -e "  ${RED}✗${NC} Build failed"
    exit 1
}

if [ -f "dist/"*.whl ] && [ -f "dist/"*.tar.gz ]; then
    echo -e "  ${GREEN}✓${NC} Build successful"
    ls -lh dist/
else
    echo -e "  ${RED}✗${NC} Build artifacts missing"
    exit 1
fi

# Check wheel contents
echo ""
echo "7. Verifying wheel contents..."

WHEEL=$(ls dist/*.whl)
CONTENTS=$(python3 -m zipfile -l "$WHEEL" | grep "rag2f/")

if echo "$CONTENTS" | grep -q "__init__.py"; then
    echo -e "  ${GREEN}✓${NC} __init__.py in wheel"
else
    echo -e "  ${RED}✗${NC} __init__.py NOT in wheel"
    exit 1
fi

if echo "$CONTENTS" | grep -q "_version.py"; then
    echo -e "  ${GREEN}✓${NC} _version.py in wheel"
else
    echo -e "  ${RED}✗${NC} _version.py NOT in wheel"
    exit 1
fi

# Optionally check for a core file
if echo "$CONTENTS" | grep -q "core/"; then
    echo -e "  ${GREEN}✓${NC} core/ in wheel"
else
    echo -e "  ${YELLOW}⚠️  core/ NOT in wheel (optional)${NC}"
fi

# Summary
echo ""
echo "===================================="
echo -e "${GREEN}✅ All checks passed!${NC}"
echo ""
echo "Next steps:"
echo "  1. Configure GitHub secrets (TESTPYPI_API_TOKEN, PYPI_API_TOKEN)"
echo "  2. Push to dev branch to test TestPyPI workflow"
echo "  3. Create tag (e.g., v0.1.0rc1) to test PyPI workflow"
echo ""