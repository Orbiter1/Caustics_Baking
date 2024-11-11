import bpy
from bpy.types import Panel

from .cb_const import CAUSTIC_RECEIVER_ATTRIBUTE, CAUSTIC_CONTRIBUTOR_ATTRIBUTE, CAUSTIC_SHADOW_ATTRIBUTE, \
    CAUSTIC_SOURCE_ATTRIBUTE

from .cb_op import CBSetCausticSource, CBSetShadowCaster, CBUnSetShadowCaster, CBSetContributor, \
    CBUnSetContributor, CBSetBakingTarget, CBUnSetBakingTarget, CBRunBaking, CBUnsetCausticSource, CBImportShaderNode


def update_sidebar_category(self, context):
    try:
        bpy.utils.unregister_class(CB_PT_PanelModifyObject)
    except:
        pass

    CB_PT_PanelModifyObject.bl_category = self.sidebar_category
    bpy.utils.register_class(CB_PT_PanelModifyObject)


class CB_PT_PanelModifyObject(Panel):
    bl_label = "Selection"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Caustics Baking"

    def draw(self, context):
        cb_props = context.scene.cb_props
        layout = self.layout
        col = layout.column(align=True)
        box = col.box()

        if bpy.context.active_object.type != 'LIGHT':
            if bpy.context.active_object.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, 0) == 1:
                col.operator(CBUnSetContributor.bl_idname)
                box.label(text="caustic contributor")

            if bpy.context.active_object.get(CAUSTIC_SHADOW_ATTRIBUTE, 0) == 1:
                col.operator(CBUnSetShadowCaster.bl_idname)
                box.label(text="caustic shadow-caster")

            if bpy.context.active_object.get(CAUSTIC_RECEIVER_ATTRIBUTE, 0) == 1:
                col.operator(CBUnSetBakingTarget.bl_idname)
                box.label(text="caustic receiver")
                col.template_list("UI_UL_list", "uvmaps", context.object.data, "uv_layers", cb_props, "uv_active_index")

            col.separator()

            if bpy.context.active_object.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, 0) == 0:
                col.operator(CBSetContributor.bl_idname)
            if bpy.context.active_object.get(CAUSTIC_RECEIVER_ATTRIBUTE, 0) == 0:
                col.operator(CBSetBakingTarget.bl_idname)
            if bpy.context.active_object.get(CAUSTIC_SHADOW_ATTRIBUTE, 0) == 0:
                col.operator(CBSetShadowCaster.bl_idname)

        else:
            if ('AREA', 'SPOT').__contains__(bpy.context.object.data.type):
                box.label(text="Area and Spot lights are not supported")
            else:
                if bpy.context.active_object.get(CAUSTIC_SOURCE_ATTRIBUTE, None) is None:
                    col.separator()
                    col.operator(CBSetCausticSource.bl_idname)
                else:
                    box.label(text="active caustic sensor")
                    col.operator(CBUnsetCausticSource.bl_idname)
        col.separator(factor=4)
        col.label(text='sources')
        col.template_list(CB_UL_sources_list.__name__, 'sources', bpy.context.scene, 'objects',
                          cb_props, 'source_active_object_index')
        col.label(text='contributors')
        col.template_list(CB_UL_contributer_list.__name__, 'contributors', bpy.context.scene, 'objects',
                          cb_props, 'contributor_active_object_index')
        col.label(text='receivers')
        col.template_list(CB_UL_recievers_list.__name__, 'receivers', bpy.context.scene, 'objects',
                          cb_props, 'receiver_active_object_index')
        col.label(text='shadow-casters')
        col.template_list(CB_UL_shadowcasters_list.__name__, 'shadow-casters', bpy.context.scene, 'objects',
                          cb_props, 'shadow_active_object_index')


class CB_PT_PanelImportShaderNode(Panel):
    bl_label = "Selection"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Caustics Baking"

    def draw(self, context):
        self.layout.operator(CBImportShaderNode.bl_idname)


class CB_PT_PanelBakingSettings(Panel):
    bl_label = "Caustics Baking"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        cb_props = context.scene.cb_props

        caustic_source = 0
        caustic_contributor = False
        caustic_receiver = False
        for obj in bpy.context.scene.objects:
            if obj.get(CAUSTIC_SOURCE_ATTRIBUTE, False):
                caustic_source += 1
            if obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, False):
                caustic_contributor = True
            if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, False):
                caustic_receiver = True

        pan = layout.panel('Baking Settings')
        pan[0].label(text="Baking Settings")

        if pan[1]:
            col = pan[1].column()
            col.prop(cb_props, 'sampleResMultiplier')
            col.prop(cb_props, "samples")
            col.prop(cb_props, "denoise")
            col.prop(cb_props, "colored")
            if caustic_source <= 1:
                col.prop(cb_props, 'bake_energy')
            else:
                col.label(text='bake energy active', icon='INFO')
            col.prop(cb_props, 'use_gpu')

        pan = layout.panel('Export Setting')
        pan[0].label(text="Export Setting")

        targetImageError = False
        if pan[1]:
            col = pan[1].column()
            col.prop(cb_props, 'useImage')
            if not cb_props.useImage:
                col.prop(cb_props, "textureRes")

            if cb_props.useImage:
                col.prop(cb_props, 'targetImage', icon_only=True)
                if cb_props.targetImage is not None:
                    width, height = cb_props.targetImage.size
                    if width != height:
                        col.label(text='target image has to be square', icon='ERROR')
                        targetImageError = True
                else:
                    targetImageError = True
            else:
                split = col.split(factor=0.4)
                split.alignment = 'RIGHT'
                split.label(text='imageName')
                split.prop(cb_props, "imageName", icon_only=True, icon='FILE_IMAGE')

            pan = layout.panel('save_image_externally')
            pan[0].prop(cb_props, 'save_image_externally')
            if pan[1] and cb_props.save_image_externally:
                pan[1].prop(cb_props, "filePath", icon_only=True)

        if caustic_source and caustic_contributor and caustic_receiver and not targetImageError:
            layout.operator(CBRunBaking.bl_idname)


class CB_UL_contributer_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon_value=layout.icon(item.data))

    def filter_items(self, context, data, property):
        items = getattr(data, property)
        filtered = [self.bitflag_filter_item] * len(items)
        ordered = []
        for i, item in enumerate(items):
            if not item.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, 0):
                filtered[i] &= ~self.bitflag_filter_item
            ordered.append(i)
        return filtered, ordered


class CB_UL_sources_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon_value=layout.icon(item.data))

    def filter_items(self, context, data, property):
        items = getattr(data, property)
        filtered = [self.bitflag_filter_item] * len(items)
        ordered = []
        for i, item in enumerate(items):
            if not item.get(CAUSTIC_SOURCE_ATTRIBUTE, 0):
                filtered[i] &= ~self.bitflag_filter_item
            ordered.append(i)
        return filtered, ordered


class CB_UL_recievers_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon_value=layout.icon(item.data))

    def filter_items(self, context, data, property):
        items = getattr(data, property)
        filtered = [self.bitflag_filter_item] * len(items)
        ordered = []
        for i, item in enumerate(items):
            if not item.get(CAUSTIC_RECEIVER_ATTRIBUTE, 0):
                filtered[i] &= ~self.bitflag_filter_item
            ordered.append(i)
        return filtered, ordered


class CB_UL_shadowcasters_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon_value=layout.icon(item.data))

    def filter_items(self, context, data, property):
        items = getattr(data, property)
        filtered = [self.bitflag_filter_item] * len(items)
        ordered = []
        for i, item in enumerate(items):
            if not item.get(CAUSTIC_SHADOW_ATTRIBUTE, 0):
                filtered[i] &= ~self.bitflag_filter_item
            ordered.append(i)
        return filtered, ordered


#### ------------------------------ REGISTRATION ------------------------------ ####

classes = [
    CB_PT_PanelModifyObject, CB_PT_PanelBakingSettings, CB_UL_contributer_list, CB_UL_sources_list,
    CB_UL_recievers_list, CB_UL_shadowcasters_list, CB_PT_PanelImportShaderNode
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    prefs = bpy.context.preferences.addons[__package__].preferences
    update_sidebar_category(prefs, bpy.context)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
