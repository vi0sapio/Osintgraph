# from argparse import ArgumentParser
from glob import glob
import os
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect
import logging

try:
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")

class CookieFileNotFoundError(Exception):
    """Raised when the Firefox cookie file is not found."""
    pass

class NoLoginInError(Exception):
    """Raised when login in Firefox is not successful."""
    pass

def get_cookiefile():
    default_cookiefile = {
        "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
        "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
    }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")
    cookiefiles = glob(expanduser(default_cookiefile))
    if not cookiefiles:
        raise CookieFileNotFoundError("No Firefox cookies.sqlite file found. Use -c COOKIEFILE.")
    return cookiefiles[0]


def import_session(cookiefile, sessionfile):
    # print("Using cookies from {}.".format(cookiefile))
    logger = logging.getLogger(__name__)
    # The sessionfile is the full path, extract the username
    username_to_import = os.path.basename(sessionfile)

    conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
    try:
        cookie_data = conn.execute(
            "SELECT host, name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
        ).fetchall()
    except OperationalError:
        cookie_data = conn.execute(
            "SELECT host, name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
        ).fetchall()
    
    # Create a temporary Instaloader instance to get the user ID
    temp_loader = Instaloader(max_connection_attempts=1)
    temp_loader.context.log = lambda *args, **kwargs: None
    try:
        profile = temp_loader.check_profile_id(username_to_import)
        user_id = str(profile.userid)
    except Exception as e:
        logger.error(f"Could not retrieve profile for {username_to_import}. Make sure the username is correct. Error: {e}")
        raise NoLoginInError(f"Failed to find profile for {username_to_import}.")

    # Filter cookies to only include those for the target user ID
    user_cookies = {}
    user_host = None

    # Find the host associated with the target user's ds_user_id
    for host, name, value in cookie_data:
        if name == 'ds_user_id' and value == user_id:
            user_host = host
            user_cookies[name] = value
            break

    # If found, get the sessionid and csrftoken for that same host
    if user_host:
        for host, name, value in cookie_data:
            if host == user_host and name in ['sessionid', 'csrftoken']:
                user_cookies[name] = value

        
    # Fallback: If sessionid or csrftoken were not found with the specific host,
    # try a more lenient match. This helps if cookies are on different subdomains.
    if 'sessionid' not in user_cookies or 'csrftoken' not in user_cookies:
        # This will overwrite with the last found, which is often the most recent
        for host, name, value in cookie_data:
            if name in ['sessionid', 'csrftoken']:
                user_cookies[name] = value

    instaloader = Instaloader(max_connection_attempts=1)
    instaloader.context.log = lambda *args, **kwargs: None
    instaloader.context._session.cookies.update(user_cookies)
    username = instaloader.test_login()
    if not username:
        raise NoLoginInError("Not logged in. Are you logged in successfully in Firefox?")
    # print("Imported session cookie for {}.".format(username))
    instaloader.context.username = username
    instaloader.save_session_to_file(sessionfile)