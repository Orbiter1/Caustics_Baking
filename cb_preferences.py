import bpy
from .cb_pnl import update_sidebar_category

class CausticsBakingPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # UI
    sidebar_category: bpy.props.StringProperty(
        name = "Category Name",
        description = "Set sidebar category name. You can type in name of the existing category and panel will be added there, instead of creating new category",
        default = "Caustics Baking",
        update = update_sidebar_category,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, property="sidebar_category", text='Sidebar Category')

#### ------------------------------ REGISTRATION ------------------------------ ####

classes = [
    CausticsBakingPreferences,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)