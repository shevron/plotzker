"""FreeCAD assemblies of a project: definition, export and build.

* :mod:`cadder.freecad.model`: :class:`FreeCadAssembly` with its :class:`Component`\\ s,
  rigid :class:`Body`\\ s and :class:`Joint`\\ s, built by the project in plain Python.
* :mod:`cadder.freecad.export`: STLs (shared between congruent components) and a manifest.
* ``build.py``: runs in FreeCAD's ``freecadcmd`` and turns the manifest into an ``.FCStd``.

``cadder freecad [NAMES]`` does it all for the project's assemblies
(``Project.freecad_assemblies``).
"""

from cadder.freecad.model import Body, Component, Components, FreeCadAssembly, Joint

__all__ = ["Body", "Component", "Components", "FreeCadAssembly", "Joint"]
