from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx


async def stitch_remote_clips(
    ad_id: str,
    assets: list[str],
    output_dir: Path,
    public_base_url: str,
) -> str:
    """Download generated clips and stitch them into one MP4 with local ffmpeg."""
    if not assets:
        raise ValueError("No clip assets supplied for stitching.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{ad_id}.mp4"

    with TemporaryDirectory(prefix=f"ynot-{ad_id}-") as tmp:
        tmpdir = Path(tmp)
        clip_paths: list[Path] = []

        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            for index, url in enumerate(assets):
                response = await client.get(url)
                response.raise_for_status()
                path = tmpdir / f"clip-{index:02d}.mp4"
                path.write_bytes(response.content)
                clip_paths.append(path)

        concat_file = tmpdir / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{path.as_posix()}'" for path in clip_paths),
            encoding="utf-8",
        )

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                "ffmpeg stitching failed: " + stderr.decode("utf-8", errors="ignore")[-1200:]
            )

    base = public_base_url.rstrip("/")
    if not base:
        raise RuntimeError("YNOT_PUBLIC_BASE_URL must be set for stitched output URLs.")
    return f"{base}/outputs/{output_path.name}"
