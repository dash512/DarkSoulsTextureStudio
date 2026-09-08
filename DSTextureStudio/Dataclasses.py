import logging
from dataclasses import dataclass, field
from textwrap import indent
from typing import Optional, Callable
from PIL import Image
from pathlib import Path
from io import BytesIO
import struct
from soulstruct.games import Game, NIGHTREIGN, ARMORED_CORE_6
from soulstruct.dcx import oodle, DCXType
from soulstruct.containers.tpf import TPFTexture, TPFPlatform, TPF
from soulstruct.containers import Binder, BinderEntry, BinderVersion, BinderVersion4Info
from soulstruct.base.textures.dds import DDS
from soulstruct.base.textures.dds.swizzle import swizzle_dds_bytes_ps4
from DSTextureStudio.Utilities import path_has_sequence, findLast, tupleAdd
from DSTextureStudio.Enums import ImageType, Resolution, DeltaMode
from DSTextureStudio.Helpers import cleanByAlpha
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)
# region LAYOUT
@dataclass(slots=True)
class AtlasLayout:
    path: Path # internal entry paths
    element: ET.Element = field(default_factory=lambda: ET.Element("TextureAtlas"))

    # region Properties

    @property
    def name(self) -> str:
        return Path(self.imagePath).stem

    @property
    def commonPath(self) -> Path:
        return Path(self.path).parent

    @property
    def res(self) -> Resolution|None:
        for r in ["Hi", "Low", "High"]:
            if path_has_sequence(self.path.parts, [r]):
                return Resolution.from_str(r)
        return None
    
    @property
    def imagePath(self) -> str:
        return self.element.get("imagePath")
    
    @property
    def xml(self) -> str:
        return ET.tostring(self.element, encoding='utf-8', method='xml')

    # region Build
    
    @classmethod
    def from_element(cls, path, el: ET.Element) -> "AtlasLayout":
        return cls(path=path,element=el)

    @classmethod
    def from_binder(cls, binder: Binder|Path) -> list["AtlasLayout"]:
        oodle.LOAD_DLL()

        if isinstance(binder, Path):
            binder = Binder(binder)

        return [
            cls(
                path=Path(entry.path),
                element=ET.fromstring(entry.data, parser=ET.XMLParser(encoding="utf-8"))
            ) for entry in binder
        ]
    
    @classmethod
    def create(cls, imagePath: str, entryPath: str, subtextures: list[SubTexture], dimensions: Optional[tuple[int, int]] = None) -> "AtlasLayout":
        """Creates a new AtlasLayout entry.
        
        imagePath - the internal path name written in each TextureAtlas element in the .layout files
        
        entryPath - the internal path name OF each .layout file and its BinderEntry

        subtextures - list of SubTexture objects to add to the Layout's root
        
        dimensions - optional TextureAtlas properties for Nightreign. Expects tuple[width, height]"""

        root = ET.Element("TextureAtlas")
        root.set("imagePath", imagePath)
        if dimensions is not None:
            root.set("width", str(dimensions[0]))
            root.set("height", str(dimensions[1]))

        obj = cls(path=entryPath, element=root)
        obj.add_subtextures(subtextures)
        return obj

    def build(layout_objs: list[AtlasLayout], output: Path) -> None:
        """
        Writes a list of AtlasLayouts to sblytbnd.dcx

        layout_objs - list of all loaded AtlasLayouts to be added as entries to the Binder

        output - where to write dcx to"""
        oodle.LOAD_DLL()

        binder = Binder(
            version=BinderVersion.V4,
            dcx_type=DCXType.DCX_KRAK,
            v4_info=BinderVersion4Info(False, False, True, 4)
        )

        for atlas in layout_objs:
            binder.add_entry(
                entry=BinderEntry(
                    data=ET.tostring(atlas.element, encoding='utf-8', method='xml'),
                    entry_id=binder.get_first_new_entry_id_in_range(0, 1000000),
                    path=str(atlas.path),
                    flags=0x2
                )
            )

        binder.write(output)

    # region Subtexture Handling

    def iter_subtextures(self) -> list[ET.Element[str]]:
        return self.element.findall("SubTexture")

    def has_subtexture(self, name: str) -> bool:
        return any(st.get("name") == name for st in self.iter_subtextures())

    def add_subtextures(self, subtextures: list[SubTexture]) -> None:
        """Adds a list of SubTexture objects to the parent AtlasLayout's Element"""
        atlas = self.element
        for sub in subtextures:
            name = sub.name
            if not name.endswith('.png'):
                name = f"{name}.png"

            if self.has_subtexture(name):
                logger.info("Subtexture entry `%s` already exists in layout file. Skipping.", name)
                continue

            item = ET.SubElement(atlas, "SubTexture", {
                "name": name,
                "x": str(sub.x),
                "y": str(sub.y),
                "width": str(sub.width),
                "height": str(sub.height),
                "half": str(int(sub.flag_half))})
            
            logger.info("Adding Subtexture to %s:\n%s", sub.parent, ET.tostring(item, encoding='unicode'))
            
            if len(atlas) == 1:
                atlas.text = '\r\n\t'
            else:
                atlas[-2].tail = '\r\n\t'

            item.tail = '\r\n'

    # region Helpers

    def getImagePath(game: Game, **kwargs):
        if game == NIGHTREIGN:
            imgpath = r"W:\CL\data\Target\INTERROOT_win64\menu\ScaleForm\Tif\01_Common\{res}\{atlas_name}.tif" 
        if game == ARMORED_CORE_6:
            imgpath = r"W:\FNR\data\Menu\ScaleForm\Tif\01_Common\{atlas_name}\{res}\exp\{atlas_name}.png"
        else: # ER/SDT
            imgpath = r"{atlas_name}.png"

        return imgpath.format(**kwargs)

    def __repr__(self) -> str:
        return (
            f"AtlasLayout(\n"
            f"    Name = {self.name}\n"
            f"    Internal Path = {self.path}\n"
            f"    imagePath = {self.imagePath}\n"
            f"    Element = {self.element.__repr__()}\n"
            f"    Subtexture Count = {len(self.iter_subtextures())}\n"
            f")"
        )
# region ATLAS
@dataclass(slots=True)
class Atlas:
    name: str
    parent: Optional[Path] # when None, is written as a standalone file 

    vanilla: Optional[bool] = False # set to True on load. Custom are False
    override: Optional[Image.Image] = None # full self atlas replacement

    texture: Optional[TPFTexture|Image.Image] = None # Image is allowed for making Deltas
    dimensions: Optional[tuple[int, int]] = None # only needed for custom Atlases, used for writing TextureAtlas xml properties

    subtextures: list[SubTexture] = field(default_factory=list)

    is_delete: Optional[bool] = False # DSTS flag to skip entire atlas when saving

    # region Properties
    @property
    def itype(self) -> ImageType:
        """Checks if self Atlas object is an atlas with SubTextures or just a plain Texture"""
        return ImageType.Atlas if self.count > 0 else ImageType.Texture

    @property
    def count(self) -> int:
        """Returns number of child SubTexture objects."""
        return len(self.subtextures)

    @property
    def filename(self) -> str:
        name = self.parent.name
        return name[:name.find('.')] # remove all extensions so that eg "01_common.sblytbnd.dcx" == "01_common.tpf.dcx"
    
    @property
    def viewable(self) -> Image.Image:
        """Returns a viewable Image of self.texture's dds"""
        # existing textures return due to being a valid DDS, custom are not swizzled; PC skips deswizzling
        # this covers both PC and PS4 games unlike BytesIO(texture.data) which wouldn't work on headerless BB textures
        dds = self.texture.get_headerized_data(TPFPlatform.PC) 
        return Image.open(BytesIO(dds)).convert("RGBA")

    @property
    def additions(self) -> list[SubTexture]:
        return [sub for sub in self.subtextures if sub.vanilla == False]

    @property
    def replacements(self) -> list[SubTexture]:
        return [sub for sub in self.subtextures if sub.override is not None]
    
    @property
    def modified(self) -> bool:
        return (self.replacements or self.additions)

    @property
    def modifications(self) -> dict:
        return {
            "Name": self.name,
            "Additions": self.additions,
            "Replacements": self.replacements
        }

    @property
    def isAtlas(self) -> bool:
        return bool(self.subtextures)

    # region Helpers
    def rename(self, new_name) -> bool:
        """Renames Atlas object. Returns True if successful"""
        def renameAttrParent(self, attr, new_name):
                for s in getattr(self, attr):
                    if s.parent is not None:
                        s.parent = new_name

        if new_name != self.name:
            self.name = new_name
            self.texture.stem = new_name
            for i in ["subtextures", "additions", "replacements"]:
                self.renameAttrParent(i, new_name)
            return True
        return False

    def empty(self):
        self.subtextures.clear()
        self.clearChanges()
        
    def clearChanges(self):
        """Clears all changes."""
        self.additions.clear()
        self.replacements.clear()

    def allSubs(self, include_non_modified: bool = True) -> list[SubTexture]:
        """Returns a single list of SubTextures defining the whole atlas. Built from modifications."""
        all_subs = self.additions.copy()
        if include_non_modified:
            all_subs += self.subtextures

        sub_map = {i.name: i for i in all_subs}
        sub_map.update({i.name: i for i in self.replacements})

        return list(sub_map.values())

    def mergeChanges(self) -> list[SubTexture]:
        """Returns combined list of all changes to the atlas."""
        return self.allSubs(include_non_modified=False)

    # region Subtexture Helpers
    def add(self, subtexture: SubTexture) -> None:
        """Appends a SubTexture to self list"""
        self.subtextures.append(subtexture)

    def match(self, name: str, attr: str = "subtextures") -> tuple[SubTexture, int]|tuple[None, None]:
        """Helper function to find SubTexture and index from self list"""
        for idx, sub in enumerate(getattr(self, attr)):
            if sub.name == name:
                return sub,idx
        return None, None

    def fetch(self, name: str) -> SubTexture|None:
        """Like Atlas.match but searches globally with self.allSubs()"""
        for sub in self.allSubs():
            if sub.name == name:
                return sub
        return None
    
    def subrename(self, name: str, new_name: str) -> None:
        """Renames SubTextures of a certain name from the Atlas."""
        sub,_ = self.match(name)
        if sub is not None:
            sub.name = new_name
        
    def rem(self, name: str) -> SubTexture|None:
        """Removes SubTextures of a certain name from the Atlas. Returns like {}.pop()"""
        _,idx = self.match(name)
        if idx is not None:
            return self.subtextures.pop(idx)
        return None

    def replace(self, name: str, image: Image.Image) -> None:
        """Finds SubTexture object of 'name' and replaces its 'img' field with a provided image"""
        sub,_ = self.match(name)
        if sub is not None:
            sub.image = image

    def update(self, atlas: Atlas):
        """Update self modifications against another Atlas object by finding diffs."""
        for sub in atlas.allSubs():
            if self.match(sub.name)[0] is None: # is unique to updater/delta; addition
                target = self.additions
            else:
                target = self.replacements

            existing = next((idx for idx,s in enumerate(target) if s.name==sub.name), None)
            if existing is not None:
                target.pop(existing)

            if sub.image is None:
                sub.parent = atlas.name
                sub.image = atlas.texture.crop(sub.box())

            target.append(sub)

    # region Creating
    @classmethod
    def from_layouts(cls, layouts: list[AtlasLayout], parent: Path):
        """Yields textureless "empty" Atlas objects from shoebox layouts."""
        for layout in layouts:
            yield Atlas(
                name=layout.name,
                vanilla=True,
                parent=parent,
                subtextures=[
                    SubTexture(
                        name=Path(sub.get("name")).stem,
                        parent=layout.name,
                        x=int(sub.get("x")),
                        y=int(sub.get("y")),
                        width=int(sub.get("width")),
                        height=int(sub.get("height")),
                        blank=False,
                        vanilla=True,
                    )
                    for sub in layout.iter_subtextures()
                ]
            )

    @classmethod
    def parse(cls, textures: list[TPFTexture], layouts: list[AtlasLayout], parent_file: Path):
        """Yields tuple[atlas.name, Atlas] for a list of Atlas objects built from TPFTextures and AtlasLayouts"""
        layout_lookup = {
            Path(atlas.imagePath).stem: atlas
            for atlas in layouts
        }

        for tex in textures:
            name = tex.stem
            layout = layout_lookup.get(name)

            if layout is None:
                logger.debug("Creating Atlas object with no SubTextures for Texture with no Layout: '%s'", name)
                subtextures = []
            else:
                subtextures = [
                    SubTexture(
                        name=Path(sub.get("name")).stem,
                        parent=name,
                        x=int(sub.get("x")),
                        y=int(sub.get("y")),
                        width=int(sub.get("width")),
                        height=int(sub.get("height")),
                        blank=False,
                        vanilla=True,
                    )
                    for sub in layout.iter_subtextures()
                ]

            yield name, Atlas(
                name=name,
                vanilla=True,
                texture=tex,
                parent=parent_file,
                subtextures=subtextures,
            )

    # region Writing     
    def writetpf(self, output: Path, dcx_type: DCXType = DCXType.Null, encoding: int = 1, flags: int = 3, platform: TPFPlatform = TPFPlatform.PC):
        """Writes a .tpf file to disk using info from self Atlas object. Mostly useful for DS2 files. Output is parent dir."""
        TPF(platform=platform,
            encoding_type=encoding,
            tpf_flags=flags,
            textures=[self.texture],
            dcx_type=dcx_type).write((output / self.name).with_suffix(".tpf"))
        logger.info("Wrote standalone file with compression '%s':\n%s", dcx_type.name, output/self.name)

    def compileTexture(self, alpha_threshold: int = 0) -> Image.Image:
        """Builds new Image() from self, applying all modifications."""
        IMG = self.viewable

        for add in self.additions:
            if add.parent != self.name or add.image is None:
                continue

            abs_w, abs_h = tupleAdd([add.size, add.pos])

            if (abs_w > IMG.width) or (abs_h > IMG.height):
                resized = Image.new("RGBA", (max(IMG.width, abs_w), max(IMG.height, abs_h)), (0, 0, 0, 0))
                resized.paste(IMG)
                IMG = resized

            add.paste_into(IMG)

        if self.override is not None:
            IMG = self.override
        else: # no full replacements, append subtexture replacements
            for rep in self.replacements:
                rep.paste_into(IMG)

        if alpha_threshold > 0: # zero RGB values with alpha 0
            IMG = cleanByAlpha(IMG, threshold=alpha_threshold)

        return IMG

    def add_to_TPF(self, _TPF: TPF, swizzle: bool = False):
        """Adds self texture to a TPF binder."""
        texture: TPFTexture = self.texture

        if swizzle:
            dds = DDS.from_bytes(texture.get_headerized_data(TPFPlatform.PC)) # dont deswizzle as image is already not swizzled
            swizzled = swizzle_dds_bytes_ps4(
                deswizzled=dds.data,
                dxgi_format=texture.console_info.dxgi_format,
                width=texture.console_info.width,
                height=texture.console_info.height,
            )
            texture.data = swizzled

        _TPF.textures.append(texture)

    # region Delta
    def getDelta(self, vanilla: Optional[Atlas] = None) -> "Atlas":
        """Creates delta of 2 Atlases, comparing self to vanilla."""
        if vanilla is None:
            subtextures = self.mergeChanges()
            return Atlas(
                name=self.name,
                parent=self.parent,
                texture=self.compileTexture(),
                subtextures=subtextures
            ) if subtextures else None

        if vanilla.filename != self.filename:
            logger.warning("%s.getDelta(%s): Attempted to find diff between 2 files without matching parents, skipping.", self.name, vanilla.name)
            return None
        
        subtextures = []

        for sub in self.allSubs():
            if vanilla.fetch(sub.name) is not None:
                continue

            subtextures.append(sub)

        if not subtextures:
            return None

        return Atlas(
            name=self.name,
            parent=self.parent,
            texture=self.compileTexture(),
            subtextures=subtextures
        )

    @staticmethod
    def generateDeltaFile(mode: DeltaMode, source: Path|list[Atlas], source_layout: Optional[Path], vanilla: Path, output: Path):
        """Generates a .delta file containing diffs between a modded and vanilla file."""
        oodle.LOAD_DLL()
        deltas = []

        match mode:
            case DeltaMode.SELF:
                assert isinstance(source, list)
                for atlas in source:
                    delta = atlas.getDelta()
                    if delta is not None:
                        deltas.append(delta)

                Atlas.writeDeltaFile(deltas, output)

            case DeltaMode.DIFF:
                if isinstance(source, Path): # else, source is list of Atlases
                    assert source_layout is not None
                    source_tpf = TPF(source)
                    source_layouts = AtlasLayout.from_binder(source_layout)
                    source = Atlas.from_layouts(source_tpf.textures, source_layouts, source)

                vanilla_layouts = AtlasLayout.from_binder(vanilla)
                vanilla_atlases = {atlas.name: atlas for atlas in
                                Atlas.from_layouts(vanilla_layouts, vanilla)
                }

                for atlas in source:
                    vanilla_atlas = vanilla_atlases.get(atlas.name)
                    delta = atlas.getDelta(vanilla_atlas)
                    if delta is not None:
                        deltas.append(delta)

                Atlas.writeDeltaFile(deltas, output)

    @staticmethod
    def writeDeltaFile(deltas: list[Atlas], path: Path):
        with open(path, 'wb') as f:
            f.write(struct.pack("<I", len(deltas)))

            for d in deltas:
                f.write(d.to_bytes())

    @classmethod
    def readDeltaFile(cls, file: Path) -> list['Atlas']:
        with open(file, 'rb') as f:
            (count,) = struct.unpack("<I", f.read(4))

            return [
                cls.from_file(f)
                for _ in range(count)
            ]

    def to_bytes(self) -> bytes:
        result = bytearray()

        name = self.name.encode("utf-8")
        result += struct.pack("<I", len(name))
        result += name

        parent = str(self.parent).encode("utf-8")
        result += struct.pack("<I", len(parent))
        result += parent

        image_buffer = BytesIO()
        self.texture.save(image_buffer, format="PNG")
        image_data = image_buffer.getvalue()

        result += struct.pack("<I", len(image_data))
        result += image_data

        result += struct.pack("<I", len(self.subtextures))
        for sub in self.subtextures:
            sub_data = sub.to_bytes()
            result += struct.pack("<I", len(sub_data))
            result += sub_data

        return bytes(result)

    @classmethod
    def from_file(cls, f) -> Atlas:
        (name_length,) = struct.unpack("<I", f.read(4))
        name = f.read(name_length).decode("utf-8")

        (parent_length,) = struct.unpack("<I", f.read(4))
        parent = Path(f.read(parent_length).decode("utf-8"))

        (image_length,) = struct.unpack("<I", f.read(4))
        image_data = f.read(image_length)
        image = Image.open(BytesIO(image_data))
        image.load()

        subtextures = []

        (count,) = struct.unpack("<I", f.read(4))
        for _ in range(count):
            (subtexture_length,) = struct.unpack("<I", f.read(4))
            subtexture_data = f.read(subtexture_length)

            subtextures.append(SubTexture.from_bytes(subtexture_data))

        return cls(
            name=name,
            parent=parent,
            texture=image,
            subtextures=subtextures,
        )

    def __repr__(self) -> str:
        return (
            f"Atlas(\n"
            f"    Name = {self.name}\n"
            f"    Parent = {self.parent}\n"
            f"    Subtexture Count = {self.count}\n"
            f"    Dimensions = {self.dimensions}\n"
            f"    Queued Additions = {len(self.additions)}\n"
            f"    Queued Replacements = {len(self.replacements)}\n"
            f"    Texture = \n{indent(self.texture.__repr__(), "        ")}\n" 
           # f"    Subtextures = \n{indent(self.subtextures.__repr__(), "        ")}\n"
            f")"
        )
    
# region SUBTEXTURE
@dataclass(slots=True)
class SubTexture:
    name: str
    x: int
    y: int
    width: int
    height: int

    override: Optional[Image.Image] = None # self replacement.

    image: Optional[Image.Image] = None # is None for vanilla subtextures as can just be cropped from parent Atlas

    parent: Optional[str] = None # name of parent atlas
    vanilla: Optional[bool] = False # set to True on load. Custom additions are False, and therefore can be filtered for 

    blank: bool = False
    flag_half: Optional[bool] = False # what even is this bro

    is_delete: Optional[bool] = False # DSTS flag to skip this subtexture when saving

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def setpos(self, x, y):
        self.x = x
        self.y = y

    def rename(self, new_name):
        self.name = new_name

    def revert(self):
        self.override = None

    def box(self, padding: int = 0) -> tuple[int, int, int, int]:
        """Return tuple of coordinates for a box to crop to this subtexture. Allows optional padding"""
        return (self.x - padding, self.y - padding, self.x + self.width + padding, self.y + self.height + padding)
    
    def paste_into(self, image: Image.Image, mask: Image.Image | None = None) -> None:
        """Pastes self into an image"""
        sub_image = self.override or self.image
        if sub_image is None:
            raise Exception("SubTexture object does not contain an image.")
        image.paste(sub_image, self.pos, mask=mask)

    def to_bytes(self) -> bytes:
        result = bytearray()

        name = self.name.encode("utf-8")
        result += struct.pack("<I", len(name))
        result += name

        result += struct.pack("<iiii", self.x, self.y, self.width, self.height)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SubTexture":
        f = BytesIO(data)

        (name_length,) = struct.unpack("<I", f.read(4))
        name = f.read(name_length).decode("utf-8")

        x, y, width, height = struct.unpack("<iiii", f.read(16))

        return cls(
            name=name,
            x=x,
            y=y,
            width=width,
            height=height,
        )

    def __repr__(self) -> str:
        return (
            f"SubTexture(\n"
            f"    Name = {self.name}\n"
            f"    Parent = {self.parent}\n"
            f"    Is Vanilla = {self.vanilla}\n"
            f"    Image = {self.image}\n"
            f"    Coordinates = {self.pos}\n"
            f"    Dimensions = {self.width}x{self.height}\n"
            f"    Blank = {self.blank}\n"
            f"    Half = {self.flag_half}\n"
            f")"
        )
    
@dataclass
class Command:
    func: Callable
    help: str

