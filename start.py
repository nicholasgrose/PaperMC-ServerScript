import os
import re
import select
import subprocess
import sys

import requests

MINECRAFT_VERSION = "1.16.5"
PROJECT = "paper"
PAPER_ENDPOINT = (
    f"https://papermc.io/api/v2/projects/{PROJECT}/versions/{MINECRAFT_VERSION}"
)

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

RESTART_PROMPT_TIMEOUT = 10

SERVER_JAR_LOCATION = os.path.abspath(".")
CURRENT_BUILD = -1
SERVER_JAR_NAME = None
CURRENT_JAR_PATH = None


def jar_name(build: int) -> str:
    return f"papermc-server_{build}.jar"


def jar_path(jar: str) -> str:
    return f"{SERVER_JAR_LOCATION}/{jar}"


def use_build(build: int) -> None:
    global CURRENT_BUILD
    global CURRENT_JAR
    global CURRENT_JAR_PATH
    CURRENT_BUILD = build
    CURRENT_JAR = jar_name(build)
    CURRENT_JAR_PATH = jar_path(CURRENT_JAR)


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


DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_CHUNK_SIZE_MB = DOWNLOAD_CHUNK_SIZE / 1024 / 1024


def download_latest_jar(latest_build: int) -> None:
    download_name = get_latest_build_download_name(
        f"{PAPER_ENDPOINT}/builds/{latest_build}"
    )
    download = requests.get(
        f"{PAPER_ENDPOINT}/builds/{latest_build}/downloads/{download_name}"
    )

    download.raise_for_status()
    downloaded_jar_path = jar_path(jar_name(latest_build))
    with open(downloaded_jar_path, "wb") as file:
        amount_downloaded = 0
        for chunk in download.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            print(f"Downloaded: {round(amount_downloaded, 2)} MB", end="\r")
            file.write(chunk)
            amount_downloaded += DOWNLOAD_CHUNK_SIZE_MB
        print()


def download_latest_server_build() -> str:
    latest_build = get_latest_build_number(f"{PAPER_ENDPOINT}")

    if CURRENT_BUILD >= latest_build:
        return None

    download_latest_jar(latest_build)

    return latest_build


def update_server() -> None:
    try:
        print("Updating server...")
        new_build = download_latest_server_build()
        if new_build is not None:
            os.remove(CURRENT_JAR_PATH)
            use_build(new_build)
            print("Server successfully updated.")
        else:
            print("Server already up-to-date.")
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


def start_server() -> None:
    print("Starting server...")
    if CURRENT_JAR_PATH is None:
        print("Cannot start server.")
        return
    subprocess.call(
        [
            "java",
        ]
        + JVM_FLAGS
        + ["-jar", CURRENT_JAR_PATH, "nogui"]
    )


def find_current_build() -> int:
    for root, dirs, files in os.walk(SERVER_JAR_LOCATION):
        for file in files:
            if PAPER_SERVER_REGEX.match(file):
                return build_from_jar_name(file)
    return -1


def build_from_jar_name(jar_name: str) -> int:
    match = PAPER_BUILD_EXTRACT_REGEX.search(jar_name)
    if match is None:
        return -1
    return int(match.group(0))


def fill_in_current_server_info() -> None:
    current_build = find_current_build()
    if current_build is not None:
        use_build(current_build)


PAPER_SERVER_REGEX = re.compile("^papermc-server_\d+\.jar$")
PAPER_BUILD_EXTRACT_REGEX = re.compile("\d+")


def main() -> None:
    fill_in_current_server_info()
    while True:
        update_server()
        start_server()
        if user_requests_stop():
            break


if __name__ == "__main__":
    main()
