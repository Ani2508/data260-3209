"""HW7 Part 6 - offline tests for the safety gate and file tools (no model, temp sandbox).

Usage:  cd code && python3 -m devtools.test_devtools
"""
import json
import shutil
import tempfile

from .file_tools import FileTools
from .safety_gate import SAFE_PREFIXES, confirm_bash, is_destructive


def test_each_deny_category():
    for cmd in ("rm -rf x", "find . -delete", "sudo ls", "chmod 600 k", "chown a b",
                "dd if=a of=/dev/sda", "mkfs.ext4 /dev/sdb1", "echo x > /etc/hosts",
                "cat a | tee /etc/passwd"):
        assert is_destructive(cmd), cmd


def test_safe_prefix_does_not_override_deny_list():
    assert "echo" in SAFE_PREFIXES and "find" in SAFE_PREFIXES
    assert confirm_bash("echo x > /etc/hosts")["allowed"] is False
    assert confirm_bash("find . -name '*.pyc' -delete")["allowed"] is False


def test_chains_and_confirmation():
    assert confirm_bash("ls && sudo reboot")["allowed"] is False
    assert confirm_bash("rm -rf build", auto_approve=True)["allowed"] is True
    assert confirm_bash("curl http://x")["allowed"] is False          # not on allow-list
    assert confirm_bash("ls -la")["allowed"] is True


def test_file_tools_in_sandbox():
    root = tempfile.mkdtemp(prefix="data260_test_")
    try:
        t = FileTools(root)
        t.write_file("a.py", "x = 1\ny = 2\nz = 3\n")
        assert t.read_file("a.py", max_lines=2)["data"]["lines_returned"] == 2
        diff = t.edit_file("a.py", "y = 2", "y = 20")["data"]["diff"]
        assert "-y = 2" in diff and "+y = 20" in diff
        assert t.search_in_files("z", file_pattern="*.py")["data"]["files"] == ["a.py"]
        assert t.read_file("../x")["success"] is False                 # sandbox escape
        assert t.bash("rm -rf .")["success"] is False                  # gate
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(json.dumps({"passed": len(tests)}))
