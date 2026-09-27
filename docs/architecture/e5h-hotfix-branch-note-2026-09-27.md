# E5h hotfix branch note

The direct-carrier bootstrap repair remains on the already leased canonical E5h r2 branch. An empty experimental ref named `work/operations/e5h-recovery-carrier-bootstrap-r3` was created at `main` before acquiring separate authority and is intentionally not used for implementation, review, or merge. It carries no commits beyond the `main` SHA at creation.

The canonical hotfix path is the E5h r2 branch under its existing exclusive write lease. The follow-up PR must contain only the direct carrier bootstrap, its CLI regression, and supporting checkpoint notes.
