# Repository settings (one-time, done on github.com)

These need the repository owner and cannot be set from the code. Each takes a minute.

1. **Make `main` the default branch.** Settings → General → Default branch → switch to `main`.
   New work then starts from `main`, and the README and badges point at it.
2. **Switch on the browser version.** Settings → Pages → Build and deployment → Source:
   *GitHub Actions*. The *browser version* workflow then publishes WeanAge at
   <https://andymaehartley.github.io/repotest/> every time `main` changes (or run it by hand from
   the Actions tab).
3. **Rename the repository to `weanage`** (recommended, optional). Settings → General → Repository
   name. GitHub redirects the old address, but please then replace `andymaehartley/repotest` with
   `andymaehartley/weanage` in `README.md`, `CITATION.cff`, `pyproject.toml`,
   `src/weanage/web/about.js` and `CONTRIBUTING.md` (one search-and-replace).
4. **Protect `main`** (optional). Settings → Branches → Add rule for `main`: require a pull request
   and the *tests* checks to pass before merging.
5. **Get a DOI.** Sign in to zenodo.org with GitHub, switch the repository on under GitHub →
   Repositories, then publish a release (tag `v0.2.0`). Zenodo archives it and gives a DOI; add it
   to `CITATION.cff`. `.zenodo.json` already holds the title, author and keywords.
6. **PyPI (optional).** To let `pip install weanage` work, register the repository as a trusted
   publisher on pypi.org; the *release* workflow then publishes each tagged version.
