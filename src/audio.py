import miniaudio


def convert_to_pcm(data):
    # Convert to 16-bit mono 48kHz PCM
    return miniaudio.decode(data, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=48000).samples.tobytes()
    