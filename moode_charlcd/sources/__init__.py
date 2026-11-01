"""Input side: adapters that know what is playing and how to control it.

Each :class:`~moode_charlcd.sources.base.PlayerAdapter` translates one kind of
source into the common :class:`~moode_charlcd.model.NowPlaying` model. Data
access is delegated to small repositories/clients (MPD protocol, moOde
SQLite database, metadata files, BlueZ D-Bus) that can be replaced in tests.
"""
