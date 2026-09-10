from PIL import Image, ImageDraw
from io import BytesIO
from pathlib import Path
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QFileDialog
from soulstruct.games import Game, get_game
from DSTextureStudio.GUI import gameTypeDialog, RadioButtonDialog
from DSTextureStudio.Utilities import path_has_sequence, checkBlockSize, align_up, tupleAdd
import tempfile
import logging

logger = logging.getLogger(__name__)

def getFreeSpace(atlas_size, used_rects, w, h, step=4, padding=2):
    atlas_w, atlas_h = atlas_size

    for y in range(padding, atlas_h - h - padding, step):
        for x in range(padding, atlas_w - w - padding, step):

            new_rect = (x - padding, y - padding, x + w + padding, y + h + padding)

            overlap = False
            for r in used_rects:
                if not (
                    new_rect[2] <= r[0] or  # left
                    new_rect[0] >= r[2] or  # right
                    new_rect[3] <= r[1] or  # above
                    new_rect[1] >= r[3]     # below
                ):
                    overlap = True
                    break

            if not overlap:
                return x, y

    return None

def cleanByAlpha(img: Image.Image, threshold: int = 5) -> Image.Image:
    """Zero RGB values where alpha <= threshold."""
    img = img.convert("RGBA")

    alpha = img.getchannel("A")
    mask = alpha.point(lambda a: 255 if a <= threshold else 0)
    black = Image.new("RGB", img.size, (0, 0, 0))

    rgb = img.convert("RGB")
    rgb.paste(black, mask)

    return Image.merge("RGBA", (*rgb.split(), alpha))


def parseGameType(path) -> Game:
    game_type = None
    parts = Path(path).parts

    if "PS3_GAME" in parts:
        game_type = 'des'
    if path_has_sequence(parts, ["steamapps", "common", "DARK SOULS REMASTERED"]):
        game_type = 'dsr'
    #elif path_has_sequence(parts, ["steamapps", "common", "Dark Souls II"]):
        #game_type = 'ds2'
    elif path_has_sequence(parts, ["steamapps", "common", "Dark Souls II Scholar of the First Sin"]):
        game_type = 'sotfs'
    elif path_has_sequence(parts, ["steamapps", "common", "DARK SOULS III"]):
        game_type = 'ds3'
    elif path_has_sequence(parts, ["Bloodborne", "CUSA03173", "dvdroot_ps4"]):
        game_type = 'bb'
    elif path_has_sequence(parts, ["steamapps", "common", "Sekiro"]):
        game_type = 'sdt'
    elif path_has_sequence(parts, ["steamapps", "common", "ARMORED CORE VI FIRES OF RUBICON"]):
        game_type = "ac6"
    elif path_has_sequence(parts, ["steamapps", "common", "ELDEN RING NIGHTREIGN"]):
        game_type = 'nr'
    elif path_has_sequence(parts, ["steamapps", "common", "ELDEN RING"]):
        game_type = 'er'

    return get_game(game_type)

def createDebugGrid(image, subtextures):
    """Outputs a png with grid lines for debugging"""
    if len(subtextures) == 0:
        return image
    
    debug = image.copy()
    draw = ImageDraw.Draw(debug)

    for icn in subtextures:
        width = icn.width
        height = icn.height
        x = icn.x
        y = icn.y
        draw.rectangle([x, y, x + width, y + height], outline="red", width=1)

    return debug

def pil2Qpixmap(pil_img) -> QPixmap:
    """Convert PIL Image to QPixmap without destroying the aspect ratio lol"""
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)

def getPngSize(pil_img):
    """Simulate a png export to get file size."""
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    return len(buf.getvalue())

def checkGame(path: str) -> Game:
    game = parseGameType(path=path)
    if game.name is None:
        game = gameTypeDialog()
    return game if game.name is not None else None

def createBlankImage(dimensions: tuple) -> str:
    img = Image.new("RGBA", dimensions, (0, 0, 0, 0))
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(temp_file.name, "PNG")

    return temp_file.name

def padImage(img: Image.Image, new_size: tuple[int, int]) -> Image.Image:
    """Pads an image to a multiple of align."""
    if new_size[0] < img.width or new_size[1] < img.height:
        raise ValueError("new_size must be at least the current image size")

    padded = Image.new("RGBA", new_size, (0, 0, 0, 0))
    padded.paste(img, (0, 0))

    return padded

def validateImageForSwizzle(img: Image.Image, parent_dims: tuple = (0, 0), padding: tuple = (0, 0)) -> Image.Image|None:
    final_dims = tupleAdd([img.size, parent_dims, padding])

    if checkBlockSize(img=final_dims, align=8):
        return img

    dlg = RadioButtonDialog(
        title="Invalid Texture",
        text="Swizzled textures should have dimensions divisible by 8.\nWhat would you like to do with this texture?",
        options={
            0: "Cancel Addition",
            1: "Ignore Warning",
            2: "Resize Image",
            3: "Pad Image With Alpha",
            4: "Choose A New Image"
        }
    )
    if not dlg.exec():
        return None

    final_required = (align_up(final_dims[0]), align_up(final_dims[1]),)

    required = (
        img.width + (final_required[0] - final_dims[0]),
        img.height + (final_required[1] - final_dims[1]),
    )

    match dlg.selected():
        case 0:
            return img

        case 1:
            return None

        case 2:
            logger.info("Resampling image to dimensions: %s", required)
            return img.resize(required, Image.Resampling.LANCZOS)

        case 3:
            logger.info("Padding image to dimensions: %s", required)
            return padImage(img, required)

        case 4:
            filename, _ = QFileDialog.getOpenFileName(None, "Select Image", "", "Image Files (*.png *.dds *.jpg *.jpeg *.webm);;All Files (*.*)",)
            if not filename:
                return None

            logger.info("Validating new image: %s", filename)

            with Image.open(filename) as new_img:
                return validateImageForSwizzle(new_img.copy(), parent_dims=parent_dims, padding=padding)

    return None
