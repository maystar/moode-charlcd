from jproperties import Properties


class CurrentSong:
    def __init__(self, config: Properties):
        self.file = config.get("file").data
        self.artist = config.get("artist").data
        self.album = config.get("album").data
        self.title = config.get("title").data
        self.track = config.get("track", 0).data
        self.date = config.get("date").data
        self.volume = config.get("volume").data
        self.mute = config.get("mute").data
        self.state = config.get("state").data

    def __str__(self) -> str:
        return f"{self.state}: {self.artist} - {self.title}"
