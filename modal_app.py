from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import modal

APP_NAME = "ynot-video-gen-worker"
COMFY_PORT = 8188
COMFY_URL = f"http://127.0.0.1:{COMFY_PORT}"

app = modal.App(APP_NAME)

models = modal.Volume.from_name("ynot-video-models", create_if_missing=True)
outputs = modal.Volume.from_name("ynot-video-outputs", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "curl")
    .pip_install(
        "httpx>=0.27",
        "requests>=2.32",
        "pillow>=10.4",
    )
    .run_commands(
        "git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git /opt/ComfyUI",
        "pip install -r /opt/ComfyUI/requirements.txt",
        "mkdir -p /opt/ComfyUI/input /opt/ComfyUI/output /models /outputs",
    )
)


def _wait_for_comfy(timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(f"{COMFY_URL}/system_stats", timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(1)
    raise RuntimeError("ComfyUI failed to start before timeout.")


def _start_comfy() -> subprocess.Popen:
    env = os.environ.copy()
    env["COMFYUI_MODEL_PATH"] = "/models"
    proc = subprocess.Popen(
        [
            "python",
            "/opt/ComfyUI/main.py",
            "--listen",
            "127.0.0.1",
            "--port",
            str(COMFY_PORT),
            "--disable-auto-launch",
            "--output-directory",
            "/outputs",
        ],
        env=env,
    )
    _wait_for_comfy()
    return proc


def _safe_input_name(url: str, index: int) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".png"
    return f"reference-{index}{suffix}"


def _download_reference(url: str, job_id: str, index: int) -> str:
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"Reference URL must use http(s): {url!r}")

    folder = Path("/opt/ComfyUI/input") / "YNOT" / job_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = _safe_input_name(url, index)
    target = folder / filename

    request = Request(url, headers={"User-Agent": "YNOT-Video-Gen/1.0"})
    with urlopen(request, timeout=60) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            raise ValueError(f"Reference URL did not return an image: {content_type}")
        data = response.read(25 * 1024 * 1024 + 1)

    if len(data) > 25 * 1024 * 1024:
        raise ValueError("Reference image exceeds 25 MB.")
    if not data:
        raise ValueError("Reference image was empty.")

    target.write_bytes(data)
    return str(Path("YNOT") / job_id / filename)


def _stage_remote_inputs(workflow: dict, metadata: dict) -> dict:
    staged = json.loads(json.dumps(workflow))
    job_id = str(metadata.get("job_id") or f"job-{int(time.time())}")
    index = 0

    for node in staged.values():
        if not isinstance(node, dict) or node.get("class_type") != "LoadImageFromUrl":
            continue
        inputs = node.get("inputs") or {}
        url = str(inputs.get("url") or "")
        index += 1
        relative_path = _download_reference(url, job_id, index)
        node["class_type"] = "LoadImage"
        node["inputs"] = {"image": relative_path}

    return staged


def _validate_workflow_nodes(workflow: dict) -> None:
    object_info = _get_json("/object_info")
    required = sorted({
        str(node.get("class_type"))
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type")
    })
    missing = [name for name in required if name not in object_info]
    if missing:
        raise RuntimeError(
            "ComfyUI worker is missing required nodes: "
            + ", ".join(missing)
            + ". Pin/install the matching native workflow before rendering."
        )


def _post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{COMFY_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(path: str) -> dict:
    with urlopen(f"{COMFY_URL}{path}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_prompt(prompt_id: str, timeout_seconds: int = 1800) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        history = _get_json(f"/history/{prompt_id}")
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} exceeded {timeout_seconds}s.")


def _collect_output_files(history: dict) -> list[str]:
    files: list[str] = []
    for node in history.get("outputs", {}).values():
        for key in ("videos", "gifs", "images"):
            for item in node.get(key, []):
                filename = item.get("filename")
                subfolder = item.get("subfolder", "")
                if not filename:
                    continue
                path = Path("/outputs") / subfolder / filename
                files.append(str(path))
    return files


@app.function(
    image=image,
    gpu="L40S",
    volumes={"/models": models, "/outputs": outputs},
    timeout=60 * 35,
    scaledown_window=60,
    max_containers=1,
)
def render_l40s(workflow: dict, metadata: dict | None = None) -> dict:
    """Execute one compiled ComfyUI API workflow on an L40S worker."""
    proc = _start_comfy()
    started = time.time()
    try:
        staged_workflow = _stage_remote_inputs(workflow, metadata or {})
        _validate_workflow_nodes(staged_workflow)
        queued = _post_json("/prompt", {"prompt": staged_workflow})
        prompt_id = queued["prompt_id"]
        history = _wait_for_prompt(prompt_id)
        result = {
            "status": "generated",
            "prompt_id": prompt_id,
            "assets": _collect_output_files(history),
            "generation_seconds": round(time.time() - started, 3),
            "gpu": "L40S",
            "metadata": metadata or {},
        }
        outputs.commit()
        return result
    finally:
        proc.terminate()


@app.function(
    image=image,
    gpu="A100-80GB",
    volumes={"/models": models, "/outputs": outputs},
    timeout=60 * 35,
    scaledown_window=60,
    max_containers=1,
)
def render_a100(workflow: dict, metadata: dict | None = None) -> dict:
    """Heavier fallback worker for models/configurations that exceed L40S VRAM."""
    proc = _start_comfy()
    started = time.time()
    try:
        queued = _post_json("/prompt", {"prompt": workflow})
        prompt_id = queued["prompt_id"]
        history = _wait_for_prompt(prompt_id)
        result = {
            "status": "generated",
            "prompt_id": prompt_id,
            "assets": _collect_output_files(history),
            "generation_seconds": round(time.time() - started, 3),
            "gpu": "A100-80GB",
            "metadata": metadata or {},
        }
        outputs.commit()
        return result
    finally:
        proc.terminate()


@app.function(image=image, gpu="L4", timeout=120)
def gpu_probe() -> dict:
    """Cheap deployment smoke test before downloading any large model."""
    import subprocess as _subprocess

    name = _subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        text=True,
    ).strip()
    memory = _subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader"],
        text=True,
    ).strip()
    return {"ok": True, "gpu": name, "memory": memory}


@app.function(image=image, gpu="L4", timeout=180)
def comfy_probe() -> dict:
    """Start the pinned worker image and report whether required workflow nodes exist."""
    proc = _start_comfy()
    try:
        object_info = _get_json("/object_info")
        required = [
            "LoadImage",
            "UNETLoader",
            "CLIPLoader",
            "VAELoader",
            "CLIPTextEncode",
            "WanImageToVideo",
            "KSamplerAdvanced",
            "VAEDecode",
            "CreateVideo",
            "SaveVideo",
            "CheckpointLoaderSimple",
            "LTXVImgToVideo",
            "KSampler",
            "Kandinsky5TextEncoderLoader",
            "Kandinsky5UNETLoader",
            "Kandinsky5TextEncode",
            "Kandinsky5ImageToVideo",
        ]
        available = [name for name in required if name in object_info]
        missing = [name for name in required if name not in object_info]
        return {
            "ok": not missing,
            "required_count": len(required),
            "available": available,
            "missing": missing,
            "comfy_node_count": len(object_info),
        }
    finally:
        proc.terminate()


@app.local_entrypoint()
def smoke():
    print(gpu_probe.remote())
    print(comfy_probe.remote())
