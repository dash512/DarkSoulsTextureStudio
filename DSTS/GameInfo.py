from soulstruct.base.textures.dds.enums import DXGI_FORMAT

DXGI_STRUCT_MAP = { # copied from soulstruct, duplicates removed and reordered
    DXGI_FORMAT.BC7_UNORM: 102,
    DXGI_FORMAT.BC7_UNORM_SRGB: 112,
    DXGI_FORMAT.BC1_UNORM: 1,
    DXGI_FORMAT.BC3_UNORM: 5,
    DXGI_FORMAT.BC2_UNORM: 3,
    DXGI_FORMAT.BC4_UNORM: 24,
    DXGI_FORMAT.BC5_UNORM: 104,
    DXGI_FORMAT.B5G5R5A1_UNORM: 6,
    DXGI_FORMAT.R8G8B8A8_UNORM: 8,
    DXGI_FORMAT.B8G8R8A8_UNORM: 9,
    DXGI_FORMAT.A8_UNORM: 16,
    DXGI_FORMAT.R16G16B16A16_UNORM: 22,
    DXGI_FORMAT.BC6H_UF16: 100,
}

SubtexturePrefix = [
    "MENU_ItemIcon_",
    "MENU_Knowledge_",
    "MENU_MAP_",
    "MENU_StatusIcon_",
    "MENU_SkillStory_",
    "MENU_ItemBase_",
    "MENU_SaveIcon_",
    "MENU_RE_",
    "MENU_Ch_",
]

def getEntryPath(game= "Game", **kwargs): # unused function, may be useful info though so I'll leave it here
    """file - parent file, eg. '01_Common`
        
        format_mode - what resolution the file is for. generally hi/low
        
        layout_name - name of the .layout file"""
    match game.name:
        case "Sekiro": 
            imgpath = r"N:\NTC\data\Menu\ScaleForm\SBLayout\{file}\{format_mode}\{layout_name}"
        case "Elden Ring": 
            imgpath = r"N:\GR\data\Menu\ScaleForm\SBLayout\{file}\{format_mode}\{layout_name}"
        case "Nightreign": 
            imgpath = r"W:\CL\data\Target\INTERROOT_win64\menu\ScaleForm\Tif\{file}\{format_mode}\{layout_name}"
        case "Armored Core 6": 
            imgpath = r"W:\FNR\data\Menu\ScaleForm\SBLayout\{file}\{format_mode}\{layout_name}"

    return imgpath.format(**kwargs)
