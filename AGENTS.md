# Commit requirements

- Every commit must include an incremental increase to `verto.__version__` in
  `verto/__init__.py`. For routine fixes, increment the patch component from the
  latest version on the target branch, unless a different release is requested.
- Include the version increase in the same commit as the change.
- Preserve the mobile About screen's Git commit count version increment in
  `verto/api/mobile/about.py`. A shallow checkout's count may differ from the
  deployed checkout, so do not report a local count as the deployed version.
