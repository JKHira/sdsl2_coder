# Golden Output Layout v0.1

Goal:
- Keep generated outputs separate from versioned golden references.

Generated output (run command):
- OUTPUT/<id_prefix>/topology.sdsl2

Golden reference (VCS-managed):
- tests/goldens/<id_prefix>/topology.sdsl2

Spec bump rule:
- Do not overwrite existing golden files.
- Add a new file with version suffix (example: topology.v0_2.sdsl2).
