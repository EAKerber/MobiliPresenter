# E5h — leased-branch-only hotfix path

The recovery-carrier hotfix is reviewed and merged only from `work/operations/e5h-own-work-integrated-delta-recovery-r2`, the branch covered by the active E5h exclusive-write lease. No auxiliary ref is part of the implementation or review path.

The hotfix scope remains limited to restoring direct-script repository bootstrap, adding the subprocess CLI regression, and recording the live-gate evidence. No recovery semantics or authority policy change in this follow-up.
