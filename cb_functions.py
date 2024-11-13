import math
import bpy
import mathutils
from mathutils.bvhtree import BVHTree
from .cb_const import CAUSTIC_RECEIVER_ATTRIBUTE, CAUSTIC_CONTRIBUTOR_ATTRIBUTE, \
    CAUSTIC_HIDDEN_ATTRIBUTE, CAUSTIC_MATERIAL_OUTPUT, CAUSTIC_SENSOR_NAME, \
    CAUSTIC_SHADOW_ATTRIBUTE, CAUSTIC_SOURCE_ATTRIBUTE, DEBUG_MODE, DELETE_NODE_ON_RESET, \
    NODEGROUP_MAIN_NAME, UV_SCALE_MAP_NAME, NODEGROUP_CAM_PLACEMENT_ORTHO, NODEGROUP_CLIPPING_PLANES_ORTHO, \
    NODEGROUP_CAM_PLACEMENT_PANO, NODEGROUP_CLIPPING_PLANES_PANO, PANO_NORMALIZATION, ORTHO_NORMALIZATION
import numpy as np


# Preparing the Scene to Render Reciever Coordinates
def scene_setup(scene):
    scene_settings = {
        'render_settings': set_render_settings(scene),
        'shader_settings': shader_setup()
    }
    visibility_setup(scene)
    uv_scale_map_setup(scene)
    return scene_settings


# Resetting the Scene to its original state
def reset_scene(scene, scene_settings):
    reset_render_settings(scene, scene_settings['render_settings'])
    reset_visibility(scene)
    shader_reset(scene_settings['shader_settings'])
    uv_scale_map_reset(scene)


# Setting render settings to the correct values for the baking Process and returning original settings
def set_render_settings(scene):
    cb_props = scene.cb_props
    render_settings = {
        'engine': scene.render.engine,
        'resolution_x': scene.render.resolution_x,
        'resolution_y': scene.render.resolution_y,
        'pixel_aspect_x': scene.render.pixel_aspect_x,
        'pixel_aspect_y': scene.render.pixel_aspect_y,
        'resolution_percentage': scene.render.resolution_percentage,
        'use_persistent_data': scene.render.use_persistent_data,
        'camera': scene.camera,
        'device': scene.cycles.device,
        'samples': scene.cycles.samples,
        'use_denoising': scene.cycles.use_denoising,
        'sample_offset': scene.cycles.sample_offset,
        'sample_clamp_direct': scene.cycles.sample_clamp_direct,
        'sample_clamp_indirect': scene.cycles.sample_clamp_indirect
    }

    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = int(1024 * cb_props.sampleResMultiplier)
    scene.render.resolution_y = int(1024 * cb_props.sampleResMultiplier)
    scene.render.resolution_percentage = 100
    scene.render.use_persistent_data = True
    if cb_props.use_gpu:
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.sample_offset = 1
    scene.cycles.sample_clamp_direct = 0
    scene.cycles.sample_clamp_indirect = 0

    return render_settings


# setting the render settings to the given settings
def reset_render_settings(scene, render_settings):
    scene.render.engine = render_settings['engine']

    scene.render.resolution_x = render_settings['resolution_x']
    scene.render.resolution_y = render_settings['resolution_y']
    scene.render.pixel_aspect_x = render_settings['pixel_aspect_x']
    scene.render.pixel_aspect_y = render_settings['pixel_aspect_y']
    scene.render.resolution_percentage = render_settings['resolution_percentage']
    scene.render.use_persistent_data = render_settings['use_persistent_data']

    scene.cycles.device = render_settings['device']
    scene.cycles.samples = render_settings['samples']
    scene.cycles.use_denoising = render_settings['use_denoising']
    scene.cycles.sample_offset = render_settings['sample_offset']
    scene.cycles.sample_clamp_direct = render_settings['sample_clamp_direct']
    scene.cycles.sample_clamp_indirect = render_settings['sample_clamp_indirect']

    scene.camera = render_settings['camera']


# Hiding all Objects that are not needed and marking them
def visibility_setup(scene):
    for obj in scene.objects:
        if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, False) is False and obj.get(CAUSTIC_CONTRIBUTOR_ATTRIBUTE,
                                                                           False) is False and obj.get(
            CAUSTIC_SHADOW_ATTRIBUTE, False) is False and obj.hide_render is False:
            obj.hide_render = True
            obj[CAUSTIC_HIDDEN_ATTRIBUTE] = 1


# Restoring visibility of all objects hidden by the previous function
def reset_visibility(scene):
    for obj in scene.objects:
        if obj.get(CAUSTIC_HIDDEN_ATTRIBUTE, False):
            obj.hide_render = False
            del obj[CAUSTIC_HIDDEN_ATTRIBUTE]


# Editing all materials to fulfill their function in the baking process
def shader_setup():
    for material in bpy.data.materials:
        material.use_nodes = True
        nodes = material.node_tree.nodes
        caustic_node = None
        for node in nodes:
            # Finding the custom shader node which holds relevant Material information
            if node.bl_idname == 'ShaderNodeGroup' and node.node_tree.name == NODEGROUP_MAIN_NAME:
                caustic_node = node

        # Creating the custom shader node in materials without it to produce default behavior
        if caustic_node is None:
            caustic_node = nodes.new('ShaderNodeGroup')
            caustic_node[DELETE_NODE_ON_RESET] = True
            caustic_node.node_tree = bpy.data.node_groups[NODEGROUP_MAIN_NAME]

        # Creating new output node to keep original connections intact
        output = nodes.new('ShaderNodeOutputMaterial')
        output.name = CAUSTIC_MATERIAL_OUTPUT
        output[DELETE_NODE_ON_RESET] = True
        output.is_active_output = True

        # linking custom shader node to the new active output
        links = material.node_tree.links
        links.new(output.inputs[0], caustic_node.outputs[0])
        links.new(output.inputs[1], caustic_node.outputs[1])

    # Deactivating world shader
    shader_settings = None
    if bpy.context.scene.world:
        shader_settings = {
            'world_use_nodes': bpy.context.scene.world.use_nodes,
            'world_color': bpy.context.scene.world.color
        }
        bpy.context.scene.world.use_nodes = False
        bpy.context.scene.world.color = (0, 0, 0)
    color_sampling(0)
    return shader_settings


# restoring all materials to their original state
def shader_reset(shader_settings):
    for material in bpy.data.materials:
        nodes = material.node_tree.nodes
        for node in nodes:
            if node.get(DELETE_NODE_ON_RESET, False):
                nodes.remove(node)

    # restoring world shader
    if bpy.context.scene.world:
        bpy.context.scene.world.color = shader_settings['world_color']
        bpy.context.scene.world.use_nodes = shader_settings['world_use_nodes']


# adding a modifier to all reciever objects that calculates the ratio between uv surface area and actual area
def uv_scale_map_setup(scene):
    for obj in scene.objects:
        if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, False):
            modifier = obj.modifiers.new(name=UV_SCALE_MAP_NAME, type='NODES')
            modifier.node_group = bpy.data.node_groups[UV_SCALE_MAP_NAME]
            inputs = modifier.node_group.interface.items_tree
            for input in inputs:
                if input.name == 'UV_Map':
                    identifier = input.identifier
            modifier[f"{identifier}_attribute_name"] = obj.data.uv_layers[obj.cb_active_uv].name


# removing the UV scale map modifier from all objects
def uv_scale_map_reset(scene):
    for obj in scene.objects:
        if obj.get(CAUSTIC_RECEIVER_ATTRIBUTE, False):
            for modifier in obj.modifiers:
                if modifier.name == UV_SCALE_MAP_NAME:
                    obj.modifiers.remove(modifier)


# modifying the compositor node tree to extract the rendered image
def setup_compositor():
    scene = bpy.context.scene

    # switch on nodes
    scene.use_nodes = True
    tree = bpy.context.scene.node_tree
    links = tree.links

    # remove any existing viewer nodes and muting all compositor nodes
    for node in tree.nodes:
        if node.bl_idname == 'CompositorNodeViewer':
            tree.nodes.remove(node)
        elif not node.mute:
            node.mute = True
            node[CAUSTIC_HIDDEN_ATTRIBUTE] = 1

    # create input render layer node
    rl = tree.nodes.new('CompositorNodeRLayers')
    rl[DELETE_NODE_ON_RESET] = True

    # create output node
    v = tree.nodes.new('CompositorNodeViewer')
    v.use_alpha = False
    v[DELETE_NODE_ON_RESET] = True

    # link Image output to Viewer input
    links.new(rl.outputs[0], v.inputs[0])


# deleting added compositor nodes and unmuting compositor nodes
def reset_compositor():
    nodes = bpy.context.scene.node_tree.nodes
    for node in nodes:
        if node.get(DELETE_NODE_ON_RESET, False):
            nodes.remove(node)
        elif node.get(CAUSTIC_HIDDEN_ATTRIBUTE, False):
            node.mute = False


# creating a compositor node tree that uses the build in AI denoiser to denoise the image
def denoising(image_name):
    # building node tree
    tree = bpy.context.scene.node_tree
    reset_compositor()
    image = tree.nodes.new(type="CompositorNodeImage")
    image.image = bpy.data.images[image_name]
    image[DELETE_NODE_ON_RESET] = True
    denoise = tree.nodes.new(type='CompositorNodeDenoise')
    denoise[DELETE_NODE_ON_RESET] = True
    viewer = tree.nodes.new('CompositorNodeViewer')
    viewer.use_alpha = False
    viewer[DELETE_NODE_ON_RESET] = True

    links = tree.links
    links.new(image.outputs[0], denoise.inputs[0])
    links.new(denoise.outputs[0], viewer.inputs[0])

    # triggering compositing
    bpy.ops.render.render()
    pixels = bpy.data.images['Viewer Node'].pixels
    pixels = np.array(pixels[:])

    reset_compositor()
    return pixels


# switching color sampling mode in shader
def color_sampling(on):
    nodes = bpy.data.node_groups[NODEGROUP_MAIN_NAME].nodes
    value = nodes["Color"]
    value.outputs[0].default_value = on


# building collections for access to object groups in Geo-Nodes
def build_collections():
    build_collection(CAUSTIC_SHADOW_ATTRIBUTE)
    build_collection(CAUSTIC_CONTRIBUTOR_ATTRIBUTE)
    build_collection(CAUSTIC_RECEIVER_ATTRIBUTE)
    build_collection(CAUSTIC_SOURCE_ATTRIBUTE)


# creating collection with all objects of given attribute
def build_collection(name):
    if not bpy.data.collections.__contains__(name):
        bpy.data.collections.new(name)
    for object in bpy.context.scene.objects:
        if object.get(name, False):
            set_collection(name, object)


# safely deletes collection and all links to it
def remove_collection(name):
    for obj in bpy.data.collections[name].all_objects:
        if obj is not None:
            if obj.type == 'CAMERA':
                bpy.context.scene.collection.objects.unlink(obj)
            unset_collection(name, obj)
    bpy.data.collections.remove(bpy.data.collections[name])


# removes collections
def remove_collections():
    remove_collection(CAUSTIC_SHADOW_ATTRIBUTE)
    remove_collection(CAUSTIC_CONTRIBUTOR_ATTRIBUTE)
    remove_collection(CAUSTIC_RECEIVER_ATTRIBUTE)
    remove_collection(CAUSTIC_SOURCE_ATTRIBUTE)
    remove_collection(CAUSTIC_SENSOR_NAME)


# automatically creates cameras at the positions of given light source
def auto_cam_placement(light):
    # find clipping Planes using Geo-Nodes
    empty_mesh = bpy.data.meshes.new('emptyMesh')
    obj = bpy.data.objects.new(name='Clip_planes', object_data=empty_mesh)
    bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
    modifier = obj.modifiers.new(name='GeometryNodes', type='NODES')
    if light.data.type == 'SUN':
        modifier.node_group = bpy.data.node_groups[NODEGROUP_CLIPPING_PLANES_ORTHO]
    else:
        modifier.node_group = bpy.data.node_groups[NODEGROUP_CLIPPING_PLANES_PANO]
    inputs = modifier.node_group.interface.items_tree
    for input in inputs:
        if input.name == 'Light':
            modifier[input.identifier] = light
        elif input.name == CAUSTIC_CONTRIBUTOR_ATTRIBUTE:
            modifier[input.identifier] = bpy.data.collections[CAUSTIC_CONTRIBUTOR_ATTRIBUTE]
        elif input.name == CAUSTIC_RECEIVER_ATTRIBUTE:
            modifier[input.identifier] = bpy.data.collections[CAUSTIC_RECEIVER_ATTRIBUTE]
        elif input.name == CAUSTIC_SHADOW_ATTRIBUTE:
            modifier[input.identifier] = bpy.data.collections[CAUSTIC_SHADOW_ATTRIBUTE]
    deps_graph = bpy.context.evaluated_depsgraph_get()
    attributes = obj.evaluated_get(deps_graph).data.attributes
    if light.data.type == 'SUN':
        sensor_height = attributes['sensor_height'].data[0].value
        sensor_clip = attributes['sensor_clip'].data[0].value
    else:
        clip_start = attributes['clip_start'].data[0].value
        clip_end = attributes['clip_end'].data[0].value
    bpy.data.objects.remove(obj)

    contributors = bpy.data.collections[CAUSTIC_CONTRIBUTOR_ATTRIBUTE].all_objects
    collections = []
    for i, contributor in enumerate(contributors):
        collections.append(set_collection(f'CB_Rendering_{i}', contributor))

    # finding optimal cam placement for each contributor object
    cam_positions = []
    for collection in collections:
        empty_mesh = bpy.data.meshes.new('emptyMesh')
        obj = bpy.data.objects.new(name='CB_Cam_Pos', object_data=empty_mesh)
        cam_positions.append(obj)
        bpy.context.view_layer.active_layer_collection.collection.objects.link(obj)
        modifier = obj.modifiers.new(name='GeometryNodes', type='NODES')
        obj.modifiers.new(name='solidify', type='SOLIDIFY')
        if light.data.type == 'SUN':
            modifier.node_group = bpy.data.node_groups[NODEGROUP_CAM_PLACEMENT_ORTHO]
        else:
            modifier.node_group = bpy.data.node_groups[NODEGROUP_CAM_PLACEMENT_PANO]
        inputs = modifier.node_group.interface.items_tree
        for input in inputs:
            if input.name == 'Light':
                modifier[input.identifier] = light
            elif input.name == 'Collection':
                modifier[input.identifier] = collection

    # Combining overlapping cam placements to avoid double sampling of overlapping area
    if light.data.type == 'SUN':
        while True:
            deps_graph = bpy.context.evaluated_depsgraph_get()
            overlap = False
            bvh_trees = []
            for cam_pos in cam_positions:
                bvh_trees.append(BVHTree.FromObject(cam_pos, deps_graph))
            for i, tree in enumerate(bvh_trees):
                if len(collections[i].all_objects) > 0:
                    for j, other_tree in enumerate(bvh_trees):
                        if not tree == other_tree and tree.overlap(other_tree) and len(collections[j].all_objects) > 0:
                            for obj in collections[j].all_objects:
                                unset_collection(f'CB_Rendering_{j}', obj)
                                set_collection(f'CB_Rendering_{i}', obj)
                            overlap = True
            if not overlap:
                break
    else:
        full_sphere = False
        while True:
            deps_graph = bpy.context.evaluated_depsgraph_get()
            overlap = False
            cam_attributes = []
            for cam_pos in cam_positions:
                attributes = cam_pos.evaluated_get(deps_graph).data.attributes
                if attributes['full_sphere'].data[0].value:
                    full_sphere = True
                    break
                cam_attributes.append({
                    'rot': attributes['rotation'].data[0].vector,
                    'fov': max(attributes['fov'].data[0].value, math.radians(10.0))
                })
            for i, cam in enumerate(cam_attributes):
                if len(collections[i].all_objects) > 0:
                    for j, other_cam in enumerate(cam_attributes):
                        if j != i and len(collections[j].all_objects) > 0:
                            a = mathutils.Vector((0, 0, 1))
                            b = mathutils.Vector((0, 0, 1))
                            a.rotate(mathutils.Euler((cam['rot'][0], cam['rot'][1], cam['rot'][2]), 'XYZ'))
                            b.rotate(
                                mathutils.Euler((other_cam['rot'][0], other_cam['rot'][1], other_cam['rot'][2]), 'XYZ'))
                            if a.angle(b) < (cam['fov'] + other_cam['fov']) / 2:
                                for obj in collections[j].all_objects:
                                    unset_collection(f'CB_Rendering_{j}', obj)
                                    set_collection(f'CB_Rendering_{i}', obj)
                                overlap = True
            if not overlap:
                break

    # creating cameras from calculated positions and storing relevant information in camera object
    cams = []
    if light.data.type == 'SUN':
        for cam_pos in cam_positions:
            if len(cam_pos.evaluated_get(deps_graph).data.vertices) > 0:
                attributes = cam_pos.evaluated_get(deps_graph).data.attributes
                pos = attributes['cam_pos'].data
                width = attributes['cam_width'].data
                height = attributes['cam_height'].data
                width = width[0].value
                height = height[0].value
                vec = mathutils.Vector((pos[0].vector[0], pos[0].vector[1], sensor_height))
                euler = mathutils.Euler((0.0, 0.0, pos[0].vector[2]))
                vec.rotate(light.rotation_euler)
                euler.rotate(light.rotation_euler)
                sensor = bpy.data.cameras.new('CB_Cam')
                sensor.type = 'ORTHO'
                sensor.ortho_scale = max(width, height)
                sensor.clip_end = sensor_clip
                sensor_object = bpy.data.objects.new('CB_Cam', sensor)
                sensor_object['cam_normalization'] = width * height * ORTHO_NORMALIZATION
                sensor_object['sample_density'] = 1 / (width * height)
                sensor_object['width'] = width / min(width, height)
                sensor_object['height'] = height / min(width, height)
                sensor_object.location = vec
                sensor_object.rotation_euler = euler
                set_collection(CAUSTIC_SENSOR_NAME, sensor_object)
                bpy.context.scene.collection.objects.link(sensor_object)
                cams.append(sensor_object)
    else:
        if full_sphere:
            for i in range(2):
                sensor = bpy.data.cameras.new('CB_Cam')
                sensor.type = 'PANO'
                sensor.panorama_type = 'FISHEYE_EQUIDISTANT'
                sensor.fisheye_fov = math.pi
                sensor.clip_end = clip_end
                sensor.clip_start = clip_start
                sensor_object = bpy.data.objects.new('CB_Cam', sensor)
                sensor_object['cam_normalization'] = 2 * math.pi * (1 - math.cos(math.pi)) * PANO_NORMALIZATION
                sensor_object['sample_density'] = 1 / (2 * math.pi * (1 - math.cos(math.pi)))
                sensor_object.location = light.location
                sensor_object.rotation_euler = mathutils.Euler((i * math.pi, 0, 0), 'XYZ')
                set_collection(CAUSTIC_SENSOR_NAME, sensor_object)
                bpy.context.scene.collection.objects.link(sensor_object)
                cams.append(sensor_object)
        else:
            for i, cam_pos in enumerate(cam_positions):
                if len(collections[i].all_objects) > 0:
                    attributes = cam_pos.evaluated_get(deps_graph).data.attributes
                    sensor = bpy.data.cameras.new('CB_Cam')
                    sensor.type = 'PANO'
                    sensor.panorama_type = 'FISHEYE_EQUIDISTANT'
                    sensor.fisheye_fov = max(attributes['fov'].data[0].value, math.radians(10.0))
                    sensor.clip_end = clip_end
                    sensor.clip_start = clip_start
                    sensor_object = bpy.data.objects.new('CB_Cam', sensor)
                    sensor_object['cam_normalization'] = 2 * math.pi * (
                            1 - math.cos(max(attributes['fov'].data[0].value, math.radians(10.0)))) * PANO_NORMALIZATION
                    sensor_object['sample_density'] = 1 / (
                            2 * math.pi * (1 - math.cos(max(attributes['fov'].data[0].value, math.radians(10.0)))))
                    sensor_object.location = light.location
                    rotation = attributes['rotation'].data[0].vector
                    sensor_object.rotation_euler = mathutils.Euler((rotation[0], rotation[1], rotation[2]), 'XYZ')
                    set_collection(CAUSTIC_SENSOR_NAME, sensor_object)
                    bpy.context.scene.collection.objects.link(sensor_object)
                    cams.append(sensor_object)

    # deleting created objects and collections that are no longer needed
    for i, cam_pos in enumerate(cam_positions):
        bpy.data.objects.remove(cam_pos)
    for index, collection in enumerate(collections):
        for obj in collection.all_objects:
            unset_collection(f'CB_Rendering_{index}', obj)
        bpy.data.collections.remove(collection)

    # adjusting the number of samples for each camera to ensure a similar amount of samples per area for all cameras
    lowest_density = cams[0]['sample_density']
    for cam in cams:
        cam['remaining'] = 0
        if cam['sample_density'] < lowest_density:
            lowest_density = cam['sample_density']
    for cam in cams:
        remaining = lowest_density * (bpy.context.scene.cb_props.samples - 1)
        while remaining > -.5 * lowest_density:
            cam['remaining'] += 1
            remaining -= cam['sample_density']
    # adjusting the normalization to reflect the number of samples
    for cam in cams:
        cam['cam_normalization'] = cam['cam_normalization'] / cam['remaining']
        if bpy.context.scene.cb_props.bake_energy or len(
                bpy.data.collections[CAUSTIC_SOURCE_ATTRIBUTE].all_objects) > 1:
            cam['cam_normalization'] *= light.data.energy
    return cams


# setting active cam and adjusting render settings to cam parameters
def cam_setup(cam):
    props = bpy.context.scene.cb_props
    scene = bpy.context.scene

    scene.camera = cam
    scene.render.resolution_x = int(1024 * props.sampleResMultiplier)
    scene.render.resolution_y = int(1024 * props.sampleResMultiplier)
    if cam.data.type == 'ORTHO':
        scene.render.pixel_aspect_x = cam['width']
        scene.render.pixel_aspect_y = cam['height']


# setting the collection of the given object
def set_collection(name, obj):
    if not bpy.data.collections.__contains__(name):
        bpy.data.collections.new(name)
    if not bpy.data.collections[name] in obj.users_collection:
        bpy.data.collections[name].objects.link(obj)
    return bpy.data.collections[name]


# removing the collection from the given object
def unset_collection(name, obj):
    try:
        bpy.data.collections[name].objects.unlink(obj)
    except:
        pass


# returns True if the debug flag is set for the blender scene
def is_debug():
    return bpy.context.scene.get(DEBUG_MODE, 0) == 1
