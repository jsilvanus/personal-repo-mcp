from .runner import GitRunner


def merge(runner: GitRunner, revision: str, no_edit: bool = False) -> str:
    args = ["merge"]
    if no_edit:
        args.append("--no-edit")
    args.append(revision)
    return runner.run(*args)


def rebase(runner: GitRunner, revision: str) -> str:
    return runner.run("rebase", revision)


def state(runner: GitRunner) -> dict[str, object]:
    merge_head = (runner.workspace / ".git" / "MERGE_HEAD").exists()
    rebase_merge = (runner.workspace / ".git" / "rebase-merge").is_dir()
    rebase_apply = (runner.workspace / ".git" / "rebase-apply").is_dir()
    return {"merge_in_progress": merge_head, "rebase_in_progress": rebase_merge or rebase_apply}


def abort_merge(runner: GitRunner) -> str:
    return runner.run("merge", "--abort")


def continue_merge(runner: GitRunner) -> str:
    return runner.run("merge", "--continue")


def abort_rebase(runner: GitRunner) -> str:
    return runner.run("rebase", "--abort")


def continue_rebase(runner: GitRunner) -> str:
    return runner.run("rebase", "--continue")
