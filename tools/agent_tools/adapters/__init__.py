from . import project_inspect, remote_git_file, routine_inspect

ADAPTERS = {
    "project-inspect": project_inspect,
    "remote-git-file": remote_git_file,
    "routine-inspect": routine_inspect,
}
