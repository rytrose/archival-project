import logging
import tweepy

from constants import FLASK_NAME
from secrets import TWITTER_API_KEY, TWITTER_API_KEY_SECRET


logger = logging.getLogger(FLASK_NAME)

# Authorize tweepy client
twitter_auth = tweepy.AppAuthHandler(TWITTER_API_KEY, TWITTER_API_KEY_SECRET)
twitter = tweepy.API(twitter_auth)

def get_trends_by_location_name(location_name):
    """Returns a list of Trend objects for the input location name, or None if the location is unavailable.

    Args:
        location_name (str): A case-insensitive location name.
    """
    available_trend_locations = twitter.trends_available()
    trend_locations = list(filter(lambda t: t['name'].lower() == location_name.lower(), available_trend_locations))

    if len(trend_locations) != 1:
        logger.warning(f"Found {len(trend_locations)} locations that matched the location named \"{location_name}\".")
        return None

    trend_location = trend_locations[0]
    trends_response = twitter.trends_place(trend_location["woeid"], exclude="hashtags")

    if len(trends_response) != 1:
        logger.warning(f"Twitter trends response length was {len(trends_response)}, not 1.")
        return None

    trends = trends_response[0]["trends"]

    return trends
    
if __name__ == "__main__":
    trends = get_trends_by_location_name("Boston")
    # Sorts trends by highest number of tweets first, accounting for None
    trends.sort(reverse=True, key=lambda t: (t['tweet_volume'] is not None, t['tweet_volume']))
    logger.debug([(t['name'], t['tweet_volume']) for t in trends])
