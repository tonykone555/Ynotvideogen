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

WAN22_REPO = "Comfy-Org/Wan_2.2_ComfyUI_Repackaged"
WAN22_FILES = {
    "split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors": "diffusion_models",
    "split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors": "diffusion_models",
    "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors": "text_encoders",
    "split_files/vae/wan_2.1_vae.safetensors": "vae",
}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "curl")
    .pip_install(
        "httpx>=0.27",
        "requests>=2.32",
        "pillow>=10.4",
        "huggingface_hub>=0.34",
    )
    .run_commands(
        "git clone --depth 1 --branch v0.36.0 https://github.com/Comfy-Org/ComfyUI.git /opt/ComfyUI",
        "pip install -r /opt/ComfyUI/requirements.txt",
        "mkdir -p /opt/ComfyUI/input /opt/ComfyUI/output /models /outputs",
        "mkdir -p /models/checkpoints /models/diffusion_models /models/text_encoders /models/clip /models/vae /models/clip_vision",
        "printf 'ynot:\\n  base_path: /models\\n  checkpoints: checkpoints\\n  diffusion_models: diffusion_models\\n  text_encoders: text_encoders\\n  clip: clip\\n  vae: vae\\n  clip_vision: clip_vision\\n' > /opt/ComfyUI/extra_model_paths.yaml",
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
    proc = subprocess.Popen(
        [
            "python",
            "/opt/ComfyUI/main.py",
            "--listen",
            "127.0.0.1",
            "--port",
            str(COMFY_PORT),
            "--disable-auto-launch",
            "--extra-model-paths-config",
            "/opt/ComfyUI/extra_model_paths.yaml",
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


def _model_names_from_workflow(workflow: dict) -> list[str]:
    keys = {
        "unet_name",
        "ckpt_name",
        "clip_name",
        "clip_name1",
        "clip_name2",
        "vae_name",
    }
    names: list[str] = []
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        for key in keys:
            value = inputs.get(key)
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    return names


def _available_model_files() -> set[str]:
    root = Path("/models")
    if not root.exists():
        return set()
    return {path.name for path in root.rglob("*") if path.is_file()}


def _validate_model_files(workflow: dict) -> None:
    required = _model_names_from_workflow(workflow)
    if not required:
        return
    available = _available_model_files()
    missing = [name for name in required if name not in available]
    if missing:
        raise RuntimeError(
            "Modal model volume is missing required files: "
            + ", ".join(missing)
            + ". Install them into ynot-video-models using ComfyUI model folders."
        )


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
        _validate_model_files(staged_workflow)
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
        staged_workflow = _stage_remote_inputs(workflow, metadata or {})
        _validate_workflow_nodes(staged_workflow)
        _validate_model_files(staged_workflow)
        queued = _post_json("/prompt", {"prompt": staged_workflow})
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


@app.function(
    image=image,
    gpu="L4",
    volumes={"/models": models},
    timeout=180,
)
def comfy_probe() -> dict:
    """Report readiness per model family without blocking Wan on optional nodes."""
    proc = _start_comfy()
    try:
        object_info = _get_json("/object_info")
        families = {
            "wan": [
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
            ],
            "ltx": [
                "LoadImage",
                "CheckpointLoaderSimple",
                "CLIPTextEncode",
                "LTXVImgToVideo",
                "KSampler",
                "VAEDecode",
                "CreateVideo",
                "SaveVideo",
            ],
            "kandinsky": [
                "LoadImage",
                "VAELoader",
                "Kandinsky5TextEncoderLoader",
                "Kandinsky5UNETLoader",
                "Kandinsky5TextEncode",
                "Kandinsky5ImageToVideo",
                "SaveVideo",
            ],
        }
        readiness = {}
        for family, required in families.items():
            missing = [name for name in required if name not in object_info]
            readiness[family] = {
                "ready": not missing,
                "missing_nodes": missing,
            }

        model_files = sorted(_available_model_files())
        required_wan_models = [Path(name).name for name in WAN22_FILES]
        missing_wan_models = [
            name for name in required_wan_models if name not in model_files
        ]
        readiness["wan"]["missing_models"] = missing_wan_models
        readiness["wan"]["ready"] = (
            readiness["wan"]["ready"] and not missing_wan_models
        )

        return {
            "ok": readiness["wan"]["ready"],
            "first_render_ready": readiness["wan"]["ready"],
            "families": readiness,
            "comfy_node_count": len(object_info),
            "model_file_count": len(model_files),
            "model_files": model_files[:80],
            "comfy_version": "v0.36.0",
            "model_root": "/models",
        }
    finally:
        proc.terminate()


@app.function(
    image=image,
    volumes={"/models": models},
    timeout=60 * 60 * 4,
)
def install_wan22_models() -> dict:
    """Install the official Comfy-Org Wan 2.2 I2V files into the persistent Modal volume."""
    from huggingface_hub import hf_hub_download

    installed: list[str] = []
    for remote_path, target_folder in WAN22_FILES.items():
        filename = Path(remote_path).name
        target_dir = Path("/models") / target_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        if target.exists() and target.stat().st_size > 1024 * 1024:
            installed.append(str(target))
            continue

        downloaded = Path(
            hf_hub_download(
                repo_id=WAN22_REPO,
                filename=remote_path,
                local_dir="/tmp/ynot-wan22",
            )
        )
        downloaded.replace(target)
        installed.append(str(target))

    models.commit()
    return {
        "ok": True,
        "repo": WAN22_REPO,
        "installed": installed,
        "count": len(installed),
    }


@app.local_entrypoint()
def smoke():
    print(gpu_probe.remote())
    print(comfy_probe.remote())
