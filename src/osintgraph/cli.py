import sys
import logging
import argparse
import asyncio

import instaloader

import osintgraph
import requests
from packaging import version as pkg_version
from .logger import setup_root_logger
from .utils.monkey_patches import custom_get_likes
instaloader.structures.Post.get_likes = custom_get_likes
from .insta_manager import InstagramManager, Insta_Config
from .neo4j_manager import Neo4jManager
from .credential_manager import get_credential_manager
from .osintgraph_agent import OSINTGraphAgent
from .constants import SERVICE_MAP, GIT_REPO, TEMPLATES_DIR




def main():
    
    setup_root_logger(False)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO) # logging.DEBUG if args.debug else logging.INFO

    logo = r"""
    ________         .__        __                             .__     
    \_____  \   _____|__| _____/  |_  ________________  ______ |  |__  
     /   |   \ /  ___/  |/    \   __\/ ___\_  __ \__  \ \____ \|  |  \ 
    /    |    \\___ \|  |   |  \  | / /_/  >  | \// __ \|  |_> >   Y  \
    \_______  /____  >__|___|  /__| \___  /|__|  (____  /   __/|___|  /
            \/     \/        \/    /_____/            \/|__|        \/     
                                                                """

    
    VERSION =f"{osintgraph.__version__}"

    
    LOGO_COLOR = "\033[38;5;209m"
    ACCENT_COLOR = "\033[38;5;210m"    # A bright green shade, used for command names and the logo
    HEADER_COLOR = "\033[38;5;224m"    # A light cyan, used for section headers
    RESET        = "\033[0m"

    print(LOGO_COLOR + logo + VERSION + RESET)


    try:
        r = requests.get(GIT_REPO, timeout=5)
        latest = r.json()["tag_name"].lstrip("v")
        if pkg_version.parse(latest) > pkg_version.parse(osintgraph.__version__):
            
            logger.warning(f"Newer version available: {latest}")

    except Exception:
        pass

    HELP_TEXT = f"""
    {ACCENT_COLOR}Commands:{RESET}

        {HEADER_COLOR}setup{RESET} [target]
            Setup services and credentials.
            Targets: all (default), instagram, neo4j, gemini, user-agent

            Examples:
                {HEADER_COLOR}osintgraph setup{RESET}
                {HEADER_COLOR}osintgraph setup instagram{RESET}

        {HEADER_COLOR}reset{RESET} [target]
            Reset stored credentials for a service, then immediately re-run setup.
            Targets: all (default), instagram, neo4j, gemini, user-agent

            Examples:
                {HEADER_COLOR}osintgraph reset{RESET}
                {HEADER_COLOR}osintgraph reset instagram{RESET}

        {HEADER_COLOR}discover{RESET} <username>
            Retrieve target account:
            - followers, followees, and posts
            - Adds AI-generated post_analysis for each post (if Gemini API is set)  
            - Adds AI-generated account_analysis using profile metadata and all post analyses (if Gemini API is set)  
            - Use a specific Instagram account for scraping. If not specified, the default account is used.


            {ACCENT_COLOR}Options:{RESET}
                {HEADER_COLOR}--skip [parts]{RESET}         
                    Skip specific scraping or AI steps
                    {ACCENT_COLOR}Options:{RESET} {HEADER_COLOR}all{RESET}, {HEADER_COLOR}follower{RESET}, {HEADER_COLOR}followee{RESET}, {HEADER_COLOR}post{RESET}, {HEADER_COLOR}post-analysis{RESET}, {HEADER_COLOR}account-analysis{RESET}
                {HEADER_COLOR}--limit TYPE=NUMBER  {RESET}     
                    Maximum number of items to fetch per account. (default: follower=1000, followee=1000, post=10)
                    {ACCENT_COLOR}Options:{RESET} {HEADER_COLOR}follower{RESET}, {HEADER_COLOR}followee{RESET}, {HEADER_COLOR}post{RESET}
                {HEADER_COLOR}--rate-limit NUMBER{RESET}         
                    Pause for 5–10 minutes after every N requests (default: 200)
                {HEADER_COLOR}--force [parts]{RESET}        
                    Re-fetch or re-analyze the chosen sections even if already completed before.  
                    {ACCENT_COLOR}Options:{RESET} {HEADER_COLOR}all{RESET}, {HEADER_COLOR}follower{RESET}, {HEADER_COLOR}followee{RESET}, {HEADER_COLOR}post{RESET}, {HEADER_COLOR}post-analysis{RESET}, {HEADER_COLOR}account-analysis{RESET}

                {HEADER_COLOR}--account USERNAME{RESET}
                    Specify which of your Instagram accounts to use for this action.
            Example:
                {HEADER_COLOR}osintgraph discover "target_user"{RESET}
                {HEADER_COLOR}osintgraph discover "target_user" --limit follower=200 post=10 --skip post-analysis account-analysis --force follower followee{RESET}

        {HEADER_COLOR}explore{RESET} <username>
            Recursive discovery (runs -discover on each followee of the target account, prioritizing accounts with the largest follower base in the Neo4j database).
            Stops after N accounts (default: 5).
            - Use a specific Instagram account for scraping. If not specified, the default account is used.

            {ACCENT_COLOR}Options:{RESET}
                {HEADER_COLOR}--max NUMBER{RESET}                
                    Max accounts to explore (default: 5)
                {HEADER_COLOR}--skip [parts]{RESET}         
                    Skip specific scraping or AI steps
                    {ACCENT_COLOR}Options:{RESET} {HEADER_COLOR}all{RESET}, {HEADER_COLOR}follower{RESET}, {HEADER_COLOR}followee{RESET}, {HEADER_COLOR}post{RESET}, {HEADER_COLOR}post-analysis{RESET}, {HEADER_COLOR}account-analysis{RESET}
                {HEADER_COLOR}--limit TYPE=NUMBER  {RESET}     
                    Maximum number of items to fetch per account. (default: follower=1000, followee=1000, post=10)
                    {ACCENT_COLOR}Options:{RESET} {HEADER_COLOR}follower{RESET}, {HEADER_COLOR}followee{RESET}, {HEADER_COLOR}post{RESET}
                {HEADER_COLOR}--rate-limit NUMBER{RESET}         
                    Pause for 5–10 minutes after every N requests (default: 200)
                {HEADER_COLOR}--force [parts]{RESET}        
                    Re-fetch or re-analyze the chosen sections even if already completed before.  
                    {ACCENT_COLOR}Options:{RESET} {HEADER_COLOR}all{RESET}, {HEADER_COLOR}follower{RESET}, {HEADER_COLOR}followee{RESET}, {HEADER_COLOR}post{RESET}, {HEADER_COLOR}post-analysis{RESET}, {HEADER_COLOR}account-analysis{RESET}

                {HEADER_COLOR}--account USERNAME{RESET}
                    Specify which of your Instagram accounts to use for this action.
            Example:
                {HEADER_COLOR}osintgraph explore "target_user" --max 10 --limit follower=1000 followee=500 --rate-limit 1000{RESET}

        {HEADER_COLOR}agent{RESET}
            Launch the OSINTGraph AI Agent for searching (keyword search, semantic search), analyzing, and template-based investigations.
            
            {ACCENT_COLOR}Options:{RESET}
                {HEADER_COLOR}--debug{RESET}
                    Enable debug output for template.
            Example:
                {HEADER_COLOR}osintgraph agent --debug{RESET}
    
    {ACCENT_COLOR} Template Folder:{RESET}
        Path: {HEADER_COLOR}{TEMPLATES_DIR}{RESET}
        This folder is used to store prompt templates.
        Add your own .yaml templates here.
        Run 'osintgraph agent' and ask "list all templates" to see all available templates.

"""
    main_parser = argparse.ArgumentParser(prog="osintgraph")

    subparsers = main_parser.add_subparsers(dest="command", required=True)

    # main_parser.add_argument("--debug", action="store_true", help="Enable Debug Mode")

    setup_parser = subparsers.add_parser("setup", help="Setup services.")
    setup_parser.add_argument("target", nargs="?", default="all",
                            choices=["all", "instagram", "neo4j", "gemini", "user-agent"],
                            help="Setup services (default=all).")
    
    reset_parser = subparsers.add_parser("reset", help="Reset credentials.")
    reset_parser.add_argument("target", nargs="?", default="all",
                            choices=["all", "instagram", "neo4j", "gemini", "user-agent"],
                            help="Service to reset (default: all).")
    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Full scrape of a target username: followers, followees, posts, and AI analysis (if Gemini API set).")
    discover_parser.add_argument("username", type=str, help="Target username to scrape.")
    discover_parser.add_argument("--skip", nargs="+", choices=["all", "follower", "followee", "post", "post-analysis", "account-analysis"], help="Skip specific scraping/analysis steps.")
    discover_parser.add_argument("--limit", nargs="+", metavar="TYPE=VALUE", help="Set scrape limits. Types: follower, followee, post. Example: --limit follower=2000 post=50")
    discover_parser.add_argument("--rate-limit", type=int, default=200, help="Pause for 5–10 min after every N requests to reduce Instagram detection (default: 200).")
    discover_parser.add_argument("--force", nargs="+", choices=["all", "follower", "followee", "post", "post-analysis", "account-analysis"], help="Force re-fetch or re-analyze for chosen sections. Use 'all' to redo all.")
    discover_parser.add_argument("--account", type=str, help="Specify which Instagram account to use for scraping.")

    # Explore command
    explore_parser = subparsers.add_parser("explore", help="Recursive discovery: run 'discover' on all followees of the target username.")
    explore_parser.add_argument("username", type=str, help="Target username to scrape.")
    explore_parser.add_argument("--max", type=int, default=5, help="Maximum followees to discover (default: 5)")
    explore_parser.add_argument("--skip", nargs="+", choices=["all", "follower", "followee", "post", "post-analysis", "account-analysis"], help="Skip specific scraping/analysis steps.")
    explore_parser.add_argument("--limit", nargs="+", metavar="TYPE=VALUE", help="Set scrape limits. Types: follower, followee, post. Example: --limit follower=2000 post=50")
    explore_parser.add_argument("--rate-limit", type=int, default=200, help="Pause for 5–10 min after every N requests to reduce Instagram detection (default: 200).")
    explore_parser.add_argument("--force", nargs="+", choices=["all", "follower", "followee", "post", "post-analysis", "account-analysis"], help="Force re-fetch or re-analyze for chosen sections. Use 'all' to redo all.")
    explore_parser.add_argument("--account", type=str, help="Specify which Instagram account to use for scraping.")

    # Agent command
    agent_parser = subparsers.add_parser("agent", help="Launch Osintgraph AI Agent (RAG-powered). Supports keyword & semantic search, simple analysis, and template-assisted complex investigations.")
    # agent_parser.add_argument("--rate-limit", action="store_true", default=False, help="Enable rate limiter for the AI Agent to reduce hitting API rate limits.")
    agent_parser.add_argument("--debug", action="store_true", help="Enable debug output for template")


    
    if len(sys.argv) == 1:
        print(HELP_TEXT)
        sys.exit()

    if "-h" in sys.argv or "--help" in sys.argv:
        print(HELP_TEXT)
        sys.exit(0)
    
    args = main_parser.parse_args()




    
        
    credential_manager = get_credential_manager()


    def run_setup(reset_target):
        try:
            logger.info("🔧︎  Setting up...")

            setup_target = reset_target if isinstance(reset_target, str) else "all"

            if setup_target not in SERVICE_MAP:
                logger.error(f"Unknown setup target: {setup_target}")
                sys.exit(1)
            
            if setup_target in ["all", "instagram"]:
                # logger.info("⚙︎  Setting up Instagram...")
                if accounts := credential_manager.get("INSTAGRAM_ACCOUNTS", []):
                    logger.info("✓  Configured Instagram Accounts:")
                    default_account = credential_manager.get(
                        "DEFAULT_INSTAGRAM_ACCOUNT"
                    )
                    for acc in accounts:
                        is_default = " (default)" if acc == default_account else ""
                        logger.info(f"   - {acc}{is_default}")
                else:
                    logger.warning("⚠  No Instagram Account configured.")

                logger.info("\nAdd a new Instagram account?")
                add_new = input("                       > (y/n): ").lower().strip()
                if add_new == 'y':
                    accounts = credential_manager.get("INSTAGRAM_ACCOUNTS", [])
                    default_account = credential_manager.get("DEFAULT_INSTAGRAM_ACCOUNT")
                    new_username = InstagramManager(config=Insta_Config(auto_login=False)).choose_login_method()
                    if new_username and new_username not in accounts:
                        accounts.append(new_username)
                        credential_manager.set("INSTAGRAM_ACCOUNTS", accounts)
                        if not default_account:
                            credential_manager.set("DEFAULT_INSTAGRAM_ACCOUNT", new_username)
                            logger.info(f"✓  Account '{new_username}' added and set as default.")
                        else:
                            logger.info(f"✓  Account '{new_username}' added.")

                if accounts and len(accounts) > 1:
                    logger.info("\nSet a default account?")
                    set_default = input(f"                      > (current default: {default_account}) (y/n): ").lower().strip()
                    if set_default == 'y':
                        logger.info("Enter username to set as default:")
                        new_default = input("                       > ").strip()
                        if new_default in accounts:
                            credential_manager.set("DEFAULT_INSTAGRAM_ACCOUNT", new_default)
                            logger.info(f"✓  Default account set to '{new_default}'.")

            if setup_target in ["all", "neo4j"]:
                # logger.info("⚙︎  Setting up Neo4j...")
                Neo4jManager()       # Will handle Neo4j login

            if setup_target in ["all", "gemini"]:
                # --- Gemini API Key ---
                if geminiApiKey := credential_manager.get("GEMINI_API_KEY"):
                    logger.info(f"✓  Gemini API key configured: (...{geminiApiKey[-4:]})")
                else:
                    logger.warning("⚠  No Gemini API key found.")
                    logger.info("Enter Gemini API key (or press Enter to skip): ")
                    key = input("                       > ").strip()
                    if key:
                        credential_manager.set("GEMINI_API_KEY", key)
                        logger.info("✓  Gemini API key set.")
                    else:
                        logger.warning("⚠  No Gemini API key set. AI pre-analysis and the OSINTGraph agent will be unavailable.")

            if setup_target in ["all", "user-agent"]:
                        # --- Instagram User-Agent ---
                if ua := credential_manager.get("INSTAGRAM_USER_AGENT"):
                    logger.info(f"✓  User-Agent configured.")
                else:
                    logger.warning("⚠  No User-Agent found.")
                    logger.info("Enter User-Agent (or press Enter to auto-generate one): ")
                    ua = input("                       > ").strip()
                    if ua:
                        credential_manager.set("INSTAGRAM_USER_AGENT", ua)
                        logger.info("✓  User-Agent set.")
                    else:
                        logger.info("✓  Skipped. A random User-Agent will be generated at runtime.")

            logger.info("🔧︎  Setup Completed")
        except KeyboardInterrupt:
            sys.exit(0)


    if args.command == "reset":
        reset_target = args.target.lower()
        if reset_target not in SERVICE_MAP:
            logger.error(f"Unknown reset target: {reset_target}")
            sys.exit(1)

        keys_to_reset = SERVICE_MAP[reset_target]
        if reset_target == "instagram":
            accounts = credential_manager.get("INSTAGRAM_ACCOUNTS", [])
            if not accounts:
                logger.info("No Instagram accounts to reset.")
            else:
                logger.info("Which account to reset? (or 'all')")
                for acc in accounts: logger.info(f" - {acc}")
                acc_to_reset = input("                       > ").strip()
                if acc_to_reset == 'all':
                    credential_manager.reset(keys_to_reset)
        else:
            credential_manager.reset(keys_to_reset)
        # logger.info(f"Reset credentials for: {reset_target}")

        # Immediately trigger setup
        run_setup(reset_target)
    elif args.command == "setup":
        run_setup(args.target.lower())

    elif args.command in ["discover", "explore"]:
        skip_args = args.skip or []

        limits_input = {"follower": 1000, "followee": 1000, "post": 10}

        if args.limit:
            for item in args.limit:
                try:
                    key, value = item.split("=")
                    key = key.strip().lower()
                    value = int(value.strip())
                    if key in limits_input:
                        limits_input[key] = value
                    else:
                        logger.error(f"Unknown limit type: {key}")
                        sys.exit(1)
                except ValueError:
                    logger.error(f"Invalid limit format: {item}. Use TYPE=VALUE")
                    sys.exit(1)
        force_map = {
            "follower": "followers",
            "followee": "followees",
            "post": "posts",
            "post-analysis": "posts_analysis",
            "account-analysis": "account_analysis"
        }

        if args.force:
            if "all" in args.force:
                config_force = ["all"]
            else:
                config_force = []
                for item in args.force:
                    if item in force_map:
                        config_force.append(force_map[item])
                    else:
                        logger.error(f"Unknown force type: {item}")
                        sys.exit(1)
        else:
            config_force = []

        config = Insta_Config(
        limits={ 
            "followers": limits_input["follower"],
            "followees": limits_input["followee"],
            "posts": limits_input["post"]
        }, 
        max_request=args.rate_limit,
        skip_followers = "all" in skip_args or "follower" in skip_args,
        skip_followees = "all" in skip_args or "followee" in skip_args,
        skip_posts = "all" in skip_args or "post" in skip_args,
        skip_posts_analysis = "all" in skip_args or "post-analysis" in skip_args,
        skip_account_analysis = "all" in skip_args or "account-analysis" in skip_args,
        force=config_force,
        auto_login= True
        )

        manager = InstagramManager(config=config, account_username=args.account)
        
        if args.command == "discover":
            print()
            logger.info(f"Discovering: {args.username}")
            manager.discover(target_user=args.username, account_username=args.account)

        elif args.command == "explore":
            print()
            logger.info(f"Exploring network of user: {args.username} (Max people: {args.max})")
            manager.explore(target_user=args.username, max_people=args.max, account_username=args.account)

        

    elif args.command == "agent":
        llm_api_key = credential_manager.get("GEMINI_API_KEY")
        if not llm_api_key:
            logger.error("✗ No Gemini API key set. Please run `osintgraph setup gemini` to configure it.")
            sys.exit(1)
        
        setup_root_logger(args.debug)

        agent = OSINTGraphAgent(debug=args.debug)
        asyncio.run(agent.run())
    else:
        logger.error("❕  No valid command provided. Use -h to see usage.")
        sys.exit(1)




if __name__ == "__main__":
    main()
