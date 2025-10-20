import asyncio
import json
import os
import logging
from fake_useragent import UserAgent
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List

import instaloader
from instaloader.exceptions import InvalidArgumentException, ProfileNotExistsException, TooManyRequestsException
from tqdm import tqdm
from google.api_core.exceptions import ResourceExhausted, TooManyRequests

from .credential_manager import get_credential_manager
from .get_session import *
from .services.llm_analyzer import LLMAnalyzer
from .custom_iterator import ResumableNodeIterator
from .neo4j_manager import *
from .utils.data_extractors import (
    extract_comment_data,
    extract_post_data,
    extract_profile_data,
    extract_user_metadata,
)
from .constants import (
    SESSIONS_DIR
)
from .migrate_hashes import migrate_resume_hashes




@dataclass
class Insta_Config:
    limits: Dict[str, int] = field(default_factory=lambda: {
        'followers': 1000,
        'followees': 1000,
        'posts'     : 10,
    })
    # batch_mode_allowed: bool = False
    skip_followers: bool = False
    skip_followees: bool = False
    skip_posts: bool = False
    skip_posts_analysis: bool = False
    skip_account_analysis: bool = False
    skip_account: str = "nature__click_pic"
    max_request: int = 200
    debug_mode: bool = False
    force: List[str] = field(default_factory=list)
    auto_login: bool = True

class InstagramManager:
    def __init__(self, config : Insta_Config = Insta_Config(), account_username: str = None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.config.debug_mode else logging.INFO)
        self.L = instaloader.Instaloader(
            compress_json=False,
            dirname_pattern=os.path.join(SESSIONS_DIR, "{target}"),
            filename_pattern="{profile}_{mediaid}"
        )
        self.L.context.error = lambda *args, **kwargs: None

        self.request_made = 0
        self.credential_manager = get_credential_manager()
        self._neo4j_manager = None  # private attribute for lazy init
        self.llmanalyzer = LLMAnalyzer()
        self.key_lock = asyncio.Lock()
        self.has_gemini_key = bool(self.credential_manager.get("GEMINI_API_KEY"))

        self.accounts = self.credential_manager.get("INSTAGRAM_ACCOUNTS", [])
        self.current_account_index = 0
        self.tried_all_accounts = False

        if account_username:
            if account_username in self.accounts:
                self.current_account_index = self.accounts.index(account_username)
            else:
                self.logger.warning(f"Account '{account_username}' not found. Using default account.")
        elif default_account := self.credential_manager.get("DEFAULT_INSTAGRAM_ACCOUNT"):
            if default_account in self.accounts:
                self.current_account_index = self.accounts.index(default_account)

        self.username = self.accounts[self.current_account_index] if self.accounts else ""

        if self.config.auto_login:
            _ = self.neo4j_manager
            self._login(self.username)
            self._initialize_neo4j()

    @property
    def neo4j_manager(self):
        """Lazily create Neo4jManager when accessed."""
        if self._neo4j_manager is None:
            self._neo4j_manager = Neo4jManager()
        return self._neo4j_manager
    
    #############################################################################################
    # Public Features 

    ## Collecting target user's profile and connection data
    def discover(self, target_user: str, account_username: str = None):
        data_types = ['followers', 'followees', 'posts', 'posts_analysis', 'account_analysis']
        self._rate_limit()
        
        try:
            self.logger.info("PROFILE -")
            self.logger.info("⧗  Starting to fetch Profile...")
            profile = instaloader.Profile.from_username(self.L.context, target_user)
        except TooManyRequestsException:
            self.logger.warning(f"Account '{self.username}' is rate-limited.")
            if self._switch_account():
                self.discover(target_user, account_username) # Retry with new account
            else:
                self.logger.error("All accounts are rate-limited. Please wait and try again later.")
            return
        except ProfileNotExistsException:
            self.logger.warning(f"Instagram user: {target_user} does not exist. Make sure the username is correct.")

        try:
            user = extract_profile_data(profile)
        except KeyError:
            self.logger.error("Your Instagram session might be expired. Try the following:\n"
                "                       1. If you log in via Firefox cookie session, re-login to your Instagram account in Firefox and run `osintgraph reset instagram`.\n"
                "                       2. If you log in manually, simply run `osintgraph reset instagram` to re-login."
            )
            return
        existing_user = self.neo4j_manager.execute_read(self.neo4j_manager.get_person_by_username, target_user)
        if isinstance(existing_user, dict):
            user["account_analysis"] = existing_user.get("account_analysis")

        
        
        self.neo4j_manager.execute_write(self.neo4j_manager.create_user, user)
        
        self.logger.info("✓  Profile fetched")
                
        if user["followees"] == 0 :
            self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, target_user, **{"followees": True})
        if user["followers"] == 0 :
            self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, target_user, **{"followers": True})
        if user["mediacount"] == 0 :
            self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, target_user, **{"posts": True})
            self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, target_user, **{"posts_analysis": True})

        if profile.is_private and not profile.followed_by_viewer:
            self.logger.error(f"Cannot fetch data. {target_user}'s profile is private. Follow the user to access their profile.")
            return
        
        force_all = "all" in self.config.force
        for data_type in data_types:
            print()
            self.logger.info(f"{data_type.upper()} -")
            completions = self.neo4j_manager.execute_read(self.neo4j_manager.get_completion_flags, target_user)
                
            if not getattr(self.config, f"skip_{data_type}"):
                force_this = force_all or data_type in self.config.force
                
                if force_this:
                    
                    self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, target_user, **{data_type: False})

                if force_this or not completions.get(data_type, False):

                    if data_type == "posts_analysis":
                        if self.has_gemini_key:
                            self.analyze_post(user["username"])
                        else:
                            self.logger.warning("⤷  Skipped posts_analysis (no Gemini key)")

                    elif data_type == "account_analysis":
                        if self.has_gemini_key:
                            self.analyze_account(user["username"])
                        else:
                            self.logger.warning("⤷  Skipped account_analysis (no Gemini key)")
                    else:
                        self._fetch_and_map(profile, data_type)

                else:
                    self.logger.info(f"⤷  {data_type.capitalize()} was already completed — skipping")
            else:
                self.logger.info(f"⤷  Skipped {data_type.capitalize()}")

            # Add a human-like pause between scraping different data types
            if data_type != data_types[-1]: # Don't sleep after the last item
                time.sleep(random.uniform(5, 15))

        

        # if self.config.debug_mode:
        #     with open(f"{target_user}_followers.json", "w") as json_file:
        #         json.dump(result['followers'], json_file, indent=4)
        #     self.logger.debug(f"Follower details saved to {target_user}_followers_batch.json.")


        #     with open(f"{target_user}_followees.json", "w") as json_file:
        #         json.dump(result['followees'], json_file, indent=4)
        #     self.logger.debug(f"Followee details saved to {target_user}_followees_batch.json.")
        


    ## Uncovering the network of target user  
    def explore(self, target_user: str, max_people: int = 5, account_username: str = None):
        result = self.neo4j_manager.execute_read(
            self.neo4j_manager.get_person_by_username, username=target_user
        )
        if not result:
            self.logger.warning(f"User does not exist. Add the user using \"discover {target_user}\", then come and try again.")
            return

        # Fetch famous users once
        famous_users = self._famous(target=target_user)
        if not famous_users:
            self.logger.warning("No famous users found.")
            return

        step = 0
        seen = set()

        for user in famous_users:
            username = user.get('username')
            if not username or username in seen:
                continue

            self.logger.info(f"Discovering: {username}")
            if username == self.config.skip_account:
                self.logger.info(f"⤷  Skipped {username} as per configuration.")
                seen.add(username)
                step += 1
                print()
                self.logger.info(f"Step {step}/{max_people} complete.")
                continue

            try:
                self.discover(username, account_username=account_username)
                # self.logger.info(f"Successfully discovered {username}.")
            except Exception as e:
                self.logger.error(f"Error discovering {username}: {e}")
                continue

            seen.add(username)
            step += 1
            print()
            self.logger.info(f"Step {step}/{max_people} complete.")
            time.sleep(random.uniform(5, 10))  # Avoid rate limits

            if step >= max_people:
                break

    #############################################################################################
    # Internal Features
    
    ### Session Handling
    
    ## Account Login (This will first try to login via session file, if not found then relogin is needed )
    def _login(self, account_username: str = None):
        self.user_agent = self.credential_manager.get("INSTAGRAM_USER_AGENT")

        if self.user_agent:
            self.L.context.user_agent = self.user_agent
        else:
            try:
                ua = UserAgent()
                self.user_agent = ua.random
                self.L.context.user_agent = self.user_agent
                self.logger.info(f"✓  No User-Agent set, using a random one: {self.user_agent}")
                self.credential_manager.set("INSTAGRAM_USER_AGENT", self.user_agent)
            except Exception as e:
                self.logger.warning(f"Could not generate a random User-Agent: {e}. Using Instaloader's default.")
        # Try to fetch the username from the environment
        self.username = account_username

        if self.username and self.username not in self.accounts:
            self.logger.error(f"Account '{self.username}' not found in configured accounts. Please run 'osintgraph setup instagram'.")
            exit(1)

        if not self.username:
            if self.accounts:
                self.logger.warning("⚠ No default Instagram account is set, and --account was not specified.")
                self.logger.info("Please set a default account via 'osintgraph setup instagram'.")
                self.username = self.accounts[0] # Fallback to the first account
            else:
                self.logger.warning("⚠  Instagram Login Required.")
                self.username = self.choose_login_method()

        try:
            self.L.load_session_from_file(self.username, filename=os.path.join(SESSIONS_DIR, self.username))
            self.logger.info(f"✓  Logged in as {self.username}.")
        except FileNotFoundError:
            self.logger.warning(f"✗ USER: {self.username} Session file not found")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()
        except CookieFileNotFoundError: 
            self.logger.warning("Cookie file not found. Please check your Firefox cookies file.")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()
        except NoLoginInError:
            self.logger.warning("Make sure you have logged in successfully in Firefox")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()
        except Exception as e:
            self.logger.error(f"Unexpected error occurred: {e}")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()

    def _switch_account(self):
        if len(self.accounts) <= 1:
            self.logger.warning("No other accounts available to switch to.")
            return False

        if self.tried_all_accounts:
            self.logger.error("All accounts have been tried and are rate-limited. Pausing for 10 minutes.")
            time.sleep(600)
            self.tried_all_accounts = False # Reset after waiting

        self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
        new_username = self.accounts[self.current_account_index]
        
        # Check if we have looped through all accounts
        default_account = self.credential_manager.get("DEFAULT_INSTAGRAM_ACCOUNT") or self.accounts[0]
        if new_username == (self.credential_manager.get("DEFAULT_INSTAGRAM_ACCOUNT") or self.accounts[0]):
             self.tried_all_accounts = True

        self.logger.info(f"Switching to account: {new_username}")
        self.username = new_username
        self._login(self.username)
        
        return True

        
    def choose_login_method(self):
        self.logger.info(
            "[1] Login via Firefox Cookie Session (Recommended – avoids suspicious detection)\n"
            "                       Just make sure you're already logged into Instagram in Firefox – your session will be auto-extracted.\n"
            "                       [2] Manual Login (Enter your username and password manually)"
        )
        self.logger.info("Choose a login method: ")
        choice = input("                       > ")
        try: 
            new_username = None
            if (choice == "1"):
                self.logger.info("Login via Firefox's Cookie Session")
                self.logger.info("Enter your Instagram username:")
                new_username = input("                       > ").strip()
                if not new_username:
                    self.logger.error("Username cannot be empty.")
                    return self.choose_login_method()
                self.username = new_username
                import_session(get_cookiefile(), os.path.join(SESSIONS_DIR, new_username))
                self.L.load_session_from_file(new_username, filename=os.path.join(SESSIONS_DIR, new_username))
                self.logger.info(f"✓  Logged in as {self.username}.")
            else:
                self.logger.info("Manual Login")
                self.logger.info("Enter your Instagram username:")
                self.username = input("                       > ")
                self.L.interactive_login(self.username)  # Log in interactively
                self.L.save_session_to_file(os.path.join(SESSIONS_DIR, self.username))
                self.logger.info(f"✓  Logged in as {self.username}.")

            accounts = self.credential_manager.get("INSTAGRAM_ACCOUNTS", [])
            if self.username not in accounts:
                # Ensure 'accounts' is a list, even if it was stored as a string
                if not isinstance(accounts, list):
                    self.logger.warning("Correcting malformed 'INSTAGRAM_ACCOUNTS' in credentials.")
                    accounts = [accounts] if accounts else []
                accounts.append(self.username)
                self.credential_manager.set("INSTAGRAM_ACCOUNTS", accounts)
            if not self.credential_manager.get("DEFAULT_INSTAGRAM_ACCOUNT"):
                self.credential_manager.set("DEFAULT_INSTAGRAM_ACCOUNT", self.username)

            return self.username

        except FileNotFoundError:
            self.logger.warning(f"✗ USER: {self.username} Session file not found")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()
        except CookieFileNotFoundError: 
            self.logger.warning("Cookie file not found. Please check your Firefox cookies file.")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()
        except NoLoginInError:
            self.logger.warning("Make sure you have logged in successfully in Firefox")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()
        except Exception as e:
            self.logger.error(f"Unexpected error occurred: {e}")
            self.logger.warning("Instagram Login required.")
            self.choose_login_method()

      

    ## Neo4j Initialization (This will check if your database constraints exit, if not will  create constriants for your database )
    def _initialize_neo4j(self):
        
        self.neo4j_manager.execute_write(self.neo4j_manager.create_unique_constraint)
        self.neo4j_manager.execute_write(self.neo4j_manager.create_vector_indexes)

    ### Data Fetching 

    ## Fetch and parse user data via Instaloader
    def _fetch_and_map(self, profile, data_type):
        max_count = self.config.limits[data_type]
        if max_count == 0:
            self.logger.info(f"Skipping {data_type} as max_count is 0.")
            return

        options = {
            'followers': {
                'method' : profile.get_followers,
                'count'  : profile.followers
            },
            'followees': {
                'method' : profile.get_followees,
                'count'  : profile.followees
            },
            'posts'    : {
                'method' : profile.get_posts,
                'count'  : profile.mediacount
            }
            
        }
        counter = 0
        total_items = min(max_count, options[data_type]['count'])
        resume_hash_created = False

        try:
            BATCH_SIZE = 100

            if data_type in ("followers", "followees"):
                
                method = options[data_type]['method']
                base_iterator = method()

                # Use our new resumable iterator
                iterator = ResumableNodeIterator(
                    node_iterator=base_iterator,
                    neo4j_manager=self.neo4j_manager,
                    profile_id=profile.userid,
                    scraper_username=self.username,
                    data_type=data_type,
                    total_count=total_items
                )

                batch_data = []

                initial_count = getattr(iterator.node_iterator, '_total_index', 0) if iterator.is_resumed else 0

                for person in tqdm(iterator, desc=f"Fetching {data_type}", unit="people", total=total_items, initial=initial_count, ncols=70):
                    
                    if counter >= max_count:
                        resume_hash_created =True
                        break
                    
                    
                    person_data = extract_user_metadata(person)
                    batch_data.append(person_data)

                    if len(batch_data) >= BATCH_SIZE:
                        self.neo4j_manager.execute_write(self.neo4j_manager.create_users, batch_data)
                        relationship_data = {data_type: {"data": batch_data, "batch_mode": True}}
                        self.neo4j_manager.execute_write(self.neo4j_manager.manage_follow_relationships, profile.userid, relationship_data)
                        batch_data = []

                    self._request_made_and_wait()
                    counter +=1

                if batch_data: # Process any remaining items in the last batch
                    self.neo4j_manager.execute_write(self.neo4j_manager.create_users, batch_data)
                    self.logger.debug(f"Successfully added {data_type}.")
                    relationship_data = {data_type: {"data": batch_data, "batch_mode": True}}
                    self.neo4j_manager.execute_write(self.neo4j_manager.manage_follow_relationships, profile.userid, relationship_data)

                # This logic is now handled by the iterator's clear_resume_state
                # if not resume_hash_created:
                #     self.neo4j_manager.execute_write(self.neo4j_manager.manage_follow_relationships, profile.userid, {data_type: {"data": [], "batch_mode": False}})
                if resume_hash_created:
                    self.logger.info(f"✓  {data_type.capitalize()} fetched (partially)")
                    self.logger.info(f"✎  Saved resume point for {data_type.capitalize()}")
                else:
                    self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, profile.username, **{data_type: True} )
                    self.logger.info(f"✓  {data_type.capitalize()} fetched")


            elif data_type == "posts":
                method = options[data_type]['method']
                base_iterator = method()

                # Use our new resumable iterator for posts as well
                iterator = ResumableNodeIterator(
                    node_iterator=base_iterator,
                    neo4j_manager=self.neo4j_manager,
                    profile_id=profile.userid,
                    scraper_username=self.username,
                    data_type=data_type,
                    total_count=total_items
                )

                for post in tqdm(iterator, desc=f"Fetching {data_type}", unit="post", total=total_items, ncols=70):
                    
                    if counter >= max_count:
                        resume_hash_created =True
                        break
                    
                    post.comments_details = {
                        'comments_list'   : [],
                        'commentors_list' : [],
                        'likers_list'      : [],
                    }
                    post.likers_list = []

                    for comment in post.get_comments():
                        post.comments_details['comments_list'].append({'reply_id': None , **extract_comment_data(comment)})
                        post.comments_details['commentors_list'].append(extract_user_metadata(comment.owner))
                        
                        for liker in comment.likes:
                            post.comments_details['likers_list'].append({'liked_comment_id': int(comment.id), **extract_user_metadata(liker)})
                        
                        for ans in comment.answers:
                            post.comments_details['comments_list'].append({'reply_id': int(comment.id), **extract_comment_data(ans)})
                            post.comments_details['commentors_list'].append(extract_user_metadata(ans.owner))
                    
                    for liker in post.get_likes():
                        post.likers_list.append({'liked_post_id': int(post.mediaid), **extract_user_metadata(liker)})
                        
                    post_data = extract_post_data(post)
                    self.neo4j_manager.execute_write(self.neo4j_manager.manage_post_relationships, post_data)
                    self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, profile.username, **{"posts_analysis": False})
                    self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, profile.username, **{"account_analysis": False})

                    self._request_made_and_wait(is_post=True)
                    counter +=1

                    
                if resume_hash_created:
                    self.logger.info(f"✓  {data_type.capitalize()} fetched (partially)")
                    self.logger.info(f"✎  Saved resume point for {data_type.capitalize()}")
                else:
                    self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, profile.username, **{data_type: True} )
                


        except KeyboardInterrupt:
            # instaloader.save_structure_to_file(iterator.freeze(), "resume_info.json")
            pass

        except TooManyRequestsException:
            self.logger.warning(f"Account '{self.username}' is rate-limited during '{data_type}' fetch.")
            if self._switch_account():
                self.logger.info("Retrying fetch with new account...")
                self._fetch_and_map(profile, data_type) # Retry the operation
            else:
                self.logger.error("All accounts are rate-limited. Aborting fetch.")

    def analyze_post(self, username: str):
        self.logger.info(f"⧗  Starting to analyze Posts with LLM...")
        total_items = self.neo4j_manager.execute_read(self.neo4j_manager.count_posts_unanalyzed_by_username, username)
        iterator = self.neo4j_manager.get_posts_unanalyzed_by_username(username)
        try:
            for post in tqdm(iterator, desc=f"Analyzing Post", unit="post", total=total_items, ncols=70):
                self.llmanalyzer.process_post(self, post)
            
            self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, username, **{"posts_analysis": True})
            self.logger.info(f"✓  Posts Analysis Completed")
            return True
        
        except (ResourceExhausted, TooManyRequests) as e:
            self.logger.warning(f"⚠  Rate limit hit. Post analysis Incomplete.")
            return False
        except RuntimeError as e:
            self.logger.error(f"⚠  Runtime error. Post analysis Incomplete.")
            return False
        except Exception as e:
            if "API_KEY_INVALID" in str(e):
                    self.logger.error(f"⚠  Gemini API key is invalid. Please run `osintgraph reset gemini` to update it.")
                    return False
            self.logger.error(f"⚠  Post analysis Failed. Unknown error  {e}")
            return False


    def analyze_account(self, username: str):
        completions = self.neo4j_manager.execute_read(self.neo4j_manager.get_completion_flags, username)
        self.logger.info(f"⧗  Starting to analyze Account with LLM...")
        
        if not completions.get("posts_analysis", False):
            self.logger.warning(f"⚠  Account analysis requires complete post analysis — running now.")
            post_success = self.analyze_post(username)
            if not post_success:
                self.logger.error("⚠ Post analysis failed — skipping account analysis.")
            return 
        
        
        try:
            self.llmanalyzer.process_account(self, username)
            self.neo4j_manager.execute_write(self.neo4j_manager.set_completion_flags, username, **{"account_analysis": True})
            self.logger.info(f"✓  Account Analysis Completed")
        except (ResourceExhausted, TooManyRequests) as e:
            self.logger.warning(f"⚠  Rate limit hit. Post analysis Incomplete.")
        except RuntimeError as e:
            self.logger.error(f"⚠  Runtime error. Post analysis Incomplete.")
        except Exception as e:
            self.logger.error(f"⚠  Post analysis Failed. Unknown error  {e}")

    ## Finds the most popular user based on a given criterion (e.g., followers, date).
    def _famous(self, target: str, limit: int = 100):
        """
        Find a popular user (by followers count) from the followees of `target`
        who still requires further discovery (incomplete profile or graph data).
        """
        self.logger.info("Finding top followees for discovery...")

        # Try users with incomplete profile
        result = self.neo4j_manager.execute_read(
            self.neo4j_manager.find_incomplete_followees_by_popularity, target
        )

        # Fallback: users with incomplete followers/followees/posts
        if not result:
            self.logger.debug("No incomplete-profile users found, checking graph-incomplete ones.")
            result = self.neo4j_manager.execute_read(
                self.neo4j_manager.find_incomplete_targets, target
            )

        if not result:
            # self.logger.debug("No famous user found.")
            return []

        # Return at most `limit` results
        return [record.data() for record in result][:limit]

    
    ### Resume Hash Logic 
    def maybe_resume_iterator(self, method, data_type: str, username: str):
        # This function is now replaced by the ResumableNodeIterator
        pass


    def _request_made_and_wait(self, is_post: bool = False):
        """
        Increments request counter and enforces rate limits with jitter.
        """
        self.request_made += 1

        # Short, random pause between each request to mimic human behavior
        time.sleep(random.uniform(0.5, 2.5))

        # Longer pause after a configurable number of requests
        if self.request_made % self.config.max_request == 0:
            self.logger.info("Proactive rate limit hit. Attempting to switch accounts...")
            if not self._switch_account():
                # If switching fails (e.g., all accounts are used), then pause.
                sleep_duration = random.uniform(5 * 60, 10 * 60)  # 5 to 10 minutes
                self.logger.info(f"All accounts tried. Pausing for {int(sleep_duration / 60)} minutes...")
                time.sleep(sleep_duration)

    ### Temporary Configuration 

    ## Temporary config 
    # @contextmanager
    # def _temporary_config(self, new_config):

    #     original_config = self.config
    #     self.config = new_config

    #     try:
    #         #Yield control to the "with" block
    #         yield
    #     finally:

    #         self.config = original_config

    ### Rate limiting

    ## Rate limit
    def _rate_limit(self):
        if self.request_made > 2000:
            self.logger.info("Count exceeded 2000. Pausing for 10 minutes before continuing session.")
                
            # Save the session before sleeping
            self.L.save_session_to_file()
            # self.logger.info("Session saved. Sleeping for 10 minutes.")
            
            time.sleep(600)  # Sleep for 10 minutes

            # After sleep, reload the session to continue
            self.L.load_session_from_file(self.username)
            self.logger.info("Session reloaded after 10 minutes sleep.")
