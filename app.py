from flask import Flask, render_template, request
import requests
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

headers = {}

if GITHUB_TOKEN:
    headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    headers["Accept"] = "application/vnd.github+json"

# -----------------------------
# DATABASE FUNCTIONS
# -----------------------------
def get_db_connection():

    connection = sqlite3.connect("students.db")

    connection.row_factory = sqlite3.Row

    return connection


def create_database():

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE,

            name TEXT,

            avatar TEXT,

            skill_index INTEGER,

            skill_level TEXT,

            total_commits INTEGER,

            activity_level TEXT

        )
    """)

    connection.commit()

    connection.close()


create_database()


# -----------------------------
# GITHUB API SETTINGS
# -----------------------------
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Student-Skill-Platform"
}


# -----------------------------
# HOME PAGE
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------
# ANALYZE GITHUB PROFILE
# -----------------------------
@app.route("/analyze", methods=["GET", "POST"])
def analyze():

    if request.method == "POST":

        # Get GitHub username
        username = request.form.get("username", "").strip()

        if not username:
            return render_template(
                "analyze.html",
                error="Please enter a GitHub username."
            )

        try:

            # -----------------------------
            # 1. FETCH GITHUB PROFILE
            # -----------------------------
            github_url = f"https://api.github.com/users/{username}"

            response = requests.get(
                github_url,
                headers=GITHUB_HEADERS,
                timeout=15
            )


            # Username not found
            if response.status_code == 404:
                return render_template(
                    "analyze.html",
                    error="GitHub username not found."
                )


            # GitHub rate limit
            if response.status_code == 403:
                return render_template(
                    "analyze.html",
                    error="GitHub API rate limit reached. Please try again later."
                )


            # Other errors
            if response.status_code != 200:
                return render_template(
                    "analyze.html",
                    error=f"Unable to fetch profile. Error code: {response.status_code}"
                )


            user_data = response.json()


            # -----------------------------
            # 2. FETCH REPOSITORIES
            # -----------------------------
            repos_url = f"https://api.github.com/users/{username}/repos"

            repos_response = requests.get(
                repos_url,
                headers=headers,
                params={
                    "per_page": 100,
                    "sort": "updated",
                    "direction": "desc"
                },
                timeout=15
            )


            if repos_response.status_code == 403:
                return render_template(
                    "analyze.html",
                    error="GitHub API rate limit reached while fetching repositories."
                )


            if repos_response.status_code == 200:
                repos_data = repos_response.json()
            else:
                repos_data = []


            # -----------------------------
            # 3. PREPARE DATA
            # -----------------------------
            repositories = []
            languages = []
            total_commits = 0


            # Last 30 days
            thirty_days_ago = (
                datetime.now(timezone.utc)
                - timedelta(days=30)
            )

            since_date = thirty_days_ago.isoformat()


            # -----------------------------
            # 4. ANALYZE REPOSITORIES
            # -----------------------------
            for repo in repos_data:

                repo_name = repo.get("name")

                # Skip invalid repository
                if not repo_name:
                    continue


                repo_owner = (
                    repo.get("owner", {})
                    .get("login", username)
                )


                # Default commit count
                commit_count = 0


                # -----------------------------
                # FETCH RECENT COMMITS
                # -----------------------------
                commits_url = (
                    f"https://api.github.com/repos/"
                    f"{repo_owner}/{repo_name}/commits"
                )


                try:

                    commits_response = requests.get(
                        commits_url,
                        headers=headers,
                        params={
                            "since": since_date,
                            "per_page": 100
                        },
                        timeout=10
                    )


                    if commits_response.status_code == 200:

                        commits_data = commits_response.json()

                        if isinstance(commits_data, list):
                            commit_count = len(commits_data)


                    # Don't stop the whole application
                    # if one repository cannot be analyzed
                    elif commits_response.status_code in [403, 409, 422]:
                        commit_count = 0


                except requests.RequestException:
                    commit_count = 0


                # Add commit count
                total_commits += commit_count


                # -----------------------------
                # STORE REPOSITORY DATA
                # -----------------------------
                repo_info = {
                    "name": repo.get(
                        "name",
                        "Unknown Repository"
                    ),

                    "description": repo.get(
                        "description"
                    ),

                    "language": repo.get(
                        "language"
                    ),

                    "stars": repo.get(
                        "stargazers_count",
                        0
                    ),

                    "forks": repo.get(
                        "forks_count",
                        0
                    ),

                    "commits": commit_count,

                    "url": repo.get(
                        "html_url"
                    )
                }


                repositories.append(repo_info)


                # -----------------------------
                # DETECT PROGRAMMING LANGUAGE
                # -----------------------------
                language = repo.get("language")

                if language and language not in languages:
                    languages.append(language)


            # -----------------------------
            # 5. CALCULATE SKILL INDEX
            # -----------------------------

            # Repository Score - /30
            repository_score = min(
                len(repositories) * 5,
                30
            )


            # Technology Score - /30
            technology_score = min(
                len(languages) * 5,
                30
            )


            # Star Score - /20
            total_stars = sum(
                repo.get("stars", 0)
                for repo in repositories
            )

            star_score = min(
                total_stars * 2,
                20
            )


            # Follower Score - /10
            follower_score = min(
                user_data.get("followers", 0),
                10
            )


            # Profile Score - /10
            profile_score = 0


            if user_data.get("name"):
                profile_score += 3


            if user_data.get("bio"):
                profile_score += 3


            if user_data.get("avatar_url"):
                profile_score += 2


            if user_data.get("html_url"):
                profile_score += 2


            # Final Skill Index - /100
            skill_index = (
                repository_score
                + technology_score
                + star_score
                + follower_score
                + profile_score
            )


            # -----------------------------
            # 6. DETERMINE SKILL LEVEL
            # -----------------------------
            if skill_index < 40:
                skill_level = "Beginner"

            elif skill_index < 70:
                skill_level = "Intermediate"

            elif skill_index < 90:
                skill_level = "Advanced"

            else:
                skill_level = "Expert"


            # -----------------------------
            # 7. COMMIT ACTIVITY ANALYSIS
            # -----------------------------
            if total_commits == 0:

                activity_score = 0
                activity_level = "Inactive"

            elif total_commits < 5:

                activity_score = 5
                activity_level = "Low Activity"

            elif total_commits < 10:

                activity_score = 10
                activity_level = "Moderately Active"

            elif total_commits < 20:

                activity_score = 15
                activity_level = "Active"

            else:

                activity_score = 20
                activity_level = "Highly Active"


            # -----------------------------
            # 8. CREATE PROFILE DATA
            # -----------------------------
            profile = {

                "name": (
                    user_data.get("name")
                    or username
                ),

                "username": (
                    user_data.get("login")
                    or username
                ),

                "avatar": user_data.get("avatar_url"),

                "bio": (
                    user_data.get("bio")
                    or "No bio available."
                ),

                "public_repos": (
                    user_data.get("public_repos", 0)
                ),

                "followers": (
                    user_data.get("followers", 0)
                ),

                "following": (
                    user_data.get("following", 0)
                ),

                "profile_url": (
                    user_data.get("html_url")
                ),


                # Skill Analysis
                "skill_index": skill_index,
                "skill_level": skill_level,


                # Commit Activity
                "total_commits": total_commits,
                "activity_score": activity_score,
                "activity_level": activity_level,


                # Score Breakdown
                "repository_score": repository_score,
                "technology_score": technology_score,
                "star_score": star_score,
                "follower_score": follower_score,
                "profile_score": profile_score
            }


            # -----------------------------
            # 9. SAVE STUDENT TO DATABASE
            # -----------------------------
            connection = get_db_connection()

            cursor = connection.cursor()

            cursor.execute("""
              INSERT INTO students (

                username,
                name,
                avatar,
                skill_index,
                skill_level,
                total_commits,
                activity_level

              )

              VALUES (?, ?, ?, ?, ?, ?, ?)

              ON CONFLICT(username) DO UPDATE SET

               name = excluded.name,
               avatar = excluded.avatar,
               skill_index = excluded.skill_index,
               skill_level = excluded.skill_level,
               total_commits = excluded.total_commits,
               activity_level = excluded.activity_level
            """, (

            profile["username"],
            profile["name"],
            profile["avatar"],
            profile["skill_index"],
            profile["skill_level"],
            profile["total_commits"],
            profile["activity_level"]

           ))

            connection.commit()

            connection.close()


            # -----------------------------
            # 10. SHOW RESULT PAGE
            # -----------------------------
            return render_template(
                "result.html",
                profile=profile,
                repositories=repositories,
                languages=languages
            )


        # -----------------------------
        # NETWORK ERROR
        # -----------------------------
        except requests.Timeout:

            return render_template(
                "analyze.html",
                error="Request timed out. Please try again."
            )


        except requests.RequestException:

            return render_template(
                "analyze.html",
                error="Network error. Check your internet connection."
            )


        except Exception as error:

            print("Application Error:", error)

            return render_template(
                "analyze.html",
                error="An unexpected error occurred. Please try again."
            )


    # -----------------------------
    # SHOW ANALYZE PAGE
    # -----------------------------
    return render_template("analyze.html")


# -----------------------------
# LEADERBOARD PAGE
# -----------------------------
@app.route("/leaderboard")
def leaderboard():

    connection = get_db_connection()

    students = connection.execute("""

        SELECT *

        FROM students

        ORDER BY skill_index DESC,
                 total_commits DESC

    """).fetchall()

    connection.close()

    return render_template(
        "leaderboard.html",
        students=students
    )


# -----------------------------
# RUN APPLICATION
# -----------------------------
if __name__ == "__main__":
    app.run(
        debug=True
    )