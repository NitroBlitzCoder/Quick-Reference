bl_info = {
    "name": "Quick Reference Free",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Reference",
    "description": "Fast single-image reference import with opacity, viewport alignment, collection organization, and transform locking.",
    "category": "3D View",
}

import os
import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper


addon_keymaps = []


def reference_collection(scene):
    collection = bpy.data.collections.get("Quick References")
    if collection is None:
        collection = bpy.data.collections.new("Quick References")
    if collection.name not in [child.name for child in scene.collection.children]:
        try:
            scene.collection.children.link(collection)
        except RuntimeError:
            pass
    return collection


def is_reference_object(obj):
    return bool(obj and obj.get("quick_reference"))


def selected_references(context):
    return [obj for obj in context.selected_objects if is_reference_object(obj)]


def move_to_reference_collection(scene, obj):
    collection = reference_collection(scene)
    for old_collection in list(obj.users_collection):
        if old_collection != collection:
            old_collection.objects.unlink(obj)
    if obj.name not in [member.name for member in collection.objects]:
        collection.objects.link(obj)


def apply_reference_settings(scene, obj):
    obj["quick_reference"] = True
    obj.show_name = scene.quick_ref_show_names
    obj.empty_display_size = scene.quick_ref_size
    if hasattr(obj, "empty_image_alpha"):
        obj.empty_image_alpha = scene.quick_ref_opacity
    if scene.quick_ref_lock_transform:
        obj.lock_location = (True, True, True)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)


def create_reference_empty(context, filepath):
    scene = context.scene
    before = set(scene.objects)
    try:
        bpy.ops.object.load_reference_image(filepath=filepath)
        obj = context.object
    except Exception:
        try:
            bpy.ops.object.empty_image_add(type="IMAGE", filepath=filepath, align="VIEW")
            obj = context.object
        except Exception:
            image = bpy.data.images.load(filepath)
            obj = bpy.data.objects.new(os.path.splitext(os.path.basename(filepath))[0], None)
            obj.empty_display_type = "IMAGE"
            try:
                obj.data = image
            except Exception:
                pass
            scene.collection.objects.link(obj)

    if obj is None:
        new_objects = [candidate for candidate in scene.objects if candidate not in before]
        obj = new_objects[-1] if new_objects else None
    if obj is None:
        return None

    obj.name = "REF_" + os.path.splitext(os.path.basename(filepath))[0]
    if context.region_data:
        obj.rotation_euler = context.region_data.view_rotation.to_euler()
        obj.location = context.region_data.view_location
    move_to_reference_collection(scene, obj)
    apply_reference_settings(scene, obj)
    return obj


class QREFFREE_OT_import_image(bpy.types.Operator, ImportHelper):
    bl_idname = "quick_reference_free.import_image"
    bl_label = "Import Reference"
    bl_description = "Import one reference image facing the current viewport"
    filename_ext = ""
    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.webp", options={"HIDDEN"})

    def execute(self, context):
        obj = create_reference_empty(context, self.filepath)
        if not obj:
            self.report({"ERROR"}, "Could not create reference image.")
            return {"CANCELLED"}
        context.view_layer.objects.active = obj
        obj.select_set(True)
        self.report({"INFO"}, "Imported reference: " + os.path.basename(self.filepath))
        return {"FINISHED"}


class QREFFREE_OT_apply_opacity(bpy.types.Operator):
    bl_idname = "quick_reference_free.apply_opacity"
    bl_label = "Apply Opacity"
    bl_description = "Apply the opacity slider to selected references, or all references if none are selected"

    def execute(self, context):
        refs = selected_references(context)
        if not refs:
            refs = [obj for obj in context.scene.objects if is_reference_object(obj)]
        for obj in refs:
            if hasattr(obj, "empty_image_alpha"):
                obj.empty_image_alpha = context.scene.quick_ref_opacity
        self.report({"INFO"}, "Updated reference opacity.")
        return {"FINISHED"}


class QREFFREE_OT_lock_selected(bpy.types.Operator):
    bl_idname = "quick_reference_free.lock_selected"
    bl_label = "Lock Selected"

    def execute(self, context):
        refs = selected_references(context)
        for obj in refs:
            obj.lock_location = (True, True, True)
            obj.lock_rotation = (True, True, True)
            obj.lock_scale = (True, True, True)
        self.report({"INFO"}, "Locked selected references.")
        return {"FINISHED"}


class QREFFREE_OT_unlock_selected(bpy.types.Operator):
    bl_idname = "quick_reference_free.unlock_selected"
    bl_label = "Unlock Selected"

    def execute(self, context):
        refs = selected_references(context)
        for obj in refs:
            obj.lock_location = (False, False, False)
            obj.lock_rotation = (False, False, False)
            obj.lock_scale = (False, False, False)
        self.report({"INFO"}, "Unlocked selected references.")
        return {"FINISHED"}


class QREFFREE_PT_panel(bpy.types.Panel):
    bl_label = "Quick Reference Free"
    bl_idname = "QREFFREE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Reference"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.operator("quick_reference_free.import_image", icon="IMAGE_DATA")
        layout.prop(scene, "quick_ref_opacity", slider=True)
        layout.prop(scene, "quick_ref_size")
        layout.prop(scene, "quick_ref_lock_transform")
        layout.prop(scene, "quick_ref_show_names")
        row = layout.row(align=True)
        row.operator("quick_reference_free.apply_opacity", icon="HIDE_OFF")
        row.operator("quick_reference_free.lock_selected", icon="LOCKED")
        row.operator("quick_reference_free.unlock_selected", icon="UNLOCKED")


classes = (
    QREFFREE_OT_import_image,
    QREFFREE_OT_apply_opacity,
    QREFFREE_OT_lock_selected,
    QREFFREE_OT_unlock_selected,
    QREFFREE_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.quick_ref_opacity = FloatProperty(name="Opacity", default=0.55, min=0.0, max=1.0, subtype="FACTOR")
    bpy.types.Scene.quick_ref_size = FloatProperty(name="Size", default=4.0, min=0.05, max=100.0)
    bpy.types.Scene.quick_ref_lock_transform = BoolProperty(name="Lock Transforms", default=True)
    bpy.types.Scene.quick_ref_show_names = BoolProperty(name="Show Names", default=False)

    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig:
        keymap = keyconfig.keymaps.new(name="3D View", space_type="VIEW_3D")
        item = keymap.keymap_items.new("quick_reference_free.import_image", "R", "PRESS", ctrl=True, alt=True)
        addon_keymaps.append((keymap, item))


def unregister():
    for keymap, item in addon_keymaps:
        keymap.keymap_items.remove(item)
    addon_keymaps.clear()
    del bpy.types.Scene.quick_ref_show_names
    del bpy.types.Scene.quick_ref_lock_transform
    del bpy.types.Scene.quick_ref_size
    del bpy.types.Scene.quick_ref_opacity
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
