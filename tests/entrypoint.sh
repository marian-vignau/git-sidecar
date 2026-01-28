#!/bin/bash
# Entrypoint script for E2E testing Docker container

set -euo pipefail

echo "=========================================="
echo "GitSidecar E2E Testing Container"
echo "=========================================="
echo ""

# Check if /workspace is mounted
if [ ! -d "/workspace" ]; then
    echo "ERROR: /workspace directory not found!"
    echo "Please mount the project directory when running the container:"
    echo "  docker run -v \$(pwd):/workspace -it <image-name>"
    echo ""
    echo "Dropping to shell for debugging..."
    exec /bin/bash
fi

# Verify workspace contains project files
if [ ! -f "/workspace/main.py" ] || [ ! -f "/workspace/pyproject.toml" ]; then
    echo "ERROR: /workspace does not appear to contain GitSidecar project files!"
    echo "Expected files: main.py, pyproject.toml"
    echo ""
    echo "Dropping to shell for debugging..."
    exec /bin/bash
fi

# Run the test script
echo "Running E2E tests..."
echo ""

if /test-e2e.sh; then
    echo ""
    echo "=========================================="
    echo "All tests PASSED!"
    echo "=========================================="
    exit 0
else
    TEST_EXIT_CODE=$?
    echo ""
    echo "=========================================="
    echo "Tests FAILED (exit code: $TEST_EXIT_CODE)"
    echo "=========================================="
    echo ""
    echo "Dropping to interactive shell for debugging..."
    echo "You can:"
    echo "  - Inspect the test repositories in /test-repos/"
    echo "  - Check ticket directories in ~/tickets/"
    echo "  - Run 'sidecar config --view' to see configuration"
    echo "  - Manually run test commands to debug"
    echo ""
    echo "Type 'exit' when done debugging."
    echo ""
    exec /bin/bash
fi
