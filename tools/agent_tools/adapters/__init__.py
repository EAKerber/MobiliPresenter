from . import project_inspect, remote_git_files, routine_inspect

ADAPTERS = {
    "project-inspect": project_inspect,
    "remote-git-files": remote_git_files,
    "routine-inspect": routine_inspect,
}
