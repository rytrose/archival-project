import os

INTERNET_ARCHIVE_USERNAME = os.environ.get("INTERNET_ARCHIVE_USERNAME")
INTERNET_ARCHIVE_PASSWORD = os.environ.get("INTERNET_ARCHIVE_PASSWORD", "ryXo!q$jKXc80c7RQuJO")
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_KEY_SECRET = os.environ.get("TWITTER_API_KEY_SECRET")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

if None in [
    INTERNET_ARCHIVE_USERNAME, 
    INTERNET_ARCHIVE_PASSWORD, 
    TWITTER_API_KEY, 
    TWITTER_API_KEY_SECRET,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY
]:
    raise Exception(f"unable to load secrets")