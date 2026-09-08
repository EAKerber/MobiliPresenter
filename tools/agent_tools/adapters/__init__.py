from . import ci_workflow_rerun, project_inspect, remote_git_files, roadmap_freshness_inspect, routine_inspect

ADAPTERS = {
    "ci-workflow-rerun": ci_workflow_rerun,
    "project-inspect": project_inspect,
    "remote-git-files": remote_git_files,
    "roadmap-freshness-inspect": roadmap_freshness_inspect,
    "routine-inspect": routine_inspect,
}
