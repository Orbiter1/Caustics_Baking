import bpy

from .cb_const import CAUSTIC_SENSOR_NAME, UV_SCALE_MAP_NAME, CAUSTIC_SOURCE_ATTRIBUTE, CAUSTIC_SHADOW_ATTRIBUTE, \
    CAUSTIC_RECEIVER_ATTRIBUTE, CAUSTIC_CONTRIBUTOR_ATTRIBUTE


def get_uv_active_index(self):
    for i, uv_layer in enumerate(bpy.context.active_object.data.uv_layers):
        if uv_layer.name == bpy.context.active_object.get(UV_SCALE_MAP_NAME, 0):
            return i
    self.uv_active_index = 0
    return 0


def set_uv_active_index(self, value):
    bpy.context.active_object[UV_SCALE_MAP_NAME] = bpy.context.active_object.data.uv_layers[value].name


def update_source_active_object_index(self, context):
    if self.source_active_object_index >= 0:
        obj = bpy.context.scene.objects[self.source_active_object_index]
        self.source_active_object_index = -1
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj


def update_contributor_active_object_index(self, context):
    if self.contributor_active_object_index >= 0:
        obj = bpy.context.scene.objects[self.contributor_active_object_index]
        self.contributor_active_object_index = -1
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj


def update_shadow_active_object_index(self, context):
    if self.shadow_active_object_index >= 0:
        obj = bpy.context.scene.objects[self.shadow_active_object_index]
        self.shadow_active_object_index = -1
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj


def update_reciever_active_object_index(self, context):
    if self.receiver_active_object_index >= 0:
        obj = bpy.context.scene.objects[self.receiver_active_object_index]
        self.receiver_active_object_index = -1
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj


class CB_Props(bpy.types.PropertyGroup):
    textureRes: bpy.props.IntProperty(name="Texture Res", default=2048, min=1,
                                      description='size of the baked texture')
    samples: bpy.props.IntProperty(name="Samples", default=1, min=1,
                                   description='number of samples per camera (the final number of samples may change based on the sample density of individual cameras)')
    colored: bpy.props.BoolProperty(name="Colored", default=False, description='Enables Colored Caustics')
    denoise: bpy.props.BoolProperty(name="Denoise", default=False,
                                    description='Uses Open Image Denoise on final Result')
    use_gpu: bpy.props.BoolProperty(name='Use GPU', default=True, description='Use GPU to render')
    bake_energy: bpy.props.BoolProperty(name='Bake Energy', default=False,
                                        description='bake the light energy into the texture')

    sampleResMultiplier: bpy.props.FloatProperty(name="Sample Resolution Multiplier", default=1, min=0,
                                                 description='base resolution is 1024x1024')

    save_image_externally: bpy.props.BoolProperty(name='save externally', default=False,
                                                  description='automatically saves the image to the given filepath')
    filePath: bpy.props.StringProperty(name="File Path", default='//cb\\', subtype='DIR_PATH')
    useImage: bpy.props.BoolProperty(name='use existing Image', default=False,
                                     description='lets you select an existing image as baking target')
    imageName: bpy.props.StringProperty(name="Image Name", default="cb", subtype='FILE_NAME')
    targetImage: bpy.props.PointerProperty(name='Baking Target', type=bpy.types.Image)
    uv_active_index: bpy.props.IntProperty(
        min=-1,
        default=-1,
        get=get_uv_active_index,
        set=set_uv_active_index
    )

    source_active_object_index: bpy.props.IntProperty(
        default=-1,
        update=update_source_active_object_index
    )
    contributor_active_object_index: bpy.props.IntProperty(
        default=-1,
        update=update_contributor_active_object_index
    )
    shadow_active_object_index: bpy.props.IntProperty(
        default=-1,
        update=update_shadow_active_object_index
    )
    receiver_active_object_index: bpy.props.IntProperty(
        default=-1,
        update=update_reciever_active_object_index
    )

    progress_indicator: bpy.props.FloatProperty(
        default=0,
        subtype='PERCENTAGE',
        precision=1,
        min=0,
        max=100)
    progress_indicator_text: bpy.props.StringProperty(default="Progress")
    time_elapsed: bpy.props.StringProperty(default='0')
    cb_running_baking: bpy.props.BoolProperty(default=False)
