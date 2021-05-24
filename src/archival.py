import os
import math
import argparse
import random
import pickle
import logging
from uuid import uuid4
from pydub import AudioSegment
from pydub.playback import play

from constants import FLASK_NAME
from twitter import get_trends_by_location_name
from internet_archive import get_mp3_data_for_search_results
from audio import convert_to_pcm, convert_to_pcm_ffmpeg
from vad import extract_voiced_sections, write_wave
from util import quantize_without_going_over


logger = logging.getLogger(FLASK_NAME)


# Separate voiced segments by length
SEGMENT_BUCKETS_MS = [500, 1000, 1500, 3000, 5000]


def generate_audio_for_search_results(name, results, max_section_length=10.0, max_sections_per_source=15):
    # Create map for audio 
    audio_segments = {bucket_max: [] for bucket_max in SEGMENT_BUCKETS_MS}

    # Search internet archive for a related MP3s
    mp3_data = get_mp3_data_for_search_results(results)

    for title, data in mp3_data:
        # Write to file to create AudioSegment
        filename = f"{str(uuid4())}.mp3"
        try:
            with open(filename, "wb") as f:
                f.write(data)
        except Exception as e:
            logger.debug(f"Unable to open file: {e}")

        # Convert MP3 data to PCM
        logger.debug(f"Converting \"{title}\"...")
        try:
            pcm_data = convert_to_pcm_ffmpeg(filename)
        except Exception as e:
            logger.debug(f"Unable to convert MP3 to PCM: {e}")
            continue

        # Create audio segment from MP3
        logger.debug(f"Creating audio segment from \"{filename}\"...")
        try:
            source_segment = AudioSegment.from_mp3(filename)
        except Exception as e:
            logger.debug(f"Unable to create audio segment from MP3 file: {e}")
            continue

        # Delete downloaded MP3 file
        logger.debug(f"Removing downloaded \"{filename}\"...")
        if os.path.exists(filename):
            os.remove(filename)

        # Save off some voiced segments
        logger.debug(f"Running VAD on \"{title}\"...")
        sections = extract_voiced_sections(pcm_data)
        added_sections = 0

        source_audio_segments = {bucket_max: [] for bucket_max in SEGMENT_BUCKETS_MS}

        for section in sections:
            if section[1] - section[0] > max_section_length:
                # Skip sections longer than max_section_length
                continue
            audio_segment = source_segment[math.floor(section[0] * 1000):math.floor(section[1] * 1000)]
            source_audio_segments[quantize_without_going_over(len(audio_segment), SEGMENT_BUCKETS_MS)].append(audio_segment)
            added_sections += 1
            # only save off a handful of sections per file for diversity
            if added_sections > max_sections_per_source:
                break
        
        # Add source audio segments to all audio segments
        for bucket_max, bucket in audio_segments.items():
            source_bucket = source_audio_segments[bucket_max]
            if source_bucket:
                audio_segments[bucket_max].append(source_bucket)

        logger.debug(f"Audio segments:")

        num_files = 0
        for bucket, source_segments_list in audio_segments.items():
            bucket_num_files = 0
            for segments in source_segments_list:
                bucket_num_files += len(segments)
                num_files += len(segments)
            logger.debug(f"\t{bucket} - {bucket_num_files}")

        if num_files > 50:
            logger.debug("Collected 50 files, composing...")
            break

    # Save off audio segments
    if os.environ.get("SAVE_SEGMENTS"):
        with open(f"{name}_audio_segments.pickle", "wb") as f:
            pickle.dump(audio_segments, f)

    # Compose and save file
    composition_filename, composition_duration = compose(name, audio_segments)

    # Return metadata
    return composition_filename, composition_duration


def compose(name, audio_segments, density=0.5):
    # Plan out the composition
    composition_buckets = {bucket: [] for bucket in audio_segments.keys()}
    composition_length = 0

    num_buckets = len(audio_segments.keys())
    bucket_index = 0
    for bucket, source_segments_list in audio_segments.items():
        logger.debug(f"Scheduling bucket {bucket}...")

        # Set pan max/min
        #   The shorter the clip, the more panned it can be
        pan_min = 1 - ((bucket_index + 1) / num_buckets)
        pan_max = 1 - (bucket_index / num_buckets)
        pan_diff = pan_max - pan_min

        # Set offset between successive segments
        #   The shorter the clip, the more variability
        offset_min = -math.floor(math.floor(bucket / 2) * (1 - (bucket_index / num_buckets)))
        offset_max = math.floor((1 + (num_buckets * (1 - (bucket_index / num_buckets)))) * bucket)
        offset_diff = offset_max - offset_min

        # Set probablility of being silent for some time
        #   The shorter the clip, the more chance for silence
        added_silence_probability = 0.55 - (0.5 * ((bucket_index + 1) / num_buckets))

        # Set initial offset
        offset = max(0, offset_min + (random.random() * offset_diff))

        # Randomly schedule available segments
        while source_segments_list:
            # Update offset
            offset += (offset_min + (random.random() * offset_diff))

            # Determine pan
            pan = pan_min + (random.random() * pan_diff)

            source_index = random.randint(0, len(source_segments_list)-1)
            segment = source_segments_list[source_index].pop(0)
            if len(source_segments_list[source_index]) < 1:
                source_segments_list.pop(source_index)
            scheduled_segment = {
                "segment": segment.normalize().fade_in(10).fade_out(10),
                "offset": max(0, offset),
                "pan": pan
            }
            composition_buckets[bucket].append(scheduled_segment)

            # Determine if silence is added to affect density
            if random.random() < added_silence_probability:
                offset += ((1 - density) * 1000)

        # Update composition length
        if len(composition_buckets[bucket]) > 0:
            last_scheduled_segment = composition_buckets[bucket][len(composition_buckets[bucket])-1]
            bucket_length = last_scheduled_segment["offset"] + len(last_scheduled_segment["segment"])
            composition_length = max(composition_length, bucket_length)

        bucket_index += 1

    # Put together the composition
    logger.debug("Putting together composition...")
    master = AudioSegment.silent(duration=composition_length)
    for scheduled_segments in composition_buckets.values():
        for scheduled_segment in scheduled_segments:
            s = scheduled_segment["segment"].pan(scheduled_segment["pan"])
            master = master.overlay(s, position=scheduled_segment["offset"])

    # Save off master to file
    duration = len(master) / 1000
    logger.debug(f"Saving composition [{duration}s]...")
    filename = f"{name}.mp3"
    with open(filename, "wb") as f:
        master.export(f, format="mp3")

    return filename, duration


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    parser.add_argument('--trend_location', default="Boston", help='A name of a location from which to collect trends.')
    parser.add_argument('--trend_index', default=0, type=int, help='Which trend to select from the current trends found on Twitter.')
    parser.add_argument('--max_section_length', default=10.0, type=float, help='The maximium length of an extracted vocal segment to use.')
    parser.add_argument('--max_sections_per_source', default=15, type=int, help='The maximium number of an extracted vocal segments to use per archive item.')
    
    args = parser.parse_args()

    generate_trend_audio(args.trend_location, args.trend_index, args.max_section_length, args.max_sections_per_source)
