from logger import setup_root_logger
import logging
from insta_manager import InstagramManager, Insta_Config
from credential_manager import CredentialManager
import argparse
import sys
def main():
    
    logo = r"""
    ________         .__        __                             .__     
    \_____  \   _____|__| _____/  |_  ________________  ______ |  |__  
     /   |   \ /  ___/  |/    \   __\/ ___\_  __ \__  \ \____ \|  |  \ 
    /    |    \\___ \|  |   |  \  | / /_/  >  | \// __ \|  |_> >   Y  \
    \_______  /____  >__|___|  /__| \___  /|__|  (____  /   __/|___|  /
            \/     \/        \/    /_____/            \/|__|        \/     """

    
    LOGO_COLOR = "\033[38;5;209m"
    ACCENT_COLOR = "\033[38;5;210m"    # A bright green shade, used for command names and the logo
    HEADER_COLOR = "\033[38;5;224m"    # A light cyan, used for section headers
    RESET        = "\033[0m"

    print(LOGO_COLOR + logo + RESET)
    HELP_TEXT = f"""

    {ACCENT_COLOR}Commands:{RESET}

    {HEADER_COLOR}-setup{RESET}                  Setup: Connect to Neo4j and log in to Instagram.   
        {ACCENT_COLOR}Optional:{RESET}
        {HEADER_COLOR}-user_agent STRING{RESET}  Set the Firefox User-Agent used to log into your Instagram account to reduce detection risk
        {HEADER_COLOR}-reset{RESET}              Clear all credentials and require re-entry for setup
                            Example: {HEADER_COLOR}-setup -user_agent "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0"{RESET}    

    {HEADER_COLOR}-discover STRING{RESET}        Get a person's metadata, followers, and followees and add them to the Neo4j database.
                            By default, the tool fetches up to 1000 followers and followees. 
                            If there are more, a resume hash is created, allowing you to continue fetching by running {HEADER_COLOR}-discover "username"{RESET} again.

                            You can also increase the limits if needed:
                            Example: {HEADER_COLOR}-discover "username" -follower_limit 2000 -followee_limit 1500{RESET}

    {HEADER_COLOR}-explore STRING{RESET}         Automatically runs -discover on everyone your target follows,
                            starting with those who have the most followers.
                            This helps you map out their social network in one go.
        {ACCENT_COLOR}Optional:{RESET}
        {HEADER_COLOR}-max_people INT{RESET}     Stop fetching users after this limit (default: 5)
                            Example: {HEADER_COLOR}-explore "username" -max_people 10 -follower_limit 500 -followee_limit 500{RESET}

    {HEADER_COLOR}-resume_fetching{RESET}        Automatically finds users whose followers or followees weren't fully fetched, and resumes the process.
                            This avoids manually running -discover for each incomplete user.
                            Each resume round is limited by the global configuration:
                            -follower_limit INT (default 1000)
                            -followee_limit INT (default 1000).
                            For example, if a user has more than the limit (e.g., 5000 followers), 
                            the fetching will take multiple rounds (5 rounds for 5000 followers).

        {ACCENT_COLOR}Optional:{RESET}
        {HEADER_COLOR}-max_rounds INT{RESET}     Limit the number of rounds for searching unfinished users.(default: 3)
                            Example: {HEADER_COLOR}-resume_hashes -max_round 5 -follower_limit 2000 -rate_limit 100{RESET}

    {ACCENT_COLOR}Global Optional Arguments:{RESET}
        {HEADER_COLOR}-follower_limit INT{RESET}     Stop fetching for followers after this limit. (default 1000)
        {HEADER_COLOR}-followee_limit INT{RESET}     Stop fetching for followees after this limit. (default 1000)
                                Example: {HEADER_COLOR}-discover "username" -follower_limit 500 -followee_limit 500{RESET}

        {HEADER_COLOR}-debug{RESET}                  Enable Debug Mode
                                Example: {HEADER_COLOR}-discover "username" -debug{RESET}

        {HEADER_COLOR}-rate_limit{RESET}             Apply random delay after every N requests (default: disabled).
                                Example: {HEADER_COLOR}-explore "username" -rate_limit 200{RESET}, will pause for few seconds
                                after every 200 requests to avoid detection or rate-limiting.
"""

    main_parser = argparse.ArgumentParser(add_help=False)

    # Add --help manually to show banner-style help
    main_parser.add_argument('-h', '--help', action='store_true', help='Show custom help message')

    
    main_parser.add_argument("-discover", type=str, help="Username to discover")
    main_parser.add_argument("-explore", type=str, help="Username to explore")
    main_parser.add_argument("-resume_fetching", action="store_true", help="Resume incomplete user follower/followees data fetches")
    main_parser.add_argument("-follower_limit", type=int, default=1000, help="Follower fetching limit")
    main_parser.add_argument("-followee_limit", type=int, default=1000, help="Followee fetching limit")
    main_parser.add_argument("-max_people", type=int, default=5, help="Maximum people to explore (default: 5)")
    main_parser.add_argument("-max_rounds", type=int, default=3, help="Maximum resume rounds")
    main_parser.add_argument("-debug", action="store_true", help="Debug Mode")
    main_parser.add_argument("-rate_limit", type=int, default=200, help="Apply random delay after every N requests")
    main_parser.add_argument("-setup", action="store_true", help="Connnect to Neo4j and Login Instrgam Account interactively")
    main_parser.add_argument("-user_agent", type=str, help="Set the Firefox User-Agent used to log into your Instagram account to reduce detection risk")
    main_parser.add_argument("-reset", action="store_true", help="Clear all credentials and require re-entry for setup")


    # Parse known args (let us separate --help or --options behavior)
    args, unknown = main_parser.parse_known_args()

    if len(sys.argv) == 1:
        print(HELP_TEXT)
        sys.exit()
        
    # Custom Help
    if args.help:
        print(HELP_TEXT)
        sys.exit()

    if unknown:
        print("❗ Unknown arguments:", " ".join(unknown))
        print("Use -h for help.")
        sys.exit(1)

    
    setup_root_logger(args.debug)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
    config = Insta_Config(limits={"followers": args.follower_limit,"followees": args.followee_limit},max_request=args.rate_limit)
    credential_manager = CredentialManager()


    if args.setup:
        
        # Handle reset first
        if args.reset:
            credential_manager.reset()
            logger.info("🔄 All credentials have been reset.")

        
        # Set custom user agent if provided
        if args.user_agent:
            credential_manager.set("INSTAGRAM_USER_AGENT", args.user_agent)
            logger.info("✅ Custom User-Agent set.")

        # Initialize InstagramManager to handle login and Neo4j connection
        manager = InstagramManager(config=config)

        

    elif args.discover or args.explore or args.resume_fetching:

        manager = InstagramManager(config=config)
        
        if args.discover:
            logger.info(f"Discovering user: {args.discover}")
            manager.discover(target_user=args.discover)

        elif args.explore:
            logger.info(f"Exploring network of user: {args.explore} (max_people={args.max_people})")
            manager.explore(target_user=args.explore, max_people=args.max_people)

        elif args.resume_fetching:
            logger.info(f"Resuming unfinished hashes (max_round={args.max_rounds})")
            manager.complete_undone_hashes(max_rounds=args.max_rounds)

    else:
        logger.error("❗ No valid command provided. Use -h to see usage.")
        sys.exit(1)




if __name__ == "__main__":
    main()

