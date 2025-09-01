# Osintgraph🌐🔍
Osintgraph is an open-source tool that collects Instagram user, follower, and followee data into Neo4j to map your target’s connections, interests, and affiliations for OSINT and social network analysis.

## Osintgraph CLI for User Data Collection
![image](https://github.com/user-attachments/assets/92b72391-6500-483b-b8c7-82c3a5885dce)



## Neo4j for Exploring Social Network Relationships
[![video](https://github.com/user-attachments/assets/71a7bd04-7a5f-4e59-9bb2-2233ce62423b)](https://github.com/user-attachments/assets/2216d329-58e5-4a99-a8f6-a8a47d8d0d40)


Above is an example of finding mutual friends between two users
# Commands 🔧


    -setup                         Connect to Neo4j and log into Instagram.
    -discover <TARGET_USERNAME>    Fetch target user’s profile data, followers, and followees.
    -explore <TARGET_USERNAME>     Discover target’s social network automatically.
    -resume_fetching               Resume unfinished user fetches.
📖 For detailed usage of all commands, see: [COMMANDS.md](https://github.com/XD-MHLOO/Osintgraph/blob/master/COMMANDS.md)

# What You Can Learn from a Target’s Instagram Network?

### 📍 Location Affiliation
If the target and their followers follow local businesses, cafes, or community pages, you can estimate where the target lives, works, or hangs out.

### 🏢 Work and School Connections
If the target and their network follow the same company, university, or alumni groups, you can guess where they studied or work.

### 🎯 Hobbies and Interests
By looking at the types of accounts followed (like sports clubs, art galleries, tech brands), you can figure out the target's hobbies and passions.

### 🌐 Language and Culture Clues
Following regional pages or accounts in a certain language can reveal what language the target uses and which culture they relate to.

### 👥 Friend and Family Mapping
Shared followers and followees often show close friends, family members, or coworkers connected to the target.

### 🔗 Hidden Accounts and Fake Profiles
Sometimes people run multiple accounts — one public, one private.
By noticing overlapping followers, shared connections, or similar profile clues, you can uncover secondary or hidden accounts.
These "alts" can reveal private sides of the target not shown on their main account.

(Sock puppets — fake or anonymous accounts — can also be spotted if they share unusual connection patterns.)

### 🧠 Behavior and Lifestyle Patterns
Following a lot of business profiles? Maybe they’re career-focused. Following many travel pages? They might love traveling.
The network gives hints about their lifestyle and mindset.

### 🧑‍🤝‍🧑 Investigating Multiple Targets
If you map two users, shared followers can show friendships, coworker relationships, or people moving in the same circles.

### 📈 Public Influence Check
A big follower count can suggest public attention, influence, or an active role in communities.

### 🛡️ Risk and Red Flags
Following controversial organizations or strange, inactive networks might hint at risky behavior or hidden agendas.

### 🗂️ Tracking Changes Over Time (if you scan again manually later)
Changes in who they follow can hint at life events — like new jobs, moves, or big shifts in interests.


## FAQ❓: 
### What if the account is private?
🔎 Reconstructing Private Accounts Through Their Circle.

Even if the target’s account is private, you can still map their world.
Scrape their friends, coworkers, or communities they're involved with.
By analyzing these public profiles, you can rebuild the private target’s connections, interests, and affiliations — without ever needing direct access.


# How to Start🚀

To get started, you need two things:
- **A Neo4j database instance** to store and visualize your datasets.
- **An Instagram account** (preferably not your main account).

## 1. Get a Neo4j instance for free🖥️:

- Go to [Neo4j](https://neo4j.com) and click **Get Started Free**.
- Sign up and create your instance.
- Download the **admin credentials** for your instance (you'll need these for connection).

## 2. Install Osintgraph⚙️:

Run these commands in your terminal:

```bash
git clone https://github.com/XD-MHLOO/Osintgraph.git
cd Osintgraph
git checkout v0.0.1-legacy
pip install -r requirements.txt
```
## 3. Connect Neo4j and log into your Instagram account🔑:
Run the following command:
```bash
python main.py -setup
```
- Use the admin credentials you downloaded from Neo4j to connect, then log in with your Instagram account.
## 4. Start collecting data📊:
Run the command, replacing <TARGET_USERNAME> with the Instagram username of the user whose data you want to retrieve.
```bash
python main.py -discover <TARGET_USERNAME>
```
## 5. View your collected data in Neo4j🌐:
- Go to [Neo4j Console](https://console-preview.neo4j.io/tools/explore).
- Click the **Explore Tab** and then Connect.
- In the search bar, type "Show me a graph".
- You should now see the person you just collected, along with their relationships.
  
# 🚫 **How to Avoid Account Suspension**

1. **Use Your Browser Session**  
   When running `-setup`, choose login via Firefox session to make the login look natural. 🌐

2. **Use Your Real User-Agent**  
   When running `-setup`, use the `-user_agent` flag to supply the exact user-agent from the browser you use to log in to your Instagram account. 🖥️

3. **Enable 2FA**  
   Turn on 2FA for your Instagram account. It’s simple: just use an authenticator app, and it helps Instagram recognize that your account is legitimate. 🔒

4. **Build Account Reputation**  
   Use your Instagram account normally (like posts, comment, watch stories) for a few days or weeks before scraping. 📈

5. **Warm Up Your Session**  
   Spend time using Instagram before scraping, like a normal user, to avoid looking suspicious. ⏳

6. **Avoid VPNs**  
   Don’t use VPNs. Instagram may flag accounts with mismatched or suspicious locations. 🚫🌍

7. **Don’t Use the Account for Other Activities While Scraping**  
   When using this tool to collect data, avoid using the same Instagram account for any other activities. 🛑

8. **Limit Scraping Time**  
   Don’t scrape for more than 6 hours straight. ⏰
### Credit:  
- Thanks to [@ahmdrz](https://github.com/ahmdrz) for these valuable insights on avoiding account suspension. 🙏
- Also see [this useful comment](https://github.com/instaloader/instaloader/issues/2391#issuecomment-2400987481) on Instaloader's GitHub for more tips.

---

## 📦 Dependencies:
- **[Instaloader](https://github.com/instaloader/instaloader)** – Used to collect Instagram profile data, followers, and followees.
- **[Neo4j](https://neo4j.com/)** – Graph database used to store and visualize the Instagram social network.
