from __future__ import annotations
import logging
# Basic Modules
import os
from io import BytesIO
from copy import deepcopy
from tempfile import NamedTemporaryFile
from pathlib import Path
from PIL import Image
import threading
# GUI
from PySide6.QtCore import QObject, Signal
# Soulstruct
from soulstruct.containers.tpf import TPF, TPFPlatform, TPFTexture, TPF_TEXTURE_FORMAT_TO_DXGI_FORMAT
from soulstruct.dcx import core, oodle
from soulstruct.games import Game, get_game, BLOODBORNE, NIGHTREIGN, DEMONS_SOULS
# Custom
from DSTS.Dataclasses import AtlasLayout, Atlas, SubTexture
from DSTS.Enums import ExportMode, GameType, WriteTask
from DSTS.Helpers import createDebugGrid
from DSTS.log_utils import format_exc_clean
from DSTS.Utilities import replaceTerms, loadJson

logger = logging.getLogger(__name__)

class LoadWorker(QObject):
    progress = Signal(int, str)   # percent, message
    finished = Signal(object, object, object, str)  # atlases, loaded dcx files, parsed xml data, error msg

    def __init__(self, file_mappings, game: Game):
        super().__init__()
        self.file_mappings = file_mappings
        self.game = game
        self.LOADED_DCX_FILES = {}
        self.LAYOUT_DATA = {}

    def run(self):
        try:
            logger.info("Beginning unpack for: %s", self.game)
            match self.game.gametype:
                case GameType.MODERN:
                    self.processModern()

                case GameType.LEGACY | GameType.PS:
                    self.processLegacy()

                case _:
                    logger.info("Unknown game type %s, defaulting to Legacy", self.game)
                    self.processLegacy()
        except:
            self.finished.emit({}, {}, {}, format_exc_clean())

    def handleUnpack(self, path):
        oodle.LOAD_DLL()
        if self.game.gametype == GameType.PS:
            try:
                tex,_ = core.decompress(path)
                tpfdcx = TPF.from_bytes(tex)
            except core.DCXError:
                tpfdcx = TPF(path) # it's probably a tpf file, may as well try
        else:
            tpfdcx = TPF(path)

        self.LOADED_DCX_FILES[path] = tpfdcx

        for texture in tpfdcx.textures:
            if self.game.gametype == GameType.PS:
                logger.debug("PS format detected. Creating headerized dds for TPFTexture: %s", texture.stem)
                if self.game == BLOODBORNE:
                    platform = TPFPlatform.PS4
                elif self.game == DEMONS_SOULS:
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

    def generateTextureList(self, dcx_path, percent) -> list[TPFTexture]:
        textures_list = []
        self.progress.emit(percent, f"Unpacking {dcx_path.stem}...")

        paths = []
        if dcx_path.is_dir():
            paths = [Path(dcx_path) / f for f in os.listdir(dcx_path) if f.endswith('tpf.dcx') or f.endswith('.tpf')]
        else:
            paths = [Path(dcx_path)]

        for path in paths:
            logger.info("Getting texture data for file: %s", path)
            for texture in self.handleUnpack(path):
                textures_list.append(texture)

        logger.info("Generated texture dictionary with %i entries", len(textures_list))
        self.progress.emit(percent, f"Loaded {dcx_path.stem}")
        return textures_list

    def processModern(self):
        atlases: dict[str, Atlas] = {}
        total_files = len(self.file_mappings)

        self.progress.emit(0, f'Loading {total_files} files...')
        for f_idx, file in enumerate(self.file_mappings, 1):
            percent = int(f_idx / total_files * 100 - 1)
            if isinstance(file, dict):
                _file: Path = file['file']
                textures = self.generateTextureList(_file, percent)

                self.progress.emit(percent, "Parsing layout binder...")
                atlas_layouts = AtlasLayout.from_binder(file['layout'])
                self.LAYOUT_DATA[_file] = atlas_layouts

                logger.info("Successfully parsed SB layout binder with %s entries", len(atlas_layouts))

                for name, atlas in Atlas.parse(textures, atlas_layouts, _file):
                    atlases[name] = atlas           

            elif isinstance(file, Path):
                textures = self.generateTextureList(file, percent)
                # add any textures that were not included in the layout
                for texture in textures:
                    name = texture.stem
                    atlases[name] = Atlas(name=name, vanilla=True, texture=texture, parent=file, subtextures=[]) # no layout info since single textures go to atlases
                logger.info("Successfully loaded %i atlases with no layouts.", len(atlases))

        logger.info("Load Worker process completed succesfully!")
        self.finished.emit(atlases, self.LOADED_DCX_FILES, self.LAYOUT_DATA, "")
        self.progress.emit(100, 'Successfully loaded all files!')

    def processLegacy(self):  
        atlases: dict[str, Atlas] = {}
        total_files = len(self.file_mappings)

        for f_idx, file in enumerate(self.file_mappings, 1):
            percent = int(f_idx / total_files * 100 - 1)
            textures = self.generateTextureList(file, percent)

            for texture in textures:
                name = texture.stem
                atlases[name] = Atlas(name=name, vanilla=True, texture=texture, parent=file, subtextures=[])
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
        self.finished.emit(atlases, self.LOADED_DCX_FILES, {}, "")

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
    requestCompression = Signal(str, bool) # file name, show encoding prompt
    finished = Signal(bool, str, Path)  # success, message, output location

    def __init__(self, atlases, new_atlases, loaded_files, layouts, alphaThreshold, game, output, task):
        super().__init__()
        self._event = threading.Event()
        self._result = None

        self.atlases = atlases
        self.new_atlases = new_atlases
        self.LOADED_DCX_FILES = loaded_files
        self.LAYOUT_FILES = layouts
        self.alphaThreshold = alphaThreshold
        self.game = game
        self.output_dir = output
        self.task = task

    def promptCompression(self, name, show_enc=True):
        self._event.clear()
        self.requestCompression.emit(name, show_enc)
        self._event.wait()
        return self._result

    def handle_new_atlases(self):
        tasks = []
        dcx_type = self.game.default_dcx_type
        enc = self.game.default_name_encoding
        is_reuse = False

        for atlas in self.new_atlases:
            if atlas.is_disabled:
                logger.debug("WriteWorker.handle_new_atlases(): Skipping disabled standalone Atlas %s", atlas.name)
                continue

            if atlas.parent is not None:
                tasks.append(atlas)
                continue

            if not is_reuse:
                _type, enc, is_reuse = self.promptCompression(atlas.name)
                dcx_type = core.DCXType[_type]

            logger.info("Writing standalone atlas: %s", self.output_dir / atlas.name)
            atlas.writetpf(
                self.output_dir,
                dcx_type=dcx_type,
                encoding=enc,
            )

        return tasks

    def processLayouts(self):
        for dcx_path in self.LAYOUT_FILES:

            logger.info("Processing layout for: %s", dcx_path)
            
            layout_objs = list(self.LAYOUT_FILES[dcx_path])

            layout_map = {
                replaceTerms(Path(layout.imagePath).stem, {"_h": "", "_l": ""}): layout # atlas name to AtlasLayout objects
                for layout in layout_objs
            }

            for atlas in self.atlases.values():
                if atlas.is_disabled:
                    logger.debug("WriteWorker.processLayouts(): Removing disabled standalone Atlas %s", atlas.name)
                    layout_map.pop(atlas.name)
                    continue

                additions = atlas.additions
                existing_layout = layout_map.get(atlas.name)

                if existing_layout:
                    if additions:
                        logger.info("Adding %i subtexture(s) to existing layout '%s'", len(additions), atlas.name)
                        existing_layout.add_subtextures(additions)

                    for sub in atlas.disabled:
                        existing_layout.rem(sub.name)

                else:
                    if not additions:
                        continue
                    
                    logger.info("Creating layout entry for '%s' with %i subtexture(s)", atlas.name, len(additions))
                    first_obj: AtlasLayout = layout_objs[0] # dummy used to fetch common info

                    imgpath = AtlasLayout.getImagePath(self.game, res=first_obj.res.display, atlas_name=atlas.name)
                    entry_path = first_obj.commonPath / f"{atlas.name}.layout"
                    dims = None
                    if self.game == NIGHTREIGN: # NR keeps width and height info in each .layout file's root
                        dims = self.atlases[atlas.name].dimensions

                    new_layout = AtlasLayout.create(
                        imagePath=imgpath,
                        entryPath=entry_path,
                        subtextures=additions,
                        dimensions=dims
                    )

                    layout_map[atlas.name] = new_layout                    

            file = dcx_path.name.replace('.tpf.dcx', '.sblytbnd.dcx')
            AtlasLayout.build(
                layout_objs=layout_map.values(),
                output=self.output_dir / file
            )
            logger.info("Successfully wrote file: %s", file)

    def processTextures(self):
        dcx_type = None
        is_reuse = False

        new_atlases = self.handle_new_atlases()

        for base_path, data in self.LOADED_DCX_FILES.items():

            if not is_reuse:
                _type, is_reuse = self.promptCompression(base_path.name, show_enc=False)
                dcx_type = core.DCXType[_type]

            base: TPF = deepcopy(data)
            if dcx_type is not None:
                base.dcx_type = dcx_type

            for atlas in new_atlases: # returns list of those with parents. Parentless files are written alone, not in a binder.
                if atlas.parent != base_path or atlas.is_disabled:
                    continue

                atlas.add_to_TPF(base, swizzle=(self.game == BLOODBORNE))

            for atlas in self.atlases.values():
                if atlas.is_disabled:
                    tex = base.find_texture_stem(atlas.name)
                    del tex
                    continue

                if (atlas.parent != base_path) or (not atlas.modified):
                    continue

                compiled_image = atlas.compileTexture()

                with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    temp_path = tmp.name
                    compiled_image.save(temp_path)
                try:
                    texture = base.find_texture_stem(atlas.name)
                    texture.replace_dds(temp_path,
                        dds_format=TPF_TEXTURE_FORMAT_TO_DXGI_FORMAT[texture.format].name,
                        swizzle=(self.game == BLOODBORNE),
                        dimensions=compiled_image.size,
                    )
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

            base.write(self.output_dir / base_path.name)
            logger.info("Successfully wrote file: %s", base_path)
        
    def run(self):
        try:
            match self.task:
                case WriteTask.ALL:
                    self.processLayouts()
                    self.processTextures()

                case WriteTask.TPF:
                    self.processTextures()

                case WriteTask.LYT:
                    self.processLayouts()             

            self.finished.emit(True, "All tasks completed successfully!", self.output_dir)

        except Exception:
            self.finished.emit(False, format_exc_clean(), self.output_dir)

