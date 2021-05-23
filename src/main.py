import os
import re
import time
import logging
import uuid
from urllib.parse import quote_plus, unquote_plus
from operator import attrgetter
from logging.config import dictConfig
import gevent
import jinja2
from flask import Flask, render_template, request

# Configure logging before any local imports to ensure config is applied
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] (%(name)s) [%(filename)s::%(funcName)s::%(lineno)s] [%(levelname)s]: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': "INFO",
        'handlers': ['wsgi']
    }
})

from constants import FLASK_NAME
from state import state, ArchivalEntry, upload_file
from twitter import get_trends_by_location_name
from internet_archive import search_internet_archive_audio
from archival import generate_audio_for_search_results

# Use reverse proxy to ensure url_for populates with the correct scheme
class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

# Create flask app
app = Flask(FLASK_NAME, static_folder="public")
app.wsgi_app = ReverseProxied(app.wsgi_app)

# Get logger
logger = logging.getLogger(FLASK_NAME)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Set templates dir
app.jinja_loader = jinja2.ChoiceLoader(
    [app.jinja_loader, jinja2.FileSystemLoader("templates")])

# Create quote_plus jina filter
app.jinja_env.filters['quote_plus'] = lambda u: quote_plus(u)


# Generates an entry and updates state
def generate_and_update(generation_interval=4*60*60):
    # Denote start time
    start = time.time()

    # Get trends for location - Boston
    trend_location = "Boston"
    trends = get_trends_by_location_name(trend_location)

    # Sort trends by most tweets
    trends.sort(reverse=True, key=lambda t: (t['tweet_volume'] is not None, t['tweet_volume']))

    # Find an appropriate trend
    for trend in trends:
        trend_name = trend["name"]
        trend_num_tweets = trend["tweet_volume"]

        # Check if trend has been used in the past 24 hours
        last_24_hour_entries = filter(lambda e: e.timestamp > (time.time() - 24*60*60), state.entries)
        if trend_name.lower() in [e.trend_name.lower() for e in last_24_hour_entries]:
            logger.debug(f"{trend_name} used in the past 24 hours, skipping...")
            continue

        # Search internet archive
        results = search_internet_archive_audio(trend_name)
        MIN_RESULTS = 10
        if len(results) < MIN_RESULTS:
            logger.debug(f"{trend_name} did not return enough results from the internet archive")
            continue
        logger.debug(f"{trend_name} returned {len(results)} results from the internet archive")

        logger.debug(f"Using trend \"{trend_name}\" ({trend_num_tweets} tweets)")

        # Generate audio
        composition_filename, composition_duration = generate_audio_for_search_results(trend_name, results)

        # Upload audio
        quoted_filename = re.sub(r'[^0-9a-zA-Z\-.]+', '_', composition_filename)
        s3_filename = f"{str(uuid.uuid4())}-{quoted_filename}"
        upload_file(composition_filename, s3_filename, ACL="public-read")

        # Create new archival entry
        entry = ArchivalEntry(trend_name, trend_location, trend_num_tweets, s3_filename, composition_duration, time.time())

        # Add entry
        state.add_entry(entry)

        # Delete original composition file
        if os.path.exists(composition_filename):
            os.remove(composition_filename)

        # Only generate once
        break

    # Compute when next generation should start
    generation_duration = time.time() - start
    next_generation_start_time = max(0, generation_interval - generation_duration)
    logger.debug(f"generation took {generation_duration}s, starting next generation in {next_generation_start_time}s")

    # Schedule next generation
    gevent.spawn_later(next_generation_start_time, generate_and_update, generation_interval)


# Kickoff generation
if not os.environ.get("SKIP_GENERATION") == "True":
    gevent.spawn(generate_and_update)
else:
    logger.info("not generating entries")


@app.route('/health')
def health():
    return 'OK', 200

@app.route('/', methods=["GET"])
def archival():
    # Allow specifying a trend
    trend_name = request.args.get("trend", None)
    
    # Get entry to present
    entry = None

    # Get entry by trend name
    if trend_name:
        unquoted_trend_name = unquote_plus(trend_name)
        entries_by_trend = list(filter(lambda e: e.trend_name.lower() == unquoted_trend_name.lower(), state.entries))
        if len(entries_by_trend) > 0:
            entry = entries_by_trend.pop(0)

    # Default to most recent
    if not entry:
        most_recent_entry = max(state.entries, default=None, key=attrgetter("timestamp"))
        entry = most_recent_entry

    return render_template('archival.html', entry=entry, all_entries=state.entries)
