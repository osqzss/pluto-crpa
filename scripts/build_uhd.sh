#!/usr/bin/env bash
# Build UHD from source for the B206mini (needs UHD >= 4.9.0.0).
# Configure and build only, no sudo, no device access. Install steps are in
# docs/b206mini_check.md, Section 2.1 (run by the user).
#
# Installed in parallel to the Ubuntu UHD 4.6 packages, which stay because
# gnuradio (libgnuradio-uhd) depends on libuhd4.6.0t64. /usr/local comes
# first in PATH, in sys.path (dist-packages) and in the ld.so search path.
#
# Usage: scripts/build_uhd.sh [source dir, default ~/Work/uhd]
set -euo pipefail

SRC=${1:-$HOME/Work/uhd}
TAG=v4.10.0.0
BUILD=$SRC/host/build

cd "$SRC"
have=$(git describe --tags --exact-match 2>/dev/null || echo none)
if [ "$have" != "$TAG" ]; then
    echo "error: $SRC is at '$have', expected $TAG" >&2
    exit 1
fi
# UHDVersion.cmake treats a detached HEAD as a development branch (version
# 4.10.0.HEAD-...); only a branch named UHD-x.y is a release. Put the tag on
# a local branch of that name so the version reads 4.10.0.0-0-g<hash>.
BRANCH=UHD-$(sed -E 's/^v([0-9]+\.[0-9]+).*/\1/' <<<"$TAG")
git switch -q -C "$BRANCH" "$TAG"
echo "UHD source $SRC at $TAG on branch $BRANCH, commit $(git rev-parse HEAD)"

# Debian/Ubuntu: Python reads /usr/local/lib/python3.12/dist-packages, but
# UHD's default (posix_prefix) would install into .../site-packages, which is
# not on sys.path. Set it explicitly.
PYDIR=lib/python$(python3 -c 'import sys;print("%d.%d" % sys.version_info[:2])')/dist-packages

# v4.10.0.0, not v4.11.0.0: 4.11 needs gRPC and Protobuf for MPMD, and with
# MPMD off its Python module does not compile (lib/include missing from the
# pyuhd include path). 4.10 has B206mini support and the same B2xx images.
# Start from an empty build directory so no cached option survives.
rm -rf "$BUILD"
mkdir -p "$BUILD"
cd "$BUILD"
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DPYTHON_EXECUTABLE=/usr/bin/python3 \
    -DUHD_PYTHON_DIR="$PYDIR" \
    -DENABLE_PYTHON_API=ON \
    -DENABLE_B200=ON \
    -DENABLE_USB=ON \
    -DENABLE_EXAMPLES=ON \
    -DENABLE_UTILS=ON \
    -DENABLE_TESTS=ON \
    -DENABLE_MANUAL=OFF \
    -DENABLE_DOXYGEN=OFF \
    2>&1 | tee cmake.log

# The "enabled components" part of the configure summary must list these.
enabled=$(sed -n '/# UHD enabled components/,/# UHD disabled components/p' cmake.log)
for comp in "LibUHD - Python API" "USB" "B200"; do
    if ! grep -q -x -F -- "--   * $comp" <<<"$enabled"; then
        echo "error: component '$comp' not enabled, see $BUILD/cmake.log" >&2
        exit 1
    fi
done

# Full logs in the build directory; with pipefail a failing make stops here.
if ! make -j"$(nproc)" > make.log 2>&1; then
    echo "error: make failed, see $BUILD/make.log:" >&2
    grep -n -E "error|Error" make.log | head -20 >&2
    exit 1
fi
if ! make test > test.log 2>&1; then
    echo "error: unit tests failed, see $BUILD/test.log:" >&2
    tail -15 test.log >&2
    exit 1
fi
tail -3 test.log
echo "Build done in $BUILD. Install: docs/b206mini_check.md, Section 2.1."
