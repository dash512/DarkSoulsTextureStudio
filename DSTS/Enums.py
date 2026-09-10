from enum import Enum, auto, IntEnum
from PySide6.QtGui import QColor

class ExportMode(Enum):
    ATLAS = auto()
    SUBTEXTURE = auto()

class GameType(Enum):
    LEGACY = auto()
    MODERN = auto()
    PS = auto()

class Modified(Enum):
    FALSE = QColor.fromString("#FFFFFF")
    ADDED = QColor.fromString("#00FF00")
    REPLACED = QColor.fromString("#FFFF00")
    DELETED = QColor.fromString("#FF0000")

class ImageType(Enum):
    Atlas = auto()
    Texture = auto()
    Subtexture = auto()
    Custom = auto()

class IconMode(Enum):
    Define = auto()
    Append = auto()

class Resolution(Enum):
    HI = auto()
    HIGH = auto()
    LOW = auto()

    @property
    def display(self):
        return {
            Resolution.HI: "Hi",
            Resolution.HIGH: "High",
            Resolution.LOW: "Low"
        }[self]

    @classmethod
    def from_str(cls, text) -> "Resolution":
        match text:
            case "Hi":
                return cls.HI
            case "High":
                return cls.HIGH
            case "Low":
                return cls.LOW
            case _:
                raise ValueError("Value should be str(hi/low/high)")

class BackgroundMode(IntEnum):
    BLACK = 0
    WHITE = 1
    CHECKERED = 2

class DeltaMode(Enum):
    SELF = auto()
    DIFF = auto()

class WriteTask(Enum):
    ALL = auto()
    TPF = auto()
    LYT = auto()

