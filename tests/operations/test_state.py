from personal_repo_mcp.operations.state import Operation, OperationStatus, OperationStore


def test_operation_store():
    store = OperationStore()
    item = Operation(id="1", repository="repo", kind="fetch")
    store.put(item)
    assert store.get("1").status is OperationStatus.PENDING
