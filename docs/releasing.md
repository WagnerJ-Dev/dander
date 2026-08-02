# Python release candidates

Dander publishes the `dander-platform` distribution while preserving `dander` as its import
package and CLI. Releases are immutable and come only from an exact `v<version>` tag on protected
`main`.

## Candidate gate

1. Merge the packaging commit and wait for post-merge CI, including `Distribution install`.
2. Confirm `git status --short` is empty and the tag target is the tested `origin/main` commit.
3. Confirm the GitHub `pypi` environment requires review and PyPI trusts this repository's
   `publish.yml` workflow for the `dander-platform` project.
4. Create and push the exact tag, such as `v0.1.0rc1`, only after explicit publication approval.
5. Dispatch **Publish Python distribution** from that tag and approve its `pypi` environment.
6. Install the published candidate into a new environment outside a checkout and repeat
   `dander --version`, `dander new`, `dander validate`, and Terraform validation.

The workflow builds fresh artifacts from the tag, validates their identity and contents, and uses
PyPI trusted publishing. It has no long-lived package token and refuses a branch or mismatched tag.

Phase 6 is acceptance-only for product code. If any functional runtime change is required after a
candidate is published, stop the proof, bump and publish the next candidate through this same gate,
and restart the complete live proof against that candidate. Tests, workflows, evidence tooling,
and documentation may change without a new candidate only when packaged runtime behavior is
unchanged.
