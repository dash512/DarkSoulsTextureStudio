from __future__ import annotations
import logging
# Basic Modules
import os
from io import BytesIO
from copy import deepcopy
from tempfile import NamedTemporaryFile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import threading
# GUI
from PySide6.QtCore import QObject, Signal
# Soulstruct
from soulstruct.containers.tpf import TPF, TPFPlatform, TPFTexture, TPF_TEXTURE_FORMAT_TO_DXGI_FORMAT
from soulstruct.dcx import core
from soulstruct.base.textures.dds import DDS
from soulstruct.base.textures.dds.swizzle import swizzle_dds_bytes_ps4
# Custom
from DSTextureStudio.Dataclasses import AtlasLayout, Atlas, SubTexture
from DSTextureStudio.Enums import ExportMode, Resolution, Game, GameType
from DSTextureStudio.Helpers import createDebugGrid, getLayoutData, getResFromLytPath
from DSTextureStudio.log_utils import format_exc_clean
from DSTextureStudio.Utilities import replaceTerms, loadJson

logger = logging.getLogger(__name__)

class LoadWorker(QObject):
    progress = Signal(int, str)   # percent, message
    finished = Signal(object, object, object, object, str)  # atlases, loaded dcx files, parsed xml data, resolutions, error msg

    def __init__(self, file_mappings, game: Game):
        super().__init__()
        self.file_mappings = file_mappings
        self.game = game
        self.LOADED_DCX_FILES = {}
        self.LAYOUT_DATA = {}
        self.RESOLUTONS = {}

    def run(self):
        try:
            logger.info("Beginning unpack for: %s", self.game)
            match self.game.type:
                case GameType.MODERN:
                    self.processModern()

                case GameType.LEGACY | GameType.PS:
                    self.processLegacy()

                case _:
                    logger.info("Unknown game type %s, defaulting to Legacy", self.game)
                    self.processLegacy()
        except:
            self.finished.emit({}, {}, {}, {}, format_exc_clean())

    def handleUnpack(self, path):
        if self.game.type == GameType.PS:
            try:
                tex,_ = core.decompress(path)
                tpfdcx = TPF.from_bytes(tex)
            except core.DCXError:
                tpfdcx = TPF(path) # it's probably a tpf file, may as well try
        else:
            tpfdcx = TPF(path)

        self.LOADED_DCX_FILES[path] = tpfdcx

        for texture in tpfdcx.textures:
            if self.game.type == GameType.PS:
                logger.debug("PS format detected. Creating headerized dds for TPFTexture: %s", texture.stem)
                match self.game.name:
                    case "Bloodborne":
                        platform = TPFPlatform.PS4
                    case "Demon's Souls":
                        platform = TPFPlatform.PC

                dds_data = texture.get_headerized_data(platform)

                texture = TPFTexture(    
                    stem=texture.stem,
                    data=dds_data,
                    platform=platform,
                    console_info=texture.console_info,
                    format=texture.format,
                    texture_type=texture.texture_type,
                    mipmap_count=texture.mipmap_count,
                    texture_flags=texture.texture_flags)
            
            yield texture

    def generateTextDict(self, dcx_path, percent):
        textures_dict: dict = {}
        self.progress.emit(percent, f"Unpacking {dcx_path.stem}...")

        paths = []
        if dcx_path.is_dir():
            paths = [Path(dcx_path) / f for f in os.listdir(dcx_path) if f.endswith('tpf.dcx') or f.endswith('.tpf')]
        else:
            paths = [Path(dcx_path)]

        for path in paths:
            logger.info("Getting texture data for file: %s", path)
            for texture in self.handleUnpack(path):
                textures_dict[texture.stem] = texture

        logger.info("Generated texture dictionary with %i entries", len(textures_dict))
        self.progress.emit(percent, f"Loaded {dcx_path.stem}")
        return textures_dict

    def processModern(self):
        atlases: dict[str, Atlas] = {}
        total_files = len(self.file_mappings)

        self.progress.emit(0, f'Loading {total_files} files...')
        for f_idx, file in enumerate(self.file_mappings, 1):
            percent = int(f_idx / total_files * 100 - 1)
            if isinstance(file, dict):
                _file: Path = file['file']
                layout_path = file['layout']
                textures_dict: dict = self.generateTextDict(_file, percent)

                layout_xml = getLayoutData(layout_path)
                root = ET.fromstring(layout_xml, parser=ET.XMLParser(encoding="utf-8"))
                self.progress.emit(percent, "Parsing layout XML...")

                atlas_layouts = [AtlasLayout.from_element(el) for el in root.findall("TextureAtlas")]
                self.LAYOUT_DATA[_file] = atlas_layouts
                fname = replaceTerms(_file.name, {".tpf.dcx": ""})
                self.RESOLUTONS[fname] = getResFromLytPath(atlas_layouts[0].imagePath)

                layout_lookup = {
                    Path(atlas.imagePath).stem: atlas
                    for atlas in atlas_layouts
                }

                logger.info("Successfully loaded %i shoebox layouts", len(atlas_layouts))

                for filename, texture in textures_dict.items():
                    texture_atlas = layout_lookup.get(filename)

                    if texture_atlas is None:
                        logger.debug("Creating Atlas object with no SubTextures for Texture with no Layout: '%s'", filename)
                        subtextures = []
                    else:
                        subtextures = [
                            SubTexture(
                                name=Path(sub.get("name")).stem,
                                parent=filename,
                                x=int(sub.get("x")),
                                y=int(sub.get("y")),
                                width=int(sub.get("width")),
                                height=int(sub.get("height")),
                                blank=False,
                                vanilla=True,
                            )
                            for sub in texture_atlas.iter_subtextures()
                        ]

                    atlases[filename] = Atlas(
                        name=filename,
                        texture=texture,
                        parent=file['file'],
                        subtextures=subtextures,
                    )

            elif isinstance(file, Path):
                textures_dict: dict = self.generateTextDict(file, percent)
                # add any textures that were not included in the layout
                for name, texture in textures_dict.items():
                    if name not in atlases:
                        atlases[name] = Atlas(name=name, texture=texture, parent=file, subtextures=[]) # no layout info since single textures go to atlases
                logger.info("Successfully loaded %i atlases with no layouts.", len(atlases))

        logger.info("Load Worker process completed succesfully!")
        self.finished.emit(atlases, self.LOADED_DCX_FILES, self.LAYOUT_DATA, self.RESOLUTONS, "")
        self.progress.emit(100, 'Successfully loaded all files!')

    def processLegacy(self):  
        atlases: dict[str, Atlas] = {}
        total_files = len(self.file_mappings)

        for f_idx, file in enumerate(self.file_mappings, 1):
            percent = int(f_idx / total_files * 100 - 1)
            textures_dict: dict = self.generateTextDict(file, percent)

            for name, texture in textures_dict.items():
                atlases[name] = Atlas(name=name, texture=texture, parent=file, subtextures=[])
                dds = texture.get_dds()
                image = Image.open(BytesIO(dds.to_bytes())).convert("RGBA")

                dimensions = loadJson("Dimensions").get(self.game.name, {}).get(name, None)
                
                if dimensions:
                    tile_width, tile_height = dimensions['width'], dimensions['height']

                    atlas_width, atlas_height = dds.header.width, dds.header.height
                    tiles_per_row = atlas_width // tile_width
                    tiles_per_column = atlas_height // tile_height

                    total_tiles = tiles_per_row * tiles_per_column

                    for idx in range(total_tiles):
                        row = idx // tiles_per_row
                        col = idx % tiles_per_row
                        x = col * tile_width
                        y = row * tile_height

                        tile = image.crop((x, y, x + tile_width, y + tile_height))
                        alpha = tile.getchannel("A")
                        opacity_ratio = sum(1 for p in alpha.getdata() if p) / (alpha.width * alpha.height)

                        isBlank: bool = opacity_ratio < 0.01

                        atlases[name].add(SubTexture(name=str(idx),
                                                        parent=name,
                                                        x=x,
                                                        y=y,
                                                        width=tile_width,
                                                        height=tile_height,
                                                        blank=isBlank,
                                                        vanilla=True
                                                ))
        
                    self.progress.emit(percent, f"Processed {name}")

        logger.info("Load Worker process completed succesfully with %i atlaes loaded!", len(atlases))
        self.finished.emit(atlases, self.LOADED_DCX_FILES, {}, {}, "")

class ExtractWorker(QObject):
    progress = Signal(int, str) # percent, message
    finished = Signal(bool, object) # success

    def __init__(self, atlases, output_dir: Path, loader, tasks=None, mode=ExportMode.SUBTEXTURE, filetype='png', gridOverlay=False):
        super().__init__()
        self.atlases = atlases
        self.output_dir = output_dir
        self.pilLoader = loader
        self.tasks = tasks if tasks is not None else []
        self.mode = mode
        self.filetype = filetype
        self.gridOverlay = gridOverlay
        self._interrupted = False

    def interrupt(self):
        self._interrupted = True

    def exportImg(self, image, filename, out_path, progress, message):
        out_path = Path(out_path)
        if not out_path.exists():
            out_path.mkdir(parents=True, exist_ok=True)
        if not filename.endswith('.png'):
            filename = f"{filename}.png"
        image.save(out_path / filename)
        self.progress.emit(progress, message)

    def run(self):
        logger.info("Initialized image export.")
        if not self.tasks: # dump mode
            match self.mode:
                case ExportMode.ATLAS:
                    if not self.atlases:
                        self.finished.emit(False, None)
                        return

                    for atlas_name in self.atlases:
                        self.tasks.append((atlas_name, None))

                case ExportMode.SUBTEXTURE:
                    if not any([a.count>0 for a in self.atlases.values()]):
                        self.finished.emit(False, None)
                        return

                    for atlas_name,_atlas in self.atlases.items():
                            for st in _atlas.subtextures:
                                self.tasks.append((atlas_name, st))

        total = len(self.tasks)
        for i, (atlas_name, st) in enumerate(self.tasks, 1):
            if self._interrupted:
                break
            
            match self.filetype:
                case 'dds':
                    texture: TPFTexture = self.atlases[atlas_name].texture
                    texture.write_dds(self.output_dir / f"{atlas_name}.dds")
                    self.progress.emit(100, f"Exported atlas: {atlas_name}")

                case _:
                    atlas_img = self.pilLoader(atlas_name=atlas_name)
                    percent = int(i / total * 100 - 1)

                    match self.mode:
                        case ExportMode.ATLAS:
                            out_path = self.output_dir
                            filename = atlas_name
                            message = f"Exported atlas: {atlas_name}"

                            if self.gridOverlay:
                                atlas_img = createDebugGrid(atlas_img, self.atlases[atlas_name].subtextures)

                        case ExportMode.SUBTEXTURE:
                            out_path = self.output_dir / atlas_name
                            filename = st.name
                            message = f"Exported {filename} from {atlas_name}"
                            atlas_img = atlas_img.crop(st.box()) # crop if in subtexture mode

                    self.exportImg(image=atlas_img, filename=filename, out_path=out_path, progress=percent, message=message)

        self.finished.emit(True, self.output_dir)

class WriteWorker(QObject):
    requestCompression = Signal(str)
    finished = Signal(bool, str, Path)  # success, message

    def __init__(self, new_atlases, replacements, additions, loaded_files, layouts, getPilImage, game, resolutions, output):
        super().__init__()
        self._event = threading.Event()
        self._result = None

        self.new_atlases = new_atlases
        self.replacements = replacements
        self.additions = additions
        self.getPilImage = getPilImage
        self.LOADED_DCX_FILES = loaded_files
        self.LAYOUT_FILES = layouts
        self.game = game
        self.RESOLUTIONS = resolutions
        self.output_dir = output

    def promptCompression(self, name):
        self._event.clear()
        self.requestCompression.emit(name)
        self._event.wait()
        return self._result

    def buildOperations(self):
        logger.info("Building operations map...")

        dcx_ops = {}

        # new atlases
        for parent, atlases in self.new_atlases.items():
            if parent == "None":
                dcx_type = core.DCXType["Null"]
                is_reuse = False
                for t in atlases:
                    if not is_reuse:
                        _type, enc, reuse = self.promptCompression(t.name)
                        dcx_type = core.DCXType[_type]
                        is_reuse = reuse
                            
                    t.writetpf(self.output_dir, dcx_type=dcx_type, encoding=enc)

            else:
                dcx_ops.setdefault(parent, {"new_atlases": [], "atlases": {}})
                dcx_ops[parent]["new_atlases"].extend(atlases)

        # replacements
        for dcx_path, atlases in self.replacements.items():
            base_name = Path(dcx_path)
            dcx_ops.setdefault(dcx_path, {"new_atlases": [], "atlases": {}})

            for atlas_name, changes in atlases.items():
                dcx_ops[dcx_path]["atlases"].setdefault(atlas_name, {"replacements": {}, "additions": []})
                dcx_ops[dcx_path]["atlases"][atlas_name]["replacements"].update(changes)

        # Additions
        for dcx_path, add_data in self.additions.items():

            dcx_ops.setdefault(dcx_path, {"new_atlases": [], "atlases": {}})

            additions_by_atlas = {}

            for sub in add_data["additions"]:
                if sub.vanilla:
                    continue

                additions_by_atlas.setdefault(sub.parent, []).append(sub)

            for atlas_name, subs in additions_by_atlas.items():
                dcx_ops[dcx_path]["atlases"].setdefault(atlas_name, {"replacements": {}, "additions": []})
                dcx_ops[dcx_path]["atlases"][atlas_name]["additions"].extend(subs)

        # Layout handling
        for dcx_path, data in dcx_ops.items():

            if dcx_path not in self.LAYOUT_FILES:
                continue

            logger.info("Processing layout for: %s", dcx_path)

            layout_objs = list(self.LAYOUT_FILES[dcx_path])

            layout_map = {
                replaceTerms(Path(layout.imagePath).stem, {"_h": "", "_l": ""}): layout # atlas name to AtlasLayout objects
                for layout in layout_objs
            }

            filename = dcx_path.name.split('.')[0]
            res = self.RESOLUTIONS.get(filename, Resolution.HI).display # fallback to high *just* in case
            if self.game.name == "Nightreign":
                filename = replaceTerms(filename, {"_h": "", "_l": ""})
                if res == "Hi":
                    res = "High" # NR is the ONLY game that usese a different name for ts

            for atlas_name, atlas_ops in data["atlases"].items():
                additions = atlas_ops["additions"]
                if not additions:
                    continue

                existing_layout = layout_map.get(atlas_name)

                if existing_layout:
                    logger.info("Adding %i subtexture(s) to existing layout '%s'", len(additions), atlas_name)
                    existing_layout.add_subtextures(additions)

                else:
                    logger.info("Creating layout entry for '%s' with %i subtexture(s)", atlas_name, len(additions))

                    match self.game.name:
                        case "Nightreign":
                            imgpath = rf"W:\CL\data\Target\INTERROOT_win64\menu\ScaleForm\Tif\01_Common\{res}\{atlas_name}.tif" 

                        case "Armored Core 6":
                            imgpath = rf"W:\FNR\data\Menu\ScaleForm\Tif\01_Common\{atlas_name}\{res}\exp\{atlas_name}.png"

                        case _:
                            imgpath = f"{atlas_name}.png"

                    new_layout = AtlasLayout.create(
                        image_path=imgpath,
                        subtextures=additions
                    )

                    layout_objs.append(new_layout)
                    layout_map[atlas_name] = new_layout

            file = dcx_path.name.replace('.tpf.dcx', '.sblytbnd.dcx')
            AtlasLayout.build(
                layout_objs=layout_objs,
                game=self.game,
                res=res,
                output=self.output_dir / file
            )
            logger.info("Successfully wrote file: %s", file)

        logger.info("Finished building operations.")
        logger.info("Summary of DCX operations:")

        for dcx_name, data in dcx_ops.items():
            logger.info("File: %s", dcx_name)

            if data["new_atlases"]:
                logger.info("  New Atlases: %s", [t.name for t in data['new_atlases']])

            for atlas_name, ops in data["atlases"].items():
                rep_keys = list(ops["replacements"].keys())
                add_names = [sub.name for sub in ops["additions"]]

                logger.info(
                    "  Atlas: %s | Replacements: %s | Additions: %s",
                    atlas_name, rep_keys, add_names)

        return dcx_ops

    def run(self):
        try:
            for base_path, data in self.buildOperations().items():
                base: TPF = deepcopy(self.LOADED_DCX_FILES[base_path])

                if data["new_atlases"]:
                    if self.game.name == "Bloodborne":
                        for t in data["new_atlases"]:
                            texture: TPFTexture = t.texture
                            dds = DDS.from_bytes(texture.get_headerized_data(TPFPlatform.PC)) # dont deswizzle as image is already not swizzled
                            swizzled = swizzle_dds_bytes_ps4(
                                deswizzled=dds.data,
                                dxgi_format=texture.console_info.dxgi_format,
                                width=texture.console_info.width,
                                height=texture.console_info.height,
                            )
                            texture.data = swizzled
                            base.textures.append(texture)
                    else:         
                        base.textures.extend([t.texture for t in data["new_atlases"]])

                atlas_cache = {}

                for atlas_name, ops in data["atlases"].items():
                    if atlas_name not in atlas_cache:
                        atlas_cache[atlas_name] = self.getPilImage(atlas_name).copy()
                    atlas_img = atlas_cache[atlas_name]

                    for add in ops["additions"]:
                        if add.img:
                            add.paste_into(atlas_img)

                    for sub_name, new_img in ops["replacements"].items():
                        if sub_name != "*Self*":  # subtexture replacement
                            st = self.getPilImage(atlas_name, return_atlas=True).fetch(sub_name) # im so sorry
                            if not st:
                                raise Exception(f"Could not resolve subtexture '{sub_name}' in atlas '{atlas_name}'")
                            atlas_img.paste(new_img, (st.x, st.y))
                        else:  # full atlas replacement
                            atlas_img = new_img.copy()
                            atlas_cache[atlas_name] = atlas_img

                for atlas_name, atlas_img in atlas_cache.items():
                    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        temp_path = tmp.name
                        atlas_img.save(temp_path)
                    try:
                        texture = TPF.find_texture_stem(base, atlas_name)
                        texture.replace_dds(temp_path,
                                            dds_format=TPF_TEXTURE_FORMAT_TO_DXGI_FORMAT[texture.format].name,
                                            swizzle=(self.game.name == "Bloodborne"),
                                            dimensions=atlas_img.size,
                        )
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                base.write(self.output_dir / base_path.name)
                logger.info("Successfully wrote file: %s", base_path)

            self.finished.emit(True, "All changes applied successfully!", self.output_dir)

        except Exception:
            self.finished.emit(False, format_exc_clean(), self.output_dir)
