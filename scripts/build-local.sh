#!/bin/bash
# Local build and verification script for rag2f

set -e

echo "================================"
echo "Local Build Verification Script"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cleanup previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ src/*.egg-info/ src/**/_version.py

# Validate structure
echo ""
echo "✅ Validating project structure..."

if [ ! -d "src" ]; then
    echo -e "${RED}❌ ERROR: /src directory not found!${NC}"
    exit 1
fi
echo "  ✓ /src directory exists"

package_found=false
for dir in src/*/; do
    if [ -d "$dir" ] && [ -f "${dir}__init__.py" ]; then
        package_found=true
        echo "  ✓ Found package: $(basename "$dir")"
    fi
done

if [ -f "src/__init__.py" ]; then
    package_found=true
    echo "  ✓ src/ is also a package"
fi

if [ "$package_found" = false ]; then
    echo -e "${RED}❌ ERROR: No importable package found in /src${NC}"
    exit 1
fi

# Validate __init__.py in all packages
echo ""
echo "✅ Validating __init__.py in all packages..."

missing_init=()
while IFS= read -r -d '' dir; do
    if [ ! -f "$dir/__init__.py" ]; then
        missing_init+=("$dir")
    else
        echo "  ✓ $(echo "$dir" | sed 's|^src/||') has __init__.py"
    fi
done < <(find src -type d -exec sh -c '[ -n "$(find "$1" -maxdepth 1 -name "*.py" -print -quit)" ]' _ {} \; -print0)

if [ ${#missing_init[@]} -gt 0 ]; then
    echo -e "${RED}❌ ERROR: The following package directories are missing __init__.py:${NC}"
    printf '  - %s\n' "${missing_init[@]}"
    exit 1
fi

# Check pyproject.toml
echo ""
echo "✅ Validating pyproject.toml..."

if ! grep -q 'dynamic.*=.*\[.*"version".*\]' pyproject.toml; then
    echo -e "${RED}❌ ERROR: dynamic version not configured${NC}"
    exit 1
fi
echo "  ✓ Dynamic version configured"

if ! grep -q 'setuptools-scm' pyproject.toml; then
    echo -e "${RED}❌ ERROR: setuptools-scm not in build-system${NC}"
    exit 1
fi
echo "  ✓ setuptools-scm configured"

if ! grep -q 'local_scheme.*=.*"no-local-version"' pyproject.toml; then
    echo -e "${RED}❌ ERROR: local_scheme must be no-local-version${NC}"
    exit 1
fi
echo "  ✓ local_scheme validated"

# Install build dependencies
echo ""
echo "📦 Installing build dependencies..."
pip install -q --upgrade build "setuptools-scm[toml]>=8.0" wheel

# Build
echo ""
echo "🔨 Building package..."
python -m build

# Show what was built
echo ""
echo "📦 Build artifacts:"
ls -lh dist/

# Extract and show version
echo ""
echo "🔍 Extracting version information..."

# Unpack wheel to check version (force overwrite to avoid prompts)
pip install -q wheel
WHEEL_FILE=$(ls dist/*.whl | head -1)
unzip -oq "$WHEEL_FILE" -d /tmp/wheel_extract/ || true

if [ -f "/tmp/wheel_extract/rag2f/_version.py" ]; then
    echo "Version file contents:"
    cat /tmp/wheel_extract/rag2f/_version.py
    rm -rf /tmp/wheel_extract/
else
    echo -e "${YELLOW}⚠️  _version.py not found in wheel${NC}"
fi

# Test installation in a virtual environment
echo ""
echo "🧪 Testing installation in virtual environment..."

# Create temp venv
VENV_DIR=$(mktemp -d)
python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install the built wheel
pip install -q dist/*.whl

# Test import and version
echo ""
echo "📊 Import test results:"
python << EOF
try:
    import rag2f
    print(f"✅ Successfully imported rag2f")
    try:
        from rag2f._version import __version__, __commit__, __distance__
        print(f"Version: {__version__}")
        print(f"Commit: {__commit__}")
        print(f"Distance: {__distance__}")
    except ImportError:
        print(f"⚠️  Version info: {getattr(rag2f, '__version__', None)}")
        print(f"⚠️  Commit: {getattr(rag2f, '__commit__', None)}")
        print(f"⚠️  Distance: {getattr(rag2f, '__distance__', None)}")
    # Test plugin path function if exists
    if hasattr(rag2f, 'get_plugin_path'):
        path = rag2f.get_plugin_path()
        print(f"Plugin path function works: {path}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    exit(1)
EOF

TEST_RESULT=$?
deactivate
rm -rf "$VENV_DIR"

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Build verification successful!${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Review build artifacts in dist/"
    echo "  - Test manually: pip install dist/*.whl"
    echo "  - Push to dev branch for TestPyPI publication"
    echo "  - Create tag for PyPI publication"
else
    echo ""
    echo -e "${RED}❌ Build verification failed!${NC}"
    exit 1
fi