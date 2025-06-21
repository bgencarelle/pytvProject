from app import TVEmulator
from playlist_builder import build_all_playlists
import config

def main():
    if config.RUN_PLAYLIST_BUILDER == True:
       build_all_playlists()
    tv = TVEmulator()
    tv.run()

if __name__ == "__main__":
    main()
