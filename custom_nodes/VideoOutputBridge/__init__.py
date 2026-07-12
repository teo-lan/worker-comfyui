"""Video Output Bridge — vendored for DREAM.

worker-comfyui's handler only returns node outputs stored under the ``images``
key. VHS_VideoCombine reports its rendered file under ``gifs``, so the video is
ignored. This node takes VHS's VHS_FILENAMES output and re-emits it as an
``images`` UI payload, so the handler picks the mp4 up and returns it
(base64 when BUCKET_ENDPOINT_URL is unset, S3 otherwise). Zero dependencies.
"""

from typing import Any, Dict, List


class VideoOutputBridge:
    CATEGORY = "Utility/Bridges"
    RETURN_TYPES: tuple = ()
    RETURN_NAMES: tuple = ()
    FUNCTION = "forward"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "filenames": ("VHS_FILENAMES",),
                "label": (
                    "STRING",
                    {"default": "dream-video", "multiline": False},
                ),
            }
        }

    def forward(self, filenames: Any, label: str):
        # VHS_FILENAMES is commonly (save_bool, [paths]) or a list of dicts,
        # depending on the VHS version — handle both shapes defensively.
        entries: List[Any] = []
        if isinstance(filenames, (list, tuple)):
            for item in filenames:
                if isinstance(item, dict):
                    entries.append(item)
                elif isinstance(item, str):
                    entries.append({"filename": item})
                elif isinstance(item, (list, tuple)):
                    for sub in item:
                        if isinstance(sub, str):
                            entries.append({"filename": sub})
                        elif isinstance(sub, dict):
                            entries.append(sub)

        images: List[Dict[str, Any]] = []
        for idx, entry in enumerate(entries):
            raw = entry.get("filename") or f"{label}_{idx}.mp4"
            # A VHS path may be absolute (/comfyui/output/sub/x.mp4); the handler
            # fetches via /view with filename + subfolder, so pass basename +
            # subfolder rather than the whole path.
            filename = raw.rsplit("/", 1)[-1]
            subfolder = entry.get("subfolder", "")
            if not subfolder and "/output/" in raw:
                tail = raw.split("/output/", 1)[1]
                subfolder = tail.rsplit("/", 1)[0] if "/" in tail else ""
            images.append(
                {
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": entry.get("type", "output"),
                }
            )

        if not images:
            images.append({"filename": f"{label}_0.mp4", "subfolder": "", "type": "output"})

        return {"ui": {"images": images}}


NODE_CLASS_MAPPINGS = {"VideoOutputBridge": VideoOutputBridge}
NODE_DISPLAY_NAME_MAPPINGS = {"VideoOutputBridge": "Video Output Bridge"}
