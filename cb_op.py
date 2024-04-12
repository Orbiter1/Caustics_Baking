import threading
from datetime import datetime
import bpy
import gpu
import json
import numpy as np

from .cb_mainfunctions import compute_caustic_map
from .cb_const import CAUSTIC_SHADOW_ATTRIBUTE, CAUSTIC_SOURCE_ATTRIBUTE, UV_SCALE_MAP_NAME, \
    CAUSTIC_CONTRIBUTOR_ATTRIBUTE, \
    CAUSTIC_RECEIVER_ATTRIBUTE
from .cb_functions import reset_compositor, reset_scene, scene_setup, setup_compositor, denoising, color_sampling, \
    is_debug, \
    auto_cam_placement, build_collections, remove_collections, cam_setup, unset_collection, set_collection
from .cb_nodeGroups_v4 import setup_shader_node_groups, setup_geo_node_groups


class CBSetContributor(bpy.types.Operator):
    bl_idname = "cb.set_contributor"
    bl_label = "Set Contributor"
    bl_description = "Sets Object to contributor"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if ('MESH', 'CURVE', 'LIGHT', 'FONT', 'META', 'SURFACE').__contains__(obj.type):
                obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE] = 1

                if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_RECEIVER_ATTRIBUTE]
                if obj.get(CAUSTIC_SHADOW_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_SHADOW_ATTRIBUTE]
        setup_shader_node_groups()
        return {"FINISHED"}


class CBUnSetContributor(bpy.types.Operator):
    bl_idname = "cb.unset_contributor"
    bl_label = "Remove Contributor"
    bl_description = "Removes object from contributors"

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
                obj[CAUSTIC_RECEIVER_ATTRIBUTE] = 1
                if obj.get(UV_SCALE_MAP_NAME, None) is None:
                    obj[UV_SCALE_MAP_NAME] = obj.data.uv_layers[0]

                hasattr(obj, CAUSTIC_CONTRIBUTOR_ATTRIBUTE)
                if obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE]
                if obj.get(CAUSTIC_SHADOW_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_SHADOW_ATTRIBUTE]
        setup_shader_node_groups()
        return {"FINISHED"}


class CBUnSetBakingTarget(bpy.types.Operator):
    bl_idname = "cb.unset_baking_target"
    bl_label = "Remove Reciever"
    bl_description = "Removes object from baking"

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
                obj[CAUSTIC_SHADOW_ATTRIBUTE] = 1
                if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_RECEIVER_ATTRIBUTE]
                if obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE, None) is not None:
                    del obj[CAUSTIC_CONTRIBUTOR_ATTRIBUTE]
        setup_shader_node_groups()
        return {"FINISHED"}


class CBUnSetShadowCaster(bpy.types.Operator):
    bl_idname = "cb.unset_shadow_caster"
    bl_label = "Remove Shadow Caster"
    bl_description = ""

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.get(CAUSTIC_SHADOW_ATTRIBUTE, None) is not None:
                del obj[CAUSTIC_SHADOW_ATTRIBUTE]
        return {"FINISHED"}


class CBSetCausticSource(bpy.types.Operator):
    bl_idname = "cb.set_caustic_source"
    bl_label = "Set Caustic Source"
    bl_description = "sets the selcted light to be the caustic source"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.type == 'LIGHT':
                if ('POINT', 'SUN').__contains__(obj.data.type):
                    obj[CAUSTIC_SOURCE_ATTRIBUTE] = True
        setup_shader_node_groups()
        return {"FINISHED"}


class CBUnsetCausticSource(bpy.types.Operator):
    bl_idname = "cb.unset_caustic_source"
    bl_label = "Remove Caustic Source"
    bl_description = "removes this light from caustic source"

    def execute(self, context):
        for obj in bpy.context.selected_objects:
            if obj.get(CAUSTIC_SOURCE_ATTRIBUTE, None) is not None:
                del obj[CAUSTIC_SOURCE_ATTRIBUTE]

        return {"FINISHED"}


class CBRunBaking(bpy.types.Operator):
    bl_idname = "cb.run_bake"
    bl_label = "Run Caustics Bake"
    bl_description = ""

    def __init__(self):
        self.ui_updated = False
        self.light_amount = None
        self.light_count = 0
        self.scene_settings = None
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

    def post(self, scene, context=None):
        ui_update = False
        if not self.finish:
            if self.colored:
                if self.coordinates is None:
                    self.coordinates = np.array(bpy.data.images['Viewer Node'].pixels[:]).reshape(-1, 4)
                    if (self.coordinates[:, 2] > 0).any():
                        color_sampling(1)
                    else:
                        scene.cycles.sample_offset = scene.cycles.sample_offset + 1
                        self.coordinates = None
                        self.counter += self.active_cam['remaining']
                        self.active_cam['remaining'] = 0
                        self.update_info()
                else:
                    if (4, 0, 0) > bpy.app.version:
                        fov = self.active_cam.data.cycles.fisheye_fov
                    else:
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

                    scene.cycles.sample_offset = scene.cycles.sample_offset + 1

                    self.coordinates = None
                    self.active_cam['remaining'] -= 1
                    self.counter += 1
                    self.update_info()
                    color_sampling(0)
            else:
                if (4, 0, 0) > bpy.app.version:
                    fov = self.active_cam.data.cycles.fisheye_fov
                else:
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

                scene.cycles.sample_offset = scene.cycles.sample_offset + 1
                if (np.array(bpy.data.images['Viewer Node'].pixels[:]).reshape(-1, 4)[:, 2] > 0).any():
                    self.active_cam['remaining'] -= 1
                    self.counter += 1
                else:
                    self.counter += self.active_cam['remaining']
                    self.active_cam['remaining'] = 0
                self.update_info()
                self.ui_updated = False
            self.render = True

    def cancelled(self, scene, context=None):
        self.stop = True

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
                for thread in self.threads:
                    thread.join()

                self.target[:, 3] = 1
                self.image.pixels = self.target.reshape(-1)

                if cb_props.denoise:
                    context.scene.cb_props.progress_indicator_text = 'Denoising'
                    self.image.pixels = denoising(self.image.name)

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
                reset_compositor()
                reset_scene(bpy.context.scene, self.scene_settings)
                bpy.app.handlers.render_post.remove(self.post)
                bpy.app.handlers.render_cancel.remove(self.cancelled)
                remove_collections()
                bpy.context.workspace.status_text_set(None)
                context.window_manager.event_timer_remove(self._timer)
                cb_props.cb_run_baking = None
                return {"FINISHED"}
            elif self.render and self.ui_updated:
                if self.active_cam['remaining'] <= 0:
                    if len(self.cams) > 0:
                        self.active_cam = self.cams.pop()
                    else:
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
                if self.active_cam['remaining'] > 0:
                    cam_setup(self.active_cam)
                    self.render = False
                    bpy.ops.render.render()
                    self.image.pixels = self.target.reshape(-1)

        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        setup_geo_node_groups()
        build_collections()
        cb_props = bpy.context.scene.cb_props
        cb_props.cb_run_baking = self
        self.light_amount = len(bpy.data.collections[CAUSTIC_SOURCE_ATTRIBUTE].all_objects)
        self.cams = auto_cam_placement(bpy.data.collections[CAUSTIC_SOURCE_ATTRIBUTE].objects[self.light_count])
        for cam in self.cams:
            self.samples += cam['remaining']
        self.active_cam = self.cams.pop()
        self.scene_settings = scene_setup(bpy.context.scene)
        setup_compositor()
        self.colored = cb_props.colored

        self.update_info()
        bpy.app.handlers.render_post.append(self.post)
        bpy.app.handlers.render_cancel.append(self.cancelled)
        bpy.context.workspace.status_text_set(info)
        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


def info(header, context):
    layout = header.layout
    layout.label(text="to cancel", icon='EVENT_ESC')
    layout.prop(context.scene.cb_props, "time_elapsed", text='time elapsed', emboss=False)
    layout.prop(context.scene.cb_props, "progress_indicator",
                text=context.scene.cb_props.progress_indicator_text, slider=True)
