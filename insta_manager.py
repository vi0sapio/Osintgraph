import instaloader
from instaloader.exceptions import InvalidArgumentException
import json
import time
import random
from tqdm import tqdm
from dataclasses import dataclass , field
from typing import Dict
import logging
from data_parser import *
from neo4j_manager import *
from get_session import *
from credential_manager import CredentialManager


@dataclass
class Insta_Config:
    limits: Dict[str, int] = field(default_factory=lambda: {
        "followers": 1000,
        "followees": 1000,
    })
    # batch_mode_allowed: bool = False
    max_request: int = 200
    debug_mode: bool = False

class InstagramManager:
    def __init__(self, config : Insta_Config = Insta_Config()):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.config.debug_mode else logging.INFO)
        self.L = instaloader.Instaloader(compress_json=False)
        self.request_made = 0
        self.credential_manager = CredentialManager()
        self.neo4j_manager = Neo4jManager()
        self.username = ""
        self._login()
        self._initialize_neo4j()


    #############################################################################################
    # Public Features 

    ## Collecting target user's profile and connection data
    def discover(self, target_user: str):
        self._rate_limit()
    
        profile = instaloader.Profile.from_username(self.L.context, target_user)
        user= extract_profile_data(profile) 

        
        self.neo4j_manager.execute_write(self.neo4j_manager.create_user, user)
        self.logger.debug(f"Successfully created user {target_user}")

        if profile.is_private:
            self.logger.error(f"Cannot fetch data. {target_user}'s profile is private.")
            return 
        
        result = {"followers":[], 
                  "followers_batch_mode": False,
                  "followees":[],
                  "followees_batch_mode": False}

        resume_hash = self._get_hash(profile.username)
        for data_type, max_count in self.config.limits.items():
            if max_count == 0:
                    self.logger.info(f"Skipping {data_type} as max_count is 0.")
                    result[f"{data_type}_batch_mode"] = True
            else:
                self.logger.info(f"Fetching {data_type} for {target_user}")
                result[data_type], result[f"{data_type}_batch_mode"]= self._fetch_and_map(profile, data_type, max_count, resume_hash=resume_hash)

        


        if self.config.debug_mode:
            with open(f"{target_user}_followers.json", "w") as json_file:
                json.dump(result['followers'], json_file, indent=4)
            self.logger.debug(f"Follower details saved to {target_user}_followers_batch.json.")


            with open(f"{target_user}_followees.json", "w") as json_file:
                json.dump(result['followees'], json_file, indent=4)
            self.logger.debug(f"Followee details saved to {target_user}_followees_batch.json.")

        
            
        if result['followees']:
            # Write the followees data
            self.neo4j_manager.execute_write(self.neo4j_manager.create_users, result['followees'])
            self.logger.debug("Successfully added followees.")
        if result['followers']:
            # Write the followers data
            self.neo4j_manager.execute_write(self.neo4j_manager.create_users, result['followers'])
            self.logger.debug("Successfully added followers.")
        
        self.neo4j_manager.execute_write(self.neo4j_manager.manage_relationships, user, result)
        self.logger.info("Successfully discovered")


    ## Uncovering the network of target user  
    def explore(self, target_user: str, max_people: int =5):
        result= self.neo4j_manager.execute_read(self.neo4j_manager.find_user, username=target_user)
        if not result:
           
            self.logger.warning(f"User does not exist. Add the user using \"-discover {target_user}\", then come and try again. ")
            return
        
        round = 0
        while round < max_people:
            # Fetch the most popular user based on the order_by criterion (e.g., "followers")
            famous_user = self._famous(target=target_user)
            
            if not famous_user:
                self.logger.warning("No famous users found.")
                break

            # Get the username of the most popular user
            username = famous_user[0].get('username')
            
            if username:
                self.logger.info(f"Discovering the most popular user: {username}")
                try:
                    # Try to discover the user (fetch followers, followees, and write to DB)
                    self.discover(username)
                    self.logger.info(f"Successfully discovered {username}.")
                except Exception as e:
                    self.logger.error(f"Error discovering {username}: {e}")
                    continue  # Skip to the next attempt if an error occurs

            # Optionally, you could add a small sleep to avoid hitting rate limits
            time.sleep(random.uniform(5, 10))  # Adjust the sleep time as needed

            # Increase the round counter
            round += 1
            self.logger.info(f"Round {round} complete.")

    ## Search for undone resume hash and complete them
    def complete_undone_hashes(self, max_rounds: int =3):
        counter = 0
        for record in self._undone_hash():
            if counter == max_rounds:
                break
            while True:
                temp_config = Insta_Config(limits={ 
                    'followers': 0 if record['followers_resume_hash'] == "" else self.config.limits.get('followers', 0),
                    'followees': 0 if record['followees_resume_hash'] == "" else self.config.limits.get('followees', 0)
                })
                with self._temporary_config(temp_config):   
                    self.discover(record['username'])
                resume_hash = self.neo4j_manager.execute_read(self.neo4j_manager.get_resume_hash, record['username'])
                if resume_hash['followers'] == "" and resume_hash['followees'] == "":
                    counter +=1
                    break
    #############################################################################################
    # Internal Features (*For internal use only!!)
    
    ### Session Handling
    
    ## Account Login (This will first try to login via session file, if not found then relogin is needed )
    def _login(self):
        self.user_agent = self.credential_manager.get("INSTAGRAM_USER_AGENT")
        if self.user_agent:
            self.L.context.user_agent = self.user_agent
        # Try to fetch the username from the environment
        self.username = self.credential_manager.get("INSTAGRAM_USERNAME")

        if not self.username:
            self.logger.warning("Instagram Login Required.")
            self._choose_login_method()
            return
        try:        
            self.L.load_session_from_file(self.username)  # Try loading the session file
            self.logger.info(f"✅ Successfully logged in to Instagram as {self.username}.")
        except FileNotFoundError:
            self.logger.warning(f"❌ USER: {self.username} Session file not found")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()
        except CookieFileNotFoundError: 
            self.logger.warning("Cookie file not found. Please check your Firefox cookies file.")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()
        except NoLoginInError:
            self.logger.warning("Make sure you have logged in successfully in Firefox")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()
        except Exception as e:
            self.logger.error(f"Unexpected error occurred: {e}")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()

        
        
    def _choose_login_method(self):
        
        print("[1] Login via Firefox Cookie Session (Recommended – avoids suspicious detection)")
        print("    Just make sure you're already logged into Instagram in Firefox – your session will be auto-extracted.")
        print("[2] Manual Login (Enter your username and password manually)")   
        choice = input("Choose a login method: ")
        try: 
            
            if (choice == "1"):
                self.logger.info("Login via Firefox's Cookie Session")
                self.username = input("Enter your Instagram username: ")
                import_session(get_cookiefile(), None)
                self.L.load_session_from_file(self.username)  # Try loading the session file
                self.logger.info(f"✅ Successfully logged in to Instagram as {self.username}.")
            else:
                self.logger.info("Manual Login")
                self.username = input("Enter your Instagram username: ")
                self.L.interactive_login(self.username)  # Log in interactively
                self.L.save_session_to_file()  # Save session to file for later use
                self.logger.info(f"✅ Successfully logged in to Instagram as {self.username}.")

            self.credential_manager.set("INSTAGRAM_USERNAME", self.username)

        except FileNotFoundError:
            self.logger.warning(f"❌ USER: {self.username} Session file not found")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()
        except CookieFileNotFoundError: 
            self.logger.warning("Cookie file not found. Please check your Firefox cookies file.")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()
        except NoLoginInError:
            self.logger.warning("Make sure you have logged in successfully in Firefox")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()
        except Exception as e:
            self.logger.error(f"Unexpected error occurred: {e}")
            self.logger.warning("Instagram Login required.")
            self._choose_login_method()

      

    ## Neo4j Initialization (This will check if your database constraints exit, if not will  create constriants for your database )
    def _initialize_neo4j(self):
        
        self.neo4j_manager.execute_write(self.neo4j_manager.create_unique_constraint)

    ### Data Fetching 

    ## Fetch and parse user data via Instaloader
    def _fetch_and_map(self, profile, data_type, max_count, resume_hash):
        batch_mode = False
        counter = 0
        data_list = []
        total_items = getattr(profile, data_type)
        total_items = max_count if total_items > max_count else total_items
        new_resume_hash= ""
        # Define a dictionary to map data_type to the corresponding method
        data_methods = {
            'followers': profile.get_followers,
            'followees': profile.get_followees,
        }
        method = data_methods.get(data_type)
        try:
            person_iterator = method()
            if resume_hash[data_type]:
                batch_mode = True
                self.logger.info("Resume from last time...")
                try:
                    person_iterator.thaw(instaloader.load_structure(self.L.context, json.loads(resume_hash[data_type])))
                except InvalidArgumentException as e:
                    person_iterator = method()
                    self.logger.warning(f"{e} for {profile.username}. Restarting from scratch.")
            else:
                self.logger.info("Fetching for first time...")
        
            for person in tqdm(person_iterator, desc=f"Fetching {data_type}", unit="person", total=total_items, ncols=70):
                person_data = map_data(person)
                data_list.append(person_data)
                self.request_made += 1
                counter +=1
                if self.request_made % self.config.max_request == 0:
                    time.sleep(random.uniform(10, 15))
                if counter >max_count:
                    batch_mode = True
                    new_resume_hash = json.dumps(instaloader.get_json_structure(person_iterator.freeze()))

                    break
            resume_hash[data_type] = new_resume_hash
            self._save_hash(id = profile.userid, hash=resume_hash)
            return data_list, batch_mode
        except KeyboardInterrupt:
            instaloader.save_structure_to_file(person_iterator.freeze(), "resume_info.json")


    ## Finds the most popular user based on a given criterion (e.g., followers, date).
    def _famous(self, target: str, limit=100):
        
        self.logger.info("Attempting to find famous person")

        result = self.neo4j_manager.execute_read(self.neo4j_manager.find_famous_by_most_followers, target)
    
        if not result:
            result = self.neo4j_manager.execute_read(self.neo4j_manager.find_famous_by_date, target)

        self.logger.info("Famous person search complete.")
        if not result:

            self.logger.debug("No famous person found.")
            return []
        else:
            processed_results = [{key: record[key] for key in record.keys()} for record in result]
        
            # Adjust time zone if 'last_checked' is present
            for record in processed_results:
                if 'last_checked' in record:
                    record['last_checked'] = record['last_checked'].isoformat()
                 

        # Return results, either one or all based on limit
            return processed_results[:limit] or None

    
    ### Resume Hash Logic 

    ## Search for undone resume hash
    def _undone_hash(self, limit=100):
        
        result = self.neo4j_manager.execute_read(self.neo4j_manager.find_resume_hash, limit=limit)
        if not result:
            self.logger.info("No unfinished hashes found.")
            return
        
        for record in result:
            print(record)
            yield record

    ## Save resume hash to the associated user
    def _save_hash(self, id, hash):
        
        self.neo4j_manager.execute_write(self.neo4j_manager.save_resume_hash, id, hash)

    ## Get resume hash from the choosen user
    def _get_hash(self, username):
        
        resume_hash = self.neo4j_manager.execute_read(self.neo4j_manager.get_resume_hash, username)
        
        return resume_hash
    

    ### Temporary Configuration 

    ## Temporary config 
    @contextmanager
    def _temporary_config(self, new_config):

        original_config = self.config
        self.config = new_config

        try:
            #Yield control to the "with" block
            yield
        finally:

            self.config = original_config

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