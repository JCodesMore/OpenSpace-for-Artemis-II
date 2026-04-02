"""Raw data archival — saves every response for post-mission analysis (D-05)."""
import logging
import pathlib
import time

logger = logging.getLogger(__name__)


def archive_response(archive_dir: pathlib.Path, result) -> pathlib.Path | None:
    """Save raw response data to a timestamped file in archive_dir.

    Args:
        archive_dir: directory for archived files
        result: SourceResult with raw_data and source_name

    Returns:
        Path to archived file, or None if raw_data is empty.
    """
    if not result.raw_data:
        return None
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(result.timestamp))
    filename = f"{result.source_name}_{timestamp}.txt"
    filepath = archive_dir / filename
    filepath.write_text(result.raw_data, encoding="utf-8")
    logger.info("Archived %s response to %s", result.source_name, filepath)
    return filepath
