import threading
from datetime import datetime
import bpy
import numpy as np

from .cb_textureRenderingFunctions import compute_caustic_map
from .cb_const import CAUSTIC_SHADOW_ATTRIBUTE, CAUSTIC_SOURCE_ATTRIBUTE, UV_SCALE_MAP_NAME, \
    CAUSTIC_CONTRIBUTOR_ATTRIBUTE, \
    CAUSTIC_RECEIVER_ATTRIBUTE
from .cb_functions import reset_compositor, reset_scene, scene_setup, setup_compositor, denoising, color_sampling, \
    is_debug, \
    auto_cam_placement, build_collections, remove_collections, cam_setup, unset_collection, set_collection
from .cb_nodeGroups import setup_shader_node_group, setup_geo_node_groups


class CBSetContributor(bpy.types.Operator):
    bl_idname = "cb.set_contributor"
    bl_label = "Set Contributor"
    bl_description = "Sets Object to contributor"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if ('MESH', 'CURVE', 'LIGHT', 'FONT', 'META', 'SURFACE').__contains__(obj.type):
                obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE] = True

                if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_RECEIVER_ATTRIBUTE]
                if obj.get(CAUSTIC_SHADOW_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_SHADOW_ATTRIBUTE]
        return {"FINISHED"}


class CBUnSetContributor(bpy.types.Operator):
    bl_idname = "cb.unset_contributor"
    bl_label = "Remove Contributor"
    bl_description = "Removes contributor attribute"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, None) is not None:
                del obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE]
        return {"FINISHED"}


class CBSetBakingTarget(bpy.types.Operator):
    bl_idname = "cb.set_baking_target"
    bl_label = "Set Reciever"
    bl_description = "Sets Object to baking target"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if ('MESH').__contains__(obj.type):
                obj[CAUSTIC_RECEIVER_ATTRIBUTE] = True
                if obj.get(UV_SCALE_MAP_NAME, None) is None:
                    obj[UV_SCALE_MAP_NAME] = obj.data.uv_layers[0]

                hasattr(obj, CAUSTIC_CONTRIBUTOR_ATTRIBUTE)
                if obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE]
                if obj.get(CAUSTIC_SHADOW_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_SHADOW_ATTRIBUTE]
        return {"FINISHED"}


class CBUnSetBakingTarget(bpy.types.Operator):
    bl_idname = "cb.unset_baking_target"
    bl_label = "Remove Reciever"
    bl_description = "Removes baking attribute"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, None) is not None:
                del obj[CAUSTIC_RECEIVER_ATTRIBUTE]
        return {"FINISHED"}


class CBSetShadowCaster(bpy.types.Operator):
    bl_idname = "cb.set_shadow_caster"
    bl_label = "Set Shadow Caster"
    bl_description = ""

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if ('MESH', 'CURVE', 'LIGHT', 'FONT', 'META', 'SURFACE').__contains__(obj.type):
                obj[CAUSTIC_SHADOW_ATTRIBUTE] = True
                if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_RECEIVER_ATTRIBUTE]
                if obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE]
        return {"FINISHED"}


class CBUnSetShadowCaster(bpy.types.Operator):
    bl_idname = "cb.unset_shadow_caster"
    bl_label = "Remove Shadow Caster attribute"
    bl_description = ""

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.get(CAUSTIC_SHADOW_ATTRIBUTE, None) is not None:
                del obj[CAUSTIC_SHADOW_ATTRIBUTE]
        return {"FINISHED"}


class CBSetCausticSource(bpy.types.Operator):
    bl_idname = "cb.set_caustic_source"
    bl_label = "Set Caustic Source"
    bl_description = "sets the selected light to be the caustic source"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.type == 'LIGHT':
                if ('POINT', 'SUN').__contains__(obj.data.type):
                    obj[CAUSTIC_SOURCE_ATTRIBUTE] = True
        return {"FINISHED"}


class CBUnsetCausticSource(bpy.types.Operator):
    bl_idname = "cb.unset_caustic_source"
    bl_label = "Remove Caustic Source"
    bl_description = "removes caustic source attribute"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.get(CAUSTIC_SOURCE_ATTRIBUTE, None) is not None:
                del obj[CAUSTIC_SOURCE_ATTRIBUTE]

        return {"FINISHED"}


class CBImportShaderNode(bpy.types.Operator):
    bl_idname = "cb.import_shadernode"
    bl_label = "Import ShaderNode"
    bl_description = "Imports the CB_Main_Caustics_Node"

    def execute(self, context):
        setup_shader_node_group()
        return {"FINISHED"}


class CBRunBaking(bpy.types.Operator):
    bl_idname = "cb.run_bake"
    bl_label = "Run Caustics Bake"
    bl_description = "starts the baking process"

    def __init__(self):
        self.ui_updated = False
        self.light_amount = None
        self.light_count = 0
        self.original_scene_settings = None
        self.active_cam = None
        self.cams = None
        cb_props = bpy.context.scene.cb_props
        self._timer = None
        self.stop = False
        self.render = True
        self.coordinates = None
        self.startTime = datetime.now()
        self.colored = cb_props.colored
        if cb_props.useImage:
            self.textureRes = cb_props.targetImage.size[0]
        else:
            self.textureRes = cb_props.textureRes
        self.samples = 0
        self.counter = 0
        self.target = np.full((self.textureRes * self.textureRes, 4), [0.0, 0.0, 0.0, 1.0])
        self.finish = False
        self.threads = []
        self.image_normalization = (self.textureRes ** 2) / ((1024 * cb_props.sampleResMultiplier) ** 2)

        if cb_props.useImage:
            self.image = cb_props.targetImage
        else:
            self.image = bpy.data.images.get(cb_props.imageName)
            if self.image is None:
                self.image = bpy.data.images.new(name=cb_props.imageName, width=self.textureRes,
                                                 height=self.textureRes,
                                                 alpha=False, float_buffer=True)
            else:
                self.image.scale(self.textureRes, self.textureRes)

        self.spaceInfo = None

    def execute(self, context):
        return {"FINISHED"}

    # function that is called after a rendering is complete
    def post(self, scene, context=None):
        if not self.finish:
            if self.colored:
                # process for colored image
                if self.coordinates is None:
                    # saving the coordinate array and setting up for the color render
                    self.coordinates = np.array(bpy.data.images['Viewer Node'].pixels[:]).reshape(-1, 4)
                    if (self.coordinates[:, 2] > 0).any():
                        color_sampling(1)
                    else:
                        # with no valid coordinates found all remaining samples for the camera are skipped
                        scene.cycles.sample_offset = scene.cycles.sample_offset + 1
                        self.coordinates = None
                        self.counter += self.active_cam['remaining']
                        self.active_cam['remaining'] = 0
                        self.update_info()
                else:
                    # starting the processing thread with the saved coordinates and the color information of the
                    # current render
                    fov = self.active_cam.data.fisheye_fov
                    thread = threading.Thread(target=compute_caustic_map,
                                              args=[self.target, self.coordinates,
                                                    np.array(bpy.data.images['Viewer Node'].pixels[:]).reshape(-1, 4),
                                                    self.textureRes, self.colored, self.counter,
                                                    self.active_cam.data.type == 'PANO',
                                                    bpy.context.scene.render.resolution_x, fov,
                                                    self.image_normalization * self.active_cam['cam_normalization'],
                                                    is_debug()])
                    self.threads.append(thread)
                    thread.start()

                    # switching to a new random sampling position within every pixel
                    scene.cycles.sample_offset = scene.cycles.sample_offset + 1

                    # resetting for next sample
                    self.coordinates = None
                    self.active_cam['remaining'] -= 1
                    self.counter += 1
                    self.update_info()
                    color_sampling(0)
            else:
                # process with only luminance, coordinate information is directly given to the processing function
                fov = self.active_cam.data.fisheye_fov
                thread = threading.Thread(target=compute_caustic_map,
                                          args=[self.target,
                                                np.array(bpy.data.images['Viewer Node'].pixels[:]).reshape(-1, 4),
                                                np.empty(0), self.textureRes, self.colored, self.counter,
                                                self.active_cam.data.type == 'PANO',
                                                bpy.context.scene.render.resolution_x, fov,
                                                self.image_normalization * self.active_cam['cam_normalization'],
                                                is_debug()])
                self.threads.append(thread)
                thread.start()

                # resetting for next sample
                scene.cycles.sample_offset = scene.cycles.sample_offset + 1
                if (np.array(bpy.data.images['Viewer Node'].pixels[:]).reshape(-1, 4)[:, 2] > 0).any():
                    self.active_cam['remaining'] -= 1
                    self.counter += 1
                else:
                    # with no valid coordinates found all remaining samples for the camera are skipped
                    self.counter += self.active_cam['remaining']
                    self.active_cam['remaining'] = 0
                self.update_info()
                self.ui_updated = False
            self.render = True

    def cancelled(self, scene, context=None):
        self.stop = True

    # updates the information displayed in the statusbar
    def update_info(self):
        if self.counter < self.samples:
            bpy.context.scene.cb_props.progress_indicator_text = f'Light {self.light_count + 1}/{self.light_amount} | Render {self.counter + 1}/{self.samples}'
        else:
            bpy.context.scene.cb_props.progress_indicator_text = f'Processing'
        bpy.context.scene.cb_props.progress_indicator = (
                                                                self.counter / self.samples / self.light_amount + self.light_count / self.light_amount) * 100
        bpy.context.scene.cb_props.time_elapsed = str(datetime.now() - self.startTime)
        self.ui_updated = True

    def modal(self, context, event):
        if event.type == 'ESC':
            self.stop = True
        if event.type == 'TIMER':
            cb_props = bpy.context.scene.cb_props
            self.update_info()
            if self.finish and not self.stop:
                # waiting for the data processing to finish which is handled in separate threads
                for thread in self.threads:
                    thread.join()

                # setting the image alpha to 1 and transferring the data into a blender image object
                self.target[:, 3] = 1
                self.image.pixels = self.target.reshape(-1)

                # denoising the image
                if cb_props.denoise:
                    context.scene.cb_props.progress_indicator_text = 'Denoising'
                    self.image.pixels = denoising(self.image.name)

                # saving the image externally
                self.image.file_format = 'OPEN_EXR'
                if cb_props.save_image_externally:
                    if cb_props.useImage:
                        image_name = cb_props.targetImage.name
                    else:
                        image_name = cb_props.imageName
                    self.image.filepath_raw = cb_props.filePath + image_name + '.exr'
                    self.image.save()

                print("caustic map complete in", datetime.now() - self.startTime)
                self.stop = True

            if self.stop:
                # resetting the blender scene to its original state
                reset_compositor()
                reset_scene(bpy.context.scene, self.original_scene_settings)
                bpy.app.handlers.render_post.remove(self.post)
                bpy.app.handlers.render_cancel.remove(self.cancelled)
                remove_collections()
                bpy.context.workspace.status_text_set(None)
                context.window_manager.event_timer_remove(self._timer)
                cb_props.cb_running_baking = False
                return {"FINISHED"}

            elif self.render and self.ui_updated:
                if self.active_cam['remaining'] <= 0:
                    if len(self.cams) > 0:
                        # switching to next cam
                        self.active_cam = self.cams.pop()
                    else:
                        # switching to next light
                        self.light_count += 1
                        if self.light_count < self.light_amount:
                            self.cams = auto_cam_placement(
                                bpy.data.collections[CAUSTIC_SOURCE_ATTRIBUTE].objects[self.light_count])
                            self.samples = 0
                            for cam in self.cams:
                                self.samples += cam['remaining']
                            self.active_cam = self.cams.pop()
                            self.counter = 0
                            self.update_info()
                        else:
                            self.finish = True

                # starting next sample
                if self.active_cam['remaining'] > 0:
                    cam_setup(self.active_cam)
                    self.render = False
                    bpy.ops.render.render()
                    # updating output image
                    self.image.pixels = self.target.reshape(-1)

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        missing_material = False
        message = 'The following objects are missing a material: '
        for obj in bpy.context.scene.objects:
            if obj.get('cb_contributor', False) or obj.get('cb_receiver', False) or obj.get('cb_shadow_caster', False):
                if obj.active_material == None:
                    missing_material = True
                    message += obj.name+', '
        cb_props = bpy.context.scene.cb_props
        if missing_material:
            show_message_box(message=message, title='Missing material detected', icon='ERROR')
        elif not cb_props.cb_running_baking:
            # setting up the baking process
            cb_props.cb_running_baking = True
            setup_geo_node_groups()
            setup_shader_node_group()
            build_collections()
            self.light_amount = len(bpy.data.collections[CAUSTIC_SOURCE_ATTRIBUTE].all_objects)
            self.cams = auto_cam_placement(bpy.data.collections[CAUSTIC_SOURCE_ATTRIBUTE].objects[self.light_count])
            for cam in self.cams:
                self.samples += cam['remaining']
            self.active_cam = self.cams.pop()
            self.original_scene_settings = scene_setup(bpy.context.scene)
            setup_compositor()
            self.colored = cb_props.colored
            self.update_info()

            # adding handlers and starting modal operator
            bpy.app.handlers.render_post.append(self.post)
            bpy.app.handlers.render_cancel.append(self.cancelled)
            bpy.context.workspace.status_text_set(info)
            self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return {"FINISHED"}


# callback to display progress information in the statusbar
def info(header, context):
    layout = header.layout
    layout.label(text="to cancel", icon='EVENT_ESC')
    layout.prop(context.scene.cb_props, "time_elapsed", text='time elapsed', emboss=False)
    layout.prop(context.scene.cb_props, "progress_indicator",
                text=context.scene.cb_props.progress_indicator_text, slider=True)


def show_message_box(message="", title="Message Box", icon='INFO'):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


#### ------------------------------ REGISTRATION ------------------------------ ####

classes = [
    CBSetContributor, CBUnSetContributor, CBSetBakingTarget, CBUnSetBakingTarget, CBSetShadowCaster,
    CBUnSetShadowCaster, CBSetCausticSource, CBRunBaking, CBUnsetCausticSource, CBImportShaderNode
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
