import shutil
import os
import sys
import select
import requests
import subprocess

MINECRAFT_VERSION = "1.16.5"
PAPER_ENDPOINT = (
    f"https://papermc.io/api/v2/projects/paper/versions/{MINECRAFT_VERSION}"
)

SERVER_JAR_LOCATION = os.path.abspath("paper_server.jar")
DOWNLOAD_LOCATION = os.path.abspath("server_updated.jar")

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
    "-jar",
    SERVER_JAR_LOCATION,
    "nogui",
]


def get_latest_build_number(endpoint: str) -> int:
    """Gets the latest build from the provided endpoint.

    Args:
        endpoint (str): Endpoint to make a GET request to.

    Returns:
        int: The number of the Paper build.
    """
    response = requests.get(endpoint)
    response.raise_for_status()
    result = response.json()
    return max(result["builds"])


def get_latest_build_download_name(endpoint: str) -> str:
    """Gets the file name for the build from the provided endpoint.

    Args:
        endpoint (str): Endpoint to make a GET request to.

    Returns:
        str: The name of the download file.
    """
    response = requests.get(endpoint, stream=True)
    response.raise_for_status()
    result = response.json()
    return result["downloads"]["application"]["name"]


DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_CHUNK_SIZE_MB = DOWNLOAD_CHUNK_SIZE / 1024 / 1024


def download_latest_server_build() -> None:
    """Downloads the latest Paper build to DOWNLOAD_LOCATION."""
    build = get_latest_build_number(f"{PAPER_ENDPOINT}")
    download_name = get_latest_build_download_name(f"{PAPER_ENDPOINT}/builds/{build}")
    download = requests.get(
        f"{PAPER_ENDPOINT}/builds/{build}/downloads/{download_name}"
    )

    download.raise_for_status()
    with open(DOWNLOAD_LOCATION, "wb") as file:
        amount_downloaded = 0
        for chunk in download.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            print(f"\rDownloaded: {round(amount_downloaded, 2)} MB", end="")
            file.write(chunk)
            amount_downloaded += DOWNLOAD_CHUNK_SIZE_MB
        print()


def update_server() -> None:
    """Updates the server jar to the latest available Paper build."""
    try:
        print("Updating server...")
        download_latest_server_build()
        shutil.move(DOWNLOAD_LOCATION, SERVER_JAR_LOCATION)
        print("Server download successful.")
    except Exception as e:
        print(e)
        print("An error occurred while updating server. Skipping update step.")


def user_requests_stop() -> bool:
    """Prompts the user to say whether to restart or stop the server.
    Assumes a restart is required if the user does not respond in RESTART_PROMPT_TIMEOUT seconds.

    Returns:
        bool: Whether to stop the server.
    """
    print()
    while True:
        print('Restart ("r") or stop ("s")?')
        stdin = select.select([sys.stdin], [], [], RESTART_PROMPT_TIMEOUT)[0]

        if stdin:
            user_response = sys.stdin.readline().strip().lower()
            if user_response == "r":
                print("Restarting server.")
                return False
            elif user_response == "s":
                print("Stopping server.")
                return True
            else:
                print("Invalid response. Please try again.")
        else:
            print("Automatically restarting server.")
            return False


def run_server() -> None:
    """Runs the current server jar with the JVM flags provided."""
    print("Starting server...")
    subprocess.call(
        [
            "java",
        ]
        + JVM_FLAGS
    )


def main() -> None:
    """Contains the infinite loop that updates the server, runs it, and restarts it, if necessary."""
    while True:
        update_server()
        run_server()
        if user_requests_stop():
            break


if __name__ == "__main__":
    main()
