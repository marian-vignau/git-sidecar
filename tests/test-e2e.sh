#!/bin/bash
# E2E Test Script for GitSidecar
# Tests all main features with two repositories

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test tracking
FAILURES=()
PASSED=0
FAILED=0

# Directories
REPO_A_DIR="/test-repos/repo-a"
REPO_B_DIR="/test-repos/repo-b"
TOOLS_DIR="/test-tools"
WORKSPACE_BASE="$HOME/tickets"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

assert() {
    if ! eval "$1"; then
        log_error "Assertion failed: $1"
        FAILURES+=("$2")
        ((FAILED++)) || true
        return 1
    else
        ((PASSED++)) || true
        return 0
    fi
}

# Setup functions
setup_tools_library() {
    log_info "Setting up tools library..."
    mkdir -p "$TOOLS_DIR"/{notebooks,scripts,utils}
    echo "# Notebooks" > "$TOOLS_DIR/notebooks/README.md"
    echo "# Scripts" > "$TOOLS_DIR/scripts/README.md"
    echo "# Utils" > "$TOOLS_DIR/utils/README.md"
}

install_gitsidecar() {
    log_info "Installing GitSidecar from /workspace..."
    if [ ! -d "/workspace" ]; then
        log_error "/workspace directory not found. Make sure to mount the project directory."
        exit 1
    fi
    
    cd /workspace
    uv tool install /workspace || {
        log_error "Failed to install GitSidecar"
        exit 1
    }
    
    # Verify installation
    if ! command -v sidecar &> /dev/null; then
        log_error "sidecar command not found after installation"
        exit 1
    fi
    
    log_info "GitSidecar installed successfully"
    
    # Configure defaults
    sidecar config --set paths workspace_base "$WORKSPACE_BASE" --default || true
    sidecar config --set paths tools_library_path "$TOOLS_DIR" --default || true
    sidecar config --set links current_ticket_link_locations "$HOME/Downloads" --default || true
}

setup_repo_a() {
    log_info "Setting up Repo A..."
    mkdir -p "$REPO_A_DIR"
    cd "$REPO_A_DIR"
    
    git init
    git config user.name "Test User"
    git config user.email "test@example.com"
    
    # Create initial commit
    echo "# Repo A" > README.md
    git add README.md
    git commit -m "Initial commit"
    
    # Create main and develop branches
    git checkout -b main
    git checkout -b develop
    
    log_info "Repo A initialized"
}

setup_repo_b() {
    log_info "Setting up Repo B..."
    mkdir -p "$REPO_B_DIR"
    cd "$REPO_B_DIR"
    
    git init
    git config user.name "Test User"
    git config user.email "test@example.com"
    
    # Create initial commit
    echo "# Repo B" > README.md
    git add README.md
    git commit -m "Initial commit"
    
    # Create main and develop branches
    git checkout -b main
    git checkout -b develop
    
    log_info "Repo B initialized"
}

get_repo_id() {
    local repo_dir="$1"
    cd "$repo_dir"
    # Get repo ID by running sidecar config --view and extracting it
    # For local repos, it will be local/repo-name-<hash>
    sidecar config --view 2>/dev/null | grep -i "repo:" | head -1 | awk '{print $2}' || echo ""
}

install_hook_repo_a() {
    log_info "Installing hook in Repo A..."
    cd "$REPO_A_DIR"
    
    # Get repo ID first
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    if [ -z "$repo_id" ]; then
        # Try to detect it by installing hook (which will detect it)
        echo "n" | sidecar hook install || true
        repo_id=$(get_repo_id "$REPO_A_DIR")
    fi
    
    if [ -n "$repo_id" ]; then
        # Configure ticket pattern for Repo A
        sidecar config --set ticket_pattern prefix_pattern "[A-Z]{2,5}" --repo "$repo_id" || true
        log_info "Configured Repo A with pattern [A-Z]{2,5}, repo_id: $repo_id"
    fi
    
    # Install hook non-interactively
    echo "n" | sidecar hook install || {
        log_error "Failed to install hook in Repo A"
        return 1
    }
    
    assert "[ -f .git/hooks/post-checkout ]" "Repo A hook file exists"
    assert "[ -x .git/hooks/post-checkout ]" "Repo A hook is executable"
}

install_hook_repo_b() {
    log_info "Installing hook in Repo B..."
    cd "$REPO_B_DIR"
    
    # Get repo ID
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    if [ -z "$repo_id" ]; then
        echo "n" | sidecar hook install || true
        repo_id=$(get_repo_id "$REPO_B_DIR")
    fi
    
    log_info "Repo B using default pattern, repo_id: $repo_id"
    
    # Install hook non-interactively (uses default pattern)
    echo "n" | sidecar hook install || {
        log_error "Failed to install hook in Repo B"
        return 1
    }
    
    assert "[ -f .git/hooks/post-checkout ]" "Repo B hook file exists"
    assert "[ -x .git/hooks/post-checkout ]" "Repo B hook is executable"
}

# Test functions for Repo A
test_repo_a_setup() {
    log_test "Testing Repo A setup..."
    cd "$REPO_A_DIR"
    
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    assert "[ -n \"$repo_id\" ]" "Repo A ID detected"
    assert "echo \"$repo_id\" | grep -q '^local/repo-a'" "Repo A has local/ prefix"
    
    log_info "Repo A ID: $repo_id"
}

test_repo_a_first_ticket() {
    log_test "Testing Repo A: Create first ticket branch (JIRA-123-first-feature)..."
    cd "$REPO_A_DIR"
    git checkout develop
    git checkout -b JIRA-123-first-feature
    
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    local ticket_dir="$WORKSPACE_BASE/$repo_id/JIRA-123-first-feature"
    
    # Wait a moment for hook to execute
    sleep 1
    
    assert "[ -d \"$ticket_dir\" ]" "Repo A first ticket directory created"
    assert "[ -L \"$HOME/Downloads/CurrentTicket\" ]" "CurrentTicket symlink exists"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$ticket_dir\" ]" "CurrentTicket symlink points to correct directory"
    
    # Check tool symlinks (may not exist if tools library setup failed, so make it non-fatal)
    if [ -d "$TOOLS_DIR/notebooks" ]; then
        assert "[ -L \"$ticket_dir/notebooks\" ]" "Notebooks symlink exists"
    fi
}

test_repo_a_switch_branch() {
    log_test "Testing Repo A: Switch to another branch (JIRA-456-second-feature)..."
    cd "$REPO_A_DIR"
    git checkout -b JIRA-456-second-feature
    
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    local new_ticket_dir="$WORKSPACE_BASE/$repo_id/JIRA-456-second-feature"
    local old_ticket_dir="$WORKSPACE_BASE/$repo_id/JIRA-123-first-feature"
    
    sleep 1
    
    assert "[ -d \"$new_ticket_dir\" ]" "Repo A second ticket directory created"
    assert "[ -d \"$old_ticket_dir\" ]" "Repo A first ticket directory still exists"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$new_ticket_dir\" ]" "CurrentTicket symlink updated to new directory"
}

test_repo_a_same_ticket_reuse() {
    log_test "Testing Repo A: Create branch with same ticket number (JIRA-123-different-description)..."
    cd "$REPO_A_DIR"
    git checkout -b JIRA-123-different-description
    
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    local reused_dir="$WORKSPACE_BASE/$repo_id/JIRA-123-first-feature"
    local new_dir="$WORKSPACE_BASE/$repo_id/JIRA-123-different-description"
    
    sleep 1
    
    # Should reuse the existing directory, not create a new one
    assert "[ -d \"$reused_dir\" ]" "Repo A reused ticket directory exists"
    assert "[ ! -d \"$new_dir\" ]" "Repo A did not create duplicate directory"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$reused_dir\" ]" "CurrentTicket symlink points to reused directory"
}

test_repo_a_standard_branches() {
    log_test "Testing Repo A: Switch to standard branches (develop, main)..."
    cd "$REPO_A_DIR"
    
    # Count directories before
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    local before_count=$(find "$WORKSPACE_BASE/$repo_id" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    
    # Switch to develop
    git checkout develop
    sleep 1
    
    local after_develop_count=$(find "$WORKSPACE_BASE/$repo_id" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    assert "[ \"$after_develop_count\" = \"$before_count\" ]" "No new directory created when switching to develop"
    
    # Switch to main
    git checkout main
    sleep 1
    
    local after_main_count=$(find "$WORKSPACE_BASE/$repo_id" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    assert "[ \"$after_main_count\" = \"$before_count\" ]" "No new directory created when switching to main"
}

test_repo_a_return_to_ticket() {
    log_test "Testing Repo A: Return to ticket branch..."
    cd "$REPO_A_DIR"
    git checkout JIRA-123-first-feature
    
    local repo_id=$(get_repo_id "$REPO_A_DIR")
    local ticket_dir="$WORKSPACE_BASE/$repo_id/JIRA-123-first-feature"
    
    sleep 1
    
    assert "[ -d \"$ticket_dir\" ]" "Repo A ticket directory still exists"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$ticket_dir\" ]" "CurrentTicket symlink points to correct directory"
}

# Test functions for Repo B
test_repo_b_setup() {
    log_test "Testing Repo B setup..."
    cd "$REPO_B_DIR"
    
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    assert "[ -n \"$repo_id\" ]" "Repo B ID detected"
    assert "echo \"$repo_id\" | grep -q '^local/repo-b'" "Repo B has local/ prefix"
    
    log_info "Repo B ID: $repo_id"
}

test_repo_b_first_ticket() {
    log_test "Testing Repo B: Create first ticket branch (TICKET-789-feature-one)..."
    cd "$REPO_B_DIR"
    git checkout develop
    git checkout -b TICKET-789-feature-one
    
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    local ticket_dir="$WORKSPACE_BASE/$repo_id/TICKET-789-feature-one"
    
    sleep 1
    
    assert "[ -d \"$ticket_dir\" ]" "Repo B first ticket directory created"
    assert "[ -L \"$HOME/Downloads/CurrentTicket\" ]" "CurrentTicket symlink exists"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$ticket_dir\" ]" "CurrentTicket symlink points to correct directory"
}

test_repo_b_switch_branch() {
    log_test "Testing Repo B: Switch to another branch (TICKET-101-feature-two)..."
    cd "$REPO_B_DIR"
    git checkout -b TICKET-101-feature-two
    
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    local new_ticket_dir="$WORKSPACE_BASE/$repo_id/TICKET-101-feature-two"
    local old_ticket_dir="$WORKSPACE_BASE/$repo_id/TICKET-789-feature-one"
    
    sleep 1
    
    assert "[ -d \"$new_ticket_dir\" ]" "Repo B second ticket directory created"
    assert "[ -d \"$old_ticket_dir\" ]" "Repo B first ticket directory still exists"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$new_ticket_dir\" ]" "CurrentTicket symlink updated to new directory"
}

test_repo_b_same_ticket_reuse() {
    log_test "Testing Repo B: Create branch with same ticket number (TICKET-789-another-desc)..."
    cd "$REPO_B_DIR"
    git checkout -b TICKET-789-another-desc
    
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    local reused_dir="$WORKSPACE_BASE/$repo_id/TICKET-789-feature-one"
    local new_dir="$WORKSPACE_BASE/$repo_id/TICKET-789-another-desc"
    
    sleep 1
    
    # Should reuse the existing directory
    assert "[ -d \"$reused_dir\" ]" "Repo B reused ticket directory exists"
    assert "[ ! -d \"$new_dir\" ]" "Repo B did not create duplicate directory"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$reused_dir\" ]" "CurrentTicket symlink points to reused directory"
}

test_repo_b_standard_branches() {
    log_test "Testing Repo B: Switch to standard branches (develop, main)..."
    cd "$REPO_B_DIR"
    
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    local before_count=$(find "$WORKSPACE_BASE/$repo_id" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    
    git checkout develop
    sleep 1
    
    local after_develop_count=$(find "$WORKSPACE_BASE/$repo_id" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    assert "[ \"$after_develop_count\" = \"$before_count\" ]" "No new directory created when switching to develop"
    
    git checkout main
    sleep 1
    
    local after_main_count=$(find "$WORKSPACE_BASE/$repo_id" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    assert "[ \"$after_main_count\" = \"$before_count\" ]" "No new directory created when switching to main"
}

test_repo_b_return_to_ticket() {
    log_test "Testing Repo B: Return to ticket branch..."
    cd "$REPO_B_DIR"
    git checkout TICKET-789-feature-one
    
    local repo_id=$(get_repo_id "$REPO_B_DIR")
    local ticket_dir="$WORKSPACE_BASE/$repo_id/TICKET-789-feature-one"
    
    sleep 1
    
    assert "[ -d \"$ticket_dir\" ]" "Repo B ticket directory still exists"
    
    local symlink_target=$(readlink -f "$HOME/Downloads/CurrentTicket")
    assert "[ \"$symlink_target\" = \"$ticket_dir\" ]" "CurrentTicket symlink points to correct directory"
}

test_cross_repo_isolation() {
    log_test "Testing cross-repository isolation..."
    
    local repo_a_id=$(get_repo_id "$REPO_A_DIR")
    local repo_b_id=$(get_repo_id "$REPO_B_DIR")
    
    assert "[ \"$repo_a_id\" != \"$repo_b_id\" ]" "Repositories have different IDs"
    
    local repo_a_dir="$WORKSPACE_BASE/$repo_a_id"
    local repo_b_dir="$WORKSPACE_BASE/$repo_b_id"
    
    assert "[ -d \"$repo_a_dir\" ]" "Repo A workspace directory exists"
    assert "[ -d \"$repo_b_dir\" ]" "Repo B workspace directory exists"
    
    # Verify they are separate
    assert "[ \"$repo_a_dir\" != \"$repo_b_dir\" ]" "Repositories have separate workspace directories"
}

print_test_summary() {
    echo ""
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo "Passed: $PASSED"
    echo "Failed: $FAILED"
    echo ""
    
    if [ ${#FAILURES[@]} -gt 0 ]; then
        echo "Failures:"
        for failure in "${FAILURES[@]}"; do
            echo "  - $failure"
        done
        echo ""
        return 1
    else
        log_info "All tests passed!"
        return 0
    fi
}

# Main test execution
main() {
    log_info "Starting E2E tests for GitSidecar"
    echo ""
    
    # Setup
    setup_tools_library
    install_gitsidecar
    setup_repo_a
    setup_repo_b
    install_hook_repo_a
    install_hook_repo_b
    
    # Test Repo A
    test_repo_a_setup
    test_repo_a_first_ticket
    test_repo_a_switch_branch
    test_repo_a_same_ticket_reuse
    test_repo_a_standard_branches
    test_repo_a_return_to_ticket
    
    # Test Repo B
    test_repo_b_setup
    test_repo_b_first_ticket
    test_repo_b_switch_branch
    test_repo_b_same_ticket_reuse
    test_repo_b_standard_branches
    test_repo_b_return_to_ticket
    
    # Cross-repo verification
    test_cross_repo_isolation
    
    # Summary
    if print_test_summary; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"
