import bpy

bl_info = {
    "name": "Caustics_Baking",
    "author": "Benary",
    "description": "This Addon uses the Cycles Pathracing Engine to do a mixture of Lighttracing and Photon Cashing.",
    "blender": (4, 2, 1),
    "version": (3, 2),
    "location": "View3D > Tools > Caustics Baking | Editor > Render > Caustics Baking",
    "warning": "",
    "category": "Render"
}

from . import (cb_preferences, cb_op, cb_pnl, cb_properties)

modules = [
    cb_preferences,
    cb_properties,
    cb_op,
    cb_pnl
]

def register():
    for module in modules:
        module.register()


def unregister():
    for module in modules:
        module.unregister()
