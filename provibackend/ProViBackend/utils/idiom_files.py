"""Where an experiment's idiom images live on disk, and which one is shown.

For one (experiment, task, idiom) the image participants see is, in order:

1. an override: an image the admin imported from an idiom bundle or uploaded
   to replace this one idiom (IDIOM_OVERRIDE_DIRECTORY). Regenerating never
   touches it, so imported stimuli stay fixed until the admin reverts them.
2. a custom idiom's fixed asset (CUSTOM_IDIOM_DIRECTORY), for admin-uploaded
   idiom types.
3. the generated SVG at data/{dataset_id}/output/{experiment_id}/{task_key}/.
4. the legacy shared SVG at data/{dataset_id}/output/{task_key}/.
"""
import logging
import pathlib as pl
import shutil

from ProViBackend.utils import config

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg")
TRACES_FILENAME = "traces.json"


def override_dir(experiment_id: str, task_key: str) -> pl.Path:
    return config.IDIOM_OVERRIDE_DIRECTORY / experiment_id / task_key


def find_override(experiment_id: str | None, task_key: str, idiom_key: str) -> pl.Path | None:
    if not experiment_id:
        return None
    base = override_dir(experiment_id, task_key)
    for ext in IMAGE_EXTENSIONS:
        path = base / f"{idiom_key}{ext}"
        if path.exists():
            return path
    return None


def write_override(experiment_id: str, task_key: str, idiom_key: str, ext: str, content: bytes) -> pl.Path:
    remove_override(experiment_id, task_key, idiom_key)
    base = override_dir(experiment_id, task_key)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{idiom_key}{ext}"
    path.write_bytes(content)
    return path


def remove_override(experiment_id: str, task_key: str, idiom_key: str) -> bool:
    removed = False
    for ext in IMAGE_EXTENSIONS:
        path = override_dir(experiment_id, task_key) / f"{idiom_key}{ext}"
        if path.exists():
            path.unlink()
            removed = True
    return removed


def list_overrides(experiment_id: str) -> list[dict]:
    """[{task_key, idiom_key, ext}] for every image override of the experiment."""
    root = config.IDIOM_OVERRIDE_DIRECTORY / experiment_id
    if not root.is_dir():
        return []
    out = []
    for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(task_dir.iterdir()):
            if f.suffix.lower() in IMAGE_EXTENSIONS:
                out.append({"task_key": task_dir.name, "idiom_key": f.stem, "ext": f.suffix.lower()})
    return out


def remove_all_overrides(experiment_id: str) -> None:
    shutil.rmtree(config.IDIOM_OVERRIDE_DIRECTORY / experiment_id, ignore_errors=True)


def custom_asset_path(idiom: dict) -> pl.Path:
    return config.CUSTOM_IDIOM_DIRECTORY / f"{idiom['idiom_key']}{idiom.get('asset_ext') or '.svg'}"


def resolve_idiom_image(dataset_id: str | None, experiment_id: str | None,
                        task_key: str, idiom: dict) -> tuple[pl.Path | None, str | None]:
    """(path, source) of the image shown for this idiom; source is one of
    "uploaded", "custom", "generated", "legacy". The path may not exist when
    nothing has been generated yet; (None, None) when there is no dataset."""
    override = find_override(experiment_id, task_key, idiom["idiom_key"])
    if override:
        return override, "uploaded"
    if idiom.get("is_custom"):
        return custom_asset_path(idiom), "custom"
    if not dataset_id:
        return None, None
    output_dir = config.BASE_DIRECTORY / "data" / dataset_id / "output"
    if experiment_id:
        generated = output_dir / experiment_id / task_key / f"{idiom['idiom_key']}.svg"
        if generated.exists():
            return generated, "generated"
    return output_dir / task_key / f"{idiom['idiom_key']}.svg", "legacy"


def resolve_traces(dataset_id: str | None, experiment_id: str | None, task_key: str) -> pl.Path | None:
    """traces.json shown next to this task's images: an imported one first,
    then the generated (per-experiment, then legacy) one."""
    if experiment_id:
        imported = override_dir(experiment_id, task_key) / TRACES_FILENAME
        if imported.exists():
            return imported
    if not dataset_id:
        return None
    output_dir = config.BASE_DIRECTORY / "data" / dataset_id / "output"
    if experiment_id:
        per_experiment = output_dir / experiment_id / task_key / TRACES_FILENAME
        if per_experiment.exists():
            return per_experiment
    return output_dir / task_key / TRACES_FILENAME


def migrate_legacy_custom_idioms() -> None:
    """Move custom idiom assets from the old, non-persisted app/static location
    into CUSTOM_IDIOM_DIRECTORY. Only files still present in the running
    container can be saved; ones lost to an earlier redeploy stay lost."""
    legacy = config.LEGACY_CUSTOM_IDIOM_DIRECTORY
    if not legacy.is_dir():
        return
    config.CUSTOM_IDIOM_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for f in legacy.iterdir():
        target = config.CUSTOM_IDIOM_DIRECTORY / f.name
        if f.is_file() and not target.exists():
            shutil.move(str(f), str(target))
            logger.info("Moved custom idiom asset %s to %s", f.name, config.CUSTOM_IDIOM_DIRECTORY)
