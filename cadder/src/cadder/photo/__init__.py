"""Measuring physical parts from photos: the tools behind ``cadder photo``.

The workflow (``cadder/docs/photo.md``): photograph the part lying on a printed ChArUco target
(``cadder photo target``), rectify the photo onto the target's plane (``rectify``: scale,
perspective and the camera's pose in one step), then measure in millimeters on the rectified
image (``crop``, ``edges``, ``holes``, ``point``), record the results in a feature file and check
them by drawing it back onto the photo (``overlay``, ``table``). Photos without a target can
still be cropped and measured in pixels.

Needs the ``photo`` extra (OpenCV, Pillow, pillow-heif); the modules import it lazily, so the
rest of cadder works without it.
"""
