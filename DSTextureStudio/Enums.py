from enum import Enum, auto, IntEnum

class ExportMode(Enum):
    ATLAS = auto()
    SUBTEXTURE = auto()

class GameType(Enum):
    LEGACY = auto()
    MODERN = auto()
    PS = auto()

class Modified(Enum):
    FALSE = auto()
    ADDED = auto()
    REPLACED = auto()

class ImageType(Enum):
    Atlas = auto()
    Texture = auto()
    Subtexture = auto()
    Custom = auto()

class IconMode(Enum):
    Define = auto()
    Append = auto()

class Game():
    LEGACY_GAMES = {"Dark Souls 1", "Dark Souls 2", "Dark Souls 3"}
    PS_GAMES = {"Bloodborne", "Demon's Souls"}

    def __init__(self, name: str):
        self.name = name
        self.type = self.classify(name)

    def classify(self, name: str | None) -> GameType | None:
        if name is None:
            return None

        if name in self.LEGACY_GAMES:
            return GameType.LEGACY
        elif name in self.PS_GAMES:
            return GameType.PS
        else:
            return GameType.MODERN

    def __repr__(self):
        type_name = self.type.name if self.type else None
        return f"Game({self.name}, {type_name})"

class Resolution(Enum):
    HI = auto()
    LOW = auto()

    @property
    def display(self):
        return {
            Resolution.HI: "Hi",
            Resolution.LOW: "Low"
        }[self]

    @classmethod
    def from_str(cls, text) -> "Resolution":
        match text:
            case "Hi"|"High":
                return cls.HI
            case "Low":
                return cls.LOW
            case _:
                raise ValueError("Value should be str(hi/low/high)")

class BackgroundMode(IntEnum):
    BLACK = 0
    WHITE = 1
    CHECKERED = 2
