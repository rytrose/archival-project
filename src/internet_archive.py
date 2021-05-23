import re
import logging
import internetarchive as ia

from constants import FLASK_NAME

logger = logging.getLogger(FLASK_NAME)


def search_internet_archive_audio(search_terms):
    query = f"({search_terms}) AND mediatype:(audio) AND language:(eng)"
    return ia.search_items(query, fields=["title"])


def get_mp3_data_for_search_results(results, max_size=30e6):
    for result in results.iter_as_items():
        identifier = result.identifier
        title = result.metadata['title']
        logger.debug(f"Evaluating \"{title}\"...")

        for file in result.files:
            filename = file["name"]

            if re.search(".mp3$", filename) is not None:
                # Grab the file size in bytes
                size = file.get("size")
                if not size:
                    continue
                size = int(size)

                # Ensure size is under max size in bytes (default 5MB)
                if size > max_size:
                    continue
                logger.debug(f"File is {size / 1e6} MB")

                # Download the file
                response = _get_download_response(identifier, filename)
                if response is None:
                    break

                logger.debug(f"Loading \"{title}\" into memory...")
                data = response.content

                # Yield the downloaded data
                yield title, data

                # Look for another result
                break

def _get_download_response(identifier, filename):
    try:
        return ia.download(identifier, files=[filename], return_responses=True)[0]
    except Exception as e:
        logger.debug(f"Unable to download {filename}: {e})")
        return None
