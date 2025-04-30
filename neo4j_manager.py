from neo4j import GraphDatabase
from contextlib import contextmanager
import logging
from neo4j.exceptions import Neo4jError,ServiceUnavailable
from dataclasses import dataclass
from credential_manager import CredentialManager

@dataclass
class Neo4j_Config:
    debug_mode: bool = False


class Neo4jManager:
    def __init__(self, config: Neo4j_Config = Neo4j_Config()):
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG if self.config.debug_mode else logging.INFO)
        self.credential = CredentialManager()

        self.driver = None
        self._load_or_prompt_credentials()        
        self._connect_to_neo4j()
            

    def _load_or_prompt_credentials(self):
        uri = self.credential.get("NEO4J_URI")
        username = self.credential.get("NEO4J_USERNAME")
        password = self.credential.get("NEO4J_PASSWORD")

        if not uri or not username or not password:
            self.logger.warning("Neo4j database setup is incomplete. Please enter the following Neo4j details:")
            uri = input("NEO4J_URI: ")
            username = input("NEO4J_USERNAME: ")
            password = input("NEO4J_PASSWORD: ")

        self.URI = uri
        self.AUTH = (username, password)

    def _connect_to_neo4j(self):
        try:
            self.driver = GraphDatabase.driver(self.URI, auth=self.AUTH)
            self.driver.verify_connectivity()
            self.logger.info("✅ Successfully connected to Neo4j")

            # Only save credentials after successful connection
            self.credential.set("NEO4J_URI", self.URI)
            self.credential.set("NEO4J_USERNAME", self.AUTH[0])  # username
            self.credential.set("NEO4J_PASSWORD", self.AUTH[1])  # password
        except (ServiceUnavailable, Exception) as e:
            self.logger.error(f"❌ Failed to connect to Neo4j: {e}")
            self._handle_failed_connection()

    def _handle_failed_connection(self):
        self.logger.warning("Connection to Neo4j failed. Please re-enter your credentials.")
        self.credential.set("NEO4J_URI", "")
        self.credential.set("NEO4J_USERNAME", "")
        self.credential.set("NEO4J_PASSWORD", "")
        self._load_or_prompt_credentials()
        self._connect_to_neo4j()
    
    # Function to get session
    @contextmanager
    def get_session(self):
        
        # Create the session
        session = self.driver.session(database="neo4j")
        try:

            yield session  # Yield the session for use
        except Exception as e:
            self.logger.error(f"Error during Neo4j session: {e}")
            raise
        finally:
            session.close()  # Ensure session is closed when done

    def execute_read(self, operation, *args, **kwargs):
        """Centralized method for read operations."""
        with self.get_session() as session:
            return session.execute_read(operation, *args, **kwargs)
    
    def execute_write(self, operation, *args, **kwargs):
        """Centralized method for write operations."""
        with self.get_session() as session:
            session.execute_write(operation, *args, **kwargs)
    def create_unique_constraint(self, session):
        existing_constraints = session.run("SHOW CONSTRAINTS")
        existing_names = [record["name"] for record in existing_constraints]
        
        if "p_id_unique" not in existing_names or "p_username_unique" not in existing_names:
            if "p_id_unique" not in existing_names:
                session.run("""
                CREATE CONSTRAINT p_id_unique FOR (p:Person) REQUIRE p.id IS UNIQUE
            """)
                
            if "p_username_unique" not in existing_names:
                session.run("""
                CREATE CONSTRAINT p_username_unique FOR (p:Person) REQUIRE p.username IS UNIQUE
            """)
        
            self.logger.info("First time initialize successfully")
        

        

    def create_users(self, session, users):
        
        self.logger.debug("Attempting to update NEO4J db with users")

        session.run("""
            WITH $users AS users
            UNWIND users AS user
            MERGE (f:Person {id: user.id}) 
            ON CREATE SET
                f.followers_resume_hash = "",
                f.followees_resume_hash = ""
            SET
                f.username = user.username,
                f.fullname = user.full_name,
                f.profile_pic_url = user.profile_pic_url,
                f.is_verified = user.is_verified,
                f.has_full_metadata = user._has_full_metadata,
                f.has_public_story = user._has_public_story
        
        """, users=users)


    def create_user(self, session, user):
        
        self.logger.debug(f"Attempting to update NEO4J db with adding {user['username']}")
        session.run("""
        MERGE (p:Person {id: $id})
        ON CREATE SET
            p.followers_resume_hash = "",
            p.followees_resume_hash = ""
        SET 
            p.username = $username,
            p.fullname = $fullname,
            p.bio = $bio,
            p.biography_mentions = $biography_mentions,
            p.biography_hashtags = $biography_hashtags,
            p.blocked_by_viewer = $blocked_by_viewer,
            p.business_category_name = $business_category_name,
            p.external_url = $external_url,
            p.followed_by_viewer = $followed_by_viewer,
            p.followees = $followees,
            p.followers = $followers,
            p.follows_viewer = $follows_viewer,
            p.has_blocked_viewer = $has_blocked_viewer,
            p.has_highlight_reels = $has_highlight_reels,
            p.has_public_story = $has_public_story,
            p.is_business_account = $is_business_account,
            p.is_private = $is_private,
            p.is_verified = $is_verified,
            p.profile_pic_url = $profile_pic_url,
            p.profile_pic_url_no_iphone = $profile_pic_url_no_iphone,
            p.mediacount = $mediacount,
            p.has_requested_viewer = $has_requested_viewer,
            p.last_checked = datetime()
        
            

        """, user)

    def find_user(self, session, username):
        query = """
            MATCH (p:Person {username: $username})
            RETURN p
        """
        result = session.run(query, username=username)
        record =  result.single()
        if record:
            user_node = record["p"]
            return dict(user_node)  # Convert the node's properties to a dictionary
        else:
            return None
    
    def find_famous_by_most_followers(self, session, username):
        query = """
            WITH $username AS username
            MATCH (target:Person {username: $username})-[:FOLLOWS]->(p:Person)
            WHERE COALESCE(p.is_private, False) = False AND p.last_checked IS NULL
            MATCH (p)<-[:FOLLOWS]-(f:Person)
            RETURN p.username AS username, COUNT(f) AS followers_count, p.last_checked
            ORDER BY followers_count DESC
        """
        result = session.run(query, username=username)
        return [record for record in result]

    def find_famous_by_date(self, session, username):
        query = """
            MATCH (target:Person {username: $username})-[:FOLLOWS]->(p:Person)
            WHERE COALESCE(p.is_private, False) = False AND p.last_checked IS NOT NULL
            MATCH (p:Person)<-[:FOLLOWS]-(f:Person) 
            WITH p, COUNT(f) AS followers_count
            ORDER BY p.last_checked ASC
            RETURN p.username AS username, followers_count, p.last_checked AS last_checked
        """
        result = session.run(query, username=username)
        return [record for record in result]

    def save_resume_hash(self, session, id, hash):
        session.run("""
            MATCH (p:Person {id: $id}) 
            SET p.followers_resume_hash = $followers_resume_hash
            SET p.followees_resume_hash = $followees_resume_hash
            """,id=id, followers_resume_hash = hash['followers'], followees_resume_hash = hash['followees']
        )
    # def save_resume_hash_v2(self, session, username, resume_hash):
        
    #     followers_resume_hash = resume_hash.get('followers', "")
    #     followees_resume_hash = resume_hash.get('followees', "")
    #     session.run("""
    #         MATCH (p:Person {username: $username})
    #         SET p.followers_resume_hash = $followers_resume_hash
    #         SET p.followees_resume_hash = $followees_resume_hash
    #         REMOVE p.resume_hash
    #         """,username=username, followers_resume_hash = followers_resume_hash, followees_resume_hash = followees_resume_hash
    #     )

    def get_resume_hash(self, session, username):
    
        try: 
            result = session.run("""
                MATCH (p:Person{username: $username})
                WHERE (p.followers_resume_hash IS NOT NULL AND p.followers_resume_hash <> "")
                OR (p.followees_resume_hash IS NOT NULL AND p.followees_resume_hash <> "")
                RETURN 
                        p.followers_resume_hash AS followers,
                        p.followees_resume_hash AS followees
            """, username=username)
            record = result.single()
            if record is None:
                return {
                "followers": "" ,
                "followees": "" 
                } 
             
            record_dict = {
            "followers": record["followers"] ,
            "followees": record["followees"] 
            }
            
            return record_dict
        except Neo4jError as e:
                self.logger.warning(f"Property not found for ID {id}, using default value.")
    def find_resume_hash(self, session, limit=100):
    
        try: 
            result = session.run("""
                MATCH (p:Person)
                WHERE (p.followers_resume_hash IS NOT NULL AND p.followers_resume_hash <> "")
                OR (p.followees_resume_hash IS NOT NULL AND p.followees_resume_hash <> "")
                RETURN p.username AS username, 
                    p.followers_resume_hash AS followers_resume_hash,
                    p.followees_resume_hash AS followees_resume_hash
                LIMIT $limit
            """, limit=limit)
            
            return [record for record in result]
        except Neo4jError as e:
                self.logger.warning(f"Property not found for ID {id}, using default value.")
    def manage_relationships(self, session, user, result):
        user_id = user['id']
        followees_id = [followee['id'] for followee in result['followees']]
        followers_id = [follower['id'] for follower in result['followers']]

        # Use session.write_transaction() to manage write operations in a single transaction
        try:
            with self.get_session() as session:
                
                session.execute_write(self.new_followees, user_id, followees_id)

                if not result['followees_batch_mode']:
                    session.execute_write(self.unfollowed_followees, user_id, followees_id)
                    session.execute_write(self.refollowed_followees, user_id, followees_id)

                session.execute_write(self.new_followers, user_id, followers_id)
                
                if not result['followers_batch_mode']:
                    session.execute_write(self.unfollowed_followers, user_id, followers_id)
                    session.execute_write(self.refollowed_followers, user_id, followers_id)

        except Exception as e:
            self.logger.error(f"Error while managing relationships: {e}")
            raise  # Optionally re-raise the error if you want it to propagate

    
    def new_followees(self, session, user_id, followees_id):
        # user_id = user['id']
        # followees_id =  [ followee['id']for followee in followees]
        session.run("""
            WITH $followees_id AS followees_id
            UNWIND followees_id AS followee_id
            MATCH (a:Person {id: $user_id}), (b:Person {id: followee_id})
            OPTIONAL MATCH (a)-[r1:FOLLOWS]->(b)
            OPTIONAL MATCH (a)-[r2:UNFOLLOWED]->(b)
            WHERE r1 IS NULL AND r2 IS NULL
            MERGE (a)-[:FOLLOWS]->(b) 

        """,user_id=user_id, followees_id=followees_id)
    def new_followers(self, session, user_id, followers_id):
        # user_id = user['id']
        # followers_id =  [ follower['id']for follower in followers]
        session.run("""
            WITH $followers_id AS followers_id
            UNWIND followers_id AS follower_id
            MATCH (a:Person {id: $user_id}), (b:Person {id: follower_id})
            OPTIONAL MATCH (b)-[r1:FOLLOWS]->(a)
            OPTIONAL MATCH (b)-[r2:UNFOLLOWED]->(a)
            WHERE r1 IS NULL AND r2 IS NULL
            MERGE (b)-[:FOLLOWS]->(a) 

        """,user_id=user_id, followers_id=followers_id)

    def unfollowed_followees(self, session, user_id, followees_id):
        # user_id = user['id']
        # followees_id =  [ followee['id']for followee in followees]
        result = session.run("""
                MATCH (a:Person {id: $user_id})-[:FOLLOWS]->(b:Person)
                WITH collect(b.id) AS existing_followees_id
                UNWIND existing_followees_id AS existing_followee_id
                WITH existing_followee_id, existing_followees_id, $current_followees_id AS current_followees_id
                WHERE NOT existing_followee_id IN current_followees_id
                MATCH (a:Person {id: $user_id})-[r:FOLLOWS]->(b:Person {id: existing_followee_id})
                MERGE (a)-[newRel:UNFOLLOWED]->(b) 
                ON CREATE SET newRel.unfollowed_at = datetime()
                DELETE r  
                
            """, user_id=user_id, current_followees_id=followees_id)
        
    def unfollowed_followers(self, session, user_id, followers_id):
        # user_id = user['id']
        # followers_id =  [ follower['id']for follower in followers]
        result = session.run("""
                MATCH (a:Person)-[:FOLLOWS]->(b:Person{id: $user_id})
                WITH collect(a.id) AS existing_followers_id
                UNWIND existing_followers_id AS existing_follower_id
                WITH existing_follower_id, existing_followers_id, $current_followers_id AS current_followers_id
                WHERE NOT existing_follower_id IN current_followers_id
                MATCH (a:Person {id: existing_follower_id})-[r:FOLLOWS]->(b:Person {id: $user_id})
                MERGE (a)-[newRel:UNFOLLOWED]->(b) 
                ON CREATE SET newRel.unfollowed_at = datetime()
                DELETE r  
            """, user_id=user_id, current_followers_id=followers_id)
        
    def refollowed_followees(self, session, user_id, followees_id):
            # user_id = user['id']
            # followees_id =  [ followee['id']for followee in followees]
            result = session.run("""
                WITH $followees_id_to_follow_back AS followees_id_to_follow_back
                UNWIND followees_id_to_follow_back AS followee_id
                MATCH (a:Person {id: $user_id})-[r:UNFOLLOWED]->(b:Person {id: followee_id})
                MERGE (a)-[newRel:FOLLOWS]->(b) 
                ON CREATE SET newRel.followed_at = datetime(), 
                        newRel.unfollowed_at = r.unfollowed_at
                DELETE r  
                
            """, user_id=user_id, followees_id_to_follow_back=followees_id)

    def refollowed_followers(self, session, user_id, followers_id):
            # user_id = user['id']
            # followers_id =  [ follower['id']for follower in followers]
            result =session.run("""
                WITH $followers_id_to_follow_back AS followers_id_to_follow_back
                UNWIND followers_id_to_follow_back AS follower_id
                MATCH (a:Person {id: follower_id})-[r:UNFOLLOWED]->(b:Person {id: $user_id})
                MERGE (a)-[newRel:FOLLOWS]->(b) 
                ON CREATE SET newRel.followed_at = datetime(), 
                        newRel.unfollowed_at = r.unfollowed_at
                DELETE r  
                
            """, user_id=user_id, followers_id_to_follow_back=followers_id)