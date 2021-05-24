import os
import subprocess
import logging
import miniaudio

from constants import FLASK_NAME


logger = logging.getLogger(FLASK_NAME)


def convert_to_pcm(data):
    # Convert to 16-bit mono 48kHz PCM
    return miniaudio.decode(data, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=48000).samples.tobytes()


def convert_to_pcm_ffmpeg(filename):
    command = f"ffmpeg -y -i {filename} -acodec pcm_s16le -f s16le -ac 1 -ar 48000 {filename}.pcm"
    logger.debug(f"running command: {command}")
    with open(os.devnull, 'wb') as devnull:
        subprocess.check_call(command.split(" "), stdout=devnull, stderr=subprocess.STDOUT)

    # Read PCM data into memory
    pcm_data = None
    with open(f"{filename}.pcm", "rb") as f:
        pcm_data = f.read()

    # Remove PCM file
    os.remove(f"{filename}.pcm")

    return pcm_data
