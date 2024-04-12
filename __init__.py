import bpy
from bpy.app.handlers import persistent

from .cb_functions import build_collections
from .cb_nodeGroups import setupNodeGroups
from .cb_nodeGroups_v4 import setupNodeGroups as setupNodeGroups_v4

bl_info = {
    "name": "Caustics_Baking",
    "author": "Benary",
    "description": "This Addon uses the Cycles Pathracing Engine to do a mixture of Lighttracing and Photon Cashing.",
    "blender": (3, 4, 0),
    "version": (3, 1),
    "location": "View3D > Tools > Caustics Baking | Editor > Render > Caustics Baking",
    "warning": "",
    "category": "Render"
}

from .cb_op import CBSetContributor, CBUnSetContributor, CBSetBakingTarget, CBUnSetBakingTarget, \
    CBSetShadowCaster, CBUnSetShadowCaster, CBSetCausticSource, CBRunBaking, CBUnsetCausticSource
from .cb_pnl import CB_PT_PanelModifyObject, CB_PT_PanelBakingSettings, \
    Contributor_UL_List, Sources_UL_List, Recievers_UL_List, ShadowCasters_UL_List
from .cb_properties import CB_Props

classes = (
    CB_Props, CB_PT_PanelModifyObject, CB_PT_PanelBakingSettings, CBSetContributor,
    CBUnSetContributor, CBSetBakingTarget, CBUnSetBakingTarget, CBSetShadowCaster,
    CBUnSetShadowCaster, CBSetCausticSource, CBRunBaking, CBUnsetCausticSource, Contributor_UL_List, Sources_UL_List,
    Recievers_UL_List, ShadowCasters_UL_List)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.cb_props = bpy.props.PointerProperty(type=CB_Props)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    del bpy.types.Scene.cb_props
