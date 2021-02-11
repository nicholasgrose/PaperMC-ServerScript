import shutil
import os
import sys
import select
from typing import Tuple, Union
import requests
import subprocess
import re

MINECRAFT_VERSION = "1.16.5"
PROJECT = "paper"
PAPER_ENDPOINT = (
    f"https://papermc.io/api/v2/projects/{PROJECT}/versions/{MINECRAFT_VERSION}"
)

SERVER_JAR_LOCATION = os.path.abspath(".")

RESTART_PROMPT_TIMEOUT = 10

SERVER_MEMORY = "6G"
# We are using Aikar's flags by default: https://aikar.co/2018/07/02/tuning-the-jvm-g1gc-garbage-collector-flags-for-minecraft/
JVM_FLAGS = [
    f"-Xms{SERVER_MEMORY}",
    f"-Xmx{SERVER_MEMORY}",
    "-XX:+UseG1GC",
    "-XX:+ParallelRefProcEnabled",
    "-XX:MaxGCPauseMillis=200",
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+DisableExplicitGC",
    "-XX:+AlwaysPreTouch",
    "-XX:G1NewSizePercent=30",
    "-XX:G1MaxNewSizePercent=40",
    "-XX:G1HeapRegionSize=8M",
    "-XX:G1ReservePercent=20",
    "-XX:G1HeapWastePercent=5",
    "-XX:G1MixedGCCountTarget=4",
    "-XX:InitiatingHeapOccupancyPercent=15",
    "-XX:G1MixedGCLiveThresholdPercent=90",
    "-XX:G1RSetUpdatingPauseTimePercent=5",
    "-XX:SurvivorRatio=32",
    "-XX:+PerfDisableSharedMem",
    "-XX:MaxTenuringThreshold=1",
    "-Dusing.aikars.flags=https://mcflags.emc.gs",
    "-Daikars.new.flags=true",
]


def get_latest_build_number(endpoint: str) -> int:
    response = requests.get(endpoint)
    response.raise_for_status()
    result = response.json()
    return max(result["builds"])


def get_latest_build_download_name(endpoint: str) -> str:
    response = requests.get(endpoint, stream=True)
    response.raise_for_status()
    result = response.json()
    return result["downloads"]["application"]["name"]


PAPER_SERVER_REGEX = re.compile("^papermc-server_\d+.jar$")


def find_current_server_jar() -> Union[str, None]:
    for root, dirs, files in os.walk(SERVER_JAR_LOCATION):
        for file in files:
            if PAPER_SERVER_REGEX.match(file):
                return file
    return None


PAPER_BUILD_EXTRACT_REGEX = re.compile("\d+")


def server_already_up_to_date(current_jar: str, latest_build: int) -> bool:
    match = PAPER_BUILD_EXTRACT_REGEX.search(current_jar)
    if match is None:
        return False
    return int(match.group(0)) == latest_build


DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_CHUNK_SIZE_MB = DOWNLOAD_CHUNK_SIZE / 1024 / 1024


def download_latest_server_build() -> Tuple[str, str]:
    latest_build = get_latest_build_number(f"{PAPER_ENDPOINT}")

    current_jar = find_current_server_jar()

    if current_jar is not None and server_already_up_to_date(current_jar, latest_build):
        return f"{SERVER_JAR_LOCATION}/{current_jar}", None

    if current_jar is None:
        current_jar_path = f"{SERVER_JAR_LOCATION}/papermc-server_{latest_build}.jar"
    else:
        current_jar_path = f"{SERVER_JAR_LOCATION}/{current_jar}"

    download_name = get_latest_build_download_name(
        f"{PAPER_ENDPOINT}/builds/{latest_build}"
    )
    download = requests.get(
        f"{PAPER_ENDPOINT}/builds/{latest_build}/downloads/{download_name}"
    )

    download.raise_for_status()
    downloaded_jar_path = f"{SERVER_JAR_LOCATION}/papermc-server_{latest_build}.jar"
    with open(downloaded_jar_path, "wb") as file:
        amount_downloaded = 0
        for chunk in download.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            print(f"\rDownloaded: {round(amount_downloaded, 2)} MB", end="")
            file.write(chunk)
            amount_downloaded += DOWNLOAD_CHUNK_SIZE_MB
        print()

    return current_jar_path, downloaded_jar_path


def update_server() -> str:
    try:
        print("Updating server...")
        jar_file_path, old_jar_path = download_latest_server_build()
        if old_jar_path is not None:
            shutil.move(jar_file_path, old_jar_path)
            print("Server successfully updated.")
        else:
            print("Server already up-to-date.")
        return jar_file_path
    except Exception as e:
        print(e)
        print("An error occurred while updating server. Skipping update step.")


def user_requests_stop() -> bool:
    print()
    while True:
        print(f"{RESTART_PROMPT_TIMEOUT} seconds to respond.")
        print('Restart ("r") or stop ("s")?')
        stdin = select.select([sys.stdin], [], [], RESTART_PROMPT_TIMEOUT)[0]

        if stdin:
            user_response = sys.stdin.readline().strip().lower()
            if user_response == "r":
                print("Restarting server.")
                return False
            elif user_response == "s":
                print("Stopping.")
                return True
            else:
                print("Invalid response. Please try again.")
        else:
            print("No response. Automatically restarting server...")
            return False


def run_server(server_jar: str) -> None:
    print("Starting server...")
    subprocess.call(
        [
            "java",
        ]
        + JVM_FLAGS
        + ["-jar", server_jar, "nogui"]
    )


def main() -> None:
    while True:
        server_jar = update_server()
        run_server(server_jar)
        if user_requests_stop():
            break


if __name__ == "__main__":
    main()
