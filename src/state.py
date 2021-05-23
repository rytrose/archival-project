import os
import json
import logging
import boto3

from secrets import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
from constants import FLASK_NAME

logger = logging.getLogger(FLASK_NAME)

S3_BUCKET_NAME = "archival-project"
AWS_SESSION = boto3.Session(aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
STATE_FILENAME = os.environ.get("STATE_FILENAME", "state.json")

class ArchivalState:

    def __init__(self, entries=None):
        self.entries = entries if entries else []

    def add_entry(self, entry):
        self.entries.append(entry)
        _update_state()

    @staticmethod
    def from_json(json_dict):
        entries = json_dict.get("entries", [])
        entries = [ArchivalEntry.from_json(e) for e in entries]
        return ArchivalState(entries)

    def to_json(self) -> dict:
        return {
            "entries": [e.to_json() for e in self.entries]
        }


class ArchivalEntry:

    def __init__(self, trend_name, trend_location, num_tweets, filename, duration, timestamp):
        self.trend_name = trend_name
        self.trend_location = trend_location
        self.num_tweets = num_tweets
        self.filename = filename
        self.duration = duration
        self.timestamp = timestamp

    @staticmethod
    def from_json(json_dict):
        trend_name = json_dict.get("trendName", "")
        trend_location = json_dict.get("trendLocation", "")
        num_tweets = json_dict.get("numTweets", 0)
        filename = json_dict.get("filename", "")
        duration = json_dict.get("duration", 0.0)
        timestamp = json_dict.get("timestamp", 0.0)
        return ArchivalEntry(trend_name, trend_location, num_tweets, filename, duration, timestamp)

    def to_json(self) -> dict:
        return {
            "trendName": self.trend_name,
            "trendLocation": self.trend_location,
            "numTweets": self.num_tweets,
            "filename": self.filename,
            "duration": self.duration,
            "timestamp": self.timestamp
        }


def upload_file(filename, key, **kwargs):
    s3 = AWS_SESSION.resource('s3')
    with open(filename, 'rb') as file_obj:
        s3.Object(S3_BUCKET_NAME, key).put(Body=file_obj, **kwargs)


def _upload_bytes(b, key):
    s3 = AWS_SESSION.resource('s3')
    s3.Object(S3_BUCKET_NAME, key).put(Body=b)


def _get_state() -> ArchivalState:
    logger.debug("fetching state from S3")
    s3 = AWS_SESSION.resource('s3')
    state_object = s3.Object(S3_BUCKET_NAME, STATE_FILENAME).get()
    state_dict = json.load(state_object["Body"])
    return ArchivalState.from_json(state_dict)

def _update_state():
    global state
    
    if not state:
        logger.warning("update_state: state not yet defined")
        return
    
    logger.debug("updating state in S3")
    state_json = state.to_json()
    state_json_bytes = json.dumps(state_json).encode("utf-8")
    _upload_bytes(state_json_bytes, STATE_FILENAME)


# Populate state from S3
state = _get_state()
