import bpy

bl_info = {
    "name": "Caustics_Baking",
    "author": "Benary",
    "description": "This Addon uses the Cycles Pathracing Engine to do a mixture of Lighttracing and Photon Cashing.",
    "blender": (4, 2, 0),
    "version": (3, 1),
    "location": "View3D > Tools > Caustics Baking | Editor > Render > Caustics Baking",
    "warning": "",
    "category": "Render"
}

from .cb_op import CBSetContributor, CBUnSetContributor, CBSetBakingTarget, CBUnSetBakingTarget, \
    CBSetShadowCaster, CBUnSetShadowCaster, CBSetCausticSource, CBRunBaking, CBUnsetCausticSource, CBImportShaderNode
from .cb_pnl import CB_PT_PanelModifyObject, CB_PT_PanelBakingSettings, \
    Contributor_UL_List, Sources_UL_List, Recievers_UL_List, ShadowCasters_UL_List, CB_PT_PanelImportShaderNode
from .cb_properties import CB_Props

classes = (
    CB_Props, CB_PT_PanelModifyObject, CB_PT_PanelBakingSettings, CB_PT_PanelImportShaderNode, CBSetContributor,
    CBUnSetContributor, CBSetBakingTarget, CBUnSetBakingTarget, CBSetShadowCaster,
    CBUnSetShadowCaster, CBSetCausticSource, CBRunBaking, CBUnsetCausticSource, Contributor_UL_List, Sources_UL_List,
    Recievers_UL_List, ShadowCasters_UL_List, CBImportShaderNode)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.cb_props = bpy.props.PointerProperty(type=CB_Props)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    del bpy.types.Scene.cb_props
