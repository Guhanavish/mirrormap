# GitHub Actions example

Copy the example workflow into your repository's `.github/workflows/` folder and customize its approved requirements path.

The action performs structural auditing only and saves the results as a downloadable GitHub Actions artifact. It intentionally does not execute project code, submit automatic fixes, or block merges on unknown findings.

The sample installs MirrorMap from the public source repository's `main` branch for demonstration. **Production workflows should pin a reviewed commit SHA or a signed release tag**, verify the changes, and use a trusted actions dependency policy. The example does not assert that it detects all bugs in a pull request.

To enable functional verification, supply independently collected test evidence in the supported map format. Never fabricate passing tests to make the report look complete.
