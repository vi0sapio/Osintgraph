# Commands 🔧
    -setup                  Setup: Connect to Neo4j and log in to Instagram.
                            Example: -setup

    -discover USERNAME      Get a person's metadata, followers, and followees and add them to the Neo4j database.
                            By default, the tool fetches up to 1000 followers and followees.
                            If there are more, a resume hash is created, allowing you to continue fetching by running -discover "username" again.

                            You can also increase the limits if needed:
                            Example: -discover "username" -follower_limit 2000 -followee_limit 1500

    -explore USERNAME       Automatically runs -discover on everyone your target follows,
                            starting with those who have the most followers.
                            This helps you map out their social network in one go.
        Optional:
        -max_people INT     Stop fetching users after this limit (default: 5)
                            Example: -explore "username" -max_people 10 -follower_limit 500 -followee_limit 500

    -resume_fetching        Automatically finds users whose followers or followees weren't fully fetched, and resumes the process.
                            This avoids manually running -discover for each incomplete user.
                            Each resume round is limited by the global configuration:
                            -follower_limit INT (default 1000)
                            -followee_limit INT (default 1000).
                            For example, if a user has more than the limit (e.g., 5000 followers),
                            the fetching will take multiple rounds (5 rounds for 5000 followers).

        Optional:
        -max_rounds INT     Limit the number of rounds for searching unfinished users.(default: 3)
                            Example: -resume_hashes -max_round 5 -follower_limit 2000 -rate_limit 100

    Global Optional Arguments:
        -follower_limit INT     Stop fetching for followers after this limit. (default 1000)
        -followee_limit INT     Stop fetching for followees after this limit. (default 1000)
                                Example: -discover "username" -follower_limit 500 -followee_limit 500

        -debug                  Enable Debug Mode
                                Example: -discover "username" -debug

        -rate_limit             Apply random delay after every N requests (default: disabled).
                                Example: -explore "username" -rate_limit 200, will pause for few seconds
                                after every 200 requests to avoid detection or rate-limiting.