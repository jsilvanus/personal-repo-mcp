import logging

from personal_repo_mcp.audit.logger import AuditLogger


def test_audit_does_not_include_content(caplog):
    audit = AuditLogger(logging.getLogger("test.audit"))
    with caplog.at_level(logging.INFO, logger="test.audit"):
        audit.record(principal="bearer", repository="repo", operation="write_file", success=True, duration_ms=1.2, path="a.txt")
    assert "write_file" in caplog.text
    assert "content" not in caplog.text
